"""Regression tests for the shared headless-safe FreeCAD command adapter."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freecad_cloth.common.CommandAdapter import FunctionCommand, register_commands


def test_function_command_uses_callable_metadata_and_returns_result():
    def example_command():
        """Example command tooltip."""
        return 42

    command = FunctionCommand(example_command)
    assert command.Activated() == 42
    assert command.GetResources() == {
        "MenuText": "Example Command",
        "ToolTip": "Example command tooltip.",
    }


def test_function_command_accepts_explicit_tooltip():
    def example_command():
        return None

    command = FunctionCommand(example_command, "Explicit tooltip")
    assert command.GetResources()["ToolTip"] == "Explicit tooltip"


def test_register_commands_is_headless_safe_and_registers_each_callable():
    registered = {}

    class FakeGui:
        def addCommand(self, name, command):
            registered[name] = command

    def first():
        return "first"

    def second():
        return "second"

    register_commands(FakeGui(), {"First": first, "Second": second})
    assert set(registered) == {"First", "Second"}
    assert registered["First"].Activated() == "first"
    assert registered["Second"].Activated() == "second"


def test_register_commands_ignores_gui_without_add_command():
    register_commands(object(), {"Unused": lambda: None})


if __name__ == "__main__":
    for name, fn in globals().copy().items():
        if name.startswith("test_"):
            fn()
    print("command adapter tests passed")
