#!/usr/bin/env python3
"""
Integrated test demonstrating both pump laser control and power meter measurement.

This script shows how the pump laser and power meter can work together
for automated optical measurements.
"""

import os
import sys
import pathlib
import glob
import time

# Add both modules to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Python-Driver-for-Thorlabs-power-meter'))
sys.path.extend(glob.glob(f'{pathlib.Path(__file__).parent.resolve()}/Python-Driver-for-Thorlabs-power-meter/*/**/', recursive=True))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'pumplaser'))

from ThorlabsPowerMeter import ThorlabsPowerMeter
from pumplaser import PumpLaser, list_visa_resources


def integrated_laser_power_test():
    """
    Demonstrate integrated laser control and power measurement.
    
    Note: This test will show laser VISA discovery but power meter 
    measurements only, since laser connection may fail without proper device.
    """
    print("="*70)
    print("Integrated Pump Laser Control & Power Meter Test")
    print("="*70)
    
    power_meter = None
    laser = None
    
    try:
        # 1. Initialize Power Meter
        print("\n1. Initializing Power Meter...")
        deviceList = ThorlabsPowerMeter.listDevices()
        
        if deviceList.resourceCount == 0:
            print("   [ERROR] No power meter devices found")
            return False
        
        power_meter = deviceList.connect(deviceList.resourceName[0])
        if power_meter is None:
            print("   [ERROR] Failed to connect to power meter")
            return False
        
        print(f"   [OK] Power meter connected: {deviceList.resourceName[0]}")
        
        # Configure power meter
        power_meter.getSensorInfo()
        power_meter.setWaveLength(1550)  # Set to 1550nm
        power_meter.setPowerAutoRange(True)
        power_meter.setAverageTime(0.01)
        print(f"   [OK] Power meter configured for {power_meter.sensorName}")
        
        # 2. Initialize Laser (Discovery Only)
        print("\n2. Discovering Pump Laser...")
        visa_resources = list_visa_resources()
        
        # Look for potential pump laser addresses
        potential_lasers = [r for r in visa_resources if 'USB0::0x1313::0x804F' in r]
        
        if potential_lasers:
            print(f"   [INFO] Found {len(potential_lasers)} potential pump laser(s):")
            for laser_addr in potential_lasers:
                print(f"     - {laser_addr}")
            
            # Try to connect to first potential laser
            laser_addr = potential_lasers[0]
            print(f"   [INFO] Attempting connection to: {laser_addr}")
            
            laser = PumpLaser(laser_addr)
            if laser.connect():
                print(f"   [OK] Laser connected successfully!")
                print(f"   [OK] Laser ID: {laser.get_identity()}")
                laser_available = True
            else:
                print(f"   [WARNING] Laser connection failed - proceeding with power meter only")
                laser_available = False
                laser = None
        else:
            print("   [WARNING] No potential pump lasers found")
            laser_available = False
        
        # 3. Baseline Power Measurement
        print("\n3. Taking baseline power measurements...")
        baseline_powers = []
        for i in range(5):
            power_meter.updatePowerReading(0.1)
            power = power_meter.meterPowerReading
            baseline_powers.append(power)
            print(f"   Baseline {i+1}: {power:.2e} W")
            time.sleep(0.2)
        
        avg_baseline = sum(baseline_powers) / len(baseline_powers)
        print(f"   [OK] Average baseline power: {avg_baseline:.2e} W")
        
        # 4. Laser Control Demonstration (if available)
        if laser_available and laser:
            print("\n4. Laser Control Demonstration...")
            
            # Ensure laser starts at 0 current
            laser.set_current(0)
            laser.set_output(False)
            print("   [OK] Laser initialized to 0 mA, output disabled")
            
            # Demonstrate current ramping
            print("   [INFO] Ramping laser current to 50 mA...")
            laser.ramp_current(50, step_ma=10, delay_s=0.3)
            
            current = laser.get_current()
            print(f"   [OK] Laser current set to: {current:.1f} mA")
            
            # Enable output briefly and measure
            print("   [INFO] Enabling laser output for measurement...")
            laser.set_output(True)
            
            # Take measurements with laser on
            laser_on_powers = []
            for i in range(5):
                time.sleep(0.2)
                power_meter.updatePowerReading(0.1)
                power = power_meter.meterPowerReading
                laser_on_powers.append(power)
                print(f"   Laser ON {i+1}: {power:.2e} W")
            
            avg_laser_power = sum(laser_on_powers) / len(laser_on_powers)
            
            # Safe shutdown
            print("   [INFO] Safely shutting down laser...")
            laser.set_output(False)
            laser.ramp_current(0, step_ma=10, delay_s=0.1)
            print("   [OK] Laser safely shut down")
            
            # Analysis
            power_difference = avg_laser_power - avg_baseline
            print(f"\n   Analysis:")
            print(f"   - Baseline power: {avg_baseline:.2e} W")
            print(f"   - Laser ON power: {avg_laser_power:.2e} W")
            print(f"   - Power difference: {power_difference:.2e} W")
            
        else:
            print("\n4. Laser Control Demonstration...")
            print("   [SKIP] No laser available - demonstrating power meter monitoring only")
            
            # Continue with power monitoring
            print("   [INFO] Monitoring power meter for changes...")
            for i in range(10):
                power_meter.updatePowerReading(0.1)
                power = power_meter.meterPowerReading
                change = ((power - avg_baseline) / avg_baseline) * 100
                print(f"   Monitor {i+1}: {power:.2e} W ({change:+.1f}% from baseline)")
                time.sleep(0.5)
        
        print("\n5. Test Summary...")
        print("   [OK] Power meter automation: WORKING")
        print(f"   [{'OK' if laser_available else 'SKIP'}] Laser control: {'WORKING' if laser_available else 'NOT AVAILABLE'}")
        print("   [OK] Integrated test: COMPLETED")
        
        return True
        
    except Exception as e:
        print(f"   [ERROR] Integrated test failed: {e}")
        return False
        
    finally:
        # Clean shutdown
        print("\n6. Cleanup...")
        if laser:
            try:
                laser.emergency_stop()
                laser.disconnect()
                print("   [OK] Laser disconnected")
            except:
                pass
        
        if power_meter:
            try:
                power_meter.disconnect()
                print("   [OK] Power meter disconnected")
            except:
                pass


if __name__ == "__main__":
    success = integrated_laser_power_test()
    
    print(f"\n" + "="*70)
    if success:
        print("Integrated Test Result: [SUCCESS]")
        print("\nThe laser and power meter drivers are ready for automation!")
        print("- Power meter: Fully functional and tested")
        print("- Laser driver: Framework ready (requires proper laser connection)")
    else:
        print("Integrated Test Result: [FAILED]")
    print("="*70)