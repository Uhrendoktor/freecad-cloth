"""Headless contract checks for the native avatar task panel."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "AvatarGui.py").read_text(encoding="utf-8")
commands = (ROOT / "AvatarCommands.py").read_text(encoding="utf-8")


def test_avatar_panel_has_clo_style_grouped_controls():
    assert "class AvatarTaskPanel" in source
    assert '"Body measurements"' in source
    assert '"Proportions"' in source
    assert '"Pose"' in source
    assert '"Display"' in source
    assert "Collision / skin offset" in source
    assert "Show measurement landmarks" in source
    assert "getStandardButtons" in source
    assert "QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel" in source


def test_avatar_panel_edits_persistent_properties_and_rebuilds():
    assert "setattr(self.avatar, key.title(), box.value())" in source
    assert "self.avatar.PosePreset = str(value)" in source
    assert "self.avatar.SkinOffset = float(value)" in source
    assert "from AvatarCommands import rebuild_avatar" in source
    assert "Gui.Control.showDialog(panel)" in source


def test_avatar_edit_command_is_publicly_registered():
    assert "ClothFitting_EditAvatar" in commands
    assert '"ClothFitting_EditAvatar":edit_avatar' in commands


if __name__ == "__main__":
    for name, fn in globals().copy().items():
        if name.startswith("test_"):
            fn()
    print("avatar GUI contract checks passed")
