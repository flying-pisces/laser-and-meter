"""
Enhanced End-to-End Test GUI with Dual Laser Support and HTTP Power Meter

Features:
- Dual laser support with individual connection status
- HTTP power meter integration (Channel 1 from 169.254.229.215)
- Status button for connection detection
- Smart current level selection with auto-enable logic
- Real-time power measurements during testing
- MaskHub integration for data upload
"""

import sys
import os
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import queue
import time
import json
import logging
import requests
import urllib.request
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

# Add paths for local modules
sys.path.insert(0, os.path.abspath('.'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'pumplaser'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'maskhub'))

from pumplaser.pump_laser import CLD1015, list_visa_resources
from maskhub.laser_maskhub_integration import (
    LaserMaskHubIntegration,
    LaserMeasurement,
    LaserRunConfig,
    create_laser_measurement_from_test_data
)
from maskhub.maskhub_config import MaskHubConfigManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Power meter configuration
POWER_METER_IP = "169.254.229.215"
POWER_METER_URL = f"http://{POWER_METER_IP}"

# Known laser resources
DEFAULT_LASER_RESOURCES = [
    "USB0::0x1313::0x804F::M01093719::INSTR",   # Laser 1
    "USB0::0x1313::0x804F::M00859480::INSTR"    # Laser 2
]


class PowerMeterHTTP:
    """HTTP interface for Thorlabs power meter at specified IP"""

    def __init__(self, base_url: str = POWER_METER_URL):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.timeout = 5
        self.connected = False

    def test_connection(self) -> bool:
        """Test if power meter is accessible"""
        try:
            response = self.session.get(f"{self.base_url}/", timeout=3)
            self.connected = response.status_code == 200
            return self.connected
        except Exception as e:
            logger.warning(f"Power meter connection test failed: {e}")
            self.connected = False
            return False

    def get_power_reading_channel1(self) -> Optional[float]:
        """Get power reading from channel 1 in mW"""
        if not self.connected:
            return None

        try:
            # Try different possible endpoints for channel 1 power reading
            endpoints = [
                "/api/power/channel1",
                "/api/v1/power/1",
                "/power/1",
                "/channel1/power",
                "/api/measurement/channel1"
            ]

            for endpoint in endpoints:
                try:
                    response = self.session.get(f"{self.base_url}{endpoint}", timeout=2)
                    if response.status_code == 200:
                        # Try to parse as JSON first
                        try:
                            data = response.json()
                            if isinstance(data, dict):
                                # Look for power value in various keys
                                for key in ['power', 'value', 'measurement', 'power_mw', 'reading']:
                                    if key in data:
                                        return float(data[key])
                            elif isinstance(data, (int, float)):
                                return float(data)
                        except:
                            # Try to parse as plain text/number
                            try:
                                return float(response.text.strip())
                            except:
                                continue
                except:
                    continue

            # If no specific endpoint works, try a generic approach
            logger.warning("No specific power meter endpoint found, using fallback")
            return None

        except Exception as e:
            logger.error(f"Failed to get power reading: {e}")
            return None

    def get_all_channels(self) -> Dict[int, Optional[float]]:
        """Get power readings from all available channels"""
        readings = {}
        for channel in range(1, 5):  # Try channels 1-4
            try:
                # This is a placeholder - adjust based on actual API
                response = self.session.get(f"{self.base_url}/api/power/channel{channel}", timeout=1)
                if response.status_code == 200:
                    readings[channel] = float(response.text.strip())
            except:
                readings[channel] = None
        return readings


class LaserStatusPanel(ttk.LabelFrame):
    """Status panel for a single laser with connection detection"""

    def __init__(self, parent, laser_name: str, resource_name: str):
        super().__init__(parent, text=f"{laser_name} Status", padding=10)
        self.laser_name = laser_name
        self.resource_name = resource_name
        self.laser = None
        self.is_connected = False

        self.setup_ui()

    def setup_ui(self):
        """Create status UI elements"""
        # Connection status row
        self.status_frame = ttk.Frame(self)
        self.status_frame.pack(fill='x', pady=(0, 10))

        # Resource name
        resource_label = ttk.Label(self.status_frame, text="Resource:")
        resource_label.pack(side='left')

        self.resource_var = tk.StringVar(value=self.resource_name[:30] + "..." if len(self.resource_name) > 30 else self.resource_name)
        resource_display = ttk.Label(self.status_frame, textvariable=self.resource_var, font=('Courier', 9))
        resource_display.pack(side='left', padx=(5, 20))

        # Connection status indicator
        self.status_var = tk.StringVar(value="Unknown")
        self.status_label = ttk.Label(self.status_frame, textvariable=self.status_var, foreground="gray")
        self.status_label.pack(side='left', padx=(0, 10))

        # Test connection button
        self.test_btn = ttk.Button(self.status_frame, text="Test Connection", command=self.test_connection)
        self.test_btn.pack(side='right')

        # Device info
        self.info_frame = ttk.Frame(self)
        self.info_frame.pack(fill='x', pady=5)

        self.device_info_var = tk.StringVar(value="Device: Not tested")
        self.device_info = ttk.Label(self.info_frame, textvariable=self.device_info_var, font=('Courier', 9))
        self.device_info.pack(side='left')

        # Temperature display
        self.temp_var = tk.StringVar(value="Temp: ---")
        self.temp_label = ttk.Label(self.info_frame, textvariable=self.temp_var, font=('Courier', 9))
        self.temp_label.pack(side='right')

    def test_connection(self) -> bool:
        """Test connection to the laser"""
        self.status_var.set("Testing...")
        self.status_label.configure(foreground="orange")
        self.test_btn.configure(state='disabled')

        try:
            # Try to connect
            if self.laser:
                self.laser.disconnect()

            self.laser = CLD1015(self.resource_name)
            if self.laser.connect():
                # Get device info
                status = self.laser.get_status()
                self.device_info_var.set(f"Device: {status['identity']}")
                self.temp_var.set(f"Temp: {status['temperature_c']:.1f}°C")

                self.status_var.set("Connected")
                self.status_label.configure(foreground="green")
                self.is_connected = True

                # Disconnect after test (will reconnect when needed)
                self.laser.disconnect()
                return True

            else:
                raise RuntimeError("Connection failed")

        except Exception as e:
            self.status_var.set("Failed")
            self.status_label.configure(foreground="red")
            self.device_info_var.set(f"Error: {str(e)[:50]}")
            self.temp_var.set("Temp: ---")
            self.is_connected = False
            return False

        finally:
            self.test_btn.configure(state='normal')

    def get_connection_status(self) -> bool:
        """Get current connection status"""
        return self.is_connected


class PowerMeterStatusPanel(ttk.LabelFrame):
    """Status panel for HTTP power meter"""

    def __init__(self, parent):
        super().__init__(parent, text="Power Meter Status", padding=10)
        self.power_meter = PowerMeterHTTP()
        self.setup_ui()

    def setup_ui(self):
        """Create power meter status UI"""
        # Connection status
        self.status_frame = ttk.Frame(self)
        self.status_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(self.status_frame, text=f"IP Address: {POWER_METER_IP}").pack(side='left')

        self.status_var = tk.StringVar(value="Not tested")
        self.status_label = ttk.Label(self.status_frame, textvariable=self.status_var, foreground="gray")
        self.status_label.pack(side='left', padx=(20, 10))

        self.test_btn = ttk.Button(self.status_frame, text="Test Connection", command=self.test_connection)
        self.test_btn.pack(side='right')

        # Power reading display
        self.reading_frame = ttk.Frame(self)
        self.reading_frame.pack(fill='x', pady=5)

        self.power_var = tk.StringVar(value="Channel 1 Power: ---")
        self.power_label = ttk.Label(self.reading_frame, textvariable=self.power_var, font=('Courier', 10, 'bold'))
        self.power_label.pack(side='left')

        self.refresh_btn = ttk.Button(self.reading_frame, text="Read Now", command=self.read_power, state='disabled')
        self.refresh_btn.pack(side='right')

    def test_connection(self) -> bool:
        """Test connection to power meter"""
        self.status_var.set("Testing...")
        self.status_label.configure(foreground="orange")
        self.test_btn.configure(state='disabled')

        try:
            if self.power_meter.test_connection():
                self.status_var.set("Connected")
                self.status_label.configure(foreground="green")
                self.refresh_btn.configure(state='normal')

                # Try to get an initial reading
                self.read_power()
                return True
            else:
                raise RuntimeError("HTTP connection failed")

        except Exception as e:
            self.status_var.set("Failed")
            self.status_label.configure(foreground="red")
            self.power_var.set(f"Error: {str(e)[:30]}")
            self.refresh_btn.configure(state='disabled')
            return False

        finally:
            self.test_btn.configure(state='normal')

    def read_power(self):
        """Read current power from channel 1"""
        try:
            power_mw = self.power_meter.get_power_reading_channel1()
            if power_mw is not None:
                self.power_var.set(f"Channel 1 Power: {power_mw:.3f} mW")
            else:
                self.power_var.set("Channel 1 Power: No reading")
        except Exception as e:
            self.power_var.set(f"Read Error: {str(e)[:20]}")

    def get_power_reading(self) -> Optional[float]:
        """Get current power reading"""
        return self.power_meter.get_power_reading_channel1()

    def is_connected(self) -> bool:
        """Check if power meter is connected"""
        return self.power_meter.connected


class CurrentLevelControl:
    """Enhanced current level selection with dual laser support"""

    def __init__(self, parent_frame, available_currents: List[float]):
        self.parent = parent_frame
        self.currents = sorted(available_currents)
        self.checkboxes = {}
        self.variables = {}

        # Create frame for current selection
        self.frame = ttk.LabelFrame(parent_frame, text="Current Test Levels (mA)", padding=10)
        self.frame.pack(fill='x', padx=5, pady=5)

        # Create checkboxes for each current level
        for i, current in enumerate(self.currents):
            var = tk.BooleanVar()

            # Default: 0mA and 50mA selected (first low level)
            if current in [0.0, 50.0]:
                var.set(True)

            checkbox = ttk.Checkbutton(
                self.frame,
                text=f"{current:g} mA",
                variable=var,
                command=lambda c=current: self._on_checkbox_change(c)
            )
            checkbox.grid(row=0, column=i, padx=10, pady=5, sticky='w')

            self.checkboxes[current] = checkbox
            self.variables[current] = var

        # Apply initial logic
        self._update_checkbox_states()

        # Status display
        self.status_frame = ttk.Frame(self.frame)
        self.status_frame.grid(row=1, column=0, columnspan=len(self.currents), pady=(10, 0))

        self.status_var = tk.StringVar()
        self.status_label = ttk.Label(self.status_frame, textvariable=self.status_var, font=('Arial', 9))
        self.status_label.pack()

        self._update_status()

    def _on_checkbox_change(self, changed_current: float):
        """Handle checkbox state changes with automatic lower-level enabling"""
        # If a current level is enabled, enable all lower current levels
        if self.variables[changed_current].get():
            for current in self.currents:
                if current <= changed_current:
                    self.variables[current].set(True)

        # If a current level is disabled, disable all higher current levels
        else:
            for current in self.currents:
                if current > changed_current:
                    self.variables[current].set(False)

        self._update_checkbox_states()
        self._update_status()

    def _update_checkbox_states(self):
        """Update checkbox visual states"""
        # This could be enhanced with colors or styles
        pass

    def _update_status(self):
        """Update status display"""
        selected = self.get_selected_currents()
        if selected:
            self.status_var.set(f"Selected levels: {', '.join(f'{c:g}mA' for c in selected)}")
        else:
            self.status_var.set("No current levels selected")

    def get_selected_currents(self) -> List[float]:
        """Get list of selected current levels"""
        return [current for current, var in self.variables.items() if var.get()]

    def set_enabled(self, enabled: bool):
        """Enable or disable all checkboxes"""
        state = 'normal' if enabled else 'disabled'
        for checkbox in self.checkboxes.values():
            checkbox.configure(state=state)


class TestProgressDisplay:
    """Enhanced progress display with power meter integration"""

    def __init__(self, parent_frame):
        self.parent = parent_frame

        # Create progress frame
        self.frame = ttk.LabelFrame(parent_frame, text="Test Progress", padding=10)
        self.frame.pack(fill='both', expand=True, padx=5, pady=5)

        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            self.frame,
            variable=self.progress_var,
            maximum=100,
            length=500
        )
        self.progress_bar.pack(fill='x', pady=(0, 10))

        # Status label
        self.status_var = tk.StringVar()
        self.status_var.set("Ready to start test")
        self.status_label = ttk.Label(self.frame, textvariable=self.status_var)
        self.status_label.pack(pady=(0, 10))

        # Real-time measurements frame
        self.measurements_frame = ttk.LabelFrame(self.frame, text="Current Measurements", padding=5)
        self.measurements_frame.pack(fill='x', pady=(0, 10))

        # Laser measurements
        laser_frame = ttk.Frame(self.measurements_frame)
        laser_frame.pack(fill='x')

        self.laser1_var = tk.StringVar(value="Laser 1: ---")
        self.laser2_var = tk.StringVar(value="Laser 2: ---")
        self.power_var = tk.StringVar(value="Power: ---")

        ttk.Label(laser_frame, textvariable=self.laser1_var, font=('Courier', 9)).pack(side='left', padx=(0, 20))
        ttk.Label(laser_frame, textvariable=self.laser2_var, font=('Courier', 9)).pack(side='left', padx=(0, 20))
        ttk.Label(laser_frame, textvariable=self.power_var, font=('Courier', 9, 'bold')).pack(side='right')

        # Results display
        self.results_text = scrolledtext.ScrolledText(
            self.frame,
            height=12,
            width=90,
            font=('Courier', 9)
        )
        self.results_text.pack(fill='both', expand=True)

        # Add tags for colored output
        self.results_text.tag_configure("info", foreground="blue")
        self.results_text.tag_configure("success", foreground="green")
        self.results_text.tag_configure("warning", foreground="orange")
        self.results_text.tag_configure("error", foreground="red")

    def update_progress(self, percentage: float, status: str):
        """Update progress bar and status"""
        self.progress_var.set(percentage)
        self.status_var.set(status)

    def update_measurements(self, laser1_current: Optional[float] = None,
                          laser2_current: Optional[float] = None,
                          power_mw: Optional[float] = None):
        """Update real-time measurement display"""
        if laser1_current is not None:
            self.laser1_var.set(f"Laser 1: {laser1_current:.2f}mA")
        if laser2_current is not None:
            self.laser2_var.set(f"Laser 2: {laser2_current:.2f}mA")
        if power_mw is not None:
            self.power_var.set(f"Power: {power_mw:.3f}mW")

    def log_message(self, message: str, level: str = "info"):
        """Add message to results display"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\\n"

        self.results_text.insert(tk.END, formatted_message, level)
        self.results_text.see(tk.END)
        self.parent.update_idletasks()

    def clear_results(self):
        """Clear the results display"""
        self.results_text.delete(1.0, tk.END)


class EnhancedEndToEndTestGUI:
    """Enhanced GUI with dual laser support and HTTP power meter integration"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Enhanced Thorlabs Dual Laser Test with HTTP Power Meter")
        self.root.geometry("1200x900")

        # Test configuration
        self.available_currents = [0, 25, 50, 75, 100, 125, 150]
        self.detected_laser_resources = []

        # Runtime state
        self.test_running = False
        self.maskhub_integration = None
        self.test_thread = None
        self.message_queue = queue.Queue()

        # Initialize UI
        self._create_widgets()
        self._setup_message_processing()

        # Auto-detect laser resources
        self._detect_laser_resources()

        # Initialize MaskHub
        self._initialize_maskhub()

    def _detect_laser_resources(self):
        """Auto-detect available laser resources"""
        try:
            resources = list_visa_resources()
            # Filter for CLD1015 devices
            laser_resources = [res for res in resources if "0x1313" in res and "0x804F" in res]

            if laser_resources:
                self.detected_laser_resources = laser_resources[:2]  # Take first two
                self.progress_display.log_message(f"Detected {len(laser_resources)} CLD1015 laser(s)", "success")
            else:
                self.detected_laser_resources = DEFAULT_LASER_RESOURCES
                self.progress_display.log_message("No lasers detected, using default resources", "warning")

            # Update laser status panels
            if len(self.detected_laser_resources) >= 1:
                self.laser1_status.resource_name = self.detected_laser_resources[0]
                self.laser1_status.resource_var.set(self.detected_laser_resources[0][:30] + "...")

            if len(self.detected_laser_resources) >= 2:
                self.laser2_status.resource_name = self.detected_laser_resources[1]
                self.laser2_status.resource_var.set(self.detected_laser_resources[1][:30] + "...")

        except Exception as e:
            self.progress_display.log_message(f"Error detecting lasers: {e}", "error")
            self.detected_laser_resources = DEFAULT_LASER_RESOURCES

    def _create_widgets(self):
        """Create and layout GUI widgets"""

        # Main notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Status Tab
        self.status_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.status_frame, text="Device Status")

        # Test Configuration Tab
        self.config_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.config_frame, text="Test Configuration")

        # Test Results Tab
        self.results_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.results_frame, text="Test Results")

        # === Status Tab ===
        self._create_status_tab()

        # === Configuration Tab ===
        self._create_config_tab()

        # === Results Tab ===
        self._create_results_tab()

    def _create_status_tab(self):
        """Create device status tab"""
        # Laser status panels
        lasers_frame = ttk.Frame(self.status_frame)
        lasers_frame.pack(fill='x', padx=10, pady=10)

        # Create placeholders - will be updated when resources are detected
        self.laser1_status = LaserStatusPanel(lasers_frame, "Laser 1", "")
        self.laser1_status.pack(side='left', fill='both', expand=True, padx=(0, 10))

        self.laser2_status = LaserStatusPanel(lasers_frame, "Laser 2", "")
        self.laser2_status.pack(side='left', fill='both', expand=True)

        # Power meter status
        self.power_meter_status = PowerMeterStatusPanel(self.status_frame)
        self.power_meter_status.pack(fill='x', padx=10, pady=10)

        # Test all connections button
        test_all_frame = ttk.Frame(self.status_frame)
        test_all_frame.pack(fill='x', padx=10, pady=20)

        test_all_btn = ttk.Button(
            test_all_frame,
            text="Test All Connections",
            command=self._test_all_connections,
            style="Accent.TButton"
        )
        test_all_btn.pack()

        # Status summary
        self.status_summary_frame = ttk.LabelFrame(self.status_frame, text="Connection Summary", padding=10)
        self.status_summary_frame.pack(fill='x', padx=10, pady=10)

        self.summary_var = tk.StringVar(value="Click 'Test All Connections' to check device status")
        summary_label = ttk.Label(self.status_summary_frame, textvariable=self.summary_var)
        summary_label.pack()

    def _create_config_tab(self):
        """Create test configuration tab"""
        # Current level selection
        self.current_control = CurrentLevelControl(self.config_frame, self.available_currents)

        # Test parameters
        params_frame = ttk.LabelFrame(self.config_frame, text="Test Parameters", padding=10)
        params_frame.pack(fill='x', padx=5, pady=5)

        # Parameters in grid
        ttk.Label(params_frame, text="Stabilization Delay (s):").grid(row=0, column=0, sticky='w', padx=(0, 5))
        self.stabilization_var = tk.DoubleVar(value=2.0)
        stabilization_spin = ttk.Spinbox(
            params_frame,
            from_=0.5,
            to=10.0,
            increment=0.5,
            textvariable=self.stabilization_var,
            width=10
        )
        stabilization_spin.grid(row=0, column=1, sticky='w', padx=(0, 20))

        ttk.Label(params_frame, text="Measurements per level:").grid(row=0, column=2, sticky='w', padx=(0, 5))
        self.measurements_var = tk.IntVar(value=3)
        measurements_spin = ttk.Spinbox(
            params_frame,
            from_=1,
            to=10,
            textvariable=self.measurements_var,
            width=10
        )
        measurements_spin.grid(row=0, column=3, sticky='w')

        # Power meter integration
        ttk.Label(params_frame, text="Power readings per measurement:").grid(row=1, column=0, sticky='w', pady=(10, 0))
        self.power_readings_var = tk.IntVar(value=5)
        power_readings_spin = ttk.Spinbox(
            params_frame,
            from_=1,
            to=20,
            textvariable=self.power_readings_var,
            width=10
        )
        power_readings_spin.grid(row=1, column=1, sticky='w', pady=(10, 0))

        # MaskHub configuration
        maskhub_frame = ttk.LabelFrame(self.config_frame, text="MaskHub Configuration", padding=10)
        maskhub_frame.pack(fill='x', padx=5, pady=5)

        # Run name
        ttk.Label(maskhub_frame, text="Run Name:").grid(row=0, column=0, sticky='w', padx=(0, 5))
        self.run_name_var = tk.StringVar(value=f"Dual_Laser_Test_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        run_name_entry = ttk.Entry(maskhub_frame, textvariable=self.run_name_var, width=50)
        run_name_entry.grid(row=0, column=1, columnspan=2, sticky='w', padx=(0, 20))

        # Operator and mask ID
        ttk.Label(maskhub_frame, text="Operator:").grid(row=1, column=0, sticky='w', padx=(0, 5), pady=(10, 0))
        self.operator_var = tk.StringVar(value="Test_User")
        operator_entry = ttk.Entry(maskhub_frame, textvariable=self.operator_var, width=20)
        operator_entry.grid(row=1, column=1, sticky='w', pady=(10, 0))

        ttk.Label(maskhub_frame, text="Mask ID:").grid(row=1, column=2, sticky='w', padx=(20, 5), pady=(10, 0))
        self.mask_id_var = tk.IntVar(value=12345)
        mask_id_entry = ttk.Entry(maskhub_frame, textvariable=self.mask_id_var, width=15)
        mask_id_entry.grid(row=1, column=3, sticky='w', pady=(10, 0))

        # Control buttons
        button_frame = ttk.Frame(self.config_frame)
        button_frame.pack(fill='x', padx=5, pady=20)

        self.start_button = ttk.Button(
            button_frame,
            text="Start Test",
            command=self._start_test,
            style="Accent.TButton"
        )
        self.start_button.pack(side='left', padx=(0, 10))

        self.stop_button = ttk.Button(
            button_frame,
            text="Stop Test",
            command=self._stop_test,
            state='disabled'
        )
        self.stop_button.pack(side='left', padx=(0, 10))

        # Config and save buttons
        config_button = ttk.Button(
            button_frame,
            text="Configure MaskHub",
            command=self._configure_maskhub
        )
        config_button.pack(side='right', padx=(10, 0))

        save_button = ttk.Button(
            button_frame,
            text="Save Results",
            command=self._save_results
        )
        save_button.pack(side='right')

    def _create_results_tab(self):
        """Create test results tab"""
        # Test progress display
        self.progress_display = TestProgressDisplay(self.results_frame)

    def _test_all_connections(self):
        """Test connections to all devices"""
        self.summary_var.set("Testing connections...")

        # Test lasers
        laser1_ok = self.laser1_status.test_connection()
        laser2_ok = self.laser2_status.test_connection()

        # Test power meter
        power_meter_ok = self.power_meter_status.test_connection()

        # Update summary
        status_parts = []
        if laser1_ok:
            status_parts.append("✓ Laser 1")
        else:
            status_parts.append("✗ Laser 1")

        if laser2_ok:
            status_parts.append("✓ Laser 2")
        else:
            status_parts.append("✗ Laser 2")

        if power_meter_ok:
            status_parts.append("✓ Power Meter")
        else:
            status_parts.append("✗ Power Meter")

        self.summary_var.set(" | ".join(status_parts))

        # Log results
        total_devices = 3
        connected_devices = sum([laser1_ok, laser2_ok, power_meter_ok])

        if connected_devices == total_devices:
            self.progress_display.log_message("All devices connected successfully!", "success")
        elif connected_devices > 0:
            self.progress_display.log_message(f"{connected_devices}/{total_devices} devices connected", "warning")
        else:
            self.progress_display.log_message("No devices connected", "error")

    def _initialize_maskhub(self):
        """Initialize MaskHub integration"""
        try:
            self.maskhub_integration = LaserMaskHubIntegration(
                enable_realtime=True,
                auto_save_data=True
            )
            self.progress_display.log_message("MaskHub integration initialized", "success")
        except Exception as e:
            self.progress_display.log_message(f"MaskHub initialization failed: {e}", "error")

    def _setup_message_processing(self):
        """Setup periodic message queue processing"""
        def process_messages():
            try:
                while True:
                    message_type, data = self.message_queue.get_nowait()

                    if message_type == "progress":
                        percentage, status = data
                        self.progress_display.update_progress(percentage, status)

                    elif message_type == "log":
                        message, level = data
                        self.progress_display.log_message(message, level)

                    elif message_type == "measurements":
                        laser1_current, laser2_current, power_mw = data
                        self.progress_display.update_measurements(laser1_current, laser2_current, power_mw)

                    elif message_type == "test_complete":
                        self._on_test_complete(data)

            except queue.Empty:
                pass

            # Schedule next check
            self.root.after(100, process_messages)

        # Start message processing
        self.root.after(100, process_messages)

    def _start_test(self):
        """Start the dual laser test"""
        if self.test_running:
            return

        # Validate inputs
        selected_currents = self.current_control.get_selected_currents()
        if not selected_currents:
            messagebox.showerror("Error", "Please select at least one current level to test")
            return

        # Check device connections
        if not (self.laser1_status.get_connection_status() or self.laser2_status.get_connection_status()):
            result = messagebox.askyesno(
                "Warning",
                "No laser connections have been tested. Continue anyway?\\n\\n"
                "Recommendation: Go to 'Device Status' tab and test connections first."
            )
            if not result:
                return

        # Clear previous results
        self.progress_display.clear_results()
        self.progress_display.update_progress(0, "Starting dual laser test...")

        # Switch to results tab
        self.notebook.select(self.results_frame)

        # Update UI state
        self.test_running = True
        self.start_button.configure(state='disabled')
        self.stop_button.configure(state='normal')
        self.current_control.set_enabled(False)

        # Start test thread
        self.test_thread = threading.Thread(
            target=self._run_test_thread,
            args=(selected_currents,),
            daemon=True
        )
        self.test_thread.start()

    def _run_test_thread(self, selected_currents: List[float]):
        """Run the dual laser test in background thread"""
        try:
            # Create run configuration
            run_config = LaserRunConfig(
                mask_id=self.mask_id_var.get(),
                run_name=self.run_name_var.get(),
                lot_name="THORLABS_DUAL_TEST",
                wafer_name="DUAL_LASER_WAFER",
                operator=self.operator_var.get(),
                station="Enhanced_Dual_Station",
                measurement_type="dual_laser_characterization"
            )

            # Start MaskHub run
            if self.maskhub_integration:
                run_id = self.maskhub_integration.start_run(run_config)
                self.message_queue.put(("log", (f"Started MaskHub run: {run_id}", "info")))

            # Test both lasers simultaneously
            test_results = self._test_dual_lasers(selected_currents)

            # Finish MaskHub run
            if self.maskhub_integration and self.test_running:
                summary = self.maskhub_integration.finish_run(trigger_analysis=True)
                self.message_queue.put(("log", (f"Finished run: {summary}", "info")))

            # Complete test
            self.message_queue.put(("test_complete", test_results))

        except Exception as e:
            self.message_queue.put(("log", (f"Test failed: {e}", "error")))
            self.message_queue.put(("test_complete", {'overall_success': False, 'error': str(e)}))

    def _test_dual_lasers(self, selected_currents: List[float]) -> Dict:
        """Test both lasers with power meter integration"""
        results = {
            'laser1_results': None,
            'laser2_results': None,
            'power_readings': [],
            'overall_success': False
        }

        # Initialize devices
        laser1 = CLD1015(self.detected_laser_resources[0]) if len(self.detected_laser_resources) > 0 else None
        laser2 = CLD1015(self.detected_laser_resources[1]) if len(self.detected_laser_resources) > 1 else None
        power_meter = self.power_meter_status.power_meter

        total_measurements = len(selected_currents) * self.measurements_var.get()
        current_measurement = 0

        try:
            # Connect to available lasers
            laser1_connected = False
            laser2_connected = False

            if laser1:
                laser1_connected = laser1.connect()
                if laser1_connected:
                    self.message_queue.put(("log", ("Connected to Laser 1", "success")))
                    laser1.set_current_limit(max(selected_currents))
                    laser1.set_ld_output(True)

            if laser2:
                laser2_connected = laser2.connect()
                if laser2_connected:
                    self.message_queue.put(("log", ("Connected to Laser 2", "success")))
                    laser2.set_current_limit(max(selected_currents))
                    laser2.set_ld_output(True)

            if not (laser1_connected or laser2_connected):
                raise RuntimeError("No lasers could be connected")

            # Test each current level
            for current_ma in selected_currents:
                if not self.test_running:
                    break

                self.message_queue.put(("log", (f"\\nTesting at {current_ma} mA", "info")))

                # Set current on both lasers
                if laser1_connected:
                    laser1.set_ld_current(current_ma)
                if laser2_connected:
                    laser2.set_ld_current(current_ma)

                # Wait for stabilization
                stabilization_time = self.stabilization_var.get()
                for i in range(int(stabilization_time * 10)):
                    if not self.test_running:
                        break
                    time.sleep(0.1)

                # Take measurements
                for meas_idx in range(self.measurements_var.get()):
                    if not self.test_running:
                        break

                    current_measurement += 1
                    progress = (current_measurement / total_measurements) * 100

                    status_msg = f"Measuring at {current_ma}mA (sample {meas_idx + 1})"
                    self.message_queue.put(("progress", (progress, status_msg)))

                    # Get laser measurements
                    laser1_current = laser1.get_ld_current_actual() if laser1_connected else None
                    laser2_current = laser2.get_ld_current_actual() if laser2_connected else None

                    # Get power meter readings
                    power_readings = []
                    for power_idx in range(self.power_readings_var.get()):
                        if power_meter.connected:
                            power_mw = power_meter.get_power_reading_channel1()
                            if power_mw is not None:
                                power_readings.append(power_mw)
                        time.sleep(0.1)

                    avg_power = sum(power_readings) / len(power_readings) if power_readings else None

                    # Update real-time display
                    self.message_queue.put(("measurements", (laser1_current, laser2_current, avg_power)))

                    # Log measurements
                    log_parts = []
                    if laser1_current is not None:
                        log_parts.append(f"L1: {laser1_current:.2f}mA")
                    if laser2_current is not None:
                        log_parts.append(f"L2: {laser2_current:.2f}mA")
                    if avg_power is not None:
                        log_parts.append(f"Power: {avg_power:.3f}mW")

                    if log_parts:
                        self.message_queue.put(("log", (f"  {' | '.join(log_parts)}", "info")))

                    # Store data for MaskHub
                    if self.maskhub_integration:
                        if laser1_connected and laser1_current is not None:
                            measurement1 = LaserMeasurement(
                                device_id="Laser_1_Enhanced",
                                position=(0, len(results.get('power_readings', []))),
                                current_setpoint_ma=current_ma,
                                current_actual_ma=laser1_current,
                                voltage_v=laser1.get_ld_voltage(),
                                power_mw=avg_power,
                                temperature_c=laser1.get_temperature(),
                                timestamp=datetime.now(),
                                metadata={'laser_number': 1, 'measurement_index': meas_idx}
                            )
                            self.maskhub_integration.add_measurement(measurement1, (0, current_measurement))

                        if laser2_connected and laser2_current is not None:
                            measurement2 = LaserMeasurement(
                                device_id="Laser_2_Enhanced",
                                position=(10, len(results.get('power_readings', []))),
                                current_setpoint_ma=current_ma,
                                current_actual_ma=laser2_current,
                                voltage_v=laser2.get_ld_voltage(),
                                power_mw=avg_power,
                                temperature_c=laser2.get_temperature(),
                                timestamp=datetime.now(),
                                metadata={'laser_number': 2, 'measurement_index': meas_idx}
                            )
                            self.maskhub_integration.add_measurement(measurement2, (10, current_measurement))

                    time.sleep(0.5)  # Brief delay between measurements

            # Safe shutdown
            self.message_queue.put(("log", ("\\nShutting down lasers safely...", "info")))

            if laser1_connected:
                laser1.ramp_current(0, 10, 0.2)
                laser1.set_ld_output(False)
                laser1.disconnect()

            if laser2_connected:
                laser2.ramp_current(0, 10, 0.2)
                laser2.set_ld_output(False)
                laser2.disconnect()

            results['overall_success'] = True
            results['laser1_connected'] = laser1_connected
            results['laser2_connected'] = laser2_connected

        except Exception as e:
            self.message_queue.put(("log", (f"Test error: {e}", "error")))

            # Emergency shutdown
            try:
                if laser1:
                    laser1.emergency_stop()
                    laser1.disconnect()
                if laser2:
                    laser2.emergency_stop()
                    laser2.disconnect()
            except:
                pass

        return results

    def _on_test_complete(self, results: Dict):
        """Handle test completion"""
        self.test_running = False

        # Update UI state
        self.start_button.configure(state='normal')
        self.stop_button.configure(state='disabled')
        self.current_control.set_enabled(True)

        # Update progress
        if results.get('overall_success', False):
            self.progress_display.update_progress(100, "Dual laser test completed successfully!")
            self.progress_display.log_message("\\n=== DUAL LASER TEST PASSED ===", "success")

            # Report which lasers were tested
            if results.get('laser1_connected'):
                self.progress_display.log_message("Laser 1: Successfully tested", "success")
            if results.get('laser2_connected'):
                self.progress_display.log_message("Laser 2: Successfully tested", "success")

        else:
            self.progress_display.update_progress(100, "Test completed with errors")
            self.progress_display.log_message("\\n=== TEST FAILED ===", "error")

    def _stop_test(self):
        """Stop the running test"""
        if self.test_running:
            self.test_running = False
            self.message_queue.put(("log", ("Test stopped by user", "warning")))

    def _configure_maskhub(self):
        """Open MaskHub configuration dialog"""
        # Use the same configuration dialog from the original GUI
        config_window = tk.Toplevel(self.root)
        config_window.title("MaskHub Configuration")
        config_window.geometry("600x400")
        config_window.transient(self.root)
        config_window.grab_set()

        config_text = scrolledtext.ScrolledText(config_window, height=20, width=70)
        config_text.pack(fill='both', expand=True, padx=10, pady=10)

        # Load current config
        config_path = Path("maskhub_config.json")
        example_path = Path("maskhub_config.example.json")

        if config_path.exists():
            with open(config_path, 'r') as f:
                config_content = f.read()
        elif example_path.exists():
            with open(example_path, 'r') as f:
                config_content = f.read()
        else:
            config_content = '''{\n  "credentials": {\n    "api_url": "https://maskhub.psiquantum.com/api",\n    "api_v3_url": "https://maskhub.psiquantum.com/api/v3",\n    "api_token": "your-api-token-here"\n  }\n}'''

        config_text.insert(1.0, config_content)

        # Buttons
        button_frame = ttk.Frame(config_window)
        button_frame.pack(fill='x', padx=10, pady=(0, 10))

        def save_config():
            content = config_text.get(1.0, tk.END).strip()
            try:
                json.loads(content)
                with open(config_path, 'w') as f:
                    f.write(content)
                messagebox.showinfo("Success", "Configuration saved successfully!")
                config_window.destroy()
                self._initialize_maskhub()
            except json.JSONDecodeError as e:
                messagebox.showerror("Error", f"Invalid JSON: {e}")

        ttk.Button(button_frame, text="Save", command=save_config).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=config_window.destroy).pack(side='left')

    def _save_results(self):
        """Save test results to file"""
        results_content = self.progress_display.results_text.get(1.0, tk.END)

        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialvalue=f"dual_laser_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write(results_content)
                messagebox.showinfo("Success", f"Results saved to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save results: {e}")

    def run(self):
        """Start the GUI application"""
        try:
            self.root.mainloop()
        finally:
            # Clean up
            if self.maskhub_integration:
                self.maskhub_integration.close()


def main():
    """Main entry point"""
    app = EnhancedEndToEndTestGUI()
    app.run()


if __name__ == "__main__":
    main()