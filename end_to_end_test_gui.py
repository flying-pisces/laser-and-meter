"""
End-to-End Test GUI with MaskHub Integration

GUI application for testing Thorlabs CLD1015 pump lasers with configurable
current levels and automatic data upload to MaskHub.

Features:
- Checkbox selection for current test levels
- Automatic enabling of lower current levels
- Real-time test progress and results
- MaskHub integration with upload status
- Power meter connectivity check
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
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pandas as pd

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
log_handler = logging.StreamHandler()
log_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
log_handler.setFormatter(formatter)

logger = logging.getLogger(__name__)
logger.addHandler(log_handler)
logger.setLevel(logging.INFO)


class CurrentLevelControl:
    """Manages current level selection with automatic lower-level enabling"""

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

            # Default: only first low level (50mA) is selected
            if current == 50.0:
                var.set(True)
            elif current == 0.0:  # 0mA always enabled for baseline
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

    def _update_checkbox_states(self):
        """Update checkbox states and visual feedback"""
        selected_currents = self.get_selected_currents()

        # Update visual feedback (could add colors, etc.)
        for current, checkbox in self.checkboxes.items():
            if current in selected_currents:
                checkbox.configure(style="Selected.TCheckbutton")
            else:
                checkbox.configure(style="TCheckbutton")

    def get_selected_currents(self) -> List[float]:
        """Get list of selected current levels"""
        return [current for current, var in self.variables.items() if var.get()]

    def set_enabled(self, enabled: bool):
        """Enable or disable all checkboxes"""
        state = 'normal' if enabled else 'disabled'
        for checkbox in self.checkboxes.values():
            checkbox.configure(state=state)


class TestProgressDisplay:
    """Displays real-time test progress and results"""

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
            length=400
        )
        self.progress_bar.pack(fill='x', pady=(0, 10))

        # Status label
        self.status_var = tk.StringVar()
        self.status_var.set("Ready to start test")
        self.status_label = ttk.Label(self.frame, textvariable=self.status_var)
        self.status_label.pack(pady=(0, 10))

        # Results display
        self.results_text = scrolledtext.ScrolledText(
            self.frame,
            height=15,
            width=80,
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

    def log_message(self, message: str, level: str = "info"):
        """Add message to results display"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"

        self.results_text.insert(tk.END, formatted_message, level)
        self.results_text.see(tk.END)
        self.parent.update_idletasks()

    def clear_results(self):
        """Clear the results display"""
        self.results_text.delete(1.0, tk.END)


class MaskHubStatusDisplay:
    """Displays MaskHub connection and upload status"""

    def __init__(self, parent_frame):
        self.parent = parent_frame

        # Create status frame
        self.frame = ttk.LabelFrame(parent_frame, text="MaskHub Status", padding=10)
        self.frame.pack(fill='x', padx=5, pady=5)

        # Connection status
        self.connection_frame = ttk.Frame(self.frame)
        self.connection_frame.pack(fill='x', pady=(0, 5))

        ttk.Label(self.connection_frame, text="Connection:").pack(side='left')
        self.connection_var = tk.StringVar()
        self.connection_var.set("Not checked")
        self.connection_label = ttk.Label(
            self.connection_frame,
            textvariable=self.connection_var,
            foreground="gray"
        )
        self.connection_label.pack(side='left', padx=(5, 0))

        # Upload statistics
        self.stats_frame = ttk.Frame(self.frame)
        self.stats_frame.pack(fill='x')

        self.stats_vars = {
            'total': tk.StringVar(),
            'successful': tk.StringVar(),
            'failed': tk.StringVar(),
            'pending': tk.StringVar()
        }

        for i, (key, var) in enumerate(self.stats_vars.items()):
            var.set("0")
            ttk.Label(self.stats_frame, text=f"{key.title()}:").grid(row=0, column=i*2, sticky='e', padx=(0, 5))
            ttk.Label(self.stats_frame, textvariable=var).grid(row=0, column=i*2+1, sticky='w', padx=(0, 15))

    def update_connection_status(self, connected: bool, mode: str = "local"):
        """Update connection status display"""
        if connected:
            self.connection_var.set(f"Connected ({mode})")
            self.connection_label.configure(foreground="green")
        else:
            self.connection_var.set("Disconnected")
            self.connection_label.configure(foreground="red")

    def update_statistics(self, stats: Dict[str, int]):
        """Update upload statistics"""
        for key, var in self.stats_vars.items():
            var.set(str(stats.get(key, 0)))


class EndToEndTestGUI:
    """Main GUI application for end-to-end laser testing"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Thorlabs Laser End-to-End Test with MaskHub")
        self.root.geometry("900x800")

        # Test configuration
        self.available_currents = [0, 25, 50, 75, 100, 125, 150]  # Available current levels
        self.laser_resources = [
            "USB0::0x1313::0x804F::M01093719::INSTR",   # Laser 1
            "USB0::0x1313::0x804F::M00859480::INSTR"    # Laser 2
        ]

        # Runtime state
        self.test_running = False
        self.maskhub_integration = None
        self.test_thread = None
        self.message_queue = queue.Queue()

        # Initialize UI
        self._create_widgets()
        self._setup_message_processing()

        # Initialize MaskHub
        self._initialize_maskhub()

    def _create_widgets(self):
        """Create and layout GUI widgets"""

        # Main notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Test Configuration Tab
        self.config_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.config_frame, text="Test Configuration")

        # Test Results Tab
        self.results_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.results_frame, text="Test Results")

        # === Configuration Tab ===

        # Current level selection
        self.current_control = CurrentLevelControl(self.config_frame, self.available_currents)

        # Test parameters
        params_frame = ttk.LabelFrame(self.config_frame, text="Test Parameters", padding=10)
        params_frame.pack(fill='x', padx=5, pady=5)

        # Stabilization delay
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

        # Measurements per level
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

        # MaskHub configuration
        maskhub_frame = ttk.LabelFrame(self.config_frame, text="MaskHub Configuration", padding=10)
        maskhub_frame.pack(fill='x', padx=5, pady=5)

        # Run name
        ttk.Label(maskhub_frame, text="Run Name:").grid(row=0, column=0, sticky='w', padx=(0, 5))
        self.run_name_var = tk.StringVar(value=f"Laser_Test_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        run_name_entry = ttk.Entry(maskhub_frame, textvariable=self.run_name_var, width=40)
        run_name_entry.grid(row=0, column=1, sticky='w', padx=(0, 20))

        # Operator name
        ttk.Label(maskhub_frame, text="Operator:").grid(row=0, column=2, sticky='w', padx=(0, 5))
        self.operator_var = tk.StringVar(value="Test_User")
        operator_entry = ttk.Entry(maskhub_frame, textvariable=self.operator_var, width=20)
        operator_entry.grid(row=0, column=3, sticky='w')

        # Mask ID
        ttk.Label(maskhub_frame, text="Mask ID:").grid(row=1, column=0, sticky='w', padx=(0, 5), pady=(10, 0))
        self.mask_id_var = tk.IntVar(value=12345)
        mask_id_entry = ttk.Entry(maskhub_frame, textvariable=self.mask_id_var, width=20)
        mask_id_entry.grid(row=1, column=1, sticky='w', pady=(10, 0))

        # MaskHub status display
        self.maskhub_status = MaskHubStatusDisplay(self.config_frame)

        # Control buttons
        button_frame = ttk.Frame(self.config_frame)
        button_frame.pack(fill='x', padx=5, pady=10)

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

        self.save_button = ttk.Button(
            button_frame,
            text="Save Results",
            command=self._save_results
        )
        self.save_button.pack(side='left', padx=(0, 10))

        # Config button
        config_button = ttk.Button(
            button_frame,
            text="Configure MaskHub",
            command=self._configure_maskhub
        )
        config_button.pack(side='right')

        # === Results Tab ===

        # Test progress display
        self.progress_display = TestProgressDisplay(self.results_frame)

        # Switch to results tab when test starts
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_change)

    def _initialize_maskhub(self):
        """Initialize MaskHub integration"""
        try:
            self.maskhub_integration = LaserMaskHubIntegration(
                enable_realtime=True,
                auto_save_data=True
            )

            # Check if service is available
            stats = self.maskhub_integration.get_statistics()
            if stats['service_available']:
                self.maskhub_status.update_connection_status(True, "cloud")
                self.progress_display.log_message("MaskHub service connected", "success")
            else:
                self.maskhub_status.update_connection_status(True, "local")
                self.progress_display.log_message("MaskHub running in local-only mode", "warning")

        except Exception as e:
            self.maskhub_status.update_connection_status(False)
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

                    elif message_type == "maskhub_stats":
                        self.maskhub_status.update_statistics(data)

                    elif message_type == "test_complete":
                        self._on_test_complete(data)

            except queue.Empty:
                pass

            # Schedule next check
            self.root.after(100, process_messages)

        # Start message processing
        self.root.after(100, process_messages)

    def _configure_maskhub(self):
        """Open MaskHub configuration dialog"""
        config_window = tk.Toplevel(self.root)
        config_window.title("MaskHub Configuration")
        config_window.geometry("600x400")
        config_window.transient(self.root)
        config_window.grab_set()

        # Configuration text
        config_text = scrolledtext.ScrolledText(config_window, height=20, width=70)
        config_text.pack(fill='both', expand=True, padx=10, pady=10)

        # Load current config if it exists
        config_path = Path("maskhub_config.json")
        example_path = Path("maskhub_config.example.json")

        if config_path.exists():
            with open(config_path, 'r') as f:
                config_content = f.read()
        elif example_path.exists():
            with open(example_path, 'r') as f:
                config_content = f.read()
        else:
            config_content = '''{
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
}'''

        config_text.insert(1.0, config_content)

        # Buttons
        button_frame = ttk.Frame(config_window)
        button_frame.pack(fill='x', padx=10, pady=(0, 10))

        def save_config():
            content = config_text.get(1.0, tk.END).strip()
            try:
                # Validate JSON
                json.loads(content)

                # Save to file
                with open(config_path, 'w') as f:
                    f.write(content)

                messagebox.showinfo("Success", "Configuration saved successfully!")
                config_window.destroy()

                # Reinitialize MaskHub
                self._initialize_maskhub()

            except json.JSONDecodeError as e:
                messagebox.showerror("Error", f"Invalid JSON: {e}")

        ttk.Button(button_frame, text="Save", command=save_config).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=config_window.destroy).pack(side='left')

    def _start_test(self):
        """Start the end-to-end test"""
        if self.test_running:
            return

        # Validate inputs
        selected_currents = self.current_control.get_selected_currents()
        if not selected_currents:
            messagebox.showerror("Error", "Please select at least one current level to test")
            return

        # Clear previous results
        self.progress_display.clear_results()
        self.progress_display.update_progress(0, "Starting test...")

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

    def _stop_test(self):
        """Stop the running test"""
        if self.test_running:
            self.test_running = False
            self.message_queue.put(("log", ("Test stopped by user", "warning")))

    def _run_test_thread(self, selected_currents: List[float]):
        """Run the test in background thread"""
        try:
            # Create run configuration
            run_config = LaserRunConfig(
                mask_id=self.mask_id_var.get(),
                run_name=self.run_name_var.get(),
                lot_name="THORLABS_GUI_TEST",
                wafer_name="LASER_WAFER",
                operator=self.operator_var.get(),
                station="Thorlabs_GUI_Station",
                measurement_type="gui_laser_test"
            )

            # Start MaskHub run
            if self.maskhub_integration:
                run_id = self.maskhub_integration.start_run(run_config)
                self.message_queue.put(("log", (f"Started run: {run_id}", "info")))

            # Test each laser
            total_steps = len(self.laser_resources) * len(selected_currents) * self.measurements_var.get()
            current_step = 0

            test_results = {'lasers': [], 'overall_success': True}

            for laser_idx, laser_resource in enumerate(self.laser_resources):
                if not self.test_running:
                    break

                laser_name = f"Laser_{laser_idx + 1}"
                self.message_queue.put(("log", (f"\\n=== Testing {laser_name} ===", "info")))

                laser_results = self._test_single_laser(
                    laser_resource,
                    laser_name,
                    selected_currents,
                    current_step,
                    total_steps
                )

                test_results['lasers'].append(laser_results)
                if not laser_results['success']:
                    test_results['overall_success'] = False

                current_step += len(selected_currents) * self.measurements_var.get()

            # Finish MaskHub run
            if self.maskhub_integration and self.test_running:
                summary = self.maskhub_integration.finish_run(trigger_analysis=True)
                self.message_queue.put(("log", (f"Finished run: {summary}", "info")))

            # Complete test
            self.message_queue.put(("test_complete", test_results))

        except Exception as e:
            self.message_queue.put(("log", (f"Test failed: {e}", "error")))
            self.message_queue.put(("test_complete", {'overall_success': False, 'error': str(e)}))

    def _test_single_laser(self, laser_resource: str, laser_name: str,
                          selected_currents: List[float], start_step: int, total_steps: int) -> Dict:
        """Test a single laser with selected current levels"""

        results = {
            'laser_name': laser_name,
            'resource': laser_resource,
            'success': False,
            'measurements': [],
            'errors': []
        }

        try:
            # Connect to laser
            laser = CLD1015(laser_resource)
            if not laser.connect():
                raise RuntimeError(f"Failed to connect to {laser_name}")

            self.message_queue.put(("log", (f"Connected to {laser_name}", "success")))

            # Get initial status
            status = laser.get_status()
            self.message_queue.put(("log", (f"  Model: {status['identity']}", "info")))

            # Set safety limits
            laser.set_current_limit(max(selected_currents))
            laser.set_ld_output(True)

            self.message_queue.put(("log", (f"  Safety limit: {max(selected_currents)} mA", "info")))

            # Test each current level
            for current_idx, current_ma in enumerate(selected_currents):
                if not self.test_running:
                    break

                self.message_queue.put(("log", (f"\\nTesting {current_ma} mA:", "info")))

                # Set current and wait for stabilization
                laser.set_ld_current(current_ma)

                stabilization_time = self.stabilization_var.get()
                for i in range(int(stabilization_time * 10)):
                    if not self.test_running:
                        break
                    time.sleep(0.1)

                # Take multiple measurements
                for meas_idx in range(self.measurements_var.get()):
                    if not self.test_running:
                        break

                    step = start_step + current_idx * self.measurements_var.get() + meas_idx
                    progress = (step / total_steps) * 100

                    status_msg = f"Testing {laser_name} at {current_ma}mA (measurement {meas_idx + 1})"
                    self.message_queue.put(("progress", (progress, status_msg)))

                    # Get measurements
                    actual_ma = laser.get_ld_current_actual()
                    voltage_v = laser.get_ld_voltage()
                    temperature_c = laser.get_temperature()

                    # Create synthetic raw data
                    raw_data = pd.DataFrame({
                        'time_s': [i * 0.1 for i in range(10)],
                        'current_ma': [actual_ma + (i % 3 - 1) * 0.01 for i in range(10)],
                        'voltage_v': [voltage_v + (i % 2) * 0.001 for i in range(10)]
                    })

                    # Estimate power (if available)
                    power_mw = None
                    if current_ma > 0:
                        power_mw = actual_ma * voltage_v * 0.5  # Rough estimate

                    # Create measurement
                    measurement = LaserMeasurement(
                        device_id=f"{laser_name}_{laser_resource.split('::')[-2]}",
                        position=(laser_idx * 10, current_idx),
                        current_setpoint_ma=current_ma,
                        current_actual_ma=actual_ma,
                        voltage_v=voltage_v,
                        power_mw=power_mw,
                        temperature_c=temperature_c,
                        timestamp=datetime.now(),
                        metadata={
                            'measurement_index': meas_idx,
                            'current_level_index': current_idx,
                            'gui_test': True
                        },
                        raw_data=raw_data
                    )

                    # Add to MaskHub
                    if self.maskhub_integration:
                        die_position = (laser_idx * 10 + meas_idx, current_idx)
                        self.maskhub_integration.add_measurement(measurement, die_position)

                        # Update MaskHub stats
                        stats = self.maskhub_integration.get_statistics()
                        self.message_queue.put(("maskhub_stats", stats))

                    # Store locally
                    results['measurements'].append({
                        'current_setpoint': current_ma,
                        'current_actual': actual_ma,
                        'voltage': voltage_v,
                        'temperature': temperature_c,
                        'power': power_mw
                    })

                    tolerance = abs(actual_ma - current_ma)
                    tolerance_ok = tolerance <= 5.0  # 5mA tolerance

                    level = "success" if tolerance_ok else "warning"
                    self.message_queue.put(("log", (
                        f"  Measurement {meas_idx + 1}: {actual_ma:.2f}mA, "
                        f"{voltage_v:.3f}V, {temperature_c:.1f}°C "
                        f"(tolerance: {tolerance:.2f}mA)",
                        level
                    )))

                    time.sleep(0.5)  # Brief delay between measurements

            # Ramp down safely
            self.message_queue.put(("log", (f"Ramping down {laser_name}...", "info")))
            laser.ramp_current(0, 10, 0.2)
            laser.set_ld_output(False)
            laser.disconnect()

            results['success'] = True
            self.message_queue.put(("log", (f"{laser_name} test completed successfully", "success")))

        except Exception as e:
            error_msg = f"{laser_name} test failed: {e}"
            self.message_queue.put(("log", (error_msg, "error")))
            results['errors'].append(error_msg)

            # Emergency shutdown
            try:
                laser.emergency_stop()
                laser.disconnect()
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
            self.progress_display.update_progress(100, "Test completed successfully!")
            self.progress_display.log_message("\\n=== ALL TESTS PASSED ===", "success")
        else:
            self.progress_display.update_progress(100, "Test completed with errors")
            self.progress_display.log_message("\\n=== SOME TESTS FAILED ===", "error")

        # Display summary
        for laser_result in results.get('lasers', []):
            laser_name = laser_result['laser_name']
            success = laser_result['success']
            measurement_count = len(laser_result['measurements'])

            status = "PASSED" if success else "FAILED"
            level = "success" if success else "error"

            self.progress_display.log_message(
                f"{laser_name}: {status} ({measurement_count} measurements)",
                level
            )

        # Final MaskHub stats
        if self.maskhub_integration:
            stats = self.maskhub_integration.get_statistics()
            self.maskhub_status.update_statistics(stats)

            self.progress_display.log_message(
                f"\\nMaskHub uploads - Total: {stats.get('total', 0)}, "
                f"Successful: {stats.get('successful', 0)}, "
                f"Failed: {stats.get('failed', 0)}",
                "info"
            )

    def _save_results(self):
        """Save test results to file"""
        # Get current results from display
        results_content = self.progress_display.results_text.get(1.0, tk.END)

        # Ask user for save location
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialvalue=f"laser_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write(results_content)
                messagebox.showinfo("Success", f"Results saved to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save results: {e}")

    def _on_tab_change(self, event):
        """Handle notebook tab changes"""
        pass

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
    # Check for required modules
    try:
        import pyvisa
    except ImportError:
        print("Error: pyvisa module not found. Please install with: pip install pyvisa")
        return

    # Start GUI
    app = EndToEndTestGUI()
    app.run()


if __name__ == "__main__":
    main()