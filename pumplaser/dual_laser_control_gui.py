#!/usr/bin/env python3
"""
Dual Laser Control GUI with Power Meter Integration

Features:
- Control and monitor two CLD1015 pump lasers simultaneously
- Real-time status display for both lasers
- Integrated power meter readings
- Safety features with minimum current verification
- Scan functionality for parameter sweeps
- Emergency stop capability
"""

import os
import sys
import pathlib
import glob
import time
import csv
import datetime
import threading
import queue
from typing import Optional, Dict, List, Tuple
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pyvisa

# Add modules to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Python-Driver-for-Thorlabs-power-meter'))
sys.path.extend(glob.glob(f'{pathlib.Path(__file__).parent.parent.resolve()}/Python-Driver-for-Thorlabs-power-meter/*/**/', recursive=True))

# Import laser and power meter modules
from pump_laser import CLD1015, list_visa_resources
from ThorlabsPowerMeter import ThorlabsPowerMeter


class LaserControlPanel(ttk.LabelFrame):
    """Control panel for a single laser with safety features."""

    def __init__(self, parent, laser_name: str, resource_name: str = None):
        super().__init__(parent, text=laser_name, padding="10")
        self.laser_name = laser_name
        self.resource_name = resource_name
        self.laser = None
        self.is_connected = False
        self.safety_min_current = 100  # Safety minimum current (mA)
        self.safety_max_current = 1500  # Safety maximum current (mA)

        self.setup_ui()

    def setup_ui(self):
        """Create the control panel UI elements."""
        # Connection status
        self.status_frame = ttk.Frame(self)
        self.status_frame.grid(row=0, column=0, columnspan=3, sticky='ew', pady=5)

        self.status_label = ttk.Label(self.status_frame, text="Status:")
        self.status_label.grid(row=0, column=0, padx=(0,5))

        self.connection_status = ttk.Label(self.status_frame, text="Disconnected",
                                          foreground="red", font=('Arial', 10, 'bold'))
        self.connection_status.grid(row=0, column=1)

        self.connect_btn = ttk.Button(self.status_frame, text="Connect",
                                     command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=2, padx=(20,0))

        # Device info
        self.device_info = ttk.Label(self, text="Device: Not connected",
                                     font=('Courier', 9))
        self.device_info.grid(row=1, column=0, columnspan=3, sticky='w', pady=2)

        # Separator
        ttk.Separator(self, orient='horizontal').grid(row=2, column=0, columnspan=3,
                                                      sticky='ew', pady=10)

        # Current control
        ttk.Label(self, text="Current Control", font=('Arial', 10, 'bold')).grid(
            row=3, column=0, columnspan=2, sticky='w', pady=(0,5))

        # Current setpoint
        ttk.Label(self, text="Setpoint (mA):").grid(row=4, column=0, sticky='w')
        self.current_var = tk.DoubleVar(value=0)
        self.current_spinbox = ttk.Spinbox(self, from_=0, to=self.safety_max_current,
                                           increment=10, textvariable=self.current_var,
                                           width=10, state='disabled')
        self.current_spinbox.grid(row=4, column=1, padx=5)

        self.set_current_btn = ttk.Button(self, text="Set",
                                         command=self.set_current,
                                         state='disabled')
        self.set_current_btn.grid(row=4, column=2, padx=5)

        # Current readback
        ttk.Label(self, text="Actual (mA):").grid(row=5, column=0, sticky='w')
        self.actual_current_label = ttk.Label(self, text="---",
                                              font=('Courier', 10, 'bold'))
        self.actual_current_label.grid(row=5, column=1, sticky='w', padx=5)

        # Voltage readback
        ttk.Label(self, text="Voltage (V):").grid(row=6, column=0, sticky='w')
        self.voltage_label = ttk.Label(self, text="---",
                                       font=('Courier', 10, 'bold'))
        self.voltage_label.grid(row=6, column=1, sticky='w', padx=5)

        # Current limit
        ttk.Label(self, text="Limit (mA):").grid(row=7, column=0, sticky='w')
        self.limit_var = tk.DoubleVar(value=1000)
        self.limit_spinbox = ttk.Spinbox(self, from_=0, to=self.safety_max_current,
                                         increment=10, textvariable=self.limit_var,
                                         width=10, state='disabled')
        self.limit_spinbox.grid(row=7, column=1, padx=5)

        self.set_limit_btn = ttk.Button(self, text="Set",
                                       command=self.set_current_limit,
                                       state='disabled')
        self.set_limit_btn.grid(row=7, column=2, padx=5)

        # Separator
        ttk.Separator(self, orient='horizontal').grid(row=8, column=0, columnspan=3,
                                                      sticky='ew', pady=10)

        # Temperature monitoring
        ttk.Label(self, text="Temperature", font=('Arial', 10, 'bold')).grid(
            row=9, column=0, columnspan=2, sticky='w', pady=(0,5))

        ttk.Label(self, text="Temperature (°C):").grid(row=10, column=0, sticky='w')
        self.temperature_label = ttk.Label(self, text="---",
                                          font=('Courier', 10, 'bold'))
        self.temperature_label.grid(row=10, column=1, sticky='w', padx=5)

        ttk.Label(self, text="TEC Status:").grid(row=11, column=0, sticky='w')
        self.tec_status_label = ttk.Label(self, text="---",
                                         font=('Courier', 10))
        self.tec_status_label.grid(row=11, column=1, sticky='w', padx=5)

        # Separator
        ttk.Separator(self, orient='horizontal').grid(row=12, column=0, columnspan=3,
                                                      sticky='ew', pady=10)

        # Output control
        self.output_frame = ttk.Frame(self)
        self.output_frame.grid(row=13, column=0, columnspan=3, pady=5)

        self.output_var = tk.BooleanVar(value=False)
        self.output_checkbox = ttk.Checkbutton(self.output_frame, text="Laser Output",
                                               variable=self.output_var,
                                               command=self.toggle_output,
                                               state='disabled')
        self.output_checkbox.grid(row=0, column=0, padx=5)

        self.output_indicator = tk.Canvas(self.output_frame, width=20, height=20)
        self.output_indicator.grid(row=0, column=1, padx=5)
        self.update_output_indicator(False)

        # Ramp control
        self.ramp_frame = ttk.LabelFrame(self, text="Ramp Control", padding="5")
        self.ramp_frame.grid(row=14, column=0, columnspan=3, sticky='ew', pady=10)

        ttk.Label(self.ramp_frame, text="Target (mA):").grid(row=0, column=0, sticky='w')
        self.ramp_target_var = tk.DoubleVar(value=0)
        self.ramp_target_spinbox = ttk.Spinbox(self.ramp_frame, from_=0,
                                               to=self.safety_max_current,
                                               increment=10,
                                               textvariable=self.ramp_target_var,
                                               width=8, state='disabled')
        self.ramp_target_spinbox.grid(row=0, column=1, padx=5)

        ttk.Label(self.ramp_frame, text="Step (mA):").grid(row=0, column=2, sticky='w', padx=(10,0))
        self.ramp_step_var = tk.DoubleVar(value=10)
        self.ramp_step_spinbox = ttk.Spinbox(self.ramp_frame, from_=1, to=100,
                                             increment=5,
                                             textvariable=self.ramp_step_var,
                                             width=6, state='disabled')
        self.ramp_step_spinbox.grid(row=0, column=3, padx=5)

        self.ramp_btn = ttk.Button(self.ramp_frame, text="Start Ramp",
                                  command=self.start_ramp,
                                  state='disabled')
        self.ramp_btn.grid(row=1, column=0, columnspan=4, pady=5)

        # Error display
        self.error_label = ttk.Label(self, text="", foreground="red",
                                    font=('Arial', 9))
        self.error_label.grid(row=15, column=0, columnspan=3, sticky='w', pady=5)

    def toggle_connection(self):
        """Toggle laser connection."""
        if self.is_connected:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        """Connect to the laser."""
        if not self.resource_name:
            self.show_error("No resource name specified")
            return

        try:
            self.laser = CLD1015(self.resource_name)
            if self.laser.connect():
                self.is_connected = True
                self.connection_status.config(text="Connected", foreground="green")
                self.connect_btn.config(text="Disconnect")

                # Enable controls
                self.current_spinbox.config(state='normal')
                self.set_current_btn.config(state='normal')
                self.limit_spinbox.config(state='normal')
                self.set_limit_btn.config(state='normal')
                self.output_checkbox.config(state='normal')
                self.ramp_target_spinbox.config(state='normal')
                self.ramp_step_spinbox.config(state='normal')
                self.ramp_btn.config(state='normal')

                # Get device info
                identity = self.laser.get_identity()
                parts = identity.split(',')
                if len(parts) >= 3:
                    self.device_info.config(text=f"Device: {parts[2].strip()}")

                # Initialize safe state
                self.laser.set_ld_output(False)
                self.laser.set_current_limit(self.limit_var.get())

                # Update status
                self.update_status()

                self.show_error("")  # Clear any previous errors
            else:
                self.show_error("Failed to connect")
        except Exception as e:
            self.show_error(f"Connection error: {e}")

    def disconnect(self):
        """Disconnect from the laser."""
        if self.laser:
            try:
                # Safety: turn off output before disconnecting
                self.laser.set_ld_output(False)
                self.laser.disconnect()
            except:
                pass

        self.laser = None
        self.is_connected = False
        self.connection_status.config(text="Disconnected", foreground="red")
        self.connect_btn.config(text="Connect")
        self.device_info.config(text="Device: Not connected")

        # Disable controls
        self.current_spinbox.config(state='disabled')
        self.set_current_btn.config(state='disabled')
        self.limit_spinbox.config(state='disabled')
        self.set_limit_btn.config(state='disabled')
        self.output_checkbox.config(state='disabled')
        self.ramp_target_spinbox.config(state='disabled')
        self.ramp_step_spinbox.config(state='disabled')
        self.ramp_btn.config(state='disabled')

        # Reset displays
        self.actual_current_label.config(text="---")
        self.voltage_label.config(text="---")
        self.temperature_label.config(text="---")
        self.tec_status_label.config(text="---")
        self.update_output_indicator(False)
        self.output_var.set(False)

    def set_current(self):
        """Set laser current with safety check."""
        if not self.is_connected:
            return

        try:
            current = self.current_var.get()

            # Safety check
            if current < self.safety_min_current and current > 0:
                if not messagebox.askyesno("Safety Warning",
                    f"Current {current:.1f} mA is below safety minimum {self.safety_min_current} mA.\n"
                    "Are you sure you want to proceed?"):
                    return

            if current > self.safety_max_current:
                messagebox.showerror("Safety Limit",
                    f"Current cannot exceed {self.safety_max_current} mA")
                return

            self.laser.set_ld_current(current)
            self.show_error("")
            time.sleep(0.1)  # Allow time for current to settle
            self.update_status()
        except Exception as e:
            self.show_error(f"Set current error: {e}")

    def set_current_limit(self):
        """Set laser current limit."""
        if not self.is_connected:
            return

        try:
            limit = self.limit_var.get()

            if limit > self.safety_max_current:
                messagebox.showerror("Safety Limit",
                    f"Limit cannot exceed {self.safety_max_current} mA")
                return

            self.laser.set_current_limit(limit)
            self.show_error("")
            self.update_status()
        except Exception as e:
            self.show_error(f"Set limit error: {e}")

    def toggle_output(self):
        """Toggle laser output with safety verification."""
        if not self.is_connected:
            return

        try:
            enable = self.output_var.get()

            if enable:
                # Safety check before enabling
                current_setpoint = self.laser.get_ld_current_setpoint()
                if current_setpoint > self.safety_max_current:
                    messagebox.showerror("Safety Check",
                        f"Current setpoint {current_setpoint:.1f} mA exceeds safety limit")
                    self.output_var.set(False)
                    return

                # Verify minimum current for safety
                if current_setpoint < self.safety_min_current:
                    response = messagebox.askyesno("Safety Verification",
                        f"Current setpoint is {current_setpoint:.1f} mA.\n"
                        f"For safety verification, set to minimum {self.safety_min_current} mA?")
                    if response:
                        self.laser.set_ld_current(self.safety_min_current)
                        self.current_var.set(self.safety_min_current)

            self.laser.set_ld_output(enable)
            self.update_output_indicator(enable)
            self.show_error("")
            time.sleep(0.1)
            self.update_status()
        except Exception as e:
            self.show_error(f"Output control error: {e}")
            self.output_var.set(False)

    def start_ramp(self):
        """Start current ramping in a separate thread."""
        if not self.is_connected:
            return

        target = self.ramp_target_var.get()
        step = self.ramp_step_var.get()

        if target > self.safety_max_current:
            messagebox.showerror("Safety Limit",
                f"Target cannot exceed {self.safety_max_current} mA")
            return

        # Run ramp in thread to avoid blocking GUI
        thread = threading.Thread(target=self._ramp_current, args=(target, step))
        thread.daemon = True
        thread.start()

    def _ramp_current(self, target: float, step: float):
        """Execute current ramp."""
        try:
            self.ramp_btn.config(state='disabled', text="Ramping...")
            self.laser.ramp_current(target, step, delay_s=0.2)
            self.current_var.set(target)
            self.update_status()
        except Exception as e:
            self.show_error(f"Ramp error: {e}")
        finally:
            self.ramp_btn.config(state='normal', text="Start Ramp")

    def update_status(self):
        """Update all status displays."""
        if not self.is_connected:
            return

        try:
            # Current readings
            actual_current = self.laser.get_ld_current_actual()
            self.actual_current_label.config(text=f"{actual_current:.1f}")

            # Voltage reading
            voltage = self.laser.get_ld_voltage()
            self.voltage_label.config(text=f"{voltage:.2f}")

            # Temperature reading
            temperature = self.laser.get_temperature()
            self.temperature_label.config(text=f"{temperature:.1f}")

            # TEC status
            tec_enabled = self.laser.get_tec_output_state()
            self.tec_status_label.config(text="ON" if tec_enabled else "OFF",
                                        foreground="green" if tec_enabled else "gray")

            # Output status
            output_enabled = self.laser.get_ld_output_state()
            self.output_var.set(output_enabled)
            self.update_output_indicator(output_enabled)

        except Exception as e:
            self.show_error(f"Status update error: {e}")

    def update_output_indicator(self, is_on: bool):
        """Update the output indicator LED."""
        self.output_indicator.delete("all")
        color = "red" if is_on else "gray"
        self.output_indicator.create_oval(2, 2, 18, 18, fill=color, outline="black")

    def show_error(self, message: str):
        """Display error message."""
        self.error_label.config(text=message)

    def emergency_stop(self):
        """Emergency stop - disable output immediately."""
        if self.laser:
            try:
                self.laser.emergency_stop()
                self.output_var.set(False)
                self.update_output_indicator(False)
                self.show_error("EMERGENCY STOP EXECUTED")
            except:
                pass


class DualLaserControlGUI:
    """Main GUI for controlling two lasers and power meter."""

    def __init__(self, root):
        self.root = root
        self.root.title("Dual Laser Control System with Power Meter")
        self.root.geometry("1400x800")

        # Power meter
        self.power_meter = None
        self.power_meter_connected = False

        # Scanning state
        self.scan_running = False
        self.scan_thread = None
        self.scan_data = []

        # Update timer
        self.update_timer = None

        self.setup_ui()
        self.detect_devices()
        self.start_periodic_updates()

    def setup_ui(self):
        """Create the main GUI layout."""
        # Top frame for title and emergency stop
        self.top_frame = ttk.Frame(self.root)
        self.top_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(self.top_frame, text="Dual Pump Laser Control System",
                 font=('Arial', 16, 'bold')).pack(side='left')

        self.emergency_btn = tk.Button(self.top_frame, text="EMERGENCY STOP",
                                      command=self.emergency_stop_all,
                                      bg='red', fg='white', font=('Arial', 12, 'bold'),
                                      padx=20, pady=10)
        self.emergency_btn.pack(side='right', padx=10)

        # Main container
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill='both', expand=True, padx=10, pady=5)

        # Left side - Laser 1
        self.laser1_panel = LaserControlPanel(self.main_frame,
                                             "Laser 1 - M01093719",
                                             "USB0::0x1313::0x804F::M01093719::0::INSTR")
        self.laser1_panel.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)

        # Middle side - Laser 2
        self.laser2_panel = LaserControlPanel(self.main_frame,
                                             "Laser 2 - M00859480",
                                             "USB0::0x1313::0x804F::M00859480::0::INSTR")
        self.laser2_panel.grid(row=0, column=1, sticky='nsew', padx=5, pady=5)

        # Right side - Power meter and scan controls
        self.right_frame = ttk.Frame(self.main_frame)
        self.right_frame.grid(row=0, column=2, sticky='nsew', padx=5, pady=5)

        # Power meter section
        self.power_frame = ttk.LabelFrame(self.right_frame, text="Power Meter",
                                         padding="10")
        self.power_frame.pack(fill='x', pady=(0, 10))

        # Power meter status
        self.pm_status_label = ttk.Label(self.power_frame, text="Status: Disconnected",
                                        foreground="red", font=('Arial', 10, 'bold'))
        self.pm_status_label.pack(anchor='w')

        self.pm_device_label = ttk.Label(self.power_frame, text="Device: ---",
                                        font=('Courier', 9))
        self.pm_device_label.pack(anchor='w', pady=2)

        # Connect button
        self.pm_connect_btn = ttk.Button(self.power_frame, text="Connect Power Meter",
                                        command=self.connect_power_meter)
        self.pm_connect_btn.pack(pady=10)

        # Power reading display
        ttk.Label(self.power_frame, text="Power Reading:",
                 font=('Arial', 10)).pack(anchor='w', pady=(10,0))

        self.power_display = ttk.Label(self.power_frame, text="--- mW",
                                      font=('Courier', 16, 'bold'),
                                      foreground="blue")
        self.power_display.pack(pady=5)

        # Wavelength setting
        wavelength_frame = ttk.Frame(self.power_frame)
        wavelength_frame.pack(fill='x', pady=10)

        ttk.Label(wavelength_frame, text="Wavelength (nm):").pack(side='left')
        self.wavelength_var = tk.IntVar(value=1550)
        self.wavelength_spinbox = ttk.Spinbox(wavelength_frame, from_=400, to=1700,
                                              increment=10, textvariable=self.wavelength_var,
                                              width=8, state='disabled')
        self.wavelength_spinbox.pack(side='left', padx=5)

        self.set_wavelength_btn = ttk.Button(wavelength_frame, text="Set",
                                            command=self.set_wavelength,
                                            state='disabled')
        self.set_wavelength_btn.pack(side='left', padx=5)

        # Scan control section
        self.scan_frame = ttk.LabelFrame(self.right_frame, text="Scan Control",
                                        padding="10")
        self.scan_frame.pack(fill='both', expand=True, pady=10)

        # Laser selection
        ttk.Label(self.scan_frame, text="Select Laser:",
                 font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=5)

        self.scan_laser_var = tk.StringVar(value="Laser 1")
        ttk.Radiobutton(self.scan_frame, text="Laser 1",
                       variable=self.scan_laser_var,
                       value="Laser 1").grid(row=0, column=1, padx=5)
        ttk.Radiobutton(self.scan_frame, text="Laser 2",
                       variable=self.scan_laser_var,
                       value="Laser 2").grid(row=0, column=2, padx=5)
        ttk.Radiobutton(self.scan_frame, text="Both",
                       variable=self.scan_laser_var,
                       value="Both").grid(row=0, column=3, padx=5)

        # Scan parameters
        ttk.Label(self.scan_frame, text="Scan Parameters:",
                 font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='w', pady=(10,5))

        # Start current
        ttk.Label(self.scan_frame, text="Start (mA):").grid(row=2, column=0, sticky='w')
        self.scan_start_var = tk.DoubleVar(value=100)
        ttk.Spinbox(self.scan_frame, from_=0, to=1500, increment=10,
                   textvariable=self.scan_start_var, width=10).grid(row=2, column=1, padx=5)

        # Stop current
        ttk.Label(self.scan_frame, text="Stop (mA):").grid(row=3, column=0, sticky='w')
        self.scan_stop_var = tk.DoubleVar(value=500)
        ttk.Spinbox(self.scan_frame, from_=0, to=1500, increment=10,
                   textvariable=self.scan_stop_var, width=10).grid(row=3, column=1, padx=5)

        # Step size
        ttk.Label(self.scan_frame, text="Step (mA):").grid(row=4, column=0, sticky='w')
        self.scan_step_var = tk.DoubleVar(value=50)
        ttk.Spinbox(self.scan_frame, from_=1, to=100, increment=5,
                   textvariable=self.scan_step_var, width=10).grid(row=4, column=1, padx=5)

        # Delay time
        ttk.Label(self.scan_frame, text="Delay (s):").grid(row=5, column=0, sticky='w')
        self.scan_delay_var = tk.DoubleVar(value=1.0)
        ttk.Spinbox(self.scan_frame, from_=0.1, to=10, increment=0.1,
                   textvariable=self.scan_delay_var, width=10).grid(row=5, column=1, padx=5)

        # Scan control buttons
        self.scan_btn = ttk.Button(self.scan_frame, text="Start Scan",
                                  command=self.toggle_scan)
        self.scan_btn.grid(row=6, column=0, columnspan=2, pady=10)

        self.export_btn = ttk.Button(self.scan_frame, text="Export Data",
                                    command=self.export_scan_data,
                                    state='disabled')
        self.export_btn.grid(row=6, column=2, columnspan=2, pady=10)

        # Scan results display
        results_frame = ttk.LabelFrame(self.scan_frame, text="Scan Results", padding="5")
        results_frame.grid(row=7, column=0, columnspan=4, sticky='nsew', pady=10)

        # Create treeview for results
        self.results_tree = ttk.Treeview(results_frame, columns=('Current', 'Power', 'Voltage'),
                                        show='tree headings', height=8)
        self.results_tree.heading('#0', text='Laser')
        self.results_tree.heading('Current', text='Current (mA)')
        self.results_tree.heading('Power', text='Power (mW)')
        self.results_tree.heading('Voltage', text='Voltage (V)')

        self.results_tree.column('#0', width=80)
        self.results_tree.column('Current', width=80)
        self.results_tree.column('Power', width=80)
        self.results_tree.column('Voltage', width=80)

        self.results_tree.pack(side='left', fill='both', expand=True)

        # Scrollbar
        scrollbar = ttk.Scrollbar(results_frame, orient='vertical',
                                 command=self.results_tree.yview)
        scrollbar.pack(side='right', fill='y')
        self.results_tree.configure(yscrollcommand=scrollbar.set)

        # Status bar
        self.status_bar = ttk.Label(self.root, text="Ready", relief='sunken')
        self.status_bar.pack(side='bottom', fill='x', padx=5, pady=2)

        # Configure grid weights
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)
        self.main_frame.columnconfigure(2, weight=1)
        self.main_frame.rowconfigure(0, weight=1)

    def detect_devices(self):
        """Detect and display available devices."""
        try:
            # Detect VISA devices
            visa_resources = list_visa_resources()

            # Update laser panels with detected devices
            laser1_found = False
            laser2_found = False

            for resource in visa_resources:
                if "M01093719" in resource:
                    self.laser1_panel.resource_name = resource
                    laser1_found = True
                elif "M00859480" in resource:
                    self.laser2_panel.resource_name = resource
                    laser2_found = True

            # Update status
            status_text = "Detected devices: "
            if laser1_found:
                status_text += "Laser 1 (M01093719) "
            if laser2_found:
                status_text += "Laser 2 (M00859480) "

            if not laser1_found and not laser2_found:
                status_text = "No laser devices detected"

            self.status_bar.config(text=status_text)

        except Exception as e:
            self.status_bar.config(text=f"Device detection error: {e}")

    def connect_power_meter(self):
        """Connect to the power meter."""
        if self.power_meter_connected:
            # Disconnect
            if self.power_meter:
                try:
                    self.power_meter.disconnect()
                except:
                    pass
            self.power_meter = None
            self.power_meter_connected = False
            self.pm_status_label.config(text="Status: Disconnected", foreground="red")
            self.pm_device_label.config(text="Device: ---")
            self.pm_connect_btn.config(text="Connect Power Meter")
            self.wavelength_spinbox.config(state='disabled')
            self.set_wavelength_btn.config(state='disabled')
            self.power_display.config(text="--- mW")
        else:
            # Connect
            try:
                # Try to connect to power meter
                dll_path = os.path.join(os.path.dirname(__file__), '..',
                                       'Python-Driver-for-Thorlabs-power-meter',
                                       'Thorlabs_DotNet_dll', '')
                deviceList = ThorlabsPowerMeter.listDevices(libraryPath=dll_path)

                if deviceList.resourceCount > 0:
                    self.power_meter = deviceList.connect(deviceList.resourceName[0])
                    if self.power_meter is not None:
                        # Configure power meter
                        self.power_meter.getSensorInfo()
                        self.power_meter.setWaveLength(self.wavelength_var.get())
                        self.power_meter.setPowerAutoRange(True)
                        self.power_meter.setAverageTime(0.1)

                        self.power_meter_connected = True
                        self.pm_status_label.config(text="Status: Connected", foreground="green")
                        self.pm_device_label.config(text=f"Device: {self.power_meter.sensorName}")
                        self.pm_connect_btn.config(text="Disconnect")
                        self.wavelength_spinbox.config(state='normal')
                        self.set_wavelength_btn.config(state='normal')

                        # Start updating power reading
                        self.update_power_reading()
                    else:
                        raise Exception("Failed to connect to power meter")
                else:
                    raise Exception("No power meter detected")

            except Exception as e:
                messagebox.showerror("Connection Error", f"Power meter connection failed: {e}")

    def set_wavelength(self):
        """Set power meter wavelength."""
        if self.power_meter_connected and self.power_meter:
            try:
                wavelength = self.wavelength_var.get()
                self.power_meter.setWaveLength(wavelength)
                self.status_bar.config(text=f"Wavelength set to {wavelength} nm")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to set wavelength: {e}")

    def update_power_reading(self):
        """Update power meter reading."""
        if self.power_meter_connected and self.power_meter:
            try:
                self.power_meter.updatePowerReading(0.1)
                power_mw = self.power_meter.power * 1000  # Convert W to mW
                self.power_display.config(text=f"{power_mw:.3f} mW")
            except:
                self.power_display.config(text="--- mW")

    def toggle_scan(self):
        """Toggle scan operation."""
        if self.scan_running:
            self.stop_scan()
        else:
            self.start_scan()

    def start_scan(self):
        """Start parameter scan."""
        # Verify at least one laser is connected
        laser_selection = self.scan_laser_var.get()

        if laser_selection == "Laser 1" and not self.laser1_panel.is_connected:
            messagebox.showerror("Error", "Laser 1 is not connected")
            return
        elif laser_selection == "Laser 2" and not self.laser2_panel.is_connected:
            messagebox.showerror("Error", "Laser 2 is not connected")
            return
        elif laser_selection == "Both":
            if not self.laser1_panel.is_connected and not self.laser2_panel.is_connected:
                messagebox.showerror("Error", "No lasers are connected")
                return

        # Verify power meter for meaningful scan
        if not self.power_meter_connected:
            response = messagebox.askyesno("Power Meter",
                "Power meter is not connected. Continue without power measurements?")
            if not response:
                return

        self.scan_running = True
        self.scan_btn.config(text="Stop Scan")
        self.scan_data = []

        # Clear previous results
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)

        # Start scan in thread
        self.scan_thread = threading.Thread(target=self._run_scan)
        self.scan_thread.daemon = True
        self.scan_thread.start()

    def stop_scan(self):
        """Stop ongoing scan."""
        self.scan_running = False
        self.scan_btn.config(text="Start Scan")
        if len(self.scan_data) > 0:
            self.export_btn.config(state='normal')
        self.status_bar.config(text="Scan stopped")

    def _run_scan(self):
        """Execute the scan sequence."""
        try:
            start = self.scan_start_var.get()
            stop = self.scan_stop_var.get()
            step = self.scan_step_var.get()
            delay = self.scan_delay_var.get()
            laser_selection = self.scan_laser_var.get()

            # Generate current points
            current_points = []
            current = start
            while current <= stop:
                current_points.append(current)
                current += step

            # Determine which lasers to scan
            lasers_to_scan = []
            if laser_selection == "Laser 1" or laser_selection == "Both":
                if self.laser1_panel.is_connected:
                    lasers_to_scan.append(("Laser 1", self.laser1_panel))
            if laser_selection == "Laser 2" or laser_selection == "Both":
                if self.laser2_panel.is_connected:
                    lasers_to_scan.append(("Laser 2", self.laser2_panel))

            # Perform scan
            for laser_name, laser_panel in lasers_to_scan:
                if not self.scan_running:
                    break

                # Ensure output is enabled
                if not laser_panel.laser.get_ld_output_state():
                    laser_panel.laser.set_ld_output(True)
                    laser_panel.output_var.set(True)
                    laser_panel.update_output_indicator(True)
                    time.sleep(0.5)  # Allow output to stabilize

                for current_ma in current_points:
                    if not self.scan_running:
                        break

                    # Set current
                    laser_panel.laser.set_ld_current(current_ma)
                    self.root.after(0, lambda c=current_ma: laser_panel.current_var.set(c))

                    # Update status
                    self.root.after(0, lambda: self.status_bar.config(
                        text=f"Scanning {laser_name}: {current_ma:.1f} mA"))

                    # Wait for settling
                    time.sleep(delay)

                    # Take measurements
                    actual_current = laser_panel.laser.get_ld_current_actual()
                    voltage = laser_panel.laser.get_ld_voltage()

                    power = 0
                    if self.power_meter_connected and self.power_meter:
                        try:
                            self.power_meter.updatePowerReading(0.1)
                            power = self.power_meter.power * 1000  # Convert to mW
                        except:
                            pass

                    # Store data
                    data_point = {
                        'laser': laser_name,
                        'current_set': current_ma,
                        'current_actual': actual_current,
                        'voltage': voltage,
                        'power': power,
                        'timestamp': datetime.datetime.now()
                    }
                    self.scan_data.append(data_point)

                    # Update display
                    self.root.after(0, lambda dp=data_point: self._add_result_to_tree(dp))

                # Return to safe current after scan
                if self.scan_running:
                    laser_panel.laser.set_ld_current(100)
                    self.root.after(0, lambda: laser_panel.current_var.set(100))

            self.root.after(0, lambda: self.stop_scan())
            self.root.after(0, lambda: self.status_bar.config(text="Scan completed"))

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Scan Error", f"Scan failed: {e}"))
            self.root.after(0, lambda: self.stop_scan())

    def _add_result_to_tree(self, data_point):
        """Add a data point to the results tree."""
        self.results_tree.insert('', 'end', text=data_point['laser'],
                                values=(f"{data_point['current_actual']:.1f}",
                                       f"{data_point['power']:.3f}",
                                       f"{data_point['voltage']:.2f}"))

    def export_scan_data(self):
        """Export scan data to CSV file."""
        if not self.scan_data:
            messagebox.showwarning("No Data", "No scan data to export")
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"laser_scan_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )

        if filename:
            try:
                with open(filename, 'w', newline='') as csvfile:
                    fieldnames = ['timestamp', 'laser', 'current_set_mA', 'current_actual_mA',
                                 'voltage_V', 'power_mW']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                    writer.writeheader()
                    for data_point in self.scan_data:
                        writer.writerow({
                            'timestamp': data_point['timestamp'].isoformat(),
                            'laser': data_point['laser'],
                            'current_set_mA': data_point['current_set'],
                            'current_actual_mA': data_point['current_actual'],
                            'voltage_V': data_point['voltage'],
                            'power_mW': data_point['power']
                        })

                messagebox.showinfo("Export Complete", f"Data exported to {filename}")

            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export data: {e}")

    def emergency_stop_all(self):
        """Emergency stop all lasers."""
        # Stop any ongoing scan
        self.scan_running = False

        # Emergency stop both lasers
        self.laser1_panel.emergency_stop()
        self.laser2_panel.emergency_stop()

        self.status_bar.config(text="EMERGENCY STOP - All outputs disabled")

        # Flash the emergency button
        original_bg = self.emergency_btn.cget('bg')
        for _ in range(3):
            self.emergency_btn.config(bg='yellow')
            self.root.update()
            time.sleep(0.1)
            self.emergency_btn.config(bg='red')
            self.root.update()
            time.sleep(0.1)

    def start_periodic_updates(self):
        """Start periodic status updates."""
        def update():
            if self.root.winfo_exists():
                # Update laser status
                self.laser1_panel.update_status()
                self.laser2_panel.update_status()

                # Update power meter
                self.update_power_reading()

                # Schedule next update
                self.update_timer = self.root.after(500, update)

        update()

    def on_closing(self):
        """Handle window closing."""
        # Cancel update timer
        if self.update_timer:
            self.root.after_cancel(self.update_timer)

        # Disconnect all devices safely
        self.laser1_panel.disconnect()
        self.laser2_panel.disconnect()

        if self.power_meter:
            try:
                self.power_meter.disconnect()
            except:
                pass

        self.root.destroy()


def main():
    """Main entry point."""
    root = tk.Tk()
    app = DualLaserControlGUI(root)

    # Handle window closing
    root.protocol("WM_DELETE_WINDOW", app.on_closing)

    root.mainloop()


if __name__ == "__main__":
    main()