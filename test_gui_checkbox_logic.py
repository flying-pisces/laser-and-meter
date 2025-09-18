"""
Test script to verify the checkbox logic for current level selection
"""

import tkinter as tk
from tkinter import ttk

class CurrentLevelControlTest:
    """Test the current level selection logic"""

    def __init__(self):
        self.currents = [0, 25, 50, 75, 100, 125, 150]
        self.variables = {}

        # Create root window
        self.root = tk.Tk()
        self.root.title("Current Level Checkbox Logic Test")
        self.root.geometry("600x300")

        # Create frame
        self.frame = ttk.LabelFrame(self.root, text="Current Test Levels (mA)", padding=10)
        self.frame.pack(fill='x', padx=10, pady=10)

        # Create checkboxes
        self.checkboxes = {}
        for i, current in enumerate(self.currents):
            var = tk.BooleanVar()

            # Default: only 0mA and 50mA selected (first low level)
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

        # Status display
        self.status_frame = ttk.LabelFrame(self.root, text="Selected Currents", padding=10)
        self.status_frame.pack(fill='x', padx=10, pady=10)

        self.status_var = tk.StringVar()
        self.status_label = ttk.Label(self.status_frame, textvariable=self.status_var)
        self.status_label.pack()

        # Test button
        test_button = ttk.Button(
            self.root,
            text="Test Logic",
            command=self._test_logic
        )
        test_button.pack(pady=10)

        # Initial update
        self._update_status()

    def _on_checkbox_change(self, changed_current: float):
        """Handle checkbox state changes with automatic lower-level enabling"""
        print(f"Checkbox changed: {changed_current} mA -> {self.variables[changed_current].get()}")

        # If a current level is enabled, enable all lower current levels
        if self.variables[changed_current].get():
            print(f"Enabling all currents <= {changed_current} mA")
            for current in self.currents:
                if current <= changed_current:
                    self.variables[current].set(True)
                    print(f"  Enabled: {current} mA")

        # If a current level is disabled, disable all higher current levels
        else:
            print(f"Disabling all currents > {changed_current} mA")
            for current in self.currents:
                if current > changed_current:
                    self.variables[current].set(False)
                    print(f"  Disabled: {current} mA")

        self._update_status()

    def _update_status(self):
        """Update status display"""
        selected = self.get_selected_currents()
        self.status_var.set(f"Selected: {selected}")
        print(f"Currently selected: {selected}")
        print("-" * 40)

    def get_selected_currents(self):
        """Get list of selected current levels"""
        return [current for current, var in self.variables.items() if var.get()]

    def _test_logic(self):
        """Test the logic programmatically"""
        print("\\n=== TESTING CHECKBOX LOGIC ===")

        # Test enabling 100mA (should enable 0, 25, 50, 75, 100)
        print("Test 1: Enable 100mA")
        self._reset_checkboxes()
        self.variables[100].set(True)
        self._on_checkbox_change(100)
        expected = [0, 25, 50, 75, 100]
        actual = self.get_selected_currents()
        print(f"Expected: {expected}, Actual: {actual}")
        assert actual == expected, f"Test 1 failed: {actual} != {expected}"
        print("[OK] Test 1 passed")

        # Test disabling 75mA (should disable 75, 100, 125, 150)
        print("\\nTest 2: Disable 75mA")
        self.variables[75].set(False)
        self._on_checkbox_change(75)
        expected = [0, 25, 50]
        actual = self.get_selected_currents()
        print(f"Expected: {expected}, Actual: {actual}")
        assert actual == expected, f"Test 2 failed: {actual} != {expected}"
        print("✓ Test 2 passed")

        # Test enabling 150mA (should enable all)
        print("\\nTest 3: Enable 150mA (max level)")
        self.variables[150].set(True)
        self._on_checkbox_change(150)
        expected = [0, 25, 50, 75, 100, 125, 150]
        actual = self.get_selected_currents()
        print(f"Expected: {expected}, Actual: {actual}")
        assert actual == expected, f"Test 3 failed: {actual} != {expected}"
        print("✓ Test 3 passed")

        print("\\n✓ All tests passed! Logic is working correctly.")

    def _reset_checkboxes(self):
        """Reset all checkboxes to unchecked"""
        for var in self.variables.values():
            var.set(False)

    def run(self):
        """Run the test GUI"""
        self.root.mainloop()

if __name__ == "__main__":
    print("Testing current level checkbox logic...")
    test = CurrentLevelControlTest()

    # Run automated tests
    test._test_logic()

    print("\\nStarting interactive GUI test...")
    print("Try checking/unchecking different current levels to see the logic in action.")
    print("Close the window when done.")

    test.run()