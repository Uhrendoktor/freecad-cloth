from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "resources" / "icons"
COMMANDS = (
    "ClothSewing_CreateSeam",
    "ClothSewing_CreateMNSewing",
    "ClothSewing_CreateOperation",
    "ClothSewing_EditOperation",
    "ClothSewing_ReverseSeam",
    "ClothSewing_ToggleAlignment",
    "ClothSewing_Validate",
    "ClothSewing_Show2D",
)


def test_sewing_commands_have_svg_icons():
    for command in COMMANDS:
        icon = ICON_DIR / f"{command}.svg"
        assert icon.is_file(), command
        text = icon.read_text(encoding="utf-8")
        assert "<svg" in text
        assert "viewBox=" in text


def test_sewing_command_resources_reference_command_icons():
    import SewingCommands

    assert set(SewingCommands.COMMANDS) == set(COMMANDS)
    assert set(SewingCommands._COMMAND_HANDLERS) == set(COMMANDS)
    assert set(SewingCommands._ACTIVATION) == set(COMMANDS)

    for command in COMMANDS:
        handler = SewingCommands._COMMAND_HANDLERS[command]
        active = SewingCommands._ACTIVATION[command]
        icon = str(ICON_DIR / f"{command}.svg")
        wrapper = SewingCommands._SewingCommand(handler, active, SewingCommands._TOOLTIPS[command], SewingCommands._MENU_TEXT[command], icon)
        resources = wrapper.GetResources()
        assert resources["Pixmap"] == icon
        assert resources["MenuText"] == SewingCommands._MENU_TEXT[command]
        assert resources["ToolTip"] == SewingCommands._TOOLTIPS[command]


def test_sewing_command_wrapper_preserves_activation_and_handler_behavior():
    import SewingCommands

    calls = []

    def handler():
        calls.append("activated")
        return "result"

    wrapper = SewingCommands._SewingCommand(handler, lambda: True, "tooltip", "Menu", "icon.svg")
    assert wrapper.IsActive() is True
    assert wrapper.Activated() == "result"
    assert calls == ["activated"]


if __name__ == "__main__":
    test_sewing_commands_have_svg_icons()
    test_sewing_command_resources_reference_command_icons()
    test_sewing_command_wrapper_preserves_activation_and_handler_behavior()
    print("sewing icon tests passed")
