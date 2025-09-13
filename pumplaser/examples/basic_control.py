#!/usr/bin/env python3
"""
Basic Pump Laser Control Example

Demonstrates basic laser control operations:
- Connection and identification
- Current setting and ramping
- Output control
- Status monitoring
"""

import sys
import os
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pump_laser import PumpLaser, list_visa_resources


def main():
    print("=" * 60)
    print("Thorlabs Pump Laser - Basic Control Example")
    print("=" * 60)
    
    # List available VISA resources
    print("\nAvailable VISA resources:")
    resources = list_visa_resources()
    for i, resource in enumerate(resources):
        print(f"  {i}: {resource}")
    
    if not resources:
        print("No VISA resources found. Please check laser connection.")
        return
    
    # Use default address or let user select
    laser_address = "USB0::0x1313::0x804F::M01093719::0::INSTR"
    
    # Check if default address is available
    if laser_address not in resources:
        print(f"\nDefault address {laser_address} not found.")
        if resources:
            print("Available resources:")
            for i, res in enumerate(resources):
                print(f"  {i}: {res}")
            try:
                choice = int(input("Select resource index (0-{}): ".format(len(resources)-1)))
                laser_address = resources[choice]
            except (ValueError, IndexError):
                print("Invalid selection. Exiting.")
                return
        else:
            print("No resources available. Exiting.")
            return
    
    print(f"\nUsing laser at: {laser_address}")
    
    try:
        # Connect to laser
        laser = PumpLaser(laser_address)
        
        if not laser.connect():
            print("Failed to connect to laser")
            return
        
        print(f"Connected successfully!")
        
        # Get initial status
        print(f"\nInitial Status:")
        status = laser.get_status()
        for key, value in status.items():
            print(f"  {key}: {value}")
        
        # Demonstrate current control
        print(f"\n--- Current Control Demo ---")
        
        # Ensure output is disabled for safety
        laser.set_output(False)
        print("Output disabled for safety")
        
        # Set initial current to 0
        laser.set_current(0)
        print(f"Current set to 0 mA")
        
        # Ramp up current gradually
        target_current = 50  # mA
        print(f"Ramping current to {target_current} mA...")
        laser.ramp_current(target_current, step_ma=5, delay_s=0.2)
        
        print(f"Current ramp complete. Set: {laser.get_current():.1f} mA, Actual: {laser.get_actual_current():.1f} mA")
        
        # Enable output briefly
        print(f"\nEnabling output for 3 seconds...")
        laser.set_output(True)
        
        for i in range(3):
            time.sleep(1)
            current = laser.get_actual_current()
            power = laser.get_power()
            temp = laser.get_temperature()
            print(f"  T+{i+1}s: Current={current:.1f}mA, Power={power:.3f}W, Temp={temp:.1f}°C")
        
        # Disable output and ramp down
        print(f"\nDisabling output and ramping down...")
        laser.set_output(False)
        laser.ramp_current(0, step_ma=10, delay_s=0.1)
        
        print(f"Current ramped to 0 mA")
        
        # Final status
        print(f"\nFinal Status:")
        status = laser.get_status()
        for key, value in status.items():
            print(f"  {key}: {value}")
        
        # Disconnect
        laser.disconnect()
        print(f"\nDisconnected successfully")
        
    except KeyboardInterrupt:
        print(f"\nKeyboard interrupt - emergency stop")
        if 'laser' in locals():
            laser.emergency_stop()
            laser.disconnect()
    
    except Exception as e:
        print(f"Error: {e}")
        if 'laser' in locals():
            laser.emergency_stop()
            laser.disconnect()


if __name__ == "__main__":
    main()