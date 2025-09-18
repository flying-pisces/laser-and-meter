"""
CLD1015 Diagnostic Script

This script checks all protection circuits and safety interlocks
to determine why the laser current isn't flowing.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from pump_laser import CLD1015

def check_protections(cld):
    """Check all protection circuits and interlocks."""
    print("\n" + "=" * 60)
    print("PROTECTION AND INTERLOCK STATUS")
    print("=" * 60)

    try:
        # Check interlock circuit
        interlock = cld.instrument.query("OUTP:PROT:INTL:TRIP?").strip()
        print(f"Interlock circuit tripped: {interlock}")

        # Check keylock
        keylock = cld.instrument.query("OUTP:PROT:KEYL:TRIP?").strip()
        print(f"Keylock protection tripped: {keylock}")

        # Check over temperature
        overtemp = cld.instrument.query("OUTP:PROT:OTEM:TRIP?").strip()
        print(f"Over temperature tripped: {overtemp}")

        # Check connection failure
        connection = cld.instrument.query("OUTP:PROT:CONN:TRIP?").strip()
        print(f"Connection failure tripped: {connection}")

        # Check output condition
        condition = cld.instrument.query("OUTP:COND?").strip()
        print(f"Output condition: {condition}")

    except Exception as e:
        print(f"Error checking protections: {e}")

def check_operating_conditions(cld):
    """Check various operating conditions."""
    print("\n" + "=" * 60)
    print("OPERATING CONDITIONS")
    print("=" * 60)

    try:
        # Check if we're in the right operating mode
        mode = cld.instrument.query("SOUR:FUNC:MODE?").strip()
        print(f"Operating mode: {mode}")

        # Check current limit
        limit = float(cld.instrument.query("SOUR:CURR:LIM:AMPL?"))
        print(f"Current limit: {limit*1000:.1f} mA")

        # Check if limit is tripped
        limit_trip = cld.instrument.query("SOUR:CURR:LIM:TRIP?").strip()
        print(f"Current limit tripped: {limit_trip}")

        # Check LD polarity if supported
        try:
            polarity = cld.instrument.query("OUTP:POL?").strip()
            print(f"LD polarity: {polarity}")
        except:
            print("LD polarity: Not supported or not readable")

    except Exception as e:
        print(f"Error checking operating conditions: {e}")

def check_measurement_subsystem(cld):
    """Check measurement capabilities."""
    print("\n" + "=" * 60)
    print("MEASUREMENT SUBSYSTEM STATUS")
    print("=" * 60)

    # Try different measurement commands
    measurements = [
        ("LD Current (SENS3:CURR:DATA?)", "SENS3:CURR:DATA?", lambda x: f"{float(x)*1000:.3f} mA"),
        ("LD Voltage (SENS4:VOLT:DATA?)", "SENS4:VOLT:DATA?", lambda x: f"{float(x):.3f} V"),
        ("Temperature (SENS2:TEMP:DATA?)", "SENS2:TEMP:DATA?", lambda x: f"{float(x):.1f}°C"),
    ]

    for name, cmd, formatter in measurements:
        try:
            result = cld.instrument.query(cmd).strip()
            formatted = formatter(result)
            print(f"{name}: {formatted}")
        except Exception as e:
            print(f"{name}: Error - {e}")

def test_manual_commands(cld):
    """Test sending commands manually and check responses."""
    print("\n" + "=" * 60)
    print("MANUAL COMMAND TESTING")
    print("=" * 60)

    # Test basic commands
    commands = [
        "*IDN?",
        "SYST:ERR?",
        "OUTP:STAT?",
        "SOUR:CURR:LEV:IMM:AMPL?",
    ]

    for cmd in commands:
        try:
            response = cld.instrument.query(cmd).strip()
            print(f"{cmd:<30}: {response}")
        except Exception as e:
            print(f"{cmd:<30}: ERROR - {e}")

def main():
    """Main diagnostic routine."""
    device_address = "USB0::0x1313::0x804F::M01093719::0::INSTR"

    print("CLD1015 COMPREHENSIVE DIAGNOSTIC")
    print("=" * 60)

    try:
        with CLD1015(device_address) as cld:
            print(f"Connected to: {cld.get_identity()}")

            # Run all diagnostic checks
            check_protections(cld)
            check_operating_conditions(cld)
            check_measurement_subsystem(cld)
            test_manual_commands(cld)

            # Try to enable output and set current
            print("\n" + "=" * 60)
            print("ATTEMPTING TO ENABLE OUTPUT AND SET CURRENT")
            print("=" * 60)

            # Set a reasonable current limit
            cld.instrument.write("SOUR:CURR:LIM:AMPL 0.1")  # 100 mA
            print("Set current limit to 100 mA")

            # Ensure we're in current mode
            cld.instrument.write("SOUR:FUNC:MODE CURR")
            print("Set to current mode")

            # Try to enable output
            cld.instrument.write("OUTP:STAT ON")
            print("Enabled output")

            # Set a small test current
            test_current = 0.01  # 10 mA
            cld.instrument.write(f"SOUR:CURR:LEV:IMM:AMPL {test_current}")
            print(f"Set current to {test_current*1000} mA")

            # Wait a moment and check again
            import time
            time.sleep(1)

            # Re-check protection status
            check_protections(cld)

            # Check final measurements
            try:
                actual = float(cld.instrument.query("SENS3:CURR:DATA?")) * 1000
                voltage = float(cld.instrument.query("SENS4:VOLT:DATA?"))
                print(f"\nFinal readings:")
                print(f"  Actual current: {actual:.3f} mA")
                print(f"  LD voltage: {voltage:.3f} V")
            except Exception as e:
                print(f"Error reading final values: {e}")

            # Clean up
            cld.instrument.write("OUTP:STAT OFF")
            cld.instrument.write("SOUR:CURR:LEV:IMM:AMPL 0")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()