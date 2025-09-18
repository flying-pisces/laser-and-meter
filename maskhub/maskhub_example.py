"""
MaskHub Service Example Usage
==============================
This file demonstrates how to use the MaskHub service for uploading data.
"""

import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

from maskhub_service import (
    MaskHubService,
    MaskHubConfig,
    MeasurementData,
    RunMetadata,
    UploadStatus,
    calculate_file_md5
)
from maskhub_config import MaskHubConfigManager, MaskHubCredentials

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
LOGGER = logging.getLogger(__name__)


class EDWAMaskHubUploader:
    """Example class showing how to integrate MaskHub uploads with EDWA"""
    
    def __init__(self, config_path: Path = None):
        """
        Initialize the uploader
        
        Args:
            config_path: Optional path to configuration file
        """
        # Load configuration
        self.config_manager = MaskHubConfigManager(config_path)
        self.service = None
        self.current_run_id = None
        
        # Initialize service if credentials available
        if self.config_manager.get_credentials():
            self._initialize_service()
        else:
            LOGGER.warning("No MaskHub credentials configured")
    
    def _initialize_service(self):
        """Initialize MaskHub service with loaded configuration"""
        credentials = self.config_manager.get_credentials()
        settings = self.config_manager.get_settings()
        
        config = MaskHubConfig(
            api_url=credentials.api_url,
            api_v3_url=credentials.api_v3_url,
            api_token=credentials.api_token,
            **settings
        )
        
        self.service = MaskHubService(config)
        LOGGER.info("MaskHub service initialized")
    
    def configure_credentials(
        self,
        api_url: str,
        api_v3_url: str,
        api_token: str
    ):
        """
        Configure MaskHub credentials programmatically
        
        Args:
            api_url: Base MaskHub API URL
            api_v3_url: MaskHub V3 API URL
            api_token: API authentication token
        """
        credentials = MaskHubCredentials(
            api_url=api_url,
            api_v3_url=api_v3_url,
            api_token=api_token
        )
        
        self.config_manager.set_credentials(credentials)
        self._initialize_service()
        LOGGER.info("Credentials configured successfully")
    
    def create_test_run(
        self,
        mask_id: int,
        run_name: str,
        config_data: Dict = None,
        calibration_data: Dict = None,
        expected_measurements: int = 0
    ) -> int:
        """
        Create a new test run in MaskHub
        
        Args:
            mask_id: Mask ID
            run_name: Name for the run
            config_data: Optional configuration data
            calibration_data: Optional calibration data
            expected_measurements: Expected number of measurements
            
        Returns:
            Run ID if successful, None otherwise
        """
        if not self.service:
            LOGGER.error("Service not initialized")
            return None
        
        metadata = RunMetadata(
            mask_id=mask_id,
            run_name=run_name,
            config=config_data,
            calibration=calibration_data,
            expected_measurement_count=expected_measurements,
            test_software_name="edwa",
            test_software_version="1.0.0",
            uuid=str(datetime.now().timestamp())
        )
        
        run_id = self.service.create_run(metadata)
        if run_id:
            self.current_run_id = run_id
            LOGGER.info(f"Created run {run_name} with ID {run_id}")
        
        return run_id
    
    def upload_measurement(
        self,
        raw_data_path: Path,
        mask_id: int,
        run_name: str,
        lot_name: str,
        wafer_name: str,
        die_x: int,
        die_y: int,
        device_name: str,
        measurement_type: str,
        test_station_name: str,
        test_meta: Dict[str, Any] = None
    ) -> bool:
        """
        Upload a single measurement to MaskHub
        
        Args:
            raw_data_path: Path to raw data file
            mask_id: Mask ID
            run_name: Run name
            lot_name: Lot name
            wafer_name: Wafer name
            die_x: Die X coordinate
            die_y: Die Y coordinate
            device_name: Device name
            measurement_type: Type of measurement
            test_station_name: Test station name
            test_meta: Optional test metadata
            
        Returns:
            True if successful, False otherwise
        """
        if not self.service:
            LOGGER.error("Service not initialized")
            return False
        
        if not raw_data_path.exists():
            LOGGER.error(f"Data file not found: {raw_data_path}")
            return False
        
        # Prepare measurement data
        measurement = MeasurementData(
            mask_id=mask_id,
            run_name=run_name,
            lot_name=lot_name,
            wafer_name=wafer_name,
            die_x=die_x,
            die_y=die_y,
            device_name=device_name,
            measurement_type=measurement_type,
            test_station_name=test_station_name,
            raw_data_path=raw_data_path,
            test_meta=test_meta or {},
            timestamp=datetime.now().isoformat()
        )
        
        try:
            status_code, result = self.service.upload_measurement(
                measurement,
                self.current_run_id
            )
            
            if status_code == 200:
                LOGGER.info(f"Successfully uploaded measurement ID: {result}")
                return True
            else:
                LOGGER.error(f"Upload failed: {result}")
                return False
                
        except Exception as e:
            LOGGER.error(f"Upload exception: {str(e)}")
            return False
    
    def upload_batch_measurements(
        self,
        measurements: List[Dict],
        show_progress: bool = True
    ) -> Dict[str, int]:
        """
        Upload multiple measurements in batch
        
        Args:
            measurements: List of measurement dictionaries
            show_progress: Whether to show progress
            
        Returns:
            Dictionary with counts of successful and failed uploads
        """
        if not self.service:
            LOGGER.error("Service not initialized")
            return {"success": 0, "failed": 0}
        
        # Convert dicts to MeasurementData objects
        measurement_objects = []
        for m in measurements:
            measurement_objects.append(
                MeasurementData(
                    mask_id=m["mask_id"],
                    run_name=m["run_name"],
                    lot_name=m["lot_name"],
                    wafer_name=m["wafer_name"],
                    die_x=m["die_x"],
                    die_y=m["die_y"],
                    device_name=m["device_name"],
                    measurement_type=m["measurement_type"],
                    test_station_name=m["test_station_name"],
                    raw_data_path=Path(m["raw_data_path"]),
                    test_meta=m.get("test_meta", {}),
                    timestamp=m.get("timestamp", datetime.now().isoformat())
                )
            )
        
        # Progress callback
        def progress_callback(current, total):
            if show_progress:
                percent = (current / total) * 100
                print(f"Upload progress: {current}/{total} ({percent:.1f}%)")
        
        # Upload batch
        results = self.service.upload_batch(
            measurement_objects,
            self.current_run_id,
            progress_callback if show_progress else None
        )
        
        return {
            "success": len(results["success"]),
            "failed": len(results["failed"])
        }
    
    def trigger_analysis(self, run_name: str) -> bool:
        """
        Trigger die analysis for a completed run
        
        Args:
            run_name: Name of the run
            
        Returns:
            True if successful, False otherwise
        """
        if not self.service:
            LOGGER.error("Service not initialized")
            return False
        
        return self.service.trigger_die_analysis(run_name)
    
    def attach_file_to_run(
        self,
        run_id: int,
        filepath: Path,
        attachment_name: str = None
    ) -> bool:
        """
        Attach a file to a run
        
        Args:
            run_id: Run ID
            filepath: Path to file to attach
            attachment_name: Optional custom name
            
        Returns:
            True if successful, False otherwise
        """
        if not self.service:
            LOGGER.error("Service not initialized")
            return False
        
        return self.service.post_attachment(run_id, filepath, attachment_name)
    
    def close(self):
        """Clean up resources"""
        if self.service:
            self.service.close()
            self.service = None


def example_basic_usage():
    """Example of basic MaskHub upload usage"""
    print("=== Basic MaskHub Upload Example ===\n")
    
    # Initialize uploader
    uploader = EDWAMaskHubUploader()
    
    # Configure credentials (if not loaded from file/env)
    # uploader.configure_credentials(
    #     api_url="https://maskhub.psiquantum.com/api",
    #     api_v3_url="https://maskhub.psiquantum.com/api/v3",
    #     api_token="your-api-token"
    # )
    
    # Create a test run
    run_id = uploader.create_test_run(
        mask_id=12345,
        run_name=f"EDWA_Test_Run_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        config_data={"instrument": "EDWA", "version": "1.0"},
        calibration_data={"calibrated": True, "date": datetime.now().isoformat()},
        expected_measurements=10
    )
    
    if run_id:
        print(f"Created run with ID: {run_id}")
        
        # Upload a measurement
        # Note: You need actual data files for this to work
        # success = uploader.upload_measurement(
        #     raw_data_path=Path("data/measurement.parquet"),
        #     mask_id=12345,
        #     run_name="EDWA_Test_Run",
        #     lot_name="LOT001",
        #     wafer_name="WAFER001",
        #     die_x=10,
        #     die_y=20,
        #     device_name="Device001",
        #     measurement_type="optical_measurement",
        #     test_station_name="EDWA_Station_1",
        #     test_meta={"power": 100, "wavelength": 1550}
        # )
        
        # Trigger analysis when done
        # uploader.trigger_analysis("EDWA_Test_Run")
    
    # Clean up
    uploader.close()


def example_batch_upload():
    """Example of batch upload with progress tracking"""
    print("=== Batch Upload Example ===\n")
    
    # Prepare batch measurements
    measurements = [
        {
            "mask_id": 12345,
            "run_name": "EDWA_Batch_Run",
            "lot_name": f"LOT00{i}",
            "wafer_name": f"WAFER00{i}",
            "die_x": i * 10,
            "die_y": i * 20,
            "device_name": f"Device00{i}",
            "measurement_type": "optical_measurement",
            "test_station_name": "EDWA_Station_1",
            "raw_data_path": f"data/measurement_{i}.parquet",
            "test_meta": {"index": i}
        }
        for i in range(1, 6)
    ]
    
    # Initialize and upload
    uploader = EDWAMaskHubUploader()
    
    # Note: Uncomment and modify paths for actual use
    # results = uploader.upload_batch_measurements(measurements, show_progress=True)
    # print(f"\nResults: {results['success']} successful, {results['failed']} failed")
    
    uploader.close()


def create_example_config():
    """Create an example configuration file"""
    print("=== Creating Example Configuration ===\n")
    
    config_manager = MaskHubConfigManager()
    config_manager.create_example_config(Path("maskhub_config.example.json"))
    
    print("\nTo use MaskHub service:")
    print("1. Edit maskhub_config.example.json with your credentials")
    print("2. Rename to maskhub_config.json")
    print("3. Place in one of these locations:")
    print("   - Current directory")
    print("   - config/ directory")
    print(f"   - {Path.home() / '.edwa' / 'maskhub_config.json'}")
    print("\nOr set environment variables:")
    print("   - MASKHUB_API")
    print("   - MASKHUB_API_V3")
    print("   - MASKHUB_API_TOKEN")


if __name__ == "__main__":
    # Create example configuration
    create_example_config()
    
    print("\n" + "="*50 + "\n")
    
    # Run basic example (will only work with valid credentials)
    example_basic_usage()
    
    print("\n" + "="*50 + "\n")
    
    # Run batch example (will only work with valid credentials and data files)
    example_batch_upload()