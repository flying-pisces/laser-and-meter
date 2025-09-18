"""
MaskHub Configuration Module
============================
Manages configuration for MaskHub API connections.
Supports loading from environment variables and config files.
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict

LOGGER = logging.getLogger(__name__)


@dataclass
class MaskHubCredentials:
    """MaskHub API credentials"""
    api_url: str
    api_v3_url: str
    api_token: str
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MaskHubCredentials":
        """Create credentials from dictionary"""
        return cls(
            api_url=data["api_url"],
            api_v3_url=data["api_v3_url"],
            api_token=data["api_token"]
        )
    
    @classmethod
    def from_env(cls) -> Optional["MaskHubCredentials"]:
        """
        Load credentials from environment variables
        
        Expected environment variables:
        - MASKHUB_API: Base API URL
        - MASKHUB_API_V3: V3 API URL
        - MASKHUB_API_TOKEN: API authentication token
        """
        api_url = os.environ.get("MASKHUB_API")
        api_v3_url = os.environ.get("MASKHUB_API_V3")
        api_token = os.environ.get("MASKHUB_API_TOKEN")
        
        if all([api_url, api_v3_url, api_token]):
            return cls(
                api_url=api_url,
                api_v3_url=api_v3_url,
                api_token=api_token
            )
        else:
            missing = []
            if not api_url:
                missing.append("MASKHUB_API")
            if not api_v3_url:
                missing.append("MASKHUB_API_V3")
            if not api_token:
                missing.append("MASKHUB_API_TOKEN")
            LOGGER.warning(f"Missing environment variables: {', '.join(missing)}")
            return None
    
    @classmethod
    def from_file(cls, filepath: Path) -> Optional["MaskHubCredentials"]:
        """
        Load credentials from JSON config file
        
        Expected JSON structure:
        {
            "api_url": "https://maskhub.example.com/api",
            "api_v3_url": "https://maskhub.example.com/api/v3",
            "api_token": "your-api-token"
        }
        """
        if not filepath.exists():
            LOGGER.error(f"Config file not found: {filepath}")
            return None
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            return cls.from_dict(data)
        except Exception as e:
            LOGGER.error(f"Failed to load config from {filepath}: {str(e)}")
            return None
    
    def to_dict(self) -> Dict[str, str]:
        """Convert credentials to dictionary"""
        return asdict(self)
    
    def save_to_file(self, filepath: Path):
        """Save credentials to JSON file"""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        LOGGER.info(f"Saved credentials to {filepath}")


class MaskHubConfigManager:
    """Manages MaskHub configuration with fallback options"""
    
    DEFAULT_CONFIG_PATHS = [
        Path.home() / ".edwa" / "maskhub_config.json",
        Path("config") / "maskhub_config.json",
        Path("maskhub_config.json"),
    ]
    
    DEFAULT_SETTINGS = {
        "timeout": 30,
        "max_retries": 5,
        "retry_multiplier": 2,
        "retry_min_wait": 15
    }
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration manager
        
        Args:
            config_path: Optional specific config file path
        """
        self.config_path = config_path
        self.credentials = None
        self.settings = self.DEFAULT_SETTINGS.copy()
        self._load_configuration()
    
    def _load_configuration(self):
        """Load configuration from available sources"""
        # Try environment variables first
        self.credentials = MaskHubCredentials.from_env()
        
        if self.credentials:
            LOGGER.info("Loaded MaskHub credentials from environment variables")
            return
        
        # Try specified config file
        if self.config_path and self.config_path.exists():
            config = self._load_full_config(self.config_path)
            if config:
                self.credentials = config.get("credentials")
                self.settings.update(config.get("settings", {}))
                LOGGER.info(f"Loaded MaskHub configuration from {self.config_path}")
                return
        
        # Try default config locations
        for path in self.DEFAULT_CONFIG_PATHS:
            if path.exists():
                config = self._load_full_config(path)
                if config:
                    self.credentials = config.get("credentials")
                    self.settings.update(config.get("settings", {}))
                    LOGGER.info(f"Loaded MaskHub configuration from {path}")
                    return
        
        LOGGER.warning("No MaskHub configuration found")
    
    def _load_full_config(self, filepath: Path) -> Optional[Dict]:
        """
        Load full configuration including credentials and settings
        
        Expected structure:
        {
            "credentials": {
                "api_url": "...",
                "api_v3_url": "...",
                "api_token": "..."
            },
            "settings": {
                "timeout": 30,
                "max_retries": 5,
                ...
            }
        }
        """
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            if "credentials" in data:
                credentials = MaskHubCredentials.from_dict(data["credentials"])
            else:
                # Assume top-level contains credentials directly
                credentials = MaskHubCredentials.from_dict(data)
            
            return {
                "credentials": credentials,
                "settings": data.get("settings", {})
            }
        except Exception as e:
            LOGGER.error(f"Failed to load config from {filepath}: {str(e)}")
            return None
    
    def get_credentials(self) -> Optional[MaskHubCredentials]:
        """Get loaded credentials"""
        return self.credentials
    
    def get_settings(self) -> Dict[str, Any]:
        """Get configuration settings"""
        return self.settings.copy()
    
    def set_credentials(self, credentials: MaskHubCredentials):
        """Set credentials programmatically"""
        self.credentials = credentials
    
    def update_settings(self, **kwargs):
        """Update configuration settings"""
        self.settings.update(kwargs)
    
    def save_configuration(self, filepath: Optional[Path] = None):
        """
        Save current configuration to file
        
        Args:
            filepath: Path to save to (defaults to first default path)
        """
        if not self.credentials:
            LOGGER.error("No credentials to save")
            return
        
        filepath = filepath or self.DEFAULT_CONFIG_PATHS[0]
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        config = {
            "credentials": self.credentials.to_dict(),
            "settings": self.settings
        }
        
        with open(filepath, 'w') as f:
            json.dump(config, f, indent=2)
        
        LOGGER.info(f"Saved configuration to {filepath}")
    
    def create_example_config(self, filepath: Optional[Path] = None):
        """Create an example configuration file"""
        filepath = filepath or Path("maskhub_config.example.json")
        
        example = {
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
        
        with open(filepath, 'w') as f:
            json.dump(example, f, indent=2)
        
        LOGGER.info(f"Created example configuration at {filepath}")
        print(f"Example configuration created at {filepath}")
        print("Edit this file with your actual credentials and rename to maskhub_config.json")