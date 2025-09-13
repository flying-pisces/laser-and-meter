# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains a Python driver for Thorlabs power meters that enables control of multiple power meters simultaneously. The driver uses the .NET CLR via pythonnet to interface with Thorlabs' native DLL libraries.

## Key Components

- **ThorlabsPowerMeter.py**: Main driver class that wraps Thorlabs' .NET DLL
- **GlobalLogger/**: Logging module providing structured logging for driver operations
- **Thorlabs_DotNet_dll/**: Directory containing required Thorlabs .NET DLL files (not included in repo)
- **Example/**: Contains ExampleSingle.py and ExampleMultiple.py demonstrating usage patterns

## Prerequisites and Setup

### Required Dependencies
- Python ≥ 3.10
- pythonnet package
- Thorlabs Optical Power Monitor software (v4.0.4100.700+ recommended)

### Setup Commands
```bash
# Test system setup and dependencies
python Python-Driver-for-Thorlabs-power-meter/test_setup.py

# Install pythonnet if missing
pip install pythonnet
```

### DLL Requirements
The driver requires `Thorlabs.TLPM_64.Interop.dll` which must be manually copied to the `Thorlabs_DotNet_dll/` directory. This file is typically found at:
- Windows: `C:\Program Files\IVI Foundation\VISA\VisaCom64\Primary Interop Assemblies`

## Development Commands

### Testing
```bash
# Run setup verification test
python Python-Driver-for-Thorlabs-power-meter/test_setup.py

# Run single device example
python Python-Driver-for-Thorlabs-power-meter/Example/ExampleSingle.py

# Run multiple device example  
python Python-Driver-for-Thorlabs-power-meter/Example/ExampleMultiple.py
```

### Virtual Environment
```bash
# Activate existing venv
cd Python-Driver-for-Thorlabs-power-meter
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows
```

## Architecture

### Core Design Pattern
The driver follows a factory pattern where `ThorlabsPowerMeter.listDevices()` returns a device list object that can then connect to individual power meters. Each connected device maintains its own state and configuration.

### Key Methods Flow
1. `listDevices()` - Discovers available power meters
2. `connect(resourceName)` - Establishes connection to specific device
3. Device configuration methods (setWaveLength, setPowerAutoRange, etc.)
4. `updatePowerReading()` - Retrieves current power measurements
5. `disconnect()` - Properly closes device connection

### Platform Considerations
- **Windows**: Native environment, full USB device access
- **WSL/Linux**: Requires Mono runtime, may have USB device limitations
- The driver checks platform at runtime and provides appropriate warnings

## Common Usage Patterns

### Single Device Control
```python
deviceList = ThorlabsPowerMeter.listDevices()
device = deviceList.connect(deviceList.resourceName[0])
device.setWaveLength(635)
device.updatePowerReading(0.1)
```

### Multiple Device Control
Multiple power meters can be controlled simultaneously by connecting to different resource names from the device list. Each device maintains independent configuration and state.

## Error Handling

The driver includes comprehensive error reporting through the GlobalLogger system. Common issues include:
- Missing DLL files (check `Thorlabs_DotNet_dll/` directory)
- USB device permissions (especially on Linux)
- .NET runtime availability (requires Mono on non-Windows systems)