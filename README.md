# Thorlabs Laser Current vs Optical Power Measurement System

A complete automation system for measuring optical power versus pump laser current, featuring both command-line tools and professional GUI interface for Thorlabs instruments.

## 🎯 Overview

This system provides automated measurement of optical power vs pump laser current with:
- **28 measurement points** from 130-1480 mA (fully configurable)
- **Professional GUI interface** with real-time progress tracking
- **Command-line automation** for scripted operation
- **Safety features** with emergency stop capabilities
- **Data export** to CSV for analysis and plotting

## 📁 Project Structure

```
thorlabs/
├── laser_power_gui.py              # Main GUI application (production)
├── laser_power_gui_demo.py         # Demo GUI (no hardware required)
├── laser_power_sweep.py            # Automated command-line measurement
├── laser_power_sweep_test.py       # Command-line test version
├── integrated_test.py              # System integration verification
├── test_power_meter.py             # Power meter standalone test
├── pumplaser/                      # Pump laser control module
│   ├── pump_laser.py               # PumpLaser driver class
│   ├── examples/                   # Usage examples and tests
│   └── requirements.txt            # PyVISA dependencies
├── Python-Driver-for-Thorlabs-power-meter/  # Power meter module
│   ├── ThorlabsPowerMeter.py       # Power meter driver
│   ├── test_setup.py               # Setup verification
│   └── GlobalLogger/               # Logging system
└── README*.md                      # Documentation files
```

## 🖥️ GUI Interface (Recommended)

### Quick Start
```bash
# Demo version (no hardware required) - Try this first!
python laser_power_gui_demo.py

# Production version (requires connected instruments)
python laser_power_gui.py
```

### GUI Features

#### **🔍 Device Status Block**
At the top of the GUI, you'll see a comprehensive status display:

```
┌─────────────────── Device Status ──────────────────────┐
│  Power Meter                    Pump Laser            │
│  Address: USB0::0x1313::0x8072  Address: USB0::0x1313 │
│  Status:  Connected             Status:  Connected     │
│  Device:  S132C (191219201)     Device:  CLD1015 (...) │
│ ──────────────────────────────────────────────────────│
│  System Mode: PRODUCTION MODE - Real Instruments       │
└────────────────────────────────────────────────────────┘
```

**Status Indicators:**
- **PRODUCTION MODE**: Real instruments connected and working
- **DEMO MODE**: All data simulated (demo version)
- **PARTIAL CONNECTION**: Only some instruments connected
- **NO INSTRUMENTS**: Check connections

**Color Coding:**
- 🟢 **Green**: Connected and communicating
- 🔴 **Red**: Disconnected or not found
- 🟠 **Orange**: Connection error or communication issue
- 🟣 **Purple**: Demo/simulated mode

#### **📊 Automated Sweep Tab**
Matches your measurement table format exactly:

| # | I Pump Laser (mA) | O. Power (mW) | Timestamp |
|---|--------------------|---------------|-----------|
| 1 | 130                | 15.234        | 14:23:45  |
| 2 | 180                | 28.567        | 14:24:12  |
| ... | ...              | ...           | ...       |
| 28 | 1480              | 245.783       | 14:28:30  |

**Features:**
- **28 current points**: 130, 180, 230... up to 1480 mA
- **Real-time updates**: Table fills as measurements progress
- **Progress tracking**: Visual progress bar and status
- **Configurable settings**: Readings per point, stabilization time
- **Start/Stop control**: Safe measurement with emergency stop

#### **🎛️ Manual Control Tab**
Individual current control and single measurements:
- **Set any current value** (not just sweep points)
- **Take single power measurements** with averaging
- **Real-time current and power display**
- **Measurement history table**
- **Laser output enable/disable**

#### **🔧 Instrument Status Tab**
- **Connection management** for both instruments
- **Real-time logging** and status updates
- **Emergency stop** functionality
- **Instrument details** and configuration

## ⚡ Command Line Interface

### Automated Measurement
```bash
# Full measurement sweep (requires connected instruments)
python laser_power_sweep.py

# Test version with simulated laser
python laser_power_sweep_test.py
```

### Individual Tests
```bash
# Test power meter connection and functionality
python test_power_meter.py

# Test system integration
python integrated_test.py

# Check laser communication
python pumplaser/examples/laser_test.py

# Verify power meter setup
python Python-Driver-for-Thorlabs-power-meter/test_setup.py
```

## 🔧 Hardware Requirements

### Instruments
- **Pump Laser**: Thorlabs ITC4001 or CLD1015 (USB connection)
  - Target address: `USB0::0x1313::0x804F::M01093719::0::INSTR`
  - Alternative addresses supported automatically
- **Power Meter**: Thorlabs power meter with sensor
  - Tested with: S132C photodiode sensor
  - Address example: `USB0::0x1313::0x8072::1905573::INSTR`

### Software Dependencies
```bash
# Power meter dependencies
cd Python-Driver-for-Thorlabs-power-meter
pip install pythonnet

# Laser control dependencies
cd pumplaser
pip install pyvisa pyvisa-py

# GUI requirements (usually pre-installed)
# tkinter - included with Python
```

## 📊 Measurement Specifications

### Current Points (Default)
```python
current_points = [
    130, 180, 230, 280, 330, 380, 430, 480, 530, 580,
    630, 680, 730, 780, 830, 880, 930, 980, 1030, 1080,
    1130, 1180, 1230, 1280, 1330, 1380, 1430, 1480
]  # 28 points total
```

### Measurement Parameters
- **Current Range**: 130-1480 mA (configurable)
- **Step Resolution**: 50 mA default (fully customizable)
- **Readings per Point**: 5 measurements averaged (1-10 selectable)
- **Stabilization Time**: 2 seconds default (0.5-10s selectable)
- **Power Meter Config**: 1550nm wavelength, auto-range, 100ms averaging

### Safety Features
- **Current Limits**: 1500 mA maximum (software enforced)
- **Power Limits**: 1W maximum expected (configurable)
- **Emergency Stop**: Immediate laser shutdown
- **Graceful Ramping**: Step-wise current changes
- **Auto Shutdown**: Safe state on errors or exit

## 📈 Data Output

### CSV Export Format
```csv
point,target_current_ma,actual_current_ma,optical_power_w,optical_power_mw,timestamp
1,130,130.2,0.015234,15.234,2025-09-13T14:23:45
2,180,179.8,0.028567,28.567,2025-09-13T14:24:12
...
```

### Files Generated
- **Automated Sweep**: `laser_power_sweep_YYYYMMDD_HHMMSS.csv`
- **Manual Measurements**: `manual_data_YYYYMMDD_HHMMSS.csv`
- **Demo Data**: `demo_sweep_data_YYYYMMDD_HHMMSS.csv`

## 🚀 Getting Started

### 1. First Time Setup
```bash
# Clone or download the repository
git clone https://github.com/flying-pisces/laser-and-meter.git
cd laser-and-meter

# Install dependencies
cd Python-Driver-for-Thorlabs-power-meter
pip install pythonnet

cd ../pumplaser
pip install -r requirements.txt
```

### 2. Try the Demo
```bash
# Test the GUI interface without hardware
python laser_power_gui_demo.py
```
This shows you exactly how the system works with simulated data.

### 3. Connect Your Instruments
- Connect pump laser via USB
- Connect power meter with sensor via USB
- Run instrument tests to verify connections

### 4. Production Use
```bash
# GUI interface (recommended)
python laser_power_gui.py

# Command-line interface
python laser_power_sweep.py
```

## 📋 Typical Workflow

### GUI Workflow (Recommended):
1. **Start GUI**: `python laser_power_gui.py`
2. **Check Status Block**: Verify both instruments show "Connected"
3. **Configure Settings**: Set readings per point, stabilization time
4. **Start Measurement**: Click "Start Sweep Measurement"
5. **Monitor Progress**: Watch real-time table updates and progress bar
6. **Export Data**: Click "Export Data" when complete

### Manual Control Workflow:
1. **Switch to Manual Tab**
2. **Set specific current** (e.g., 500 mA)
3. **Enable laser output**
4. **Take measurements** at that current
5. **Explore interesting regions** between sweep points

## 🛡️ Safety Guidelines

### Before Each Use:
- ✅ Verify instrument connections in status block
- ✅ Check current and power limits are appropriate
- ✅ Ensure proper optical safety measures
- ✅ Test emergency stop functionality

### During Operation:
- 🔍 Monitor real-time measurements for anomalies
- ⏸️ Use emergency stop if needed (red button in GUI)
- 📊 Watch for unexpected power readings
- 🌡️ Monitor laser temperature if available

### After Use:
- 💾 Export data before closing
- 🔌 System automatically disables laser on exit
- 📁 Backup important measurement files

## 🔍 Troubleshooting

### Status Block Shows "Disconnected":
1. Check USB connections
2. Verify instrument power
3. Run individual instrument tests:
   ```bash
   python test_status_display.py
   python pumplaser/examples/laser_test.py
   ```

### "Communication Error" Status:
- Instrument found but not responding
- Try reconnecting USB cables
- Restart instruments
- Check for driver conflicts

### "PARTIAL CONNECTION" Mode:
- Only one instrument connected
- Verify both USB connections
- Check instrument-specific requirements

### GUI Performance Issues:
- Large number of measurement points may slow updates
- Reduce readings per point for faster operation
- Use command-line version for maximum speed

## 📚 Documentation Files

- **README.md**: This comprehensive guide
- **README_MEASUREMENT.md**: Detailed command-line measurement guide  
- **README_GUI.md**: Complete GUI user manual
- **CLAUDE.md**: Developer guide for Claude Code integration

## 🤝 Contributing

This project uses Claude Code for development. The system is designed to be:
- **Modular**: Each component can be used independently
- **Extensible**: Easy to add new measurement patterns
- **Safe**: Multiple layers of safety protection
- **User-friendly**: Both GUI and command-line interfaces

## 📊 Example Results

### Typical Current vs Power Data:
- **Threshold Current**: ~100-200 mA (where lasing begins)
- **Linear Region**: 300-1200 mA (steady power increase)
- **Saturation**: >1200 mA (power levels off)
- **Maximum Output**: Depends on laser and current limits

### Data Analysis:
The CSV output can be directly imported into:
- **Excel/Google Sheets**: For quick plotting and analysis
- **Python (pandas/matplotlib)**: For advanced data processing
- **MATLAB**: For curve fitting and modeling
- **Origin/Igor Pro**: For scientific plotting

## ⚡ Performance

### Measurement Speed:
- **Full 28-point sweep**: ~5-10 minutes (depending on settings)
- **Single measurement**: ~2-5 seconds
- **Demo mode**: ~1-2 minutes (accelerated timing)

### Accuracy:
- **Current Setting**: ±1 mA typical
- **Power Measurement**: Limited by power meter specifications
- **Timing**: Microsecond precision timestamps
- **Repeatability**: Excellent with proper stabilization time

---

## 🎉 Ready to Measure!

This system provides everything needed for professional laser characterization:
- **Production-ready GUI** with real-time feedback
- **Command-line automation** for scripted measurements  
- **Comprehensive safety features** and error handling
- **Professional data output** ready for analysis

Start with the demo version to familiarize yourself with the interface, then connect your instruments for real measurements!

```bash
# Try the demo now!
python laser_power_gui_demo.py
```