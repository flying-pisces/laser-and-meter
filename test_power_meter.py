#!/usr/bin/env python3
"""
Test script for Thorlabs Power Meter automation
"""
import os
import sys
import pathlib
import glob
import time

# Add Python-Driver-for-Thorlabs-power-meter to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Python-Driver-for-Thorlabs-power-meter'))
sys.path.extend(glob.glob(f'{pathlib.Path(__file__).parent.resolve()}/Python-Driver-for-Thorlabs-power-meter/*/**/', recursive=True))

from ThorlabsPowerMeter import ThorlabsPowerMeter


def test_power_meter():
    """Test power meter basic functionality."""
    print("="*60)
    print("Thorlabs Power Meter - Automation Test")
    print("="*60)
    
    try:
        # List devices
        print("\n1. Discovering power meter devices...")
        deviceList = ThorlabsPowerMeter.listDevices()
        logger = deviceList.logger
        
        if deviceList.resourceCount == 0:
            print("   [ERROR] No power meter devices found")
            return False
        
        print(f"   [OK] Found {deviceList.resourceCount} power meter device(s)")
        for i, resource in enumerate(deviceList.resourceName):
            print(f"   Device {i}: {resource}")
        
        # Connect to first device
        print(f"\n2. Connecting to first device: {deviceList.resourceName[0]}")
        device = deviceList.connect(deviceList.resourceName[0])
        
        if device is None:
            print("   [ERROR] Failed to connect to device")
            return False
        
        print("   [OK] Connected successfully")
        
        # Get sensor info
        print(f"\n3. Reading sensor information...")
        device.getSensorInfo()
        print(f"   Sensor Name: {device.sensorName}")
        print(f"   Serial Number: {device.sensorSerialNumber}")
        print(f"   Sensor Type: {device.sensorType}")
        
        # Configure device
        print(f"\n4. Configuring device settings...")
        device.setWaveLength(1550)  # Set to 1550nm (common fiber optic wavelength)
        device.setDispBrightness(0.5)
        device.setAttenuation(0)
        device.setPowerAutoRange(True)
        device.setAverageTime(0.01)  # 10ms averaging
        device.setTimeoutValue(2000)  # 2 second timeout
        
        print("   [OK] Device configured successfully")
        
        # Take power readings
        print(f"\n5. Taking power readings...")
        for i in range(10):
            device.updatePowerReading(0.1)
            power = device.meterPowerReading
            unit = device.meterPowerUnit
            logger.info(f'Reading {i+1}: {power} {unit}')
            print(f"   Reading {i+1}: {power} {unit}")
            time.sleep(0.2)
        
        # Disconnect
        print(f"\n6. Disconnecting from device...")
        device.disconnect()
        print("   [OK] Disconnected successfully")
        
        return True
        
    except Exception as e:
        print(f"   [ERROR] Test failed: {e}")
        if 'device' in locals():
            try:
                device.disconnect()
            except:
                pass
        return False


if __name__ == "__main__":
    success = test_power_meter()
    
    print(f"\n" + "="*60)
    if success:
        print("Power Meter Test: [SUCCESS]")
    else:
        print("Power Meter Test: [FAILED]")
    print("="*60)