#!/usr/bin/env python3
"""
Test version of the laser power sweep measurement script.

This version can run without a connected laser, simulating laser behavior
while using the real power meter for validation.
"""

import os
import sys
import pathlib
import glob
import time
import csv
import datetime
from typing import List, Tuple, Optional
import random

# Add power meter module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Python-Driver-for-Thorlabs-power-meter'))
sys.path.extend(glob.glob(f'{pathlib.Path(__file__).parent.resolve()}/Python-Driver-for-Thorlabs-power-meter/*/**/', recursive=True))

from ThorlabsPowerMeter import ThorlabsPowerMeter


class LaserPowerSweepTest:
    """
    Test version of laser power sweep - simulates laser, uses real power meter.
    """
    
    def __init__(self):
        self.power_meter = None
        self.measurement_data = []
        self.logger = None
        
        # Test with first 10 points for quick validation
        self.current_points = [130, 180, 230, 280, 330, 380, 430, 480, 530, 580]
        
        self.stabilization_time = 1.0  # Shorter for testing
        self.readings_per_point = 3    # Fewer readings for testing
    
    def initialize_power_meter(self) -> bool:
        """Initialize power meter only."""
        print("="*60)
        print("Laser Power Sweep - TEST VERSION")
        print("="*60)
        
        try:
            print("\n1. Initializing Power Meter...")
            deviceList = ThorlabsPowerMeter.listDevices()
            self.logger = deviceList.logger
            
            if deviceList.resourceCount == 0:
                print("   [ERROR] No power meter devices found")
                return False
            
            self.power_meter = deviceList.connect(deviceList.resourceName[0])
            if self.power_meter is None:
                print("   [ERROR] Failed to connect to power meter")
                return False
            
            print(f"   [OK] Power meter connected: {deviceList.resourceName[0]}")
            
            # Configure power meter
            self.power_meter.getSensorInfo()
            self.power_meter.setWaveLength(1550)
            self.power_meter.setPowerAutoRange(True)
            self.power_meter.setAverageTime(0.1)
            
            print(f"   [OK] Power meter configured: {self.power_meter.sensorName}")
            
            print("\n2. Laser Simulation Mode...")
            print("   [INFO] Simulating pump laser behavior")
            print("   [INFO] Using real power meter measurements")
            
            return True
            
        except Exception as e:
            print(f"   [ERROR] Power meter initialization failed: {e}")
            return False
    
    def simulate_laser_current(self, current_ma: float):
        """Simulate setting laser current."""
        print(f"   [SIM] Setting laser current to {current_ma} mA")
        time.sleep(0.2)  # Simulate ramp time
        print(f"   [SIM] Laser output enabled")
    
    def take_power_measurement(self, current_ma: float) -> Optional[float]:
        """Take real power measurement while simulating laser."""
        try:
            # Simulate laser operation
            self.simulate_laser_current(current_ma)
            
            # Wait for "stabilization"
            print(f"   Waiting {self.stabilization_time}s for stabilization...")
            time.sleep(self.stabilization_time)
            
            # Take real power readings from power meter
            power_readings = []
            print(f"   Taking {self.readings_per_point} power readings...")
            
            for i in range(self.readings_per_point):
                self.power_meter.updatePowerReading(0.2)
                power = self.power_meter.meterPowerReading
                power_readings.append(power)
                print(f"     Reading {i+1}: {power:.6f} W")
                time.sleep(0.3)
            
            # Calculate average
            avg_power = sum(power_readings) / len(power_readings)
            std_dev = (sum((p - avg_power)**2 for p in power_readings) / len(power_readings))**0.5
            
            print(f"   Average Power: {avg_power:.6f} W (±{std_dev:.6f} W)")
            
            return avg_power
            
        except Exception as e:
            print(f"   [ERROR] Power measurement failed: {e}")
            return None
    
    def run_test_sweep(self) -> bool:
        """Run test measurement sweep."""
        print(f"\n3. Starting Test Measurement Sweep...")
        print(f"   Current points: {self.current_points}")
        print(f"   Number of points: {len(self.current_points)}")
        
        self.measurement_data = []
        start_time = datetime.datetime.now()
        
        try:
            for i, current_ma in enumerate(self.current_points):
                print(f"\n--- Test Point {i+1}/{len(self.current_points)} ---")
                print(f"Target Current: {current_ma} mA")
                
                # Take measurement
                optical_power = self.take_power_measurement(current_ma)
                
                if optical_power is None:
                    print(f"   [ERROR] Measurement failed at {current_ma} mA")
                    break
                
                # Simulate actual current (with small deviation)
                actual_current = current_ma + random.uniform(-2, 2)
                
                # Store data
                measurement = {
                    'point': i + 1,
                    'target_current_ma': current_ma,
                    'actual_current_ma': actual_current,
                    'optical_power_w': optical_power,
                    'optical_power_mw': optical_power * 1000,
                    'timestamp': datetime.datetime.now().isoformat()
                }
                
                self.measurement_data.append(measurement)
                
                print(f"   [OK] Point {i+1}: {actual_current:.1f}mA -> {optical_power*1000:.3f}mW")
                
                time.sleep(0.2)  # Brief pause
            
            print(f"\n   [SIM] Disabling laser output")
            
            end_time = datetime.datetime.now()
            duration = end_time - start_time
            
            print(f"\n4. Test Sweep Complete!")
            print(f"   Duration: {duration}")
            print(f"   Points collected: {len(self.measurement_data)}")
            
            return True
            
        except KeyboardInterrupt:
            print(f"\n   [WARNING] Test interrupted by user")
            return False
            
        except Exception as e:
            print(f"\n   [ERROR] Test sweep failed: {e}")
            return False
    
    def save_test_results(self) -> str:
        """Save test results to CSV."""
        if not self.measurement_data:
            return ""
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"laser_power_sweep_TEST_{timestamp}.csv"
        filepath = os.path.join(os.path.dirname(__file__), filename)
        
        try:
            with open(filepath, 'w', newline='') as csvfile:
                fieldnames = ['point', 'target_current_ma', 'actual_current_ma', 
                            'optical_power_w', 'optical_power_mw', 'timestamp']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for measurement in self.measurement_data:
                    writer.writerow(measurement)
            
            print(f"\n5. Test Results Saved: {filename}")
            print(f"   File path: {filepath}")
            
            # Print summary
            powers_mw = [m['optical_power_mw'] for m in self.measurement_data]
            print(f"   Power readings: {min(powers_mw):.3f} - {max(powers_mw):.3f} mW")
            
            return filepath
            
        except Exception as e:
            print(f"   [ERROR] Failed to save test results: {e}")
            return ""
    
    def cleanup(self):
        """Clean shutdown."""
        print(f"\n6. Cleanup...")
        if self.power_meter:
            try:
                self.power_meter.disconnect()
                print("   [OK] Power meter disconnected")
            except:
                pass


def main():
    """Run test version."""
    test_system = LaserPowerSweepTest()
    
    try:
        if not test_system.initialize_power_meter():
            print("\n[FAILED] Power meter initialization failed")
            return
        
        if not test_system.run_test_sweep():
            print("\n[FAILED] Test sweep failed")
            return
        
        result_file = test_system.save_test_results()
        
        if result_file:
            print(f"\n[SUCCESS] Test completed successfully!")
            print(f"Test results: {result_file}")
            print(f"\nThis validates the measurement framework is working.")
            print(f"Run laser_power_sweep.py when laser is connected.")
        
    except Exception as e:
        print(f"\n[ERROR] Test system error: {e}")
    
    finally:
        test_system.cleanup()
        print("\n" + "="*60)


if __name__ == "__main__":
    main()