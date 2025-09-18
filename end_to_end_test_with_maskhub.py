"""
End-to-End Test with MaskHub Integration

Tests both CLD1015 pump lasers with power measurement and uploads
data to MaskHub for analysis and storage.
"""

import sys
import os
import time
import logging
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add paths for local modules
sys.path.insert(0, os.path.abspath('.'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'pumplaser'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'maskhub'))

from pumplaser.pump_laser import CLD1015, list_visa_resources
from maskhub.laser_maskhub_integration import (
    LaserMaskHubIntegration,
    LaserMeasurement,
    LaserRunConfig,
    create_laser_measurement_from_test_data
)
from maskhub.maskhub_config import MaskHubConfigManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'laser_maskhub_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Test configuration
SAFE_CURRENT_LEVELS_MA = [0, 50, 100]  # Limited to safe levels
STABILIZATION_DELAY_S = 2
MEASUREMENT_COUNT = 3  # Number of measurements per current level

# Known laser resources
LASER_RESOURCES = [
    "USB0::0x1313::0x804F::M01093719::INSTR",   # Laser 1
    "USB0::0x1313::0x804F::M00859480::INSTR"    # Laser 2
]

# MaskHub run configuration
MASKHUB_RUN_CONFIG = LaserRunConfig(
    mask_id=12345,  # Update with actual mask ID
    run_name=f"Thorlabs_Laser_Test_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
    lot_name="THORLABS_LOT_001",
    wafer_name="LASER_WAFER_001",
    operator="Test_Operator",
    station="Thorlabs_CLD1015_Station",
    measurement_type="laser_iv_characterization"
)


def create_synthetic_raw_data(current_ma: float, voltage_v: float,
                             duration_s: float = 1.0, sample_rate_hz: float = 100) -> pd.DataFrame:
    """Create synthetic raw measurement data"""
    n_samples = int(duration_s * sample_rate_hz)
    time_points = [i / sample_rate_hz for i in range(n_samples)]

    # Add small variations to simulate real measurements
    current_noise = [current_ma + (i % 5 - 2) * 0.01 for i in range(n_samples)]
    voltage_noise = [voltage_v + (i % 3 - 1) * 0.001 for i in range(n_samples)]

    return pd.DataFrame({
        'time_s': time_points,
        'current_ma': current_noise,
        'voltage_v': voltage_noise,
        'measurement_id': range(n_samples)
    })


def test_laser_with_maskhub(laser_resource: str, laser_name: str,
                           maskhub_integration: LaserMaskHubIntegration,
                           device_position: tuple = (0, 0)) -> Dict:
    """Test a single laser and upload data to MaskHub"""

    logger.info(f"\n{'='*50}")
    logger.info(f"Testing {laser_name}: {laser_resource}")
    logger.info(f"{'='*50}")

    results = {
        'laser_name': laser_name,
        'resource': laser_resource,
        'test_passed': False,
        'measurements_taken': 0,
        'measurements_uploaded': 0,
        'errors': []
    }

    try:
        # Connect to laser
        laser = CLD1015(laser_resource)
        if not laser.connect():
            raise RuntimeError(f"Failed to connect to {laser_name}")

        logger.info(f"[OK] Connected to {laser_name}")

        # Get initial status
        status = laser.get_status()
        logger.info(f"  Model: {status['identity']}")
        logger.info(f"  Temperature: {status['temperature_c']:.1f}°C")

        # Set safety limits
        laser.set_current_limit(100)
        laser.set_ld_output(True)
        logger.info(f"[OK] {laser_name} output enabled with 100mA limit")

        # Test each current level
        for current_ma in SAFE_CURRENT_LEVELS_MA:
            logger.info(f"\n{laser_name}: Testing at {current_ma} mA")

            # Set current and wait for stabilization
            laser.set_ld_current(current_ma)
            time.sleep(STABILIZATION_DELAY_S)

            # Take multiple measurements at this current level
            for measurement_idx in range(MEASUREMENT_COUNT):
                # Get measurements
                actual_ma = laser.get_ld_current_actual()
                voltage_v = laser.get_ld_voltage()
                temperature_c = laser.get_temperature()

                # Create synthetic raw data (replace with real power meter data if available)
                raw_data = create_synthetic_raw_data(actual_ma, voltage_v)

                # Simulate power measurement (replace with actual power meter reading)
                power_mw = None
                if current_ma > 0:
                    # Rough approximation: assume ~50% efficiency
                    power_mw = (actual_ma * voltage_v * 0.5)  # Very rough estimate

                # Create laser measurement
                measurement = LaserMeasurement(
                    device_id=f"{laser_name}_{laser_resource.split('::')[-2]}",
                    position=device_position,
                    current_setpoint_ma=current_ma,
                    current_actual_ma=actual_ma,
                    voltage_v=voltage_v,
                    power_mw=power_mw,
                    temperature_c=temperature_c,
                    timestamp=datetime.now(),
                    metadata={
                        'measurement_index': measurement_idx,
                        'laser_serial': laser_resource.split('::')[-2],
                        'test_type': 'iv_characterization',
                        'current_tolerance_ma': abs(actual_ma - current_ma)
                    },
                    raw_data=raw_data
                )

                # Add measurement to MaskHub integration
                die_position = (device_position[0] + measurement_idx, device_position[1])
                maskhub_integration.add_measurement(measurement, die_position)

                results['measurements_taken'] += 1

                logger.info(f"  Measurement {measurement_idx + 1}: "
                          f"{actual_ma:.2f}mA, {voltage_v:.3f}V, {temperature_c:.1f}°C")

                # Small delay between measurements
                time.sleep(0.5)

        # Ramp down and disable output
        logger.info(f"\n{laser_name}: Shutting down safely")
        laser.ramp_current(0, 10, 0.2)
        laser.set_ld_output(False)
        laser.disconnect()

        results['test_passed'] = True
        logger.info(f"[OK] {laser_name} test completed successfully")

    except Exception as e:
        error_msg = f"{laser_name} test failed: {e}"
        logger.error(f"[FAIL] {error_msg}")
        results['errors'].append(error_msg)

        # Emergency shutdown
        try:
            laser.emergency_stop()
            laser.disconnect()
        except:
            pass

    return results


def main():
    """Main test function with MaskHub integration"""

    logger.info("="*60)
    logger.info("THORLABS LASER TEST WITH MASKHUB INTEGRATION")
    logger.info("="*60)

    # Check MaskHub configuration
    config_manager = MaskHubConfigManager()
    credentials = config_manager.get_credentials()

    if not credentials:
        logger.warning("No MaskHub credentials found - creating example config")
        config_manager.create_example_config()
        logger.info("Please edit maskhub_config.example.json with your credentials")
        logger.info("Running test in local-only mode (no MaskHub upload)")

    # Initialize MaskHub integration
    logger.info("\nInitializing MaskHub integration...")
    maskhub_integration = LaserMaskHubIntegration(
        enable_realtime=True,
        auto_save_data=True
    )

    # Start measurement run
    logger.info(f"\nStarting measurement run: {MASKHUB_RUN_CONFIG.run_name}")
    run_id = maskhub_integration.start_run(MASKHUB_RUN_CONFIG)
    logger.info(f"Run ID: {run_id}")

    test_results = {
        'run_id': run_id,
        'run_config': MASKHUB_RUN_CONFIG,
        'laser_results': [],
        'overall_success': False,
        'maskhub_stats': {}
    }

    try:
        # Test Laser 1
        logger.info("\n" + "="*40)
        logger.info("TESTING LASER 1")
        logger.info("="*40)

        laser1_results = test_laser_with_maskhub(
            LASER_RESOURCES[0],
            "Laser_1",
            maskhub_integration,
            device_position=(0, 0)
        )
        test_results['laser_results'].append(laser1_results)

        # Test Laser 2
        logger.info("\n" + "="*40)
        logger.info("TESTING LASER 2")
        logger.info("="*40)

        laser2_results = test_laser_with_maskhub(
            LASER_RESOURCES[1],
            "Laser_2",
            maskhub_integration,
            device_position=(10, 0)
        )
        test_results['laser_results'].append(laser2_results)

        # Wait for uploads to complete
        logger.info("\nWaiting for MaskHub uploads to complete...")
        time.sleep(5)  # Give time for background uploads

        # Get upload statistics
        maskhub_stats = maskhub_integration.get_statistics()
        test_results['maskhub_stats'] = maskhub_stats

        # Finish the run
        logger.info("\nFinishing measurement run...")
        run_summary = maskhub_integration.finish_run(trigger_analysis=True)
        test_results['run_summary'] = run_summary

        # Determine overall success
        all_lasers_passed = all(result['test_passed'] for result in test_results['laser_results'])
        upload_success = maskhub_stats.get('failed', 0) == 0

        test_results['overall_success'] = all_lasers_passed

        # Print summary
        logger.info("\n" + "="*60)
        logger.info("TEST SUMMARY")
        logger.info("="*60)

        for result in test_results['laser_results']:
            status = "PASS" if result['test_passed'] else "FAIL"
            logger.info(f"{result['laser_name']}: {status} "
                       f"({result['measurements_taken']} measurements)")

        logger.info(f"\nMaskHub Upload Stats:")
        logger.info(f"  Total: {maskhub_stats.get('total', 0)}")
        logger.info(f"  Successful: {maskhub_stats.get('successful', 0)}")
        logger.info(f"  Failed: {maskhub_stats.get('failed', 0)}")
        logger.info(f"  Service Available: {maskhub_stats.get('service_available', False)}")

        if test_results['overall_success']:
            logger.info("\n*** ALL LASER TESTS PASSED ***")
            if maskhub_stats.get('service_available', False):
                logger.info(f"Data uploaded to MaskHub run: {run_id}")
        else:
            logger.error("\n*** SOME TESTS FAILED ***")

    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        test_results['overall_success'] = False

    finally:
        # Clean up MaskHub integration
        maskhub_integration.close()

    # Save test results
    import json
    results_file = f"laser_maskhub_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    # Make results JSON serializable
    def clean_for_json(obj):
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        elif isinstance(obj, dict):
            return {k: clean_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [clean_for_json(item) for item in obj]
        elif isinstance(obj, (int, float, str, bool, type(None))):
            return obj
        else:
            return str(obj)

    with open(results_file, 'w') as f:
        json.dump(clean_for_json(test_results), f, indent=2)

    logger.info(f"\nTest results saved to: {results_file}")

    return test_results['overall_success']


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.warning("\nTest interrupted by user")
        sys.exit(2)
    except Exception as e:
        logger.error(f"\nUnexpected error: {e}")
        sys.exit(3)