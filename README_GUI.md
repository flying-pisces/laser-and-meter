# Thorlabs Laser Power Measurement GUI

A comprehensive GUI application for automated laser current vs optical power measurements, featuring both automated sweep measurements and manual control capabilities.

## 🖥️ GUI Overview

The GUI provides three main tabs:

1. **Automated Sweep** - Matches your measurement table format (130-1480 mA)
2. **Manual Control** - Individual current setting and single measurements  
3. **Instrument Status** - Connection management and system information

## 📊 Automated Sweep Tab

### Layout matches your table exactly:
- **Column 1**: Point number (#)
- **Column 2**: I Pump Laser (mA) - Current values
- **Column 3**: O. Power (mW) - Measured optical power
- **Column 4**: Timestamp

### Features:
- **28 measurement points**: 130, 180, 230... up to 1480 mA
- **Configurable settings**: Readings per point (1-10), Stabilization time (0.5-10s)
- **Real-time progress**: Progress bar and status updates
- **Start/Stop control**: Safe measurement control with emergency stop
- **Data export**: Direct CSV export for analysis

### Measurement Process:
1. Click "Start Sweep Measurement"
2. GUI automatically steps through all 28 current values
3. At each point: Sets current → Waits for stabilization → Takes multiple readings → Averages results
4. Real-time table updates show measured values
5. Progress bar indicates completion status
6. Export data when complete

## 🎛️ Manual Control Tab

### Laser Current Control:
- **Target Current Entry**: Set any current value (mA)
- **Set Current Button**: Apply the current setting
- **Laser Output Checkbox**: Enable/disable laser output
- **Actual Current Display**: Shows real measured current

### Single Power Measurement:
- **Averaging Control**: 1-10 readings per measurement
- **Take Measurement Button**: Perform single power reading
- **Power Display**: Large, prominent power reading (mW)
- **Measurement History**: Table of all manual measurements with timestamps

### Use Cases:
- **Testing specific currents** not in the sweep
- **Quick power checks** at any current
- **Manual characterization** of interesting regions
- **Troubleshooting** and verification

## 🔧 Instrument Status Tab

### Connection Management:
- **Power Meter Status**: Connection indicator and device info
- **Laser Status**: Connection indicator and device identity
- **Connect/Disconnect**: Manual connection control
- **Emergency Stop**: Immediate safety shutdown

### Instrument Information:
- **Device Details**: Model, serial number, capabilities
- **Connection Log**: Real-time status updates
- **Configuration**: Current settings and parameters

## 🚀 Getting Started

### Option 1: Demo Mode (No Hardware Required)
```bash
python laser_power_gui_demo.py
```
- **Simulated instruments** for interface testing
- **All features functional** with fake data
- **Perfect for training** and familiarization

### Option 2: Full Version (Hardware Required)
```bash
python laser_power_gui.py
```
- **Real instrument control** with safety features
- **Actual measurements** from connected hardware
- **Production ready** for data collection

## 📋 Hardware Requirements

- **Pump Laser**: Thorlabs ITC4001 or compatible (USB connection)
- **Power Meter**: Thorlabs power meter with S132C sensor or compatible
- **Computer**: Windows PC with Python 3.10+

## 📈 Typical Workflow

### Automated Measurement:
1. **Connect instruments** (Status tab)
2. **Configure settings** (Sweep tab)
3. **Start measurement** → GUI runs automatically
4. **Monitor progress** in real-time
5. **Export data** for analysis

### Manual Exploration:
1. **Set specific current** (Manual tab)
2. **Enable laser output**
3. **Take measurement** 
4. **Record interesting points**
5. **Export manual data**

## 📊 Data Output

Both measurement modes export CSV files:

### Automated Sweep Data:
```csv
point,target_current_ma,actual_current_ma,optical_power_mw,timestamp
1,130,130.2,15.234,14:23:45
2,180,179.8,28.567,14:24:12
...
```

### Manual Measurement Data:
```csv
Current (mA),Power (mW),Time
245.3,42.156,14:35:22
315.7,58.923,14:36:01
...
```

## 🛡️ Safety Features

- **Emergency Stop**: Immediate laser shutdown from any tab
- **Current Limits**: Software-enforced maximum current protection  
- **Graceful Shutdown**: Automatic laser disable on error/exit
- **Real-time Monitoring**: Continuous safety parameter checking
- **User Confirmation**: Important actions require confirmation

## 🎨 GUI Design Highlights

- **Table Layout**: Exactly matches your measurement table format
- **Color Coding**: Green=connected, Red=disconnected, Blue=current values
- **Real-time Updates**: Live data display during measurements
- **Progress Indicators**: Visual feedback for long operations
- **Tabbed Interface**: Organized workflow separation
- **Professional Appearance**: Clean, scientific interface design

## 💡 Tips for Use

1. **Start with Demo**: Familiarize yourself with the interface using demo mode
2. **Test Connections**: Always verify instrument status before measurements
3. **Save Frequently**: Export data after each measurement session
4. **Monitor Progress**: Watch for any anomalies during sweep measurements
5. **Use Manual Mode**: For exploring regions between sweep points
6. **Emergency Stop**: Don't hesitate to use emergency stop if needed

## 🔄 Comparison with Command Line

| Feature | Command Line | GUI |
|---------|-------------|-----|
| **Ease of Use** | Requires script knowledge | Point-and-click operation |
| **Real-time Feedback** | Text updates | Visual progress bars |
| **Data Visualization** | External tools needed | Built-in table display |
| **Manual Control** | Script modification required | Dedicated interface |
| **Safety** | Command-based | Visual indicators & buttons |
| **Learning Curve** | Programming knowledge | Intuitive operation |

The GUI provides the same powerful measurement capabilities as the command-line scripts but with an intuitive, user-friendly interface that matches your measurement table format exactly.

## 🏃 Quick Demo

Try the demo version to see the interface in action - it simulates realistic measurement data and demonstrates all features without requiring connected hardware!