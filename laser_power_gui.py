#!/usr/bin/env python3
"""
Thorlabs Laser Current vs Power Measurement GUI

This GUI provides:
1. Automated sweep measurement table (130-1480 mA)
2. Manual current control and single measurements
3. Real-time data display and export capabilities
"""

import os
import sys
import pathlib
import glob
import time
import csv
import datetime
import threading
from typing import Optional, List
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# Add modules to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Python-Driver-for-Thorlabs-power-meter'))
sys.path.extend(glob.glob(f'{pathlib.Path(__file__).parent.resolve()}/Python-Driver-for-Thorlabs-power-meter/*/**/', recursive=True))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'pumplaser'))

from ThorlabsPowerMeter import ThorlabsPowerMeter
from pumplaser import PumpLaser, list_visa_resources


class LaserPowerGUI:
    """GUI for automated and manual laser current vs power measurements."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Thorlabs Laser Current vs Power Measurement")
        self.root.geometry("800x700")
        
        # Instrument objects
        self.power_meter = None
        self.laser = None
        self.logger = None
        
        # Measurement data
        self.sweep_data = []
        self.current_points = [
            130, 180, 230, 280, 330, 380, 430, 480, 530, 580,
            630, 680, 730, 780, 830, 880, 930, 980, 1030, 1080,
            1130, 1180, 1230, 1280, 1330, 1380, 1430, 1480
        ]
        
        # GUI state
        self.sweep_running = False
        self.manual_measurement_active = False
        
        self.setup_gui()
        self.update_instrument_status()
    
    def setup_gui(self):
        """Create the GUI layout."""
        # Add device status header block
        self.setup_status_header()
        
        # Create main notebook for tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Tab 1: Automated Sweep
        self.sweep_frame = ttk.Frame(notebook)
        notebook.add(self.sweep_frame, text="Automated Sweep")
        self.setup_sweep_tab()
        
        # Tab 2: Manual Control
        self.manual_frame = ttk.Frame(notebook)
        notebook.add(self.manual_frame, text="Manual Control")
        self.setup_manual_tab()
        
        # Tab 3: Instrument Status
        self.status_frame = ttk.Frame(notebook)
        notebook.add(self.status_frame, text="Instrument Status")
        self.setup_status_tab()
    
    def setup_sweep_tab(self):
        """Setup the automated sweep measurement tab."""
        # Title
        title_label = ttk.Label(self.sweep_frame, text="Automated Current Sweep Measurement", 
                               font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        
        # Control frame
        control_frame = ttk.Frame(self.sweep_frame)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Sweep controls
        ttk.Label(control_frame, text="Sweep Parameters:").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(control_frame, text=f"Current Range: {self.current_points[0]} - {self.current_points[-1]} mA").grid(row=1, column=0, sticky=tk.W)
        ttk.Label(control_frame, text=f"Number of Points: {len(self.current_points)}").grid(row=2, column=0, sticky=tk.W)
        
        # Measurement settings
        settings_frame = ttk.LabelFrame(control_frame, text="Settings")
        settings_frame.grid(row=0, column=1, rowspan=3, padx=20, sticky=tk.W)
        
        ttk.Label(settings_frame, text="Readings per point:").grid(row=0, column=0, sticky=tk.W)
        self.readings_var = tk.StringVar(value="5")
        readings_spin = ttk.Spinbox(settings_frame, from_=1, to=10, width=5, textvariable=self.readings_var)
        readings_spin.grid(row=0, column=1, padx=5)
        
        ttk.Label(settings_frame, text="Stabilization time (s):").grid(row=1, column=0, sticky=tk.W)
        self.stab_time_var = tk.StringVar(value="2.0")
        stab_spin = ttk.Spinbox(settings_frame, from_=0.5, to=10.0, increment=0.5, width=5, textvariable=self.stab_time_var)
        stab_spin.grid(row=1, column=1, padx=5)
        
        # Start/Stop buttons
        button_frame = ttk.Frame(self.sweep_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.start_sweep_btn = ttk.Button(button_frame, text="Start Sweep Measurement", 
                                         command=self.start_sweep_measurement, style='Accent.TButton')
        self.start_sweep_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_sweep_btn = ttk.Button(button_frame, text="Stop Sweep", 
                                        command=self.stop_sweep_measurement, state=tk.DISABLED)
        self.stop_sweep_btn.pack(side=tk.LEFT, padx=5)
        
        self.export_sweep_btn = ttk.Button(button_frame, text="Export Data", 
                                          command=self.export_sweep_data)
        self.export_sweep_btn.pack(side=tk.RIGHT, padx=5)
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.sweep_frame, variable=self.progress_var, 
                                           maximum=len(self.current_points))
        self.progress_bar.pack(fill=tk.X, padx=10, pady=5)
        
        # Status label
        self.sweep_status_var = tk.StringVar(value="Ready for sweep measurement")
        status_label = ttk.Label(self.sweep_frame, textvariable=self.sweep_status_var)
        status_label.pack(pady=5)
        
        # Measurement table
        table_frame = ttk.Frame(self.sweep_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create treeview with scrollbar
        columns = ('#', 'I Pump Laser (mA)', 'O. Power (mW)', 'Timestamp')
        self.sweep_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=12)
        
        # Configure columns
        self.sweep_tree.heading('#', text='#')
        self.sweep_tree.heading('I Pump Laser (mA)', text='I Pump Laser (mA)')
        self.sweep_tree.heading('O. Power (mW)', text='O. Power (mW)')
        self.sweep_tree.heading('Timestamp', text='Timestamp')
        
        self.sweep_tree.column('#', width=50, anchor=tk.CENTER)
        self.sweep_tree.column('I Pump Laser (mA)', width=150, anchor=tk.CENTER)
        self.sweep_tree.column('O. Power (mW)', width=150, anchor=tk.CENTER)
        self.sweep_tree.column('Timestamp', width=200, anchor=tk.CENTER)
        
        # Scrollbar for table
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.sweep_tree.yview)
        self.sweep_tree.configure(yscrollcommand=scrollbar.set)
        
        self.sweep_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Populate table with target currents
        self.populate_sweep_table()
    
    def setup_status_header(self):
        """Setup the device status header block."""
        # Main status frame
        status_header = ttk.LabelFrame(self.root, text="Device Status", padding=10)
        status_header.pack(fill=tk.X, padx=5, pady=5)
        
        # Create two-column layout
        left_frame = ttk.Frame(status_header)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        right_frame = ttk.Frame(status_header)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(20, 0))
        
        # Power Meter Status
        pm_title = ttk.Label(left_frame, text="Power Meter", font=('Arial', 10, 'bold'))
        pm_title.grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        ttk.Label(left_frame, text="Address:").grid(row=1, column=0, sticky=tk.W)
        self.pm_address_var = tk.StringVar(value="Not Connected")
        self.pm_address_label = ttk.Label(left_frame, textvariable=self.pm_address_var, 
                                         font=('Courier', 9), foreground='gray')
        self.pm_address_label.grid(row=1, column=1, sticky=tk.W, padx=(5, 0))
        
        ttk.Label(left_frame, text="Status:").grid(row=2, column=0, sticky=tk.W)
        self.pm_status_var = tk.StringVar(value="Disconnected")
        self.pm_status_label = ttk.Label(left_frame, textvariable=self.pm_status_var, 
                                        font=('Arial', 9, 'bold'))
        self.pm_status_label.grid(row=2, column=1, sticky=tk.W, padx=(5, 0))
        
        ttk.Label(left_frame, text="Device:").grid(row=3, column=0, sticky=tk.W)
        self.pm_device_var = tk.StringVar(value="--")
        ttk.Label(left_frame, textvariable=self.pm_device_var, 
                 font=('Arial', 9)).grid(row=3, column=1, sticky=tk.W, padx=(5, 0))
        
        # Laser Status  
        laser_title = ttk.Label(right_frame, text="Pump Laser", font=('Arial', 10, 'bold'))
        laser_title.grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        ttk.Label(right_frame, text="Address:").grid(row=1, column=0, sticky=tk.W)
        self.laser_address_var = tk.StringVar(value="Not Connected")
        self.laser_address_label = ttk.Label(right_frame, textvariable=self.laser_address_var,
                                           font=('Courier', 9), foreground='gray')
        self.laser_address_label.grid(row=1, column=1, sticky=tk.W, padx=(5, 0))
        
        ttk.Label(right_frame, text="Status:").grid(row=2, column=0, sticky=tk.W)
        self.laser_status_var = tk.StringVar(value="Disconnected")
        self.laser_status_label = ttk.Label(right_frame, textvariable=self.laser_status_var,
                                          font=('Arial', 9, 'bold'))
        self.laser_status_label.grid(row=2, column=1, sticky=tk.W, padx=(5, 0))
        
        ttk.Label(right_frame, text="Device:").grid(row=3, column=0, sticky=tk.W)
        self.laser_device_var = tk.StringVar(value="--")
        ttk.Label(right_frame, textvariable=self.laser_device_var,
                 font=('Arial', 9)).grid(row=3, column=1, sticky=tk.W, padx=(5, 0))
        
        # Overall system status
        separator = ttk.Separator(status_header, orient='horizontal')
        separator.pack(fill=tk.X, pady=(10, 5))
        
        system_frame = ttk.Frame(status_header)
        system_frame.pack(fill=tk.X)
        
        ttk.Label(system_frame, text="System Mode:", font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
        self.system_mode_var = tk.StringVar(value="Checking Instruments...")
        self.system_mode_label = ttk.Label(system_frame, textvariable=self.system_mode_var,
                                          font=('Arial', 10, 'bold'))
        self.system_mode_label.pack(side=tk.LEFT, padx=(5, 0))
    
    def setup_manual_tab(self):
        """Setup the manual control tab."""
        # Title
        title_label = ttk.Label(self.manual_frame, text="Manual Current Control & Single Measurements", 
                               font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        
        # Manual control frame
        control_frame = ttk.LabelFrame(self.manual_frame, text="Laser Current Control")
        control_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Current setting
        current_frame = ttk.Frame(control_frame)
        current_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(current_frame, text="Target Current (mA):").pack(side=tk.LEFT)
        self.manual_current_var = tk.StringVar(value="100")
        current_entry = ttk.Entry(current_frame, textvariable=self.manual_current_var, width=10)
        current_entry.pack(side=tk.LEFT, padx=5)
        
        self.set_current_btn = ttk.Button(current_frame, text="Set Current", 
                                         command=self.set_manual_current)
        self.set_current_btn.pack(side=tk.LEFT, padx=10)
        
        self.laser_output_var = tk.BooleanVar()
        output_check = ttk.Checkbutton(current_frame, text="Laser Output", 
                                      variable=self.laser_output_var, 
                                      command=self.toggle_laser_output)
        output_check.pack(side=tk.LEFT, padx=20)
        
        # Current status display
        status_frame = ttk.Frame(control_frame)
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(status_frame, text="Actual Current:").pack(side=tk.LEFT)
        self.actual_current_var = tk.StringVar(value="0.0 mA")
        ttk.Label(status_frame, textvariable=self.actual_current_var, 
                 foreground='blue').pack(side=tk.LEFT, padx=5)
        
        # Single measurement frame
        measure_frame = ttk.LabelFrame(self.manual_frame, text="Single Power Measurement")
        measure_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Measurement controls
        meas_control_frame = ttk.Frame(measure_frame)
        meas_control_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(meas_control_frame, text="Averaging:").pack(side=tk.LEFT)
        self.manual_avg_var = tk.StringVar(value="3")
        avg_spin = ttk.Spinbox(meas_control_frame, from_=1, to=10, width=5, 
                              textvariable=self.manual_avg_var)
        avg_spin.pack(side=tk.LEFT, padx=5)
        
        self.single_measure_btn = ttk.Button(meas_control_frame, text="Take Measurement", 
                                           command=self.take_single_measurement,
                                           style='Accent.TButton')
        self.single_measure_btn.pack(side=tk.LEFT, padx=20)
        
        # Power display
        power_frame = ttk.Frame(measure_frame)
        power_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(power_frame, text="Optical Power:").pack(side=tk.LEFT)
        self.optical_power_var = tk.StringVar(value="-- mW")
        ttk.Label(power_frame, textvariable=self.optical_power_var, 
                 font=('Arial', 12, 'bold'), foreground='red').pack(side=tk.LEFT, padx=5)
        
        # Manual measurement history
        history_frame = ttk.LabelFrame(self.manual_frame, text="Measurement History")
        history_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Manual measurement table
        manual_columns = ('Current (mA)', 'Power (mW)', 'Time')
        self.manual_tree = ttk.Treeview(history_frame, columns=manual_columns, show='headings', height=8)
        
        for col in manual_columns:
            self.manual_tree.heading(col, text=col)
            self.manual_tree.column(col, width=120, anchor=tk.CENTER)
        
        manual_scrollbar = ttk.Scrollbar(history_frame, orient=tk.VERTICAL, command=self.manual_tree.yview)
        self.manual_tree.configure(yscrollcommand=manual_scrollbar.set)
        
        self.manual_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        manual_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Export manual data button
        export_manual_btn = ttk.Button(self.manual_frame, text="Export Manual Data", 
                                      command=self.export_manual_data)
        export_manual_btn.pack(pady=10)
    
    def setup_status_tab(self):
        """Setup the instrument status tab."""
        # Title
        title_label = ttk.Label(self.status_frame, text="Instrument Status & Connection", 
                               font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        
        # Connection frame
        conn_frame = ttk.LabelFrame(self.status_frame, text="Instrument Connections")
        conn_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Power meter status
        pm_frame = ttk.Frame(conn_frame)
        pm_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(pm_frame, text="Power Meter:").pack(side=tk.LEFT)
        self.pm_status_var = tk.StringVar(value="Disconnected")
        self.pm_status_label = ttk.Label(pm_frame, textvariable=self.pm_status_var)
        self.pm_status_label.pack(side=tk.LEFT, padx=5)
        
        self.connect_pm_btn = ttk.Button(pm_frame, text="Connect Power Meter", 
                                        command=self.connect_power_meter)
        self.connect_pm_btn.pack(side=tk.RIGHT)
        
        # Laser status
        laser_frame = ttk.Frame(conn_frame)
        laser_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(laser_frame, text="Pump Laser:").pack(side=tk.LEFT)
        self.laser_status_var = tk.StringVar(value="Disconnected")
        self.laser_status_label = ttk.Label(laser_frame, textvariable=self.laser_status_var)
        self.laser_status_label.pack(side=tk.LEFT, padx=5)
        
        self.connect_laser_btn = ttk.Button(laser_frame, text="Connect Laser", 
                                           command=self.connect_laser)
        self.connect_laser_btn.pack(side=tk.RIGHT)
        
        # Instrument info
        info_frame = ttk.LabelFrame(self.status_frame, text="Instrument Information")
        info_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self.info_text = tk.Text(info_frame, height=15, wrap=tk.WORD)
        info_scrollbar = ttk.Scrollbar(info_frame, orient=tk.VERTICAL, command=self.info_text.yview)
        self.info_text.configure(yscrollcommand=info_scrollbar.set)
        
        self.info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        info_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Emergency stop button
        emergency_frame = ttk.Frame(self.status_frame)
        emergency_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.emergency_btn = ttk.Button(emergency_frame, text="EMERGENCY STOP", 
                                       command=self.emergency_stop,
                                       style='Danger.TButton')
        self.emergency_btn.pack(pady=10)
        
        # Configure button styles
        style = ttk.Style()
        style.configure('Danger.TButton', background='red', foreground='white')
        style.configure('Accent.TButton', background='blue', foreground='white')
    
    def populate_sweep_table(self):
        """Populate the sweep table with target current values."""
        for i, current in enumerate(self.current_points):
            self.sweep_tree.insert('', 'end', values=(i+1, current, '', ''))
    
    def update_instrument_status(self):
        """Update instrument status display."""
        # Update power meter status
        if self.power_meter:
            # Get the actual device address
            try:
                deviceList = ThorlabsPowerMeter.listDevices()
                if deviceList.resourceCount > 0:
                    pm_address = deviceList.resourceName[0]
                    self.pm_address_var.set(pm_address)
                    self.pm_address_label.configure(foreground='blue')
                else:
                    self.pm_address_var.set("Address Unknown")
                    self.pm_address_label.configure(foreground='orange')
            except:
                self.pm_address_var.set("Address Error")
                self.pm_address_label.configure(foreground='orange')
            
            self.pm_status_var.set("Connected")
            self.pm_status_label.configure(foreground='green')
            self.pm_device_var.set(f"{self.power_meter.sensorName} ({self.power_meter.sensorSerialNumber})")
        else:
            self.pm_address_var.set("Not Connected")
            self.pm_address_label.configure(foreground='gray')
            self.pm_status_var.set("Disconnected")
            self.pm_status_label.configure(foreground='red')
            self.pm_device_var.set("--")
        
        # Update laser status
        if self.laser and self.laser.is_connected:
            try:
                # Get laser address from resource name
                self.laser_address_var.set(self.laser.resource_name)
                self.laser_address_label.configure(foreground='blue')
                
                identity = self.laser.get_identity()
                self.laser_status_var.set("Connected")
                self.laser_status_label.configure(foreground='green')
                self.laser_device_var.set(identity.split(',')[0] + f" ({identity.split(',')[2]})")
            except Exception as e:
                self.laser_address_var.set(getattr(self.laser, 'resource_name', 'Address Error'))
                self.laser_address_label.configure(foreground='orange')
                self.laser_status_var.set("Communication Error")
                self.laser_status_label.configure(foreground='orange')
                self.laser_device_var.set("Error")
        else:
            self.laser_address_var.set("Not Connected")
            self.laser_address_label.configure(foreground='gray')
            self.laser_status_var.set("Disconnected")
            self.laser_status_label.configure(foreground='red')
            self.laser_device_var.set("--")
        
        # Update overall system status
        if self.power_meter and self.laser and self.laser.is_connected:
            self.system_mode_var.set("PRODUCTION MODE - Real Instruments")
            self.system_mode_label.configure(foreground='green')
        elif self.power_meter or (self.laser and self.laser.is_connected):
            self.system_mode_var.set("PARTIAL CONNECTION - Some Instruments")
            self.system_mode_label.configure(foreground='orange')
        else:
            self.system_mode_var.set("NO INSTRUMENTS - Check Connections")
            self.system_mode_label.configure(foreground='red')
    
    def connect_power_meter(self):
        """Connect to power meter."""
        try:
            self.info_text.insert(tk.END, "Connecting to power meter...\n")
            self.info_text.see(tk.END)
            
            deviceList = ThorlabsPowerMeter.listDevices()
            
            if deviceList.resourceCount == 0:
                messagebox.showerror("Error", "No power meter devices found")
                return
            
            self.power_meter = deviceList.connect(deviceList.resourceName[0])
            if self.power_meter is None:
                messagebox.showerror("Error", "Failed to connect to power meter")
                return
            
            # Configure power meter
            self.power_meter.getSensorInfo()
            self.power_meter.setWaveLength(1550)
            self.power_meter.setPowerAutoRange(True)
            self.power_meter.setAverageTime(0.1)
            
            self.info_text.insert(tk.END, f"Power meter connected: {self.power_meter.sensorName}\n")
            self.info_text.insert(tk.END, f"Serial: {self.power_meter.sensorSerialNumber}\n")
            self.info_text.insert(tk.END, f"Type: {self.power_meter.sensorType}\n\n")
            self.info_text.see(tk.END)
            
            self.update_instrument_status()
            
        except Exception as e:
            messagebox.showerror("Power Meter Error", f"Failed to connect: {str(e)}")
            self.info_text.insert(tk.END, f"Power meter connection failed: {str(e)}\n\n")
            self.info_text.see(tk.END)
    
    def connect_laser(self):
        """Connect to pump laser."""
        try:
            self.info_text.insert(tk.END, "Discovering laser devices...\n")
            self.info_text.see(tk.END)
            
            visa_resources = list_visa_resources()
            potential_lasers = [r for r in visa_resources if 'USB0::0x1313::0x804F' in r]
            
            if not potential_lasers:
                messagebox.showerror("Error", "No pump laser devices found")
                return
            
            # Try default address first
            target_address = "USB0::0x1313::0x804F::M01093719::0::INSTR"
            if target_address in potential_lasers:
                laser_addr = target_address
            else:
                laser_addr = potential_lasers[0]
            
            self.info_text.insert(tk.END, f"Connecting to: {laser_addr}\n")
            self.info_text.see(tk.END)
            
            self.laser = PumpLaser(laser_addr)
            if not self.laser.connect():
                messagebox.showerror("Error", f"Failed to connect to laser: {laser_addr}")
                return
            
            # Initialize to safe state
            self.laser.set_current(0)
            self.laser.set_output(False)
            
            identity = self.laser.get_identity()
            self.info_text.insert(tk.END, f"Laser connected: {identity}\n")
            self.info_text.insert(tk.END, "Laser initialized to safe state (0 mA, output OFF)\n\n")
            self.info_text.see(tk.END)
            
            self.update_instrument_status()
            
        except Exception as e:
            messagebox.showerror("Laser Error", f"Failed to connect: {str(e)}")
            self.info_text.insert(tk.END, f"Laser connection failed: {str(e)}\n\n")
            self.info_text.see(tk.END)
    
    def start_sweep_measurement(self):
        """Start automated sweep measurement."""
        if not self.power_meter:
            messagebox.showerror("Error", "Power meter not connected")
            return
        
        if not self.laser or not self.laser.is_connected:
            messagebox.showerror("Error", "Laser not connected")
            return
        
        if self.sweep_running:
            return
        
        # Clear previous data
        for item in self.sweep_tree.get_children():
            self.sweep_tree.delete(item)
        self.populate_sweep_table()
        self.sweep_data.clear()
        
        # Update UI
        self.sweep_running = True
        self.start_sweep_btn.configure(state=tk.DISABLED)
        self.stop_sweep_btn.configure(state=tk.NORMAL)
        self.progress_var.set(0)
        
        # Start measurement in separate thread
        self.sweep_thread = threading.Thread(target=self.run_sweep_measurement)
        self.sweep_thread.daemon = True
        self.sweep_thread.start()
    
    def run_sweep_measurement(self):
        """Run the automated sweep measurement (in background thread)."""
        try:
            readings_per_point = int(self.readings_var.get())
            stab_time = float(self.stab_time_var.get())
            
            for i, current_ma in enumerate(self.current_points):
                if not self.sweep_running:  # Check for stop
                    break
                
                # Update status
                self.root.after(0, lambda: self.sweep_status_var.set(
                    f"Measuring point {i+1}/{len(self.current_points)}: {current_ma} mA"))
                
                # Set laser current
                self.laser.ramp_current(current_ma, step_ma=20, delay_s=0.1)
                self.laser.set_output(True)
                
                # Wait for stabilization
                time.sleep(stab_time)
                
                # Take power readings
                power_readings = []
                for j in range(readings_per_point):
                    if not self.sweep_running:
                        break
                    self.power_meter.updatePowerReading(0.2)
                    power = self.power_meter.meterPowerReading
                    power_readings.append(power)
                    time.sleep(0.3)
                
                if not self.sweep_running:
                    break
                
                # Calculate average
                avg_power = sum(power_readings) / len(power_readings)
                actual_current = self.laser.get_actual_current()
                
                # Store data
                measurement = {
                    'point': i + 1,
                    'target_current_ma': current_ma,
                    'actual_current_ma': actual_current,
                    'optical_power_mw': avg_power * 1000,
                    'timestamp': datetime.datetime.now().strftime("%H:%M:%S")
                }
                self.sweep_data.append(measurement)
                
                # Update table
                self.root.after(0, lambda idx=i, data=measurement: self.update_sweep_table_row(idx, data))
                
                # Update progress
                self.root.after(0, lambda: self.progress_var.set(i + 1))
            
            # Disable laser
            self.laser.set_output(False)
            self.laser.ramp_current(0, step_ma=50, delay_s=0.1)
            
            # Update UI
            self.root.after(0, self.sweep_measurement_complete)
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Sweep Error", f"Measurement failed: {str(e)}"))
            self.root.after(0, self.sweep_measurement_complete)
    
    def update_sweep_table_row(self, row_index, data):
        """Update a row in the sweep table."""
        items = self.sweep_tree.get_children()
        if row_index < len(items):
            item = items[row_index]
            self.sweep_tree.set(item, 'I Pump Laser (mA)', f"{data['actual_current_ma']:.1f}")
            self.sweep_tree.set(item, 'O. Power (mW)', f"{data['optical_power_mw']:.3f}")
            self.sweep_tree.set(item, 'Timestamp', data['timestamp'])
    
    def stop_sweep_measurement(self):
        """Stop the automated sweep measurement."""
        self.sweep_running = False
        self.sweep_status_var.set("Stopping sweep...")
    
    def sweep_measurement_complete(self):
        """Called when sweep measurement completes."""
        self.sweep_running = False
        self.start_sweep_btn.configure(state=tk.NORMAL)
        self.stop_sweep_btn.configure(state=tk.DISABLED)
        self.sweep_status_var.set(f"Sweep complete - {len(self.sweep_data)} points measured")
    
    def set_manual_current(self):
        """Set laser current manually."""
        if not self.laser or not self.laser.is_connected:
            messagebox.showerror("Error", "Laser not connected")
            return
        
        try:
            current = float(self.manual_current_var.get())
            self.laser.ramp_current(current, step_ma=20, delay_s=0.1)
            self.update_actual_current()
            
        except ValueError:
            messagebox.showerror("Error", "Invalid current value")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to set current: {str(e)}")
    
    def toggle_laser_output(self):
        """Toggle laser output on/off."""
        if not self.laser or not self.laser.is_connected:
            messagebox.showerror("Error", "Laser not connected")
            self.laser_output_var.set(False)
            return
        
        try:
            self.laser.set_output(self.laser_output_var.get())
        except Exception as e:
            messagebox.showerror("Error", f"Failed to toggle output: {str(e)}")
            self.laser_output_var.set(False)
    
    def update_actual_current(self):
        """Update the actual current display."""
        if self.laser and self.laser.is_connected:
            try:
                current = self.laser.get_actual_current()
                self.actual_current_var.set(f"{current:.1f} mA")
            except:
                self.actual_current_var.set("Error")
    
    def take_single_measurement(self):
        """Take a single power measurement."""
        if not self.power_meter:
            messagebox.showerror("Error", "Power meter not connected")
            return
        
        if self.manual_measurement_active:
            return
        
        try:
            self.manual_measurement_active = True
            self.single_measure_btn.configure(state=tk.DISABLED)
            
            avg_count = int(self.manual_avg_var.get())
            power_readings = []
            
            for i in range(avg_count):
                self.power_meter.updatePowerReading(0.2)
                power = self.power_meter.meterPowerReading
                power_readings.append(power)
                time.sleep(0.2)
            
            avg_power = sum(power_readings) / len(power_readings)
            power_mw = avg_power * 1000
            
            # Update display
            self.optical_power_var.set(f"{power_mw:.3f} mW")
            
            # Add to history
            current_str = self.actual_current_var.get().replace(" mA", "")
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            
            self.manual_tree.insert('', 0, values=(current_str, f"{power_mw:.3f}", timestamp))
            
        except Exception as e:
            messagebox.showerror("Error", f"Measurement failed: {str(e)}")
        
        finally:
            self.manual_measurement_active = False
            self.single_measure_btn.configure(state=tk.NORMAL)
    
    def export_sweep_data(self):
        """Export sweep measurement data to CSV."""
        if not self.sweep_data:
            messagebox.showwarning("Warning", "No sweep data to export")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Save Sweep Data"
        )
        
        if filename:
            try:
                with open(filename, 'w', newline='') as csvfile:
                    fieldnames = ['point', 'target_current_ma', 'actual_current_ma', 
                                'optical_power_mw', 'timestamp']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    for data in self.sweep_data:
                        writer.writerow(data)
                
                messagebox.showinfo("Success", f"Data exported to {filename}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Export failed: {str(e)}")
    
    def export_manual_data(self):
        """Export manual measurement data to CSV."""
        items = self.manual_tree.get_children()
        if not items:
            messagebox.showwarning("Warning", "No manual data to export")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Save Manual Data"
        )
        
        if filename:
            try:
                with open(filename, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Current (mA)', 'Power (mW)', 'Time'])
                    for item in reversed(items):  # Reverse to get chronological order
                        values = self.manual_tree.item(item)['values']
                        writer.writerow(values)
                
                messagebox.showinfo("Success", f"Manual data exported to {filename}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Export failed: {str(e)}")
    
    def emergency_stop(self):
        """Emergency stop - disable laser immediately."""
        if self.laser and self.laser.is_connected:
            try:
                self.laser.emergency_stop()
                self.laser_output_var.set(False)
                self.actual_current_var.set("0.0 mA")
                messagebox.showwarning("Emergency Stop", "Laser output disabled and current set to 0")
            except Exception as e:
                messagebox.showerror("Error", f"Emergency stop failed: {str(e)}")
        
        # Stop any running sweep
        self.sweep_running = False
    
    def on_closing(self):
        """Handle application closing."""
        try:
            # Safe shutdown
            if self.laser and self.laser.is_connected:
                self.laser.set_output(False)
                self.laser.set_current(0)
                self.laser.disconnect()
            
            if self.power_meter:
                self.power_meter.disconnect()
                
        except:
            pass
        
        self.root.destroy()


def main():
    """Main function to run the GUI."""
    root = tk.Tk()
    app = LaserPowerGUI(root)
    
    # Handle window closing
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    # Start the GUI
    root.mainloop()


if __name__ == "__main__":
    main()