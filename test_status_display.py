#!/usr/bin/env python3
"""
Quick test to demonstrate the device status display in different scenarios.
"""

import os
import sys
import pathlib
import glob

# Add modules to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Python-Driver-for-Thorlabs-power-meter'))
sys.path.extend(glob.glob(f'{pathlib.Path(__file__).parent.resolve()}/Python-Driver-for-Thorlabs-power-meter/*/**/', recursive=True))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'pumplaser'))

from ThorlabsPowerMeter import ThorlabsPowerMeter
from pumplaser import PumpLaser, list_visa_resources

def test_instrument_discovery():
    """Test what the status block will show for instrument discovery."""
    
    print("="*60)
    print("Device Status Display Test")
    print("="*60)
    
    # Test power meter discovery
    print("\n1. Power Meter Discovery:")
    try:
        deviceList = ThorlabsPowerMeter.listDevices()
        if deviceList.resourceCount > 0:
            pm_address = deviceList.resourceName[0]
            print(f"   Address: {pm_address}")
            print(f"   Status: Available for connection")
            
            # Try connection
            power_meter = deviceList.connect(pm_address)
            if power_meter:
                power_meter.getSensorInfo()
                print(f"   Device: {power_meter.sensorName} ({power_meter.sensorSerialNumber})")
                print(f"   Connection: SUCCESS")
                power_meter.disconnect()
            else:
                print(f"   Connection: FAILED")
        else:
            print(f"   Address: Not Found")
            print(f"   Status: No power meter detected")
            
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test laser discovery
    print("\n2. Laser Discovery:")
    try:
        visa_resources = list_visa_resources()
        potential_lasers = [r for r in visa_resources if 'USB0::0x1313::0x804F' in r]
        
        if potential_lasers:
            target_address = "USB0::0x1313::0x804F::M01093719::0::INSTR"
            if target_address in potential_lasers:
                laser_addr = target_address
                print(f"   Address: {laser_addr} (Target Found)")
            else:
                laser_addr = potential_lasers[0]
                print(f"   Address: {laser_addr} (Alternative)")
            
            print(f"   Status: Available for connection")
            
            # Try connection
            laser = PumpLaser(laser_addr)
            if laser.connect():
                identity = laser.get_identity()
                print(f"   Device: {identity}")
                print(f"   Connection: SUCCESS")
                laser.disconnect()
            else:
                print(f"   Connection: FAILED - Device not responding")
        else:
            print(f"   Address: Not Found")
            print(f"   Status: No pump laser detected")
            
    except Exception as e:
        print(f"   Error: {e}")
    
    # Summary of what GUI will show
    print("\n3. GUI Status Block Summary:")
    print("   The GUI will display:")
    print("   - Actual VISA addresses (e.g., USB0::0x1313::0x804F::M01093719::0::INSTR)")
    print("   - Connection status (Connected/Disconnected/Communication Error)")
    print("   - Device information (Model, Serial Number)")
    print("   - System mode:")
    print("     * PRODUCTION MODE - Real Instruments (both connected)")
    print("     * PARTIAL CONNECTION - Some Instruments (one connected)")
    print("     * NO INSTRUMENTS - Check Connections (none connected)")
    print("     * DEMO MODE - All Data Simulated (demo version)")
    
    print(f"\n" + "="*60)


if __name__ == "__main__":
    test_instrument_discovery()