"""
Simple End-to-End Test for CLD1015 Pump Lasers and Power Meter

Verifies both pump lasers work with limited safe currents (50mA, 100mA)
and checks power meter connectivity at IP 169.254.229.215
"""

import time
import logging
from datetime import datetime
import urllib.request
import json

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import laser control
from pumplaser.pump_laser import CLD1015, list_visa_resources

# Test configuration
POWER_METER_IP = "169.254.229.215"
SAFE_CURRENTS_MA = [0, 50, 100]  # Limited to first two low levels
STABILIZATION_DELAY = 2  # seconds

# Known good laser resources
LASER_RESOURCES = [
    "USB0::0x1313::0x804F::M01093719::INSTR",   # Laser 1
    "USB0::0x1313::0x804F::M00859480::INSTR"    # Laser 2
]


def test_power_meter_connection():
    """Test power meter HTTP connectivity"""
    try:
        # Simple HTTP check
        url = f"http://{POWER_METER_IP}/"
        with urllib.request.urlopen(url, timeout=3) as response:
            if response.status == 200:
                logger.info(f"[OK] Power meter accessible at {POWER_METER_IP}")
                return True
    except Exception as e:
        logger.warning(f"[FAIL] Power meter not accessible: {e}")
    return False


def test_laser(resource_name, laser_num):
    """Test a single laser with safe current levels"""
    logger.info(f"\n{'='*50}")
    logger.info(f"Testing Laser {laser_num}: {resource_name}")
    logger.info(f"{'='*50}")

    try:
        laser = CLD1015(resource_name)

        if not laser.connect():
            logger.error(f"[FAIL] Failed to connect to Laser {laser_num}")
            return False

        # Get initial status
        status = laser.get_status()
        logger.info(f"[OK] Connected: {status['identity']}")
        logger.info(f"  Temperature: {status['temperature_c']:.1f}°C")
        logger.info(f"  Current Limit: {status['ld_current_limit_ma']:.1f} mA")

        # Set safety limit
        laser.set_current_limit(100)
        logger.info(f"[OK] Safety limit set to 100 mA")

        # Enable output
        laser.set_ld_output(True)
        logger.info(f"[OK] Laser output enabled")

        # Test each current level
        for current_ma in SAFE_CURRENTS_MA:
            logger.info(f"\nTesting at {current_ma} mA:")

            # Set current
            laser.set_ld_current(current_ma)
            time.sleep(STABILIZATION_DELAY)

            # Read actual values
            actual_ma = laser.get_ld_current_actual()
            voltage = laser.get_ld_voltage()

            logger.info(f"  Set: {current_ma} mA")
            logger.info(f"  Actual: {actual_ma:.2f} mA")
            logger.info(f"  Voltage: {voltage:.2f} V")

            # Check if values are reasonable
            if current_ma > 0:
                if abs(actual_ma - current_ma) > 5:  # 5mA tolerance
                    logger.warning(f"  [WARNING] Current mismatch > 5mA")
                else:
                    logger.info(f"  [OK] Current within tolerance")

        # Safely shut down
        logger.info("\nShutting down laser...")
        laser.set_ld_current(0)
        time.sleep(0.5)
        laser.set_ld_output(False)
        laser.disconnect()

        logger.info(f"[OK] Laser {laser_num} test completed successfully")
        return True

    except Exception as e:
        logger.error(f"[FAIL] Laser {laser_num} test failed: {e}")
        try:
            laser.emergency_stop()
            laser.disconnect()
        except:
            pass
        return False


def main():
    """Run the complete end-to-end test"""
    print("\n" + "="*60)
    print("END-TO-END FUNCTIONALITY TEST")
    print(f"Power Meter IP: {POWER_METER_IP}")
    print(f"Safe Current Levels: {SAFE_CURRENTS_MA} mA")
    print("="*60)

    results = {
        'timestamp': datetime.now().isoformat(),
        'power_meter_ok': False,
        'laser1_ok': False,
        'laser2_ok': False
    }

    # Test power meter
    logger.info("\n1. Testing Power Meter Connection")
    results['power_meter_ok'] = test_power_meter_connection()

    # List available resources
    logger.info("\n2. Available VISA Resources:")
    resources = list_visa_resources()
    for res in resources:
        if "0x1313" in res and "0x804F" in res:  # CLD1015 devices
            logger.info(f"  CLD1015: {res}")

    # Test Laser 1
    logger.info("\n3. Testing Laser 1")
    results['laser1_ok'] = test_laser(LASER_RESOURCES[0], 1)

    # Test Laser 2
    logger.info("\n4. Testing Laser 2")
    results['laser2_ok'] = test_laser(LASER_RESOURCES[1], 2)

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Power Meter (IP: {POWER_METER_IP}): {'PASS' if results['power_meter_ok'] else 'FAIL'}")
    print(f"Laser 1: {'PASS' if results['laser1_ok'] else 'FAIL'}")
    print(f"Laser 2: {'PASS' if results['laser2_ok'] else 'FAIL'}")

    # Overall result
    all_passed = all([results['laser1_ok'], results['laser2_ok']])
    if all_passed:
        print("\n*** ALL TESTS PASSED - BOTH PUMP LASERS WORK ***")
        if results['power_meter_ok']:
            print("[OK] Power meter is also accessible")
    else:
        print("\n[FAIL] SOME TESTS FAILED - CHECK LOG FOR DETAILS")

    # Save results
    results_file = f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {results_file}")

    return all_passed


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)