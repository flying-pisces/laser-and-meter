"""
Example script for controlling Thorlabs CLD1015 laser diode controller.

This script demonstrates how to:
- Connect to the CLD1015
- Set and monitor laser current
- Control temperature via TEC
- Ramp current safely
"""

import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pump_laser import CLD1015, list_visa_resources


def find_cld1015():
    """Find CLD1015 device in available VISA resources."""
    resources = list_visa_resources()
    print("Available VISA resources:")
    for res in resources:
        print(f"  {res}")

    # Look for CLD1015 (Thorlabs vendor ID is 0x1313)
    for res in resources:
        if "0x1313" in res or "CLD" in res.upper():
            print(f"\nFound CLD1015: {res}")
            return res

    return None


def main():
    """Main control demonstration."""
    print("=" * 60)
    print("Thorlabs CLD1015 Laser Diode Controller Demo")
    print("=" * 60)

    # Find device
    device_address = find_cld1015()
    if not device_address:
        print("\nERROR: No CLD1015 device found!")
        print("Please check:")
        print("  - Device is powered on")
        print("  - USB cable is connected")
        print("  - VISA drivers are installed")
        return

    # Connect and control
    try:
        with CLD1015(device_address) as cld:
            print("\n" + "-" * 40)
            print("Device Information:")
            print("-" * 40)
            print(f"Identity: {cld.get_identity()}")

            # Set operating mode to current control
            print("\n" + "-" * 40)
            print("Configuring Device:")
            print("-" * 40)
            cld.set_operating_mode("CURRENT")
            print(f"Operating mode: {cld.get_operating_mode()}")

            # Set current limit for safety
            current_limit_ma = 200  # 200 mA limit
            cld.set_current_limit(current_limit_ma)
            print(f"Current limit set to: {cld.get_current_limit():.1f} mA")

            # Enable TEC for temperature control
            print("\n" + "-" * 40)
            print("Temperature Control:")
            print("-" * 40)
            cld.set_temperature_setpoint(25.0)  # 25°C
            cld.set_tec_output(True)
            print(f"TEC enabled: {cld.get_tec_output_state()}")
            print(f"Temperature setpoint: {cld.get_temperature_setpoint():.1f}°C")
            time.sleep(1)
            print(f"Current temperature: {cld.get_temperature():.1f}°C")

            # Laser current control demo
            print("\n" + "-" * 40)
            print("Laser Current Control:")
            print("-" * 40)

            # Start with zero current
            cld.set_ld_current(0)
            print("Current set to 0 mA")

            # Enable laser output
            cld.set_ld_output(True)
            print("Laser output enabled")

            # Ramp current up slowly
            target_current_ma = 50  # Target: 50 mA
            print(f"\nRamping current to {target_current_ma} mA...")
            cld.ramp_current(target_current_ma, step_ma=5, delay_s=0.2)

            # Monitor current and voltage
            print("\n" + "-" * 40)
            print("Monitoring (5 seconds):")
            print("-" * 40)
            print("Time\tSetpoint\tActual\t\tVoltage\t\tTemp")
            print("(s)\t(mA)\t\t(mA)\t\t(V)\t\t(°C)")
            print("-" * 60)

            for i in range(5):
                setpoint = cld.get_ld_current_setpoint()
                actual = cld.get_ld_current_actual()
                voltage = cld.get_ld_voltage()
                temp = cld.get_temperature()

                print(f"{i+1}\t{setpoint:.2f}\t\t{actual:.2f}\t\t"
                      f"{voltage:.3f}\t\t{temp:.1f}")
                time.sleep(1)

            # Ramp current down
            print("\nRamping current down to 0 mA...")
            cld.ramp_current(0, step_ma=5, delay_s=0.1)

            # Disable outputs
            print("\nDisabling outputs...")
            cld.set_ld_output(False)
            cld.set_tec_output(False)

            # Final status
            print("\n" + "-" * 40)
            print("Final Status:")
            print("-" * 40)
            status = cld.get_status()
            for key, value in status.items():
                if key != 'identity':  # Skip long identity string
                    print(f"  {key}: {value}")

            print("\n" + "=" * 60)
            print("Demo completed successfully!")
            print("=" * 60)

    except Exception as e:
        print(f"\nERROR: {e}")
        print("\nMake sure:")
        print("  - The CLD1015 is properly connected")
        print("  - No other software is using the device")
        print("  - You have the necessary permissions")


if __name__ == "__main__":
    main()