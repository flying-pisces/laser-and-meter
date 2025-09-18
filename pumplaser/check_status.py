"""
Quick CLD1015 status checker
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from pump_laser import CLD1015

def main():
    """Check CLD1015 status."""
    device_address = "USB0::0x1313::0x804F::M01093719::0::INSTR"

    try:
        with CLD1015(device_address) as cld:
            print("CLD1015 Status Report")
            print("=" * 40)

            status = cld.get_status()

            for key, value in status.items():
                print(f"{key:25}: {value}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()