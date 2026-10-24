# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression checks for the fitting commands that cross into Simulation."""

from pathlib import Path
from types import SimpleNamespace

from freecad_cloth.avatar import FittingCommands
from freecad_cloth.common.CommandAdapter import FunctionCommand
from freecad_cloth.simulation import FittingHandoff as fitting_handoff
from tests.support.assertions import require

_ROOT = Path(__file__).resolve().parents[1]
_EXPECTED_HANDOFF_COMMANDS = frozenset(
    {"ClothFitting_AssignAvatar", "ClothFitting_CreateSimulation"}
)


def test_fitting_handoff_registers_both_simulation_owned_command_ids() -> None:
    """Keep the two fitting-to-simulation GUI commands registered by Simulation."""
    registered: dict[str, object] = {}

    def add_command(name: str, command: object) -> None:
        """Capture one GUI command registration for the contract check.

        Args:
            name: Stable FreeCAD command identifier.
            command: Command adapter supplied to the GUI registrar.
        """
        registered[name] = command

    gui = SimpleNamespace(addCommand=add_command)
    fitting_handoff.register_fitting_handoff_commands(gui)

    require(
        condition=set(FittingCommands.COMMANDS) >= _EXPECTED_HANDOFF_COMMANDS,
        message="The public fitting inventory must retain both handoff command identifiers.",
    )
    require(
        condition=set(registered) == _EXPECTED_HANDOFF_COMMANDS,
        message="Simulation must register exactly the two fitting handoff commands.",
    )
    registered_functions = {
        name: command.function
        for name, command in registered.items()
        if isinstance(command, FunctionCommand)
    }
    require(
        condition=registered_functions == fitting_handoff.FITTING_HANDOFF_COMMAND_HANDLERS,
        message="GUI command adapters must call the simulation-side handoff functions.",
    )


def test_fitting_command_module_has_no_simulation_dependency() -> None:
    """Keep Sewing-to-Simulation dependencies out of avatar fitting commands."""
    source = (_ROOT / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
    require(
        condition="freecad_cloth.simulation." not in source,
        message="FittingCommands must not import the Simulation package.",
    )


def test_shared_bootstrap_registers_handoff_commands_before_workbench_activation() -> None:
    """Keep the simulation handoff handlers available during normal FreeCAD startup."""
    source = (_ROOT / "freecad_cloth" / "bootstrap.py").read_text(encoding="utf-8")
    require(
        condition='from freecad_cloth.simulation import FittingHandoff as fitting_handoff' in source,
        message="The shared bootstrap must load the simulation handoff module.",
    )
    require(
        condition="fitting_handoff.register_fitting_handoff_commands(gui)" in source,
        message="The shared bootstrap must register simulation-owned fitting commands.",
    )
