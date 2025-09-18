"""
MaskHub Service Module
======================
This module provides a modular service for uploading data to MaskHub.
Extracted and refactored from psiqtest for use in edwa.
"""

import json
import hashlib
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple, Union, Any, List
from dataclasses import dataclass, field
from enum import IntEnum
import time

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    retry_if_result,
    stop_after_attempt,
    wait_exponential,
    RetryError
)

# Configure logger
LOGGER = logging.getLogger(__name__)

# Constants
SUPREMUM_GOOD_STATUS_CODE = 400
RETRYABLE_STATUS_CODES = (413, 429, 500, 502, 503, 504)
RETRYABLE_EXCEPTIONS = (requests.exceptions.ConnectionError,)


class UploadStatus(IntEnum):
    """Upload status enumeration"""
    NOT_UPLOADED = 0
    UPLOADED = 1
    UPLOAD_FAILED = 2
    UPLOAD_FAILED_NORETRY = 3
    DELETED = 4


@dataclass
class MaskHubConfig:
    """Configuration for MaskHub connection"""
    api_url: str
    api_v3_url: str
    api_token: str
    timeout: int = 30
    max_retries: int = 5
    retry_multiplier: int = 2
    retry_min_wait: int = 15


@dataclass
class MeasurementData:
    """Data class for measurement information"""
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
    sequence: Optional[int] = None
    timestamp: Optional[str] = None
    measurement_status: Optional[str] = None
    extra_meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RunMetadata:
    """Metadata for a test run"""
    mask_id: int
    run_name: str
    project_id: Optional[int] = None
    config: Optional[Dict] = None
    calibration: Optional[Dict] = None
    uuid: Optional[str] = None
    expected_measurement_count: int = 0
    expected_material_counts: Optional[List[List]] = None
    test_software_name: str = "edwa"
    test_software_version: str = "1.0.0"
    instrument_id: Optional[str] = None
    operator: Optional[str] = None
    station: Optional[str] = None
    room: Optional[str] = None
    run_suffix: Optional[str] = None


class MaskHubService:
    """Service class for interacting with MaskHub API"""
    
    def __init__(self, config: MaskHubConfig):
        """
        Initialize MaskHub service
        
        Args:
            config: MaskHub configuration object
        """
        self.config = config
        self.session = None
        self._setup_session()
    
    def _setup_session(self):
        """Setup requests session with persistent connection"""
        self.session = requests.Session()
        self.session.headers.update({
            "X-API-KEY": self.config.api_token
        })
        # Connection pooling for better performance
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=10,
            max_retries=0  # We handle retries with tenacity
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def _access_resource(
        self, 
        url: str, 
        method: str, 
        payload: Optional[Dict] = None,
        files: Optional[Dict] = None,
        allowed_status_codes: Tuple[int, ...] = (200, 409),
        timeout: Optional[int] = None
    ) -> Tuple[Union[Dict, List, str], int]:
        """
        Access MaskHub resource using GET/POST methods
        
        Args:
            url: API endpoint URL
            method: HTTP method ('get' or 'post')
            payload: Request payload
            files: Files to upload
            allowed_status_codes: Status codes considered successful
            timeout: Request timeout
            
        Returns:
            Tuple of (response data, status code)
        """
        timeout = timeout or self.config.timeout
        
        try:
            if method.lower() == 'get':
                response = self.session.get(url, params=payload, timeout=timeout)
            elif method.lower() == 'post':
                if files:
                    response = self.session.post(url, data=payload, files=files, timeout=timeout)
                else:
                    response = self.session.post(url, json=payload, timeout=timeout)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            if response.status_code in allowed_status_codes:
                try:
                    return response.json(), response.status_code
                except json.JSONDecodeError as e:
                    LOGGER.error(f"JSON decoding failed: {str(e)}")
                    return response.text, response.status_code
            else:
                error_msg = f"MaskHub {method} failed for url={url}, status={response.status_code}, response={response.text}"
                LOGGER.error(error_msg)
                raise requests.HTTPError(error_msg)
                
        except requests.RequestException as e:
            LOGGER.error(f"Request failed: {str(e)}")
            raise
    
    def get_teststation_id(self, name: str) -> Optional[int]:
        """
        Get or create test station ID
        
        Args:
            name: Test station name
            
        Returns:
            Test station ID or None if failed
        """
        try:
            # Try to get existing test station
            r, status_code = self._access_resource(
                f"{self.config.api_url}/teststations/",
                "get",
                {"name": name}
            )
            
            if r and status_code == 200:
                if len(r) == 1:
                    return r[0]["id"]
                elif len(r) > 1:
                    raise ValueError(f"Multiple test stations found: {r}")
            
            # Create new test station if not found
            LOGGER.info(f"Test station {name} not found, creating one")
            r, status_code = self._access_resource(
                f"{self.config.api_url}/teststations/",
                "post",
                {"name": name}
            )
            return r["id"] if r else None
            
        except Exception as e:
            LOGGER.error(f"Failed to get test station id: {str(e)}")
            return None
    
    def send_heartbeat(
        self,
        teststation_id: int,
        status: str,
        code: str,
        **kwargs
    ) -> Optional[Dict]:
        """
        Send heartbeat to MaskHub
        
        Args:
            teststation_id: Test station ID
            status: Status string
            code: Code string
            **kwargs: Additional heartbeat data
            
        Returns:
            Response dict or None if failed
        """
        heartbeat = {
            'teststation_id': teststation_id,
            'status': status,
            'code': code,
            **kwargs
        }
        
        try:
            response, _ = self._access_resource(
                f"{self.config.api_url}/heartbeats/",
                "post",
                heartbeat
            )
            return response
        except Exception as e:
            LOGGER.error(f"Failed to send heartbeat: {str(e)}")
            return None
    
    def create_run(self, metadata: RunMetadata) -> Optional[int]:
        """
        Create a new run in MaskHub
        
        Args:
            metadata: Run metadata
            
        Returns:
            Run ID or None if failed
        """
        try:
            # Get mask info to get project_id
            if metadata.project_id is None:
                r_mask, _ = self._access_resource(
                    f"{self.config.api_url}/masks/{metadata.mask_id}",
                    "get",
                    {}
                )
                metadata.project_id = r_mask["project_id"]
            
            # Prepare payload
            payload = {
                "name": metadata.run_name,
                "project_id": metadata.project_id,
                "test_software_name": metadata.test_software_name,
                "test_software_version": metadata.test_software_version,
                "expected_measurement_count": metadata.expected_measurement_count
            }
            
            if metadata.config is not None:
                payload["config"] = json.dumps(metadata.config)
            if metadata.calibration is not None:
                payload["calibration"] = json.dumps(metadata.calibration)
            if metadata.uuid is not None:
                payload["test_software_guid"] = metadata.uuid
            if metadata.expected_material_counts:
                payload["expected_material_counts"] = json.dumps(metadata.expected_material_counts)
            
            # Create run
            r_run, _ = self._access_resource(
                f"{self.config.api_url}/runs/",
                "post",
                payload
            )
            
            run_id = r_run["id"]
            LOGGER.info(f"Created run {metadata.run_name} with ID {run_id}")
            return run_id
            
        except Exception as e:
            LOGGER.error(f"Failed to create run: {str(e)}")
            return None
    
    def _retryable_result(self, result: Tuple[int, Union[int, str]]) -> bool:
        """Check if result should be retried"""
        status_code, _ = result
        return status_code in RETRYABLE_STATUS_CODES
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=15),
        retry=(retry_if_exception_type(RETRYABLE_EXCEPTIONS) | 
               retry_if_result(lambda r: r[0] in RETRYABLE_STATUS_CODES))
    )
    def upload_measurement(
        self,
        measurement: MeasurementData,
        run_id: Optional[int] = None
    ) -> Tuple[int, Union[int, str]]:
        """
        Upload measurement data to MaskHub
        
        Args:
            measurement: Measurement data to upload
            run_id: Optional run ID for logging
            
        Returns:
            Tuple of (status_code, measurement_id or error_message)
        """
        # Prepare data payload
        data = {
            "mask_id": measurement.mask_id,
            "run_name": measurement.run_name,
            "lot_name": measurement.lot_name,
            "wafer_name": measurement.wafer_name,
            "die_x": measurement.die_x,
            "die_y": measurement.die_y,
            "device_name": measurement.device_name,
            "type": measurement.measurement_type,
            "test_station_name": measurement.test_station_name,
            "test_meta": json.dumps(measurement.test_meta),
        }
        
        # Add optional fields
        if measurement.nas_path:
            data["meta"] = json.dumps({"path": str(measurement.nas_path)})
        elif measurement.extra_meta:
            data["meta"] = json.dumps(measurement.extra_meta)
        else:
            data["meta"] = json.dumps({})
        
        # Upload file
        try:
            with open(measurement.raw_data_path, "rb") as f:
                files = {"raw_data": (measurement.raw_data_path.name, f)}
                
                response = self.session.post(
                    f"{self.config.api_v3_url}/measurements",
                    data=data,
                    files=files,
                    timeout=self.config.timeout
                )
                
                if response.status_code == 200:
                    payload = response.json()
                    measurement_id = payload["id"]
                    LOGGER.info(
                        f"Uploaded measurement: {measurement.wafer_name} "
                        f"({measurement.die_x}, {measurement.die_y}) {measurement.device_name}"
                    )
                    return response.status_code, measurement_id
                else:
                    try:
                        payload = response.json()
                        error_msg = payload.get("message", "Unknown error")
                    except json.JSONDecodeError:
                        error_msg = response.text
                    
                    LOGGER.error(
                        f"Upload failed: {measurement.wafer_name} "
                        f"({measurement.die_x}, {measurement.die_y}) {measurement.device_name} - "
                        f"[{response.status_code}] {error_msg}"
                    )
                    return response.status_code, error_msg
                    
        except Exception as e:
            LOGGER.error(f"Upload exception: {str(e)}")
            raise
    
    def upload_batch(
        self,
        measurements: List[MeasurementData],
        run_id: Optional[int] = None,
        progress_callback=None
    ) -> Dict[str, List[MeasurementData]]:
        """
        Upload batch of measurements
        
        Args:
            measurements: List of measurements to upload
            run_id: Optional run ID
            progress_callback: Optional callback function for progress updates
            
        Returns:
            Dict with 'success' and 'failed' lists
        """
        results = {"success": [], "failed": []}
        total = len(measurements)
        
        for i, measurement in enumerate(measurements):
            try:
                status_code, result = self.upload_measurement(measurement, run_id)
                if status_code == 200:
                    results["success"].append(measurement)
                else:
                    results["failed"].append(measurement)
            except RetryError:
                LOGGER.error(f"Max retries exceeded for {measurement.device_name}")
                results["failed"].append(measurement)
            except Exception as e:
                LOGGER.error(f"Unexpected error: {str(e)}")
                results["failed"].append(measurement)
            
            if progress_callback:
                progress_callback(i + 1, total)
        
        return results
    
    def trigger_die_analysis(self, run_name: str) -> bool:
        """
        Trigger die analysis for a completed run
        
        Args:
            run_name: Name of the run
            
        Returns:
            True if successful, False otherwise
        """
        try:
            response = self.session.post(
                f"{self.config.api_url}/runs/{run_name}/trigger_die_analysis",
                timeout=self.config.timeout
            )
            
            if response.status_code == 200:
                LOGGER.info(f"Triggered die analysis for run {run_name}")
                return True
            else:
                LOGGER.error(
                    f"Failed to trigger die analysis: [{response.status_code}] {response.text}"
                )
                return False
                
        except Exception as e:
            LOGGER.error(f"Exception triggering die analysis: {str(e)}")
            return False
    
    def post_attachment(
        self,
        run_id: int,
        filepath: Path,
        attachment_name: Optional[str] = None
    ) -> bool:
        """
        Upload attachment file to a run
        
        Args:
            run_id: Run ID to attach to
            filepath: Path to file to upload
            attachment_name: Optional custom name for attachment
            
        Returns:
            True if successful, False otherwise
        """
        if not filepath.exists():
            LOGGER.error(f"File does not exist: {filepath}")
            return False
        
        try:
            with open(filepath, "rb") as f:
                response = self.session.post(
                    f"{self.config.api_url}/attachments/",
                    data={
                        "target_model_name": "run",
                        "target_model_id": run_id,
                        "name": attachment_name or filepath.name,
                    },
                    files=[("files", f)],
                    timeout=self.config.timeout
                )
                
                if response.status_code < SUPREMUM_GOOD_STATUS_CODE:
                    LOGGER.info(f"Successfully uploaded attachment: {filepath.name}")
                    return True
                else:
                    LOGGER.error(
                        f"Failed to upload attachment: [{response.status_code}] {response.text}"
                    )
                    return False
                    
        except Exception as e:
            LOGGER.error(f"Exception uploading attachment: {str(e)}")
            return False
    
    def close(self):
        """Close the session and clean up resources"""
        if self.session:
            self.session.close()
            self.session = None
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


def calculate_file_md5(filepath: Path) -> str:
    """
    Calculate MD5 hash of a file
    
    Args:
        filepath: Path to file
        
    Returns:
        MD5 hash string
    """
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()