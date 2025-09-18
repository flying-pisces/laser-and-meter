"""
Check connection protection details and see if it can be disabled for testing
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from pump_laser import CLD1015

def main():
    device_address = "USB0::0x1313::0x804F::M01093719::0::INSTR"

    try:
        with CLD1015(device_address) as cld:
            print("CONNECTION PROTECTION ANALYSIS")
            print("=" * 50)

            # Check if connection protection can be disabled
            protection_commands = [
                ("Connection protection mode", "OUTP:PROT:CONN:MODE?"),
                ("Temperature protection mode", "OUTP:PROT:TEMP:MODE?"),
            ]

            for name, cmd in protection_commands:
                try:
                    result = cld.instrument.query(cmd).strip()
                    print(f"{name}: {result}")
                except Exception as e:
                    print(f"{name}: Not available - {e}")

            # Check if we can get more details about the connection
            print(f"\nCurrent protection status:")
            print(f"Connection failure: {cld.instrument.query('OUTP:PROT:CONN:TRIP?').strip()}")

            # Try to see if there are any settings we can adjust
            print(f"\nOutput condition: {cld.instrument.query('OUTP:COND?').strip()}")
            print(f"Output state: {cld.instrument.query('OUTP:STAT?').strip()}")

            # Check if there's a way to set connection protection mode
            try:
                # Try to set protection mode to OFF (if supported)
                print(f"\nAttempting to disable connection protection...")
                cld.instrument.write("OUTP:PROT:CONN:MODE OFF")
                print("Command sent (may not be supported)")

                # Check if it worked
                mode = cld.instrument.query("OUTP:PROT:CONN:MODE?").strip()
                print(f"Connection protection mode: {mode}")

            except Exception as e:
                print(f"Cannot disable connection protection: {e}")

            print(f"\nRECOMMENDATIONS:")
            print("1. Connect a laser diode to the CLD1015 output")
            print("2. If laser diode is connected, check all connections")
            print("3. For testing without laser diode, use a load resistor (~10-50 ohm)")
            print("4. Ensure proper polarity and secure connections")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()