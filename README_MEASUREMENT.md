# Automated Laser Current vs Optical Power Measurement System

This system provides automated measurement of optical power vs pump laser current, implementing the measurement table you provided (130-1480 mA current range).

## 🎯 Overview

The system automatically:
1. Steps through predefined laser current values (130, 180, 230... up to 1480 mA)
2. Records corresponding optical power measurements from Thorlabs power meter
3. Exports results to timestamped CSV files
4. Includes safety monitoring and emergency stop capabilities

## 📁 Files

- **`laser_power_sweep.py`** - Main automated measurement script (requires connected laser)
- **`laser_power_sweep_test.py`** - Test version with simulated laser (validates framework)
- **`integrated_test.py`** - System integration verification
- **`test_power_meter.py`** - Power meter standalone test

## 🚀 Quick Start

### 1. Test Framework (No Laser Required)
```bash
python laser_power_sweep_test.py
```
This validates the measurement system using the real power meter but simulated laser.

### 2. Full Measurement (Laser Required)
```bash
python laser_power_sweep.py
```
This runs the complete automated measurement with real laser control.

## 📊 Measurement Parameters

- **Current Range**: 130 - 1480 mA (28 points)
- **Current Steps**: [130, 180, 230, 280, 330, 380, 430, 480, 530, 580, 630, 680, 730, 780, 830, 880, 930, 980, 1030, 1080, 1130, 1180, 1230, 1280, 1330, 1380, 1430, 1480] mA
- **Readings per Point**: 5 measurements averaged
- **Stabilization Time**: 2 seconds per current setting
- **Power Meter Config**: 1550nm wavelength, auto-range, 100ms averaging

## 🛡️ Safety Features

- **Current Limits**: Maximum 1500 mA safety limit
- **Power Monitoring**: Automatic shutdown if power exceeds 1W
- **Emergency Stop**: Immediate laser shutdown on error/interrupt
- **Graceful Ramp**: Current ramped up/down in steps to avoid transients
- **Connection Validation**: Verifies instruments before starting

## 📈 Output Data

Results are saved to timestamped CSV files with columns:
- `point`: Measurement number (1-28)
- `target_current_ma`: Intended laser current (mA)  
- `actual_current_ma`: Measured laser current (mA)
- `optical_power_w`: Optical power in watts
- `optical_power_mw`: Optical power in milliwatts
- `timestamp`: ISO format timestamp

Example filename: `laser_power_sweep_20250913_145302.csv`

## 🔧 System Requirements

### Hardware
- Thorlabs pump laser (USB0::0x1313::0x804F::M01093719::0::INSTR or similar)
- Thorlabs power meter (S132C sensor or compatible)
- USB connections for both instruments

### Software
- Python 3.10+
- pythonnet (for power meter)
- pyvisa (for laser communication)

### Installation
```bash
# Power meter dependencies
cd Python-Driver-for-Thorlabs-power-meter
pip install pythonnet

# Laser dependencies  
cd pumplaser
pip install -r requirements.txt
```

## 🎛️ Usage Instructions

### Pre-flight Checklist
1. Connect pump laser via USB
2. Connect power meter with sensor via USB
3. Verify instruments are detected:
   ```bash
   python pumplaser/examples/laser_test.py
   python Python-Driver-for-Thorlabs-power-meter/test_setup.py
   ```

### Running Measurements
1. **Test first** (recommended):
   ```bash
   python laser_power_sweep_test.py
   ```
   
2. **Full measurement**:
   ```bash
   python laser_power_sweep.py
   ```

3. **Monitor progress**: The script provides real-time updates of current settings and power readings

4. **Results**: CSV file will be automatically saved with timestamp

### Emergency Stop
- Press `Ctrl+C` to immediately stop measurement
- Laser will be safely shut down (output disabled, current ramped to 0)

## 📋 Typical Output

```
======================================================================
Laser Current vs Optical Power Measurement System
======================================================================

1. Initializing Power Meter...
   [OK] Power meter connected: USB0::0x1313::0x8072::1905573::INSTR
   [OK] Power meter configured: S132C

2. Initializing Pump Laser...
   [OK] Laser connected successfully!
   [OK] Laser ID: Thorlabs,ITC4001,M01093719,1.0.0

3. Starting Measurement Sweep...
   Current range: 130 - 1480 mA
   Number of points: 28

--- Measurement 1/28 ---
Target Current: 130 mA
   Setting laser current to 130 mA...
   Waiting 2.0s for stabilization...
   Taking 5 power readings...
     Reading 1: 0.015234 W
     Reading 2: 0.015198 W
     [...]
   Average Power: 0.015216 W (±0.000018 W)
   [OK] Point 1: 130.2mA -> 15.216mW

[... continues for all 28 points ...]

5. Results Saved: laser_power_sweep_20250913_145302.csv
   Summary Statistics:
   - Current range: 130.1 - 1479.8 mA
   - Power range: 15.216 - 245.783 mW
   - Max efficiency point: 1430.1 mA -> 245.783 mW
```

## 🔍 Data Analysis

The CSV output can be directly imported into:
- Excel/Google Sheets for plotting
- Python (pandas/matplotlib) for analysis
- MATLAB for curve fitting
- Any data analysis software

Typical analysis includes:
- Current vs Power curves
- Efficiency calculations
- Threshold current determination
- Linear/nonlinear regions identification

## ⚠️ Important Notes

1. **Laser Safety**: Always follow proper laser safety protocols
2. **Current Limits**: Script enforces 1500mA max current - adjust if needed
3. **Power Limits**: 1W max power limit - increase if expecting higher powers
4. **Stabilization**: 2 second stabilization may need adjustment for your laser
5. **Measurements**: 5 readings per point provides good statistics - adjust if needed

## 🐛 Troubleshooting

**No laser found**: 
- Check USB connection
- Verify VISA driver installation
- Run `python pumplaser/examples/laser_test.py`

**No power meter found**:
- Check USB connection and power
- Verify .NET/pythonnet installation  
- Run `python Python-Driver-for-Thorlabs-power-meter/test_setup.py`

**Measurement fails mid-sweep**:
- Check laser overheating
- Verify optical alignment
- Review power/current limits

**CSV save fails**:
- Check disk space
- Verify write permissions
- Close any open CSV files