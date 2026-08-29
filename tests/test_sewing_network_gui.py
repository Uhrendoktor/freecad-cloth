import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_sewing_network_gui_contract_is_headless_importable():
    import SewingNetworkGui
    assert hasattr(SewingNetworkGui, "SewingNetworkTaskPanel")
    assert hasattr(SewingNetworkGui, "show_sewing_network_task")


def test_sewing_network_commands_expose_free_sewing_and_editor():
    import SewingNetworkCommands
    assert "ClothSewing_FreeSewing" in SewingNetworkCommands.COMMANDS
    assert "ClothSewing_EditNetwork" in SewingNetworkCommands.COMMANDS
    assert "ClothSewing_CreateNetwork" in SewingNetworkCommands.COMMANDS


if __name__ == "__main__":
    test_sewing_network_gui_contract_is_headless_importable()
    test_sewing_network_commands_expose_free_sewing_and_editor()
    print("sewing network GUI contract tests passed")
