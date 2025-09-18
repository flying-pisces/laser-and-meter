"""
Thorlabs CLD1015 Laser Diode Controller Driver

This module provides a Python interface for controlling Thorlabs CLD1015
laser diode controller via VISA/SCPI commands over USB connection.

Supports the CLD101x series compact laser diode controllers.
"""

import pyvisa
import time
import logging
from typing import Optional, Union


class CLD1015:
    """
    Driver for Thorlabs CLD1015 laser diode controller via VISA.

    Supports current control, power control, temperature monitoring,
    TEC control, and comprehensive safety features.

    Compatible with CLD101x series controllers.
    """
    
    def __init__(self, resource_name: str = "USB0::0x1313::0x804F::M01093719::0::INSTR"):
        """
        Initialize CLD1015 laser controller connection.
        
        Args:
            resource_name: VISA resource identifier for the CLD1015 controller
                          Default is for USB connection. Update with your device's address.
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
        Establish connection to the CLD1015 controller.
        
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
            self.logger.info(f"Connected to CLD1015: {idn.strip()}")

            # Clear any errors
            self.instrument.write("*CLS")
            
            self.is_connected = True
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to CLD1015: {e}")
            self.is_connected = False
            return False
    
    def disconnect(self) -> None:
        """Close connection to the CLD1015 controller."""
        if self.instrument:
            try:
                # Ensure laser is turned off before disconnecting
                self.set_ld_output(False)
                self.instrument.close()
                self.logger.info("Disconnected from CLD1015")
            except Exception as e:
                self.logger.error(f"Error during disconnect: {e}")
            finally:
                self.instrument = None
                self.is_connected = False
    
    def _check_connection(self) -> None:
        """Check if instrument is connected, raise exception if not."""
        if not self.is_connected or not self.instrument:
            raise RuntimeError("CLD1015 not connected. Call connect() first.")
    
    def get_identity(self) -> str:
        """
        Get CLD1015 identification string.
        
        Returns:
            str: Instrument identification (Manufacturer, Model, Serial, Firmware)
        """
        self._check_connection()
        return self.instrument.query("*IDN?").strip()
    
    def set_ld_current(self, current_ma: float) -> None:
        """
        Set laser diode drive current setpoint.
        
        Args:
            current_ma: Current in milliamps
        """
        self._check_connection()
        
        if current_ma < 0:
            raise ValueError("Current cannot be negative")
        
        # Convert mA to A for SCPI command
        current_a = current_ma / 1000.0
        
        # Use CLD1015 specific command: SOURce[1]:CURRent:LEVel:IMMediate:AMPLitude
        self.instrument.write(f"SOUR:CURR:LEV:IMM:AMPL {current_a:.6f}")
        self.logger.info(f"Set LD current setpoint to {current_ma:.3f} mA")
    
    def get_ld_current_setpoint(self) -> float:
        """
        Get laser diode current setpoint.
        
        Returns:
            float: Current setpoint in milliamps
        """
        self._check_connection()
        current_a = float(self.instrument.query("SOUR:CURR:LEV:IMM:AMPL?"))
        return current_a * 1000.0  # Convert A to mA
    
    def get_ld_current_actual(self) -> float:
        """
        Get actual measured laser diode current.
        
        Returns:
            float: Actual measured current in milliamps
        """
        self._check_connection()
        # Use SENS3:CURR:DATA? for LD current measurement
        current_a = float(self.instrument.query("SENS3:CURR:DATA?"))
        return current_a * 1000.0  # Convert A to mA
    
    def set_ld_output(self, enabled: bool) -> None:
        """
        Enable or disable laser diode output.
        
        Args:
            enabled: True to enable output, False to disable
        """
        self._check_connection()
        state = "ON" if enabled else "OFF"
        # Use OUTPut[1]:STATe for LD output control
        self.instrument.write(f"OUTP:STAT {state}")
        self.logger.info(f"LD output {'enabled' if enabled else 'disabled'}")
    
    def get_ld_output_state(self) -> bool:
        """
        Get laser diode output enable state.
        
        Returns:
            bool: True if output enabled, False if disabled
        """
        self._check_connection()
        response = self.instrument.query("OUTP:STAT?").strip()
        return response == "1" or response.upper() == "ON"
    
    def get_ld_voltage(self) -> float:
        """
        Get measured laser diode voltage.

        Returns:
            float: LD voltage in volts
        """
        self._check_connection()
        try:
            # Use SENS4:VOLT:DATA? for LD voltage measurement
            voltage = float(self.instrument.query("SENS4:VOLT:DATA?"))
            return voltage
        except Exception as e:
            self.logger.warning(f"LD voltage measurement failed: {e}")
            return 0.0

    def set_current_limit(self, limit_ma: float) -> None:
        """
        Set laser diode current limit.

        Args:
            limit_ma: Current limit in milliamps
        """
        self._check_connection()

        if limit_ma < 0:
            raise ValueError("Current limit cannot be negative")

        # Convert mA to A for SCPI command
        limit_a = limit_ma / 1000.0

        # Use SOURce[1]:CURRent:LIMit:AMPLitude
        self.instrument.write(f"SOUR:CURR:LIM:AMPL {limit_a:.6f}")
        self.logger.info(f"Set LD current limit to {limit_ma:.3f} mA")

    def get_current_limit(self) -> float:
        """
        Get laser diode current limit.

        Returns:
            float: Current limit in milliamps
        """
        self._check_connection()
        limit_a = float(self.instrument.query("SOUR:CURR:LIM:AMPL?"))
        return limit_a * 1000.0  # Convert A to mA

    def set_operating_mode(self, mode: str) -> None:
        """
        Set LD driver operating mode (current or power control).

        Args:
            mode: 'CURRENT' or 'POWER'
        """
        self._check_connection()

        mode = mode.upper()
        if mode not in ['CURRENT', 'CURR', 'POWER', 'POW']:
            raise ValueError("Mode must be 'CURRENT' or 'POWER'")

        # Normalize mode string
        mode_cmd = 'CURR' if mode in ['CURRENT', 'CURR'] else 'POW'

        # Use SOURce[1]:FUNCtion:MODE
        self.instrument.write(f"SOUR:FUNC:MODE {mode_cmd}")
        self.logger.info(f"Set operating mode to {mode_cmd}")

    def get_operating_mode(self) -> str:
        """
        Get LD driver operating mode.

        Returns:
            str: 'CURRENT' or 'POWER'
        """
        self._check_connection()
        mode = self.instrument.query("SOUR:FUNC:MODE?").strip()
        return mode.upper()
    
    def get_temperature(self) -> float:
        """
        Get temperature measurement from TEC sensor.

        Returns:
            float: Temperature in Celsius
        """
        self._check_connection()
        try:
            # Use SENS2:TEMP:DATA? for temperature measurement
            temp = float(self.instrument.query("SENS2:TEMP:DATA?"))
            return temp
        except Exception as e:
            self.logger.warning(f"Temperature measurement failed: {e}")
            return 0.0

    def set_tec_output(self, enabled: bool) -> None:
        """
        Enable or disable TEC (temperature controller) output.

        Args:
            enabled: True to enable TEC, False to disable
        """
        self._check_connection()
        state = "ON" if enabled else "OFF"
        # Use OUTPut2:STATe for TEC output control
        self.instrument.write(f"OUTP2:STAT {state}")
        self.logger.info(f"TEC output {'enabled' if enabled else 'disabled'}")

    def get_tec_output_state(self) -> bool:
        """
        Get TEC output enable state.

        Returns:
            bool: True if TEC enabled, False if disabled
        """
        self._check_connection()
        response = self.instrument.query("OUTP2:STAT?").strip()
        return response == "1" or response.upper() == "ON"

    def set_temperature_setpoint(self, temp_c: float) -> None:
        """
        Set temperature setpoint for TEC control.

        Args:
            temp_c: Temperature setpoint in Celsius
        """
        self._check_connection()
        # Use SOURce2:TEMPerature:SPOint
        self.instrument.write(f"SOUR2:TEMP:SPO {temp_c:.2f}")
        self.logger.info(f"Set temperature setpoint to {temp_c:.2f}°C")

    def get_temperature_setpoint(self) -> float:
        """
        Get temperature setpoint.

        Returns:
            float: Temperature setpoint in Celsius
        """
        self._check_connection()
        return float(self.instrument.query("SOUR2:TEMP:SPO?"))
    
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
            'ld_output_enabled': self.get_ld_output_state(),
            'operating_mode': self.get_operating_mode(),
            'ld_current_setpoint_ma': self.get_ld_current_setpoint(),
            'ld_current_actual_ma': self.get_ld_current_actual(),
            'ld_current_limit_ma': self.get_current_limit(),
            'ld_voltage_v': self.get_ld_voltage(),
            'temperature_c': self.get_temperature(),
            'temperature_setpoint_c': self.get_temperature_setpoint(),
            'tec_enabled': self.get_tec_output_state()
        }

        # Check for any errors
        try:
            error = self.instrument.query("SYST:ERR?").strip()
            status['last_error'] = error
        except:
            status['last_error'] = None
        
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
        
        current_ma = self.get_ld_current_setpoint()
        
        if abs(current_ma - target_ma) < 0.001:
            self.logger.info(f"Current already at target: {target_ma:.3f} mA")
            return
        
        step_sign = 1 if target_ma > current_ma else -1
        step_ma = abs(step_ma) * step_sign
        
        self.logger.info(f"Ramping current from {current_ma:.3f} mA to {target_ma:.3f} mA")
        
        while (step_sign > 0 and current_ma < target_ma) or (step_sign < 0 and current_ma > target_ma):
            current_ma += step_ma
            
            # Don't overshoot target
            if (step_sign > 0 and current_ma > target_ma) or (step_sign < 0 and current_ma < target_ma):
                current_ma = target_ma
            
            self.set_ld_current(current_ma)
            time.sleep(delay_s)
        
        self.logger.info(f"Current ramp complete: {self.get_ld_current_setpoint():.3f} mA")
    
    def emergency_stop(self) -> None:
        """Emergency shutdown - disable output immediately."""
        if self.instrument:
            try:
                # Disable LD output
                self.instrument.write("OUTP:STAT OFF")
                # Set current to zero
                self.instrument.write("SOUR:CURR:LEV:IMM:AMPL 0")
                # Disable TEC output
                self.instrument.write("OUTP2:STAT OFF")
                self.logger.warning("EMERGENCY STOP - All outputs disabled")
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
    # Quick test of the CLD1015 driver
    print("Available VISA resources:")
    resources = list_visa_resources()
    for resource in resources:
        print(f"  {resource}")

    # Look for CLD1015 device (typically shows as USB with vendor ID 0x1313)
    cld_resource = None
    for res in resources:
        if "0x1313" in res or "CLD" in res.upper():
            cld_resource = res
            print(f"\nFound potential CLD1015 device: {cld_resource}")
            break

    # Test connection
    if cld_resource:
        try:
            with CLD1015(cld_resource) as controller:
                print(f"\nCLD1015 Status:")
                status = controller.get_status()
                for key, value in status.items():
                    print(f"  {key}: {value}")
        except Exception as e:
            print(f"Test failed: {e}")
    else:
        print("\nNo CLD1015 device found. Please check connections.")