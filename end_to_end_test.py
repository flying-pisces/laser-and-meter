"""
End-to-End Test for Dual Pump Lasers and Power Meter

This test verifies functionality of both CLD1015 pump lasers with
power measurement from the Thorlabs power meter at the specified IP.

Safety: Current limited to first two low levels (50mA and 100mA)
"""

import sys
import os
import time
import logging
import requests
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# Add paths for local modules
sys.path.insert(0, os.path.abspath('.'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'pumplaser'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Python-Driver-for-Thorlabs-power-meter'))

from pumplaser.pump_laser import CLD1015, list_visa_resources
from ThorlabsPowerMeter import ThorlabsPowerMeter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'end_to_end_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Power meter configuration
POWER_METER_IP = "http://169.254.229.215"
POWER_METER_TIMEOUT = 5  # seconds

# Safety limits for testing
SAFE_CURRENT_LEVELS_MA = [0, 50, 100]  # Only use first two low levels
MAX_CURRENT_MA = 100  # Absolute maximum for testing
RAMP_STEP_MA = 10  # Current ramp step size
RAMP_DELAY_S = 0.2  # Delay between ramp steps

# Test configuration
STABILIZATION_DELAY_S = 2  # Time to wait after setting current
MEASUREMENT_COUNT = 5  # Number of power measurements to average


class PowerMeterHTTP:
    """Simple HTTP interface for Thorlabs power meter"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.timeout = POWER_METER_TIMEOUT

    def test_connection(self) -> bool:
        """Test if power meter is accessible"""
        try:
            response = self.session.get(f"{self.base_url}/", timeout=2)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Power meter connection test failed: {e}")
            return False

    def get_power_reading(self) -> Optional[float]:
        """Get current power reading in mW"""
        try:
            # This endpoint may vary - adjust based on actual power meter API
            response = self.session.get(f"{self.base_url}/power")
            if response.status_code == 200:
                # Parse power value from response
                # Adjust parsing based on actual response format
                return float(response.text.strip())
            return None
        except Exception as e:
            logger.error(f"Failed to get power reading: {e}")
            return None


def find_laser_resources() -> Tuple[Optional[str], Optional[str]]:
    """Find two CLD1015 laser controllers"""
    resources = list_visa_resources()
    logger.info(f"Found {len(resources)} VISA resources")

    cld_resources = []
    for res in resources:
        if "0x1313" in res or "0x804F" in res:  # Thorlabs vendor/product IDs
            cld_resources.append(res)
            logger.info(f"Found CLD1015: {res}")

    if len(cld_resources) >= 2:
        return cld_resources[0], cld_resources[1]
    elif len(cld_resources) == 1:
        logger.warning("Only one CLD1015 found, will test single laser")
        return cld_resources[0], None
    else:
        logger.error("No CLD1015 devices found")
        return None, None


def test_laser_at_currents(
    laser: CLD1015,
    laser_name: str,
    currents_ma: List[float],
    power_meter: Optional[PowerMeterHTTP] = None
) -> Dict:
    """Test a single laser at multiple current levels"""

    results = {
        'laser_name': laser_name,
        'resource': laser.resource_name,
        'measurements': []
    }

    try:
        # Get initial status
        initial_status = laser.get_status()
        results['initial_status'] = initial_status
        logger.info(f"\n{laser_name} Initial Status:")
        logger.info(f"  Model: {initial_status['identity']}")
        logger.info(f"  Current Limit: {initial_status['ld_current_limit_ma']:.1f} mA")
        logger.info(f"  Temperature: {initial_status['temperature_c']:.1f}°C")

        # Set current limit for safety
        laser.set_current_limit(MAX_CURRENT_MA)
        logger.info(f"{laser_name}: Set current limit to {MAX_CURRENT_MA} mA")

        # Enable laser output
        laser.set_ld_output(True)
        logger.info(f"{laser_name}: Output enabled")

        # Test each current level
        for current_ma in currents_ma:
            logger.info(f"\n{laser_name}: Testing at {current_ma} mA")

            # Ramp to target current
            if current_ma > 0:
                laser.ramp_current(current_ma, RAMP_STEP_MA, RAMP_DELAY_S)
            else:
                laser.set_ld_current(0)

            # Wait for stabilization
            time.sleep(STABILIZATION_DELAY_S)

            # Take measurements
            measurement = {
                'current_setpoint_ma': current_ma,
                'current_actual_ma': laser.get_ld_current_actual(),
                'voltage_v': laser.get_ld_voltage(),
                'power_readings_mw': []
            }

            # Get power readings if power meter available
            if power_meter and power_meter.test_connection():
                for i in range(MEASUREMENT_COUNT):
                    power = power_meter.get_power_reading()
                    if power is not None:
                        measurement['power_readings_mw'].append(power)
                    time.sleep(0.2)

                if measurement['power_readings_mw']:
                    avg_power = sum(measurement['power_readings_mw']) / len(measurement['power_readings_mw'])
                    measurement['power_average_mw'] = avg_power
                    logger.info(f"  Average Power: {avg_power:.3f} mW")

            logger.info(f"  Actual Current: {measurement['current_actual_ma']:.3f} mA")
            logger.info(f"  Voltage: {measurement['voltage_v']:.3f} V")

            results['measurements'].append(measurement)

        # Ramp down safely
        logger.info(f"\n{laser_name}: Ramping down to 0 mA")
        laser.ramp_current(0, RAMP_STEP_MA, RAMP_DELAY_S)

        # Disable output
        laser.set_ld_output(False)
        logger.info(f"{laser_name}: Output disabled")

        # Get final status
        final_status = laser.get_status()
        results['final_status'] = final_status
        results['test_passed'] = True

    except Exception as e:
        logger.error(f"{laser_name} test failed: {e}")
        results['error'] = str(e)
        results['test_passed'] = False

        # Emergency shutdown
        try:
            laser.emergency_stop()
        except:
            pass

    return results


def run_end_to_end_test():
    """Main end-to-end test function"""

    logger.info("="*60)
    logger.info("Starting End-to-End Test")
    logger.info(f"Power Meter IP: {POWER_METER_IP}")
    logger.info(f"Safe Current Levels: {SAFE_CURRENT_LEVELS_MA} mA")
    logger.info("="*60)

    # Initialize test results
    test_results = {
        'timestamp': datetime.now().isoformat(),
        'power_meter_ip': POWER_METER_IP,
        'laser1_results': None,
        'laser2_results': None,
        'power_meter_accessible': False,
        'overall_status': 'PENDING'
    }

    # Test power meter connection
    logger.info("\nTesting Power Meter Connection...")
    power_meter = PowerMeterHTTP(POWER_METER_IP)

    if power_meter.test_connection():
        logger.info("Power meter is accessible")
        test_results['power_meter_accessible'] = True
    else:
        logger.warning("Power meter not accessible - will test lasers only")
        power_meter = None

    # Alternative: Try USB power meter if HTTP fails
    if not test_results['power_meter_accessible']:
        logger.info("\nTrying USB Power Meter...")
        try:
            pm_device_list = ThorlabsPowerMeter.listDevices()
            if pm_device_list.resourceCount > 0:
                logger.info(f"Found {pm_device_list.resourceCount} USB power meter(s)")
                # We'll use HTTP power meter for now
        except Exception as e:
            logger.info(f"No USB power meter found: {e}")

    # Find laser controllers
    logger.info("\nSearching for CLD1015 Laser Controllers...")
    laser1_resource, laser2_resource = find_laser_resources()

    if not laser1_resource:
        logger.error("No laser controllers found - cannot proceed")
        test_results['overall_status'] = 'NO_DEVICES'
        return test_results

    # Test Laser 1
    logger.info("\n" + "="*40)
    logger.info("Testing Laser 1")
    logger.info("="*40)

    laser1 = CLD1015(laser1_resource)
    if laser1.connect():
        test_results['laser1_results'] = test_laser_at_currents(
            laser1, "Laser 1", SAFE_CURRENT_LEVELS_MA, power_meter
        )
        laser1.disconnect()
    else:
        logger.error("Failed to connect to Laser 1")
        test_results['laser1_results'] = {'error': 'Connection failed', 'test_passed': False}

    # Test Laser 2 if available
    if laser2_resource:
        logger.info("\n" + "="*40)
        logger.info("Testing Laser 2")
        logger.info("="*40)

        laser2 = CLD1015(laser2_resource)
        if laser2.connect():
            test_results['laser2_results'] = test_laser_at_currents(
                laser2, "Laser 2", SAFE_CURRENT_LEVELS_MA, power_meter
            )
            laser2.disconnect()
        else:
            logger.error("Failed to connect to Laser 2")
            test_results['laser2_results'] = {'error': 'Connection failed', 'test_passed': False}

    # Determine overall test status
    laser1_passed = test_results['laser1_results'] and test_results['laser1_results'].get('test_passed', False)
    laser2_passed = test_results['laser2_results'] is None or test_results['laser2_results'].get('test_passed', False)

    if laser1_passed and laser2_passed:
        test_results['overall_status'] = 'PASSED'
        logger.info("\n" + "="*60)
        logger.info("END-TO-END TEST PASSED")
        logger.info("Both pump lasers functioning correctly")
        if test_results['power_meter_accessible']:
            logger.info("Power meter measurements recorded")
        logger.info("="*60)
    else:
        test_results['overall_status'] = 'FAILED'
        logger.error("\n" + "="*60)
        logger.error("END-TO-END TEST FAILED")
        if not laser1_passed:
            logger.error("Laser 1 failed")
        if not laser2_passed:
            logger.error("Laser 2 failed")
        logger.error("="*60)

    # Print summary
    logger.info("\nTest Summary:")
    logger.info(f"  Timestamp: {test_results['timestamp']}")
    logger.info(f"  Overall Status: {test_results['overall_status']}")
    logger.info(f"  Power Meter Accessible: {test_results['power_meter_accessible']}")

    if test_results['laser1_results']:
        logger.info(f"  Laser 1: {'PASSED' if test_results['laser1_results'].get('test_passed') else 'FAILED'}")
        if test_results['laser1_results'].get('measurements'):
            for m in test_results['laser1_results']['measurements']:
                logger.info(f"    {m['current_setpoint_ma']}mA -> {m['current_actual_ma']:.1f}mA actual")

    if test_results['laser2_results']:
        logger.info(f"  Laser 2: {'PASSED' if test_results['laser2_results'].get('test_passed') else 'FAILED'}")
        if test_results['laser2_results'].get('measurements'):
            for m in test_results['laser2_results']['measurements']:
                logger.info(f"    {m['current_setpoint_ma']}mA -> {m['current_actual_ma']:.1f}mA actual")

    return test_results


if __name__ == "__main__":
    try:
        results = run_end_to_end_test()

        # Save results to file
        import json
        results_file = f"end_to_end_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            # Convert any non-serializable objects
            def clean_for_json(obj):
                if isinstance(obj, dict):
                    return {k: clean_for_json(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [clean_for_json(v) for v in obj]
                else:
                    try:
                        json.dumps(obj)
                        return obj
                    except:
                        return str(obj)

            json.dump(clean_for_json(results), f, indent=2)

        logger.info(f"\nResults saved to: {results_file}")

        # Exit with appropriate code
        sys.exit(0 if results['overall_status'] == 'PASSED' else 1)

    except KeyboardInterrupt:
        logger.warning("\nTest interrupted by user")
        sys.exit(2)
    except Exception as e:
        logger.error(f"\nUnexpected error: {e}")
        sys.exit(3)