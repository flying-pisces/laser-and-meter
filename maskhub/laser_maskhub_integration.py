"""
Laser MaskHub Integration
========================

Integration module for uploading Thorlabs laser measurement data to MaskHub.
Adapted specifically for CLD1015 pump laser and power meter measurements.
"""

import json
import logging
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass, field
import threading
import queue
import time

from .maskhub_service import MaskHubService, MaskHubConfig, MeasurementData, RunMetadata
from .maskhub_config import MaskHubConfigManager, MaskHubCredentials

# Configure logger
LOGGER = logging.getLogger(__name__)


@dataclass
class LaserMeasurement:
    """Data class for laser measurement data"""
    device_id: str  # e.g., "Laser_1_M01093719" or "Laser_2_M00859480"
    position: tuple  # (x, y) position if applicable
    current_setpoint_ma: float
    current_actual_ma: float
    voltage_v: float
    power_mw: Optional[float] = None  # From power meter
    temperature_c: Optional[float] = None
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw_data: Optional[pd.DataFrame] = None


@dataclass
class LaserRunConfig:
    """Configuration for a laser measurement run"""
    mask_id: int
    run_name: str
    lot_name: str = "DEFAULT_LOT"
    wafer_name: str = "DEFAULT_WAFER"
    operator: Optional[str] = None
    station: str = "Thorlabs_Laser_Station"
    measurement_type: str = "laser_characterization"
    project_id: Optional[int] = None


class LaserMaskHubIntegration:
    """
    Integration class for uploading laser measurement data to MaskHub
    """

    def __init__(self,
                 config_path: Optional[Path] = None,
                 enable_realtime: bool = True,
                 auto_save_data: bool = True):
        """
        Initialize laser MaskHub integration

        Args:
            config_path: Optional path to MaskHub config file
            enable_realtime: Enable real-time upload of measurements
            auto_save_data: Automatically save measurement data to files
        """
        self.config_manager = MaskHubConfigManager(config_path)
        self.enable_realtime = enable_realtime
        self.auto_save_data = auto_save_data

        # Initialize MaskHub service
        credentials = self.config_manager.get_credentials()
        if not credentials:
            LOGGER.warning("No MaskHub credentials found. Service will be disabled.")
            self.service = None
        else:
            settings = self.config_manager.get_settings()
            config = MaskHubConfig(
                api_url=credentials.api_url,
                api_v3_url=credentials.api_v3_url,
                api_token=credentials.api_token,
                **settings
            )
            self.service = MaskHubService(config)
            LOGGER.info("MaskHub service initialized successfully")

        # Runtime state
        self.current_run: Optional[LaserRunConfig] = None
        self.run_id: Optional[str] = None
        self.measurements: List[LaserMeasurement] = []
        self.upload_queue = queue.Queue()
        self.failed_uploads: List[Dict] = []
        self.upload_stats = {
            'total': 0,
            'successful': 0,
            'failed': 0,
            'pending': 0
        }

        # Background upload thread
        self.upload_thread = None
        self.stop_uploads = threading.Event()

        if self.enable_realtime and self.service:
            self._start_upload_thread()

    def _start_upload_thread(self):
        """Start background thread for uploading measurements"""
        self.upload_thread = threading.Thread(
            target=self._upload_worker,
            daemon=True,
            name="MaskHubUploader"
        )
        self.upload_thread.start()
        LOGGER.info("Background upload thread started")

    def _upload_worker(self):
        """Background worker thread for processing upload queue"""
        while not self.stop_uploads.is_set():
            try:
                # Wait for measurement with timeout
                measurement_data = self.upload_queue.get(timeout=1.0)

                if self.service:
                    try:
                        status_code, result = self.service.upload_measurement(measurement_data)

                        if status_code < 400:
                            self.upload_stats['successful'] += 1
                            LOGGER.info(f"Successfully uploaded measurement: {result}")
                        else:
                            self.upload_stats['failed'] += 1
                            self.failed_uploads.append({
                                'measurement_data': measurement_data,
                                'error': result,
                                'timestamp': datetime.now().isoformat()
                            })
                            LOGGER.error(f"Failed to upload measurement: {result}")

                    except Exception as e:
                        self.upload_stats['failed'] += 1
                        LOGGER.error(f"Exception during upload: {e}")
                        self.failed_uploads.append({
                            'measurement_data': measurement_data,
                            'error': str(e),
                            'timestamp': datetime.now().isoformat()
                        })

                self.upload_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                LOGGER.error(f"Error in upload worker: {e}")

    def start_run(self, run_config: LaserRunConfig) -> Optional[str]:
        """
        Start a new measurement run

        Args:
            run_config: Configuration for the measurement run

        Returns:
            Run ID if successful, None if failed
        """
        self.current_run = run_config
        self.measurements.clear()
        self.upload_stats = {'total': 0, 'successful': 0, 'failed': 0, 'pending': 0}

        if not self.service:
            LOGGER.warning("MaskHub service not available. Run started in local-only mode.")
            self.run_id = f"local_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            return self.run_id

        # Create run metadata
        run_metadata = RunMetadata(
            mask_id=run_config.mask_id,
            run_name=run_config.run_name,
            project_id=run_config.project_id,
            test_software_name="thorlabs_laser_control",
            test_software_version="1.0.0",
            operator=run_config.operator,
            station=run_config.station
        )

        try:
            status_code, result = self.service.create_run(run_metadata)

            if status_code < 400:
                self.run_id = result
                LOGGER.info(f"Started MaskHub run: {self.run_id}")
                return self.run_id
            else:
                LOGGER.error(f"Failed to create MaskHub run: {result}")
                # Fall back to local mode
                self.run_id = f"local_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                return self.run_id

        except Exception as e:
            LOGGER.error(f"Exception creating MaskHub run: {e}")
            self.run_id = f"local_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            return self.run_id

    def add_measurement(self, measurement: LaserMeasurement, die_position: Optional[tuple] = None):
        """
        Add a laser measurement to the current run

        Args:
            measurement: Laser measurement data
            die_position: Optional (x, y) die position for MaskHub
        """
        if not self.current_run:
            raise RuntimeError("No active run. Call start_run() first.")

        # Add timestamp if not provided
        if not measurement.timestamp:
            measurement.timestamp = datetime.now()

        # Store measurement locally
        self.measurements.append(measurement)

        # Save raw data if enabled
        if self.auto_save_data and measurement.raw_data is not None:
            self._save_measurement_data(measurement)

        # Prepare for MaskHub upload
        if self.service and self.enable_realtime:
            self._queue_measurement_upload(measurement, die_position)

    def _save_measurement_data(self, measurement: LaserMeasurement):
        """Save measurement raw data to file"""
        if measurement.raw_data is None:
            return

        # Create data directory
        data_dir = Path(f"laser_data/{self.run_id}")
        data_dir.mkdir(parents=True, exist_ok=True)

        # Save to parquet file
        timestamp_str = measurement.timestamp.strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = f"{measurement.device_id}_{timestamp_str}.parquet"
        filepath = data_dir / filename

        try:
            measurement.raw_data.to_parquet(filepath)
            LOGGER.debug(f"Saved measurement data to {filepath}")
        except Exception as e:
            LOGGER.error(f"Failed to save measurement data: {e}")

    def _queue_measurement_upload(self, measurement: LaserMeasurement, die_position: Optional[tuple]):
        """Queue measurement for upload to MaskHub"""
        if not self.current_run or not self.service:
            return

        # Use die position or default coordinates
        if die_position:
            die_x, die_y = die_position
        else:
            die_x, die_y = 0, 0

        # Create MaskHub measurement data
        test_meta = {
            'device_id': measurement.device_id,
            'current_setpoint_ma': measurement.current_setpoint_ma,
            'current_actual_ma': measurement.current_actual_ma,
            'voltage_v': measurement.voltage_v,
            'temperature_c': measurement.temperature_c,
            'timestamp': measurement.timestamp.isoformat() if measurement.timestamp else None,
            **measurement.metadata
        }

        if measurement.power_mw is not None:
            test_meta['power_mw'] = measurement.power_mw

        # Prepare raw data path
        data_path = None
        if measurement.raw_data is not None and self.auto_save_data:
            timestamp_str = measurement.timestamp.strftime("%Y%m%d_%H%M%S_%f")[:-3]
            filename = f"{measurement.device_id}_{timestamp_str}.parquet"
            data_path = Path(f"laser_data/{self.run_id}/{filename}")

        measurement_data = MeasurementData(
            mask_id=self.current_run.mask_id,
            run_name=self.current_run.run_name,
            lot_name=self.current_run.lot_name,
            wafer_name=self.current_run.wafer_name,
            die_x=die_x,
            die_y=die_y,
            device_name=measurement.device_id,
            measurement_type=self.current_run.measurement_type,
            test_station_name=self.current_run.station,
            raw_data_path=data_path or Path("/dev/null"),  # Placeholder if no data
            test_meta=test_meta,
            timestamp=measurement.timestamp.isoformat() if measurement.timestamp else None
        )

        # Queue for upload
        self.upload_queue.put(measurement_data)
        self.upload_stats['total'] += 1
        self.upload_stats['pending'] += 1

        LOGGER.debug(f"Queued measurement for upload: {measurement.device_id}")

    def batch_upload_measurements(self, show_progress: bool = True) -> Dict[str, int]:
        """
        Upload all queued measurements in batch mode

        Args:
            show_progress: Show progress bar during upload

        Returns:
            Dictionary with upload statistics
        """
        if not self.service:
            LOGGER.warning("MaskHub service not available")
            return {'successful': 0, 'failed': 0, 'total': 0}

        # Collect all measurements from queue
        batch_measurements = []
        while not self.upload_queue.empty():
            try:
                measurement_data = self.upload_queue.get_nowait()
                batch_measurements.append(measurement_data)
            except queue.Empty:
                break

        if not batch_measurements:
            LOGGER.info("No measurements to upload")
            return {'successful': 0, 'failed': 0, 'total': 0}

        LOGGER.info(f"Starting batch upload of {len(batch_measurements)} measurements")

        results = {'successful': 0, 'failed': 0, 'total': len(batch_measurements)}

        for i, measurement_data in enumerate(batch_measurements):
            if show_progress:
                print(f"Uploading {i+1}/{len(batch_measurements)}: {measurement_data.device_name}")

            try:
                status_code, result = self.service.upload_measurement(measurement_data)

                if status_code < 400:
                    results['successful'] += 1
                    LOGGER.debug(f"Successfully uploaded: {measurement_data.device_name}")
                else:
                    results['failed'] += 1
                    self.failed_uploads.append({
                        'measurement_data': measurement_data,
                        'error': result,
                        'timestamp': datetime.now().isoformat()
                    })
                    LOGGER.error(f"Failed to upload {measurement_data.device_name}: {result}")

            except Exception as e:
                results['failed'] += 1
                LOGGER.error(f"Exception uploading {measurement_data.device_name}: {e}")
                self.failed_uploads.append({
                    'measurement_data': measurement_data,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                })

        # Update stats
        self.upload_stats['successful'] += results['successful']
        self.upload_stats['failed'] += results['failed']
        self.upload_stats['pending'] = 0

        LOGGER.info(f"Batch upload complete: {results['successful']} successful, {results['failed']} failed")
        return results

    def finish_run(self, trigger_analysis: bool = True) -> Dict[str, Any]:
        """
        Finish the current measurement run

        Args:
            trigger_analysis: Whether to trigger MaskHub analysis

        Returns:
            Run summary with statistics
        """
        if not self.current_run:
            raise RuntimeError("No active run to finish")

        # Wait for any pending uploads
        if self.enable_realtime:
            self.upload_queue.join()

        summary = {
            'run_id': self.run_id,
            'run_name': self.current_run.run_name,
            'measurement_count': len(self.measurements),
            'upload_stats': self.upload_stats.copy(),
            'failed_uploads': len(self.failed_uploads),
            'duration': None,
            'analysis_triggered': False
        }

        # Trigger analysis if requested and service available
        if trigger_analysis and self.service and self.run_id:
            try:
                status_code, result = self.service.trigger_die_analysis(
                    self.current_run.mask_id,
                    self.current_run.run_name
                )
                if status_code < 400:
                    summary['analysis_triggered'] = True
                    LOGGER.info(f"Analysis triggered for run {self.run_id}")
                else:
                    LOGGER.warning(f"Failed to trigger analysis: {result}")
            except Exception as e:
                LOGGER.error(f"Exception triggering analysis: {e}")

        LOGGER.info(f"Finished run {self.run_id}: {summary}")

        # Reset state
        self.current_run = None
        self.run_id = None

        return summary

    def retry_failed_uploads(self) -> Dict[str, int]:
        """
        Retry all failed uploads

        Returns:
            Dictionary with retry statistics
        """
        if not self.service or not self.failed_uploads:
            return {'retried': 0, 'successful': 0, 'failed': 0}

        LOGGER.info(f"Retrying {len(self.failed_uploads)} failed uploads")

        results = {'retried': len(self.failed_uploads), 'successful': 0, 'failed': 0}
        remaining_failures = []

        for failure in self.failed_uploads:
            measurement_data = failure['measurement_data']

            try:
                status_code, result = self.service.upload_measurement(measurement_data)

                if status_code < 400:
                    results['successful'] += 1
                    LOGGER.info(f"Retry successful: {measurement_data.device_name}")
                else:
                    results['failed'] += 1
                    remaining_failures.append(failure)
                    LOGGER.error(f"Retry failed: {measurement_data.device_name} - {result}")

            except Exception as e:
                results['failed'] += 1
                remaining_failures.append(failure)
                LOGGER.error(f"Retry exception: {measurement_data.device_name} - {e}")

        # Update failed uploads list
        self.failed_uploads = remaining_failures

        # Update stats
        self.upload_stats['successful'] += results['successful']
        self.upload_stats['failed'] = len(self.failed_uploads)

        LOGGER.info(f"Retry complete: {results['successful']} successful, {results['failed']} still failed")
        return results

    def get_statistics(self) -> Dict[str, Any]:
        """Get current upload statistics"""
        stats = self.upload_stats.copy()
        stats['queue_size'] = self.upload_queue.qsize()
        stats['failed_uploads_count'] = len(self.failed_uploads)
        stats['service_available'] = self.service is not None
        stats['current_run'] = self.current_run.run_name if self.current_run else None
        return stats

    def save_failed_uploads(self, filepath: Optional[Path] = None):
        """Save failed uploads to JSON file for later analysis"""
        if not self.failed_uploads:
            LOGGER.info("No failed uploads to save")
            return

        filepath = filepath or Path(f"failed_uploads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")

        # Convert measurement data to serializable format
        serializable_failures = []
        for failure in self.failed_uploads:
            failure_copy = failure.copy()
            # Convert MeasurementData to dict
            measurement_data = failure['measurement_data']
            failure_copy['measurement_data'] = {
                'mask_id': measurement_data.mask_id,
                'run_name': measurement_data.run_name,
                'device_name': measurement_data.device_name,
                'test_meta': measurement_data.test_meta,
                'timestamp': measurement_data.timestamp
            }
            serializable_failures.append(failure_copy)

        with open(filepath, 'w') as f:
            json.dump(serializable_failures, f, indent=2)

        LOGGER.info(f"Saved {len(self.failed_uploads)} failed uploads to {filepath}")

    def close(self):
        """Clean up resources and stop background threads"""
        if self.upload_thread:
            LOGGER.info("Stopping upload thread...")
            self.stop_uploads.set()

            # Wait for current uploads to finish
            try:
                self.upload_queue.join()
            except:
                pass

            # Wait for thread to stop
            self.upload_thread.join(timeout=5)
            if self.upload_thread.is_alive():
                LOGGER.warning("Upload thread did not stop cleanly")

        # Save any failed uploads
        if self.failed_uploads:
            self.save_failed_uploads()

        LOGGER.info("Laser MaskHub integration closed")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


def create_laser_measurement_from_test_data(device_id: str, current_ma: float,
                                          actual_ma: float, voltage_v: float,
                                          power_mw: Optional[float] = None,
                                          temperature_c: Optional[float] = None) -> LaserMeasurement:
    """
    Helper function to create LaserMeasurement from test data

    Args:
        device_id: Laser device identifier
        current_ma: Set current in mA
        actual_ma: Measured current in mA
        voltage_v: Measured voltage in V
        power_mw: Optional power measurement in mW
        temperature_c: Optional temperature in Celsius

    Returns:
        LaserMeasurement object
    """
    return LaserMeasurement(
        device_id=device_id,
        position=(0, 0),  # Default position
        current_setpoint_ma=current_ma,
        current_actual_ma=actual_ma,
        voltage_v=voltage_v,
        power_mw=power_mw,
        temperature_c=temperature_c,
        timestamp=datetime.now(),
        metadata={
            'test_type': 'laser_characterization',
            'current_tolerance_ma': abs(actual_ma - current_ma)
        }
    )


if __name__ == "__main__":
    # Example usage
    print("Laser MaskHub Integration Example")

    # Create example configuration
    config_manager = MaskHubConfigManager()
    config_manager.create_example_config(Path("maskhub_config.example.json"))

    print("Example configuration created. Edit maskhub_config.example.json with your credentials.")