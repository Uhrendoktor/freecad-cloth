"""Headless contract checks for the native avatar task panel."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "AvatarGui.py").read_text(encoding="utf-8")
commands = (ROOT / "AvatarCommands.py").read_text(encoding="utf-8")


def test_avatar_panel_has_grouped_controls_and_lifecycle():
    assert "class AvatarTaskPanel" in source
    assert '"Body measurements"' in source
    assert '"Proportions"' in source
    assert '"Pose"' in source
    assert '"Display"' in source
    assert '"Arrangement points"' in source
    assert "Apply & Rebuild" in source
    assert "getStandardButtons" in source
    assert "QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel" in source


def test_avatar_panel_stages_values_and_validates_before_mutation():
    assert "self._dirty = False" in source
    assert "self._dirty = True" in source
    assert "def _staged_parameters(self):" in source
    assert "AvatarParameters(values, self.skin_offset.value(), Pose(str(self.pose.currentText())))" in source
    assert "for key, property_name in self.PROPERTY_MAP.items()" in source
    assert "setattr(self.avatar, property_name, params.measurements[key])" in source
    assert "from freecad_cloth.avatar.AvatarCommands import rebuild_avatar" in source


def test_avatar_panel_uses_explicit_property_mapping():
    assert '"high_hip": "High_Hip"' in source
    assert '"upper_arm": "Upper_Arm"' in source
    assert '"front_waist": "Front_Waist"' in source
    assert '"back_waist": "Back_Waist"' in source
    assert 'PROPERTY_MAP = {' in commands
    assert '"high_hip": "High_Hip"' in commands
    assert '"upper_arm": "Upper_Arm"' in commands
    assert '"front_waist": "Front_Waist"' in commands
    assert '"back_waist": "Back_Waist"' in commands


def test_avatar_panel_exposes_persistent_fitting_points():
    assert "self.arrangement_points = QtWidgets.QListWidget()" in source
    assert "getattr(self.avatar, \"ArrangementPoints\", [])" in source
    assert "self._update_arrangement_points()" in source
    assert '"ArrangementPoints"' in commands
    assert "def avatar_arrangement_points():" in commands


def test_avatar_edit_command_is_publicly_registered():
    assert "ClothFitting_EditAvatar" in commands
    assert '"ClothFitting_EditAvatar":edit_avatar' in commands


if __name__ == "__main__":
    for name, fn in globals().copy().items():
        if name.startswith("test_"):
            fn()
    print("avatar GUI contract checks passed")
