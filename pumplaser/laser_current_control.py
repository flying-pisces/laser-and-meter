"""
Thorlabs CLD1015 Laser Current Control Example

This script demonstrates how to safely control the laser current
and monitor the device status.
"""

import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from pump_laser import CLD1015

# Use the CLD1015 address from Keysight Connection Expert
DEVICE_ADDRESS = "USB0::0x1313::0x804F::M01093719::0::INSTR"

def main():
    """Main laser control demonstration."""
    print("=" * 60)
    print("CLD1015 Laser Current Control")
    print("=" * 60)

    try:
        with CLD1015(DEVICE_ADDRESS) as cld:
            print(f"Connected to: {cld.get_identity()}")

            # Safety: Set current limit
            current_limit = 100.0  # 100 mA limit
            cld.set_current_limit(current_limit)
            print(f"Current limit set to: {current_limit} mA")

            # Set to current control mode
            cld.set_operating_mode("CURRENT")
            print(f"Operating mode: {cld.get_operating_mode()}")

            # Start with zero current
            print("\nSetting initial current to 0 mA...")
            cld.set_ld_current(0)

            # Enable laser output
            print("Enabling laser output...")
            cld.set_ld_output(True)

            # Test current control
            test_currents = [10, 25, 50, 75, 50, 25, 0]  # mA

            print("\n" + "=" * 60)
            print("Current Control Test")
            print("=" * 60)

            for target_current in test_currents:
                print(f"\nSetting current to {target_current} mA...")

                # Set current
                cld.set_ld_current(target_current)
                time.sleep(0.5)  # Allow time to settle

                # Read back values
                setpoint = cld.get_ld_current_setpoint()
                actual = cld.get_ld_current_actual()
                voltage = cld.get_ld_voltage()
                temp = cld.get_temperature()

                print(f"  Setpoint: {setpoint:.2f} mA")
                print(f"  Actual:   {actual:.2f} mA")
                print(f"  Voltage:  {voltage:.3f} V")
                print(f"  Temp:     {temp:.1f}°C")

                # Wait a bit before next change
                time.sleep(1)

            # Final cleanup
            print("\nDisabling laser output...")
            cld.set_ld_output(False)
            print("Test completed successfully!")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()