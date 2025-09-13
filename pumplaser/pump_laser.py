"""
Thorlabs Pump Laser Driver

This module provides a Python interface for controlling Thorlabs pump lasers
via VISA/SCPI commands over USB connection.
"""

import pyvisa
import time
import logging
from typing import Optional, Union


class PumpLaser:
    """
    Driver for Thorlabs pump laser control via VISA.
    
    Supports current control, status monitoring, and safety features.
    """
    
    def __init__(self, resource_name: str = "USB0::0x1313::0x804F::M01093719::0::INSTR"):
        """
        Initialize pump laser connection.
        
        Args:
            resource_name: VISA resource identifier for the laser
        """
        self.resource_name = resource_name
        self.instrument = None
        self.is_connected = False
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def connect(self) -> bool:
        """
        Establish connection to the laser.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            rm = pyvisa.ResourceManager()
            self.instrument = rm.open_resource(self.resource_name)
            
            # Configure communication parameters
            self.instrument.timeout = 5000  # 5 second timeout
            self.instrument.write_termination = '\n'
            self.instrument.read_termination = '\n'
            
            # Test connection with identification query
            idn = self.instrument.query("*IDN?")
            self.logger.info(f"Connected to laser: {idn.strip()}")
            
            self.is_connected = True
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to laser: {e}")
            self.is_connected = False
            return False
    
    def disconnect(self) -> None:
        """Close connection to the laser."""
        if self.instrument:
            try:
                # Ensure laser is turned off before disconnecting
                self.set_output(False)
                self.instrument.close()
                self.logger.info("Disconnected from laser")
            except Exception as e:
                self.logger.error(f"Error during disconnect: {e}")
            finally:
                self.instrument = None
                self.is_connected = False
    
    def _check_connection(self) -> None:
        """Check if instrument is connected, raise exception if not."""
        if not self.is_connected or not self.instrument:
            raise RuntimeError("Laser not connected. Call connect() first.")
    
    def get_identity(self) -> str:
        """
        Get laser identification string.
        
        Returns:
            str: Instrument identification
        """
        self._check_connection()
        return self.instrument.query("*IDN?").strip()
    
    def set_current(self, current_ma: float) -> None:
        """
        Set laser drive current.
        
        Args:
            current_ma: Current in milliamps
        """
        self._check_connection()
        
        if current_ma < 0:
            raise ValueError("Current cannot be negative")
        
        # Convert mA to A for SCPI command
        current_a = current_ma / 1000.0
        
        self.instrument.write(f"SOUR:CURR {current_a:.6f}")
        self.logger.info(f"Set laser current to {current_ma} mA")
    
    def get_current(self) -> float:
        """
        Get current laser drive current setting.
        
        Returns:
            float: Current in milliamps
        """
        self._check_connection()
        current_a = float(self.instrument.query("SOUR:CURR?"))
        return current_a * 1000.0  # Convert A to mA
    
    def get_actual_current(self) -> float:
        """
        Get actual measured laser current.
        
        Returns:
            float: Actual current in milliamps
        """
        self._check_connection()
        current_a = float(self.instrument.query("MEAS:CURR?"))
        return current_a * 1000.0  # Convert A to mA
    
    def set_output(self, enabled: bool) -> None:
        """
        Enable or disable laser output.
        
        Args:
            enabled: True to enable output, False to disable
        """
        self._check_connection()
        state = "ON" if enabled else "OFF"
        self.instrument.write(f"OUTP {state}")
        self.logger.info(f"Laser output {'enabled' if enabled else 'disabled'}")
    
    def get_output_state(self) -> bool:
        """
        Get current output enable state.
        
        Returns:
            bool: True if output enabled, False if disabled
        """
        self._check_connection()
        response = self.instrument.query("OUTP?").strip()
        return response == "1" or response.upper() == "ON"
    
    def get_power(self) -> float:
        """
        Get measured optical power (if supported).
        
        Returns:
            float: Optical power in watts
        """
        self._check_connection()
        try:
            power = float(self.instrument.query("MEAS:POW?"))
            return power
        except Exception as e:
            self.logger.warning(f"Power measurement not supported: {e}")
            return 0.0
    
    def get_temperature(self) -> float:
        """
        Get laser diode temperature (if supported).
        
        Returns:
            float: Temperature in Celsius
        """
        self._check_connection()
        try:
            temp = float(self.instrument.query("MEAS:TEMP?"))
            return temp
        except Exception as e:
            self.logger.warning(f"Temperature measurement not supported: {e}")
            return 0.0
    
    def get_status(self) -> dict:
        """
        Get comprehensive laser status.
        
        Returns:
            dict: Status information including current, output state, etc.
        """
        self._check_connection()
        
        status = {
            'connected': self.is_connected,
            'identity': self.get_identity(),
            'output_enabled': self.get_output_state(),
            'set_current_ma': self.get_current(),
            'actual_current_ma': self.get_actual_current(),
            'power_w': self.get_power(),
            'temperature_c': self.get_temperature()
        }
        
        return status
    
    def ramp_current(self, target_ma: float, step_ma: float = 10, delay_s: float = 0.1) -> None:
        """
        Gradually ramp laser current to target value.
        
        Args:
            target_ma: Target current in milliamps
            step_ma: Current step size in milliamps
            delay_s: Delay between steps in seconds
        """
        self._check_connection()
        
        current_ma = self.get_current()
        
        if current_ma == target_ma:
            self.logger.info(f"Current already at target: {target_ma} mA")
            return
        
        step_sign = 1 if target_ma > current_ma else -1
        step_ma = abs(step_ma) * step_sign
        
        self.logger.info(f"Ramping current from {current_ma} mA to {target_ma} mA")
        
        while (step_sign > 0 and current_ma < target_ma) or (step_sign < 0 and current_ma > target_ma):
            current_ma += step_ma
            
            # Don't overshoot target
            if (step_sign > 0 and current_ma > target_ma) or (step_sign < 0 and current_ma < target_ma):
                current_ma = target_ma
            
            self.set_current(current_ma)
            time.sleep(delay_s)
        
        self.logger.info(f"Current ramp complete: {self.get_current()} mA")
    
    def emergency_stop(self) -> None:
        """Emergency shutdown - disable output immediately."""
        if self.instrument:
            try:
                self.instrument.write("OUTP OFF")
                self.set_current(0)
                self.logger.warning("EMERGENCY STOP - Laser output disabled")
            except Exception as e:
                self.logger.error(f"Emergency stop failed: {e}")
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()


def list_visa_resources() -> list:
    """
    List all available VISA resources.
    
    Returns:
        list: Available VISA resource names
    """
    try:
        rm = pyvisa.ResourceManager()
        resources = rm.list_resources()
        return list(resources)
    except Exception as e:
        print(f"Error listing VISA resources: {e}")
        return []


if __name__ == "__main__":
    # Quick test of the laser driver
    print("Available VISA resources:")
    for resource in list_visa_resources():
        print(f"  {resource}")
    
    # Test connection with default address
    try:
        with PumpLaser() as laser:
            print(f"\nLaser Status: {laser.get_status()}")
    except Exception as e:
        print(f"Test failed: {e}")