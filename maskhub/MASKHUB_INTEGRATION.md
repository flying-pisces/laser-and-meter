# MaskHub Integration for EDWA

This document describes the MaskHub upload service that has been integrated into the EDWA repository. The service provides a modular, robust way to upload measurement data to MaskHub.

## Overview

The MaskHub integration consists of four main components:

1. **`maskhub_service.py`** - Core service module for MaskHub API interactions
2. **`maskhub_config.py`** - Configuration management for credentials and settings
3. **`maskhub_example.py`** - Example usage and demonstration code
4. **`edwa_maskhub_integration.py`** - Full integration with EDWA measurement system

## Features

- ✅ Modular design - Easy to integrate with existing EDWA code
- ✅ Persistent HTTP sessions for better performance
- ✅ Automatic retry logic with exponential backoff
- ✅ Real-time and batch upload modes
- ✅ Progress tracking for batch uploads
- ✅ Failed upload recovery
- ✅ Multiple configuration options (environment variables, config files)
- ✅ Thread-safe queue-based uploads
- ✅ Comprehensive error handling and logging

## Installation

The MaskHub service uses the following dependencies (already in psiqtest):
- `requests` - HTTP client
- `tenacity` - Retry logic
- `pandas` - Data handling (optional)
- `orjson` or `json` - JSON serialization

Install required packages:
```bash
pip install requests tenacity pandas
```

## Configuration

### Method 1: Environment Variables

Set the following environment variables:
```bash
export MASKHUB_API="https://maskhub.psiquantum.com/api"
export MASKHUB_API_V3="https://maskhub.psiquantum.com/api/v3"
export MASKHUB_API_TOKEN="your-api-token-here"
```

### Method 2: Configuration File

Create a `maskhub_config.json` file in one of these locations:
- `~/.edwa/maskhub_config.json` (user home directory)
- `config/maskhub_config.json` (project config directory)
- `maskhub_config.json` (current directory)

Example configuration file:
```json
{
  "credentials": {
    "api_url": "https://maskhub.psiquantum.com/api",
    "api_v3_url": "https://maskhub.psiquantum.com/api/v3",
    "api_token": "your-api-token-here"
  },
  "settings": {
    "timeout": 30,
    "max_retries": 5,
    "retry_multiplier": 2,
    "retry_min_wait": 15
  }
}
```

### Method 3: Programmatic Configuration

```python
from maskhub_config import MaskHubCredentials
from maskhub_service import MaskHubService, MaskHubConfig

# Create credentials
credentials = MaskHubCredentials(
    api_url="https://maskhub.psiquantum.com/api",
    api_v3_url="https://maskhub.psiquantum.com/api/v3",
    api_token="your-api-token"
)

# Create config
config = MaskHubConfig(
    api_url=credentials.api_url,
    api_v3_url=credentials.api_v3_url,
    api_token=credentials.api_token,
    timeout=30,
    max_retries=5
)

# Initialize service
service = MaskHubService(config)
```

## Usage Examples

### Basic Upload

```python
from pathlib import Path
from maskhub_service import MaskHubService, MaskHubConfig, MeasurementData

# Initialize service (assumes config is set up)
config = MaskHubConfig(
    api_url="...",
    api_v3_url="...",
    api_token="..."
)
service = MaskHubService(config)

# Create measurement data
measurement = MeasurementData(
    mask_id=12345,
    run_name="Test_Run_001",
    lot_name="LOT001",
    wafer_name="WAFER001",
    die_x=10,
    die_y=20,
    device_name="Device001",
    measurement_type="optical_measurement",
    test_station_name="EDWA_Station_1",
    raw_data_path=Path("data/measurement.parquet"),
    test_meta={"power": 10.5, "wavelength": 1550}
)

# Upload measurement
status_code, result = service.upload_measurement(measurement)
if status_code == 200:
    print(f"Success! Measurement ID: {result}")
else:
    print(f"Failed: {result}")
```

### Integrated EDWA Workflow

```python
from edwa_maskhub_integration import EDWAMaskHubIntegration, EDWAMeasurement
from datetime import datetime
import pandas as pd

# Initialize integration
integration = EDWAMaskHubIntegration(enable_realtime=True)

# Start a run
run_id = integration.start_run(
    mask_id=12345,
    run_name="EDWA_Run_001",
    wafer_id="WAFER_001",
    lot_id="LOT_001",
    operator="Operator Name",
    station="EDWA_Station_1"
)

# Create and add measurements
measurement = EDWAMeasurement(
    device_id="Device_001",
    position=(10, 20),
    optical_power=10.5,
    wavelength=1550.0,
    insertion_loss=3.2,
    timestamp=datetime.now(),
    metadata={"temperature": 25.0},
    raw_data=pd.DataFrame({"time": [1, 2, 3], "power": [10, 11, 12]})
)

integration.add_measurement(measurement)

# Finish run and trigger analysis
summary = integration.finish_run(trigger_analysis=True)
print(f"Run complete: {summary}")

# Clean up
integration.close()
```

### Batch Upload with Progress

```python
from maskhub_example import EDWAMaskHubUploader

uploader = EDWAMaskHubUploader()

# Prepare batch measurements
measurements = [
    {
        "mask_id": 12345,
        "run_name": "Batch_Run",
        "lot_name": f"LOT00{i}",
        "wafer_name": f"WAFER00{i}",
        "die_x": i * 10,
        "die_y": i * 20,
        "device_name": f"Device00{i}",
        "measurement_type": "optical",
        "test_station_name": "EDWA_1",
        "raw_data_path": f"data/meas_{i}.parquet",
        "test_meta": {"index": i}
    }
    for i in range(1, 11)
]

# Upload with progress tracking
results = uploader.upload_batch_measurements(measurements, show_progress=True)
print(f"Uploaded: {results['success']}, Failed: {results['failed']}")
```

## API Reference

### Core Classes

#### `MaskHubService`
Main service class for MaskHub API interactions.

**Key Methods:**
- `upload_measurement()` - Upload single measurement
- `upload_batch()` - Upload multiple measurements
- `create_run()` - Create a new run
- `trigger_die_analysis()` - Trigger analysis
- `post_attachment()` - Attach files to run

#### `EDWAMaskHubIntegration`
Integration class for EDWA system.

**Key Methods:**
- `start_run()` - Start a measurement run
- `add_measurement()` - Add measurement to upload queue
- `finish_run()` - Complete run and trigger analysis
- `retry_failed_uploads()` - Retry failed uploads
- `get_statistics()` - Get upload statistics

### Data Classes

#### `MeasurementData`
```python
@dataclass
class MeasurementData:
    mask_id: int
    run_name: str
    lot_name: str
    wafer_name: str
    die_x: int
    die_y: int
    device_name: str
    measurement_type: str
    test_station_name: str
    raw_data_path: Path
    test_meta: Dict[str, Any]
    nas_path: Optional[Path] = None
    # ... additional optional fields
```

#### `RunMetadata`
```python
@dataclass
class RunMetadata:
    mask_id: int
    run_name: str
    project_id: Optional[int] = None
    config: Optional[Dict] = None
    calibration: Optional[Dict] = None
    # ... additional fields
```

## Error Handling

The service includes comprehensive error handling:

1. **Automatic Retries** - Failed uploads are automatically retried with exponential backoff
2. **Failed Upload Recovery** - Failed uploads are stored and can be retried later
3. **Connection Pooling** - Persistent HTTP sessions reduce connection errors
4. **Detailed Logging** - All operations are logged for debugging

## Performance Considerations

1. **Real-time Mode** - Uploads happen in background thread, doesn't block measurements
2. **Batch Mode** - Collect measurements and upload in parallel for efficiency
3. **Connection Reuse** - HTTP session pooling for better performance
4. **Queue-based** - Thread-safe queue prevents data loss

## Testing

Run the example code to test the integration:

```bash
# Create example configuration
python src/maskhub_example.py

# Test integration workflow
python src/edwa_maskhub_integration.py
```

## Troubleshooting

### Common Issues

1. **No credentials found**
   - Check environment variables are set
   - Verify config file exists and is valid JSON
   - Check file permissions

2. **Upload failures**
   - Check network connectivity
   - Verify API token is valid
   - Check MaskHub service status
   - Review logs for specific error messages

3. **Performance issues**
   - Use batch mode for large datasets
   - Adjust thread pool size in integration
   - Check network bandwidth

### Debug Logging

Enable debug logging to see detailed information:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Migration from psiqtest

If migrating from psiqtest's upload functionality:

1. The API is similar but more modular
2. Replace direct `upload_measurement_v3` calls with `MaskHubService.upload_measurement()`
3. Use `MeasurementData` dataclass instead of dictionaries
4. Configuration is now separate from the service

## Support

For issues or questions about the MaskHub integration:
1. Check the logs for error messages
2. Verify configuration is correct
3. Test with example code first
4. Contact the MaskHub team for API issues

## License

This integration module follows the same license as the EDWA project.