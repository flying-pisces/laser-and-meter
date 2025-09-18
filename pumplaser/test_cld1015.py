"""
Quick test script for CLD1015 connection
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from pump_laser import CLD1015

# Use the exact address shown in Keysight Connection Expert
device_address = "USB0::0x1313::0x804F::M01093719::0::INSTR"

print(f"Attempting to connect to: {device_address}")

try:
    # Create controller instance
    controller = CLD1015(device_address)

    # Connect to the device
    if controller.connect():
        print("Successfully connected!")

        # Get device identity
        identity = controller.get_identity()
        print(f"Device Identity: {identity}")

        # Get current status
        print("\nDevice Status:")
        print("-" * 40)

        # Get operating mode
        mode = controller.get_operating_mode()
        print(f"Operating Mode: {mode}")

        # Get current setpoint
        current = controller.get_ld_current_setpoint()
        print(f"Current Setpoint: {current:.3f} mA")

        # Get actual current
        actual = controller.get_ld_current_actual()
        print(f"Actual Current: {actual:.3f} mA")

        # Get output state
        output_state = controller.get_ld_output_state()
        print(f"LD Output Enabled: {output_state}")

        # Get temperature
        temp = controller.get_temperature()
        print(f"Temperature: {temp:.1f}°C")

        # Disconnect
        controller.disconnect()
        print("\nDisconnected successfully")

    else:
        print("Failed to connect")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()