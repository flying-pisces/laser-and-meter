#!/usr/bin/env python3
"""
Pump Laser Test Script

Quick test script to verify laser communication and basic functionality.
"""

import sys
import os

# Add parent directory to path for imports  
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pump_laser import PumpLaser, list_visa_resources


def test_visa_connection():
    """Test VISA resource discovery."""
    print("=" * 50)
    print("VISA Connection Test")
    print("=" * 50)
    
    print("\n1. Testing VISA resource manager...")
    try:
        resources = list_visa_resources()
        print(f"   [OK] VISA manager working, found {len(resources)} resources")
        
        for i, resource in enumerate(resources):
            print(f"   Resource {i}: {resource}")
            
        return resources
        
    except Exception as e:
        print(f"   [ERROR] VISA manager failed: {e}")
        return []


def test_laser_connection(resource_name):
    """Test laser connection and basic commands."""
    print(f"\n2. Testing laser connection to {resource_name}...")
    
    try:
        laser = PumpLaser(resource_name)
        
        if laser.connect():
            print("   [OK] Connection successful")
            
            # Test identification
            try:
                idn = laser.get_identity()
                print(f"   [OK] Identity: {idn}")
            except Exception as e:
                print(f"   [ERROR] Identity query failed: {e}")
            
            # Test current query
            try:
                current = laser.get_current()
                print(f"   [OK] Current reading: {current:.1f} mA")
            except Exception as e:
                print(f"   [ERROR] Current query failed: {e}")
            
            # Test output state query
            try:
                output_state = laser.get_output_state()
                print(f"   [OK] Output state: {'ON' if output_state else 'OFF'}")
            except Exception as e:
                print(f"   [ERROR] Output state query failed: {e}")
            
            # Test status
            try:
                status = laser.get_status()
                print("   [OK] Status query successful")
                print("   Status details:")
                for key, value in status.items():
                    print(f"     {key}: {value}")
            except Exception as e:
                print(f"   [ERROR] Status query failed: {e}")
            
            laser.disconnect()
            print("   [OK] Disconnection successful")
            return True
            
        else:
            print("   [ERROR] Connection failed")
            return False
            
    except Exception as e:
        print(f"   [ERROR] Laser test failed: {e}")
        return False


def main():
    print("Thorlabs Pump Laser - Connection Test")
    
    # Test VISA
    resources = test_visa_connection()
    
    if not resources:
        print("\n[WARNING] No VISA resources found")
        print("   - Check laser is connected via USB")
        print("   - Verify VISA runtime is installed")
        print("   - Check device drivers")
        return
    
    # Default laser address
    default_address = "USB0::0x1313::0x804F::M01093719::0::INSTR"
    
    # Test default address if available
    if default_address in resources:
        print(f"\n[INFO] Testing default laser address: {default_address}")
        if test_laser_connection(default_address):
            print(f"\n[SUCCESS] Default laser connection successful!")
        else:
            print(f"\n[ERROR] Default laser connection failed")
    else:
        print(f"\n[WARNING] Default address {default_address} not found")
    
    # Test all USB resources that might be lasers
    usb_resources = [r for r in resources if r.startswith('USB') and '1313' in r]
    
    if usb_resources:
        print(f"\n[INFO] Found {len(usb_resources)} potential Thorlabs USB device(s):")
        for resource in usb_resources:
            print(f"\n--- Testing {resource} ---")
            test_laser_connection(resource)
    else:
        print("\n[WARNING] No Thorlabs USB devices found (vendor ID 0x1313)")
    
    print(f"\n" + "="*50)
    print("Test Complete")
    print("="*50)


if __name__ == "__main__":
    main()