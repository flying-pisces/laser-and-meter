#!/usr/bin/env python3
"""
Automated Laser Current vs Optical Power Measurement Script

This script performs automated measurements by setting different pump laser currents
and recording the corresponding optical power from the Thorlabs power meter.

Measurement sequence:
- Step through laser currents from 130mA to 1480mA in 50mA increments
- At each current, record stabilized optical power readings
- Export results to CSV file for analysis
- Include safety monitoring and emergency stop capabilities
"""

import os
import sys
import pathlib
import glob
import time
import csv
import datetime
from typing import List, Tuple, Optional

# Add both modules to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Python-Driver-for-Thorlabs-power-meter'))
sys.path.extend(glob.glob(f'{pathlib.Path(__file__).parent.resolve()}/Python-Driver-for-Thorlabs-power-meter/*/**/', recursive=True))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'pumplaser'))

from ThorlabsPowerMeter import ThorlabsPowerMeter
from pumplaser import PumpLaser, list_visa_resources


class LaserPowerSweepMeasurement:
    """
    Automated laser current vs optical power measurement system.
    """
    
    def __init__(self):
        self.power_meter = None
        self.laser = None
        self.measurement_data = []
        self.logger = None
        
        # Measurement parameters from your table
        self.current_points = [
            130, 180, 230, 280, 330, 380, 430, 480, 530, 580,
            630, 680, 730, 780, 830, 880, 930, 980, 1030, 1080,
            1130, 1180, 1230, 1280, 1330, 1380, 1430, 1480
        ]
        
        # Safety limits
        self.max_current_ma = 1500  # Maximum safe current
        self.max_power_w = 1.0      # Maximum expected power (1W)
        self.stabilization_time = 2.0  # Seconds to wait for stabilization
        self.readings_per_point = 5    # Number of readings to average
        
    def initialize_instruments(self) -> bool:
        """Initialize both laser and power meter."""
        print("="*70)
        print("Laser Current vs Optical Power Measurement System")
        print("="*70)
        
        try:
            # Initialize Power Meter
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
            self.power_meter.setWaveLength(1550)  # Set to 1550nm
            self.power_meter.setPowerAutoRange(True)
            self.power_meter.setAverageTime(0.1)  # 100ms averaging for stability
            self.power_meter.setTimeoutValue(5000)  # 5 second timeout
            
            print(f"   [OK] Power meter configured: {self.power_meter.sensorName}")
            print(f"        - Wavelength: 1550 nm")
            print(f"        - Auto range: Enabled")
            print(f"        - Averaging: 100 ms")
            
            # Initialize Laser
            print("\n2. Initializing Pump Laser...")
            visa_resources = list_visa_resources()
            
            # Look for pump laser addresses (your specified address pattern)
            potential_lasers = [r for r in visa_resources if 'USB0::0x1313::0x804F' in r]
            
            if not potential_lasers:
                print("   [ERROR] No pump laser devices found")
                print("   Expected pattern: USB0::0x1313::0x804F::*")
                return False
            
            print(f"   [INFO] Found {len(potential_lasers)} potential pump laser(s):")
            for laser_addr in potential_lasers:
                print(f"     - {laser_addr}")
            
            # Try to connect to the specified laser address first
            target_address = "USB0::0x1313::0x804F::M01093719::0::INSTR"
            if target_address in potential_lasers:
                laser_addr = target_address
                print(f"   [INFO] Using specified laser: {laser_addr}")
            else:
                laser_addr = potential_lasers[0]
                print(f"   [WARNING] Specified laser not found, using: {laser_addr}")
            
            self.laser = PumpLaser(laser_addr)
            if not self.laser.connect():
                print(f"   [ERROR] Failed to connect to laser: {laser_addr}")
                return False
            
            print(f"   [OK] Laser connected successfully!")
            print(f"   [OK] Laser ID: {self.laser.get_identity()}")
            
            # Initialize laser to safe state
            self.laser.set_current(0)
            self.laser.set_output(False)
            print("   [OK] Laser initialized: 0 mA, output disabled")
            
            return True
            
        except Exception as e:
            print(f"   [ERROR] Instrument initialization failed: {e}")
            return False
    
    def take_power_measurement(self, current_ma: float) -> Optional[float]:
        """
        Take stabilized power measurement at given laser current.
        
        Args:
            current_ma: Laser current in milliamps
            
        Returns:
            Average optical power in watts, or None if measurement failed
        """
        try:
            print(f"\n   Setting laser current to {current_ma} mA...")
            
            # Set laser current
            self.laser.ramp_current(current_ma, step_ma=20, delay_s=0.1)
            
            # Enable laser output
            self.laser.set_output(True)
            
            # Wait for stabilization
            print(f"   Waiting {self.stabilization_time}s for stabilization...")
            time.sleep(self.stabilization_time)
            
            # Take multiple readings for averaging
            power_readings = []
            print(f"   Taking {self.readings_per_point} power readings...")
            
            for i in range(self.readings_per_point):
                self.power_meter.updatePowerReading(0.2)
                power = self.power_meter.meterPowerReading
                power_readings.append(power)
                print(f"     Reading {i+1}: {power:.6f} W")
                time.sleep(0.3)
            
            # Calculate average power
            avg_power = sum(power_readings) / len(power_readings)
            std_dev = (sum((p - avg_power)**2 for p in power_readings) / len(power_readings))**0.5
            
            print(f"   Average Power: {avg_power:.6f} W (±{std_dev:.6f} W)")
            
            # Safety check
            if avg_power > self.max_power_w:
                print(f"   [WARNING] Power {avg_power:.3f}W exceeds safety limit {self.max_power_w}W")
                self.emergency_stop()
                return None
            
            return avg_power
            
        except Exception as e:
            print(f"   [ERROR] Power measurement failed: {e}")
            self.emergency_stop()
            return None
    
    def run_measurement_sweep(self) -> bool:
        """Run the complete laser current vs power measurement sweep."""
        
        print(f"\n3. Starting Measurement Sweep...")
        print(f"   Current range: {self.current_points[0]} - {self.current_points[-1]} mA")
        print(f"   Number of points: {len(self.current_points)}")
        print(f"   Readings per point: {self.readings_per_point}")
        
        # Initialize data storage
        self.measurement_data = []
        start_time = datetime.datetime.now()
        
        try:
            for i, current_ma in enumerate(self.current_points):
                print(f"\n--- Measurement {i+1}/{len(self.current_points)} ---")
                print(f"Target Current: {current_ma} mA")
                
                # Safety check
                if current_ma > self.max_current_ma:
                    print(f"   [ERROR] Current {current_ma}mA exceeds safety limit {self.max_current_ma}mA")
                    break
                
                # Take measurement
                optical_power = self.take_power_measurement(current_ma)
                
                if optical_power is None:
                    print(f"   [ERROR] Measurement failed at {current_ma} mA")
                    break
                
                # Verify actual laser current
                actual_current = self.laser.get_actual_current()
                
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
                
                # Brief pause between measurements
                time.sleep(0.5)
            
            # Disable laser output after sweep
            print(f"\n   Disabling laser output...")
            self.laser.set_output(False)
            self.laser.ramp_current(0, step_ma=50, delay_s=0.1)
            
            end_time = datetime.datetime.now()
            duration = end_time - start_time
            
            print(f"\n4. Measurement Sweep Complete!")
            print(f"   Duration: {duration}")
            print(f"   Points collected: {len(self.measurement_data)}")
            
            return True
            
        except KeyboardInterrupt:
            print(f"\n   [WARNING] Measurement interrupted by user")
            self.emergency_stop()
            return False
            
        except Exception as e:
            print(f"\n   [ERROR] Measurement sweep failed: {e}")
            self.emergency_stop()
            return False
    
    def save_results(self) -> str:
        """Save measurement results to CSV file."""
        
        if not self.measurement_data:
            print("   [WARNING] No data to save")
            return ""
        
        # Generate filename with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"laser_power_sweep_{timestamp}.csv"
        filepath = os.path.join(os.path.dirname(__file__), filename)
        
        try:
            with open(filepath, 'w', newline='') as csvfile:
                fieldnames = ['point', 'target_current_ma', 'actual_current_ma', 
                            'optical_power_w', 'optical_power_mw', 'timestamp']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                # Write header
                writer.writeheader()
                
                # Write data
                for measurement in self.measurement_data:
                    writer.writerow(measurement)
            
            print(f"\n5. Results Saved: {filename}")
            print(f"   File path: {filepath}")
            print(f"   Data points: {len(self.measurement_data)}")
            
            # Print summary statistics
            powers_mw = [m['optical_power_mw'] for m in self.measurement_data]
            currents_ma = [m['actual_current_ma'] for m in self.measurement_data]
            
            print(f"\n   Summary Statistics:")
            print(f"   - Current range: {min(currents_ma):.1f} - {max(currents_ma):.1f} mA")
            print(f"   - Power range: {min(powers_mw):.3f} - {max(powers_mw):.3f} mW")
            print(f"   - Max efficiency point: {currents_ma[powers_mw.index(max(powers_mw))]:.1f} mA -> {max(powers_mw):.3f} mW")
            
            return filepath
            
        except Exception as e:
            print(f"   [ERROR] Failed to save results: {e}")
            return ""
    
    def emergency_stop(self):
        """Emergency stop - immediately disable laser."""
        print(f"\n   [EMERGENCY STOP] Disabling laser output")
        if self.laser:
            try:
                self.laser.emergency_stop()
            except:
                pass
    
    def cleanup(self):
        """Clean shutdown of all instruments."""
        print(f"\n6. Cleanup...")
        
        if self.laser:
            try:
                self.laser.set_output(False)
                self.laser.set_current(0)
                self.laser.disconnect()
                print("   [OK] Laser safely disconnected")
            except Exception as e:
                print(f"   [WARNING] Laser cleanup error: {e}")
        
        if self.power_meter:
            try:
                self.power_meter.disconnect()
                print("   [OK] Power meter disconnected")
            except Exception as e:
                print(f"   [WARNING] Power meter cleanup error: {e}")


def main():
    """Main measurement function."""
    
    measurement_system = LaserPowerSweepMeasurement()
    
    try:
        # Initialize instruments
        if not measurement_system.initialize_instruments():
            print("\n[FAILED] Instrument initialization failed")
            return
        
        # Run measurement sweep
        if not measurement_system.run_measurement_sweep():
            print("\n[FAILED] Measurement sweep failed")
            return
        
        # Save results
        result_file = measurement_system.save_results()
        
        if result_file:
            print(f"\n[SUCCESS] Measurement completed successfully!")
            print(f"Results saved to: {result_file}")
        else:
            print(f"\n[WARNING] Measurement completed but save failed")
    
    except KeyboardInterrupt:
        print(f"\n[INTERRUPTED] Measurement stopped by user")
    
    except Exception as e:
        print(f"\n[ERROR] Measurement system error: {e}")
    
    finally:
        measurement_system.cleanup()
        print("\n" + "="*70)


if __name__ == "__main__":
    main()