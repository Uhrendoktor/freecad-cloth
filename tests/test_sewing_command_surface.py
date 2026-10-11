"""Regression coverage for the public Sewing workbench command surface."""

from freecad_cloth.avatar import AvatarCommands, FittingCommands
from freecad_cloth.sewing import SewingCommands, SewingNetworkCommands


def test_sewing_command_inventory_is_unique_and_fully_owned_by_command_modules():
    core = tuple(SewingCommands.COMMANDS)
    network = tuple(SewingNetworkCommands.COMMANDS)
    fitting = tuple(FittingCommands.COMMANDS)
    avatar = tuple(AvatarCommands.COMMANDS)
    all_commands = core + network + fitting + avatar

    assert all_commands
    assert len(all_commands) == len(set(all_commands))
    assert all(name.startswith(("ClothSewing_", "ClothFitting_")) for name in all_commands)


def test_core_sewing_commands_have_handlers_resources_and_activation_rules():
    assert tuple(SewingCommands._COMMAND_HANDLERS) == tuple(SewingCommands.COMMANDS)
    assert set(SewingCommands._MENU_TEXT) == set(SewingCommands.COMMANDS)
    assert set(SewingCommands._TOOLTIPS) == set(SewingCommands.COMMANDS)
    assert set(SewingCommands._ACTIVATION) == set(SewingCommands.COMMANDS)
    assert all(callable(handler) for handler in SewingCommands._COMMAND_HANDLERS.values())
    assert all(callable(rule) for rule in SewingCommands._ACTIVATION.values())
    assert all(str(SewingCommands._MENU_TEXT[name]).strip() for name in SewingCommands.COMMANDS)
    assert all(str(SewingCommands._TOOLTIPS[name]).strip() for name in SewingCommands.COMMANDS)
