"""Headless contract checks for the focused mannequin Pose Mode UI."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "freecad_cloth" / "avatar" / "AvatarPoseGui.py").read_text(
    encoding="utf-8"
)
AVATAR_GUI = (ROOT / "freecad_cloth" / "avatar" / "AvatarGui.py").read_text(
    encoding="utf-8"
)
COMMANDS = (ROOT / "freecad_cloth" / "avatar" / "AvatarCommands.py").read_text(
    encoding="utf-8"
)


def test_pose_mode_is_a_dedicated_task_panel():
    assert "class AvatarPoseTaskPanel" in SOURCE
    assert 'title = QtWidgets.QLabel("Pose Mode")' in SOURCE
    assert 'self.symmetry = QtWidgets.QCheckBox("Symmetry")' in SOURCE
    assert 'self.angle_snap = QtWidgets.QCheckBox("Snap 5°")' in SOURCE
    assert 'self.precision.setText("Precision")' in SOURCE
    assert "self.precision_widget.setVisible(False)" in SOURCE


def test_pose_mode_is_viewport_first():
    assert "class SkeletonPoseController" in SOURCE
    assert "coin.SoTrackballDragger()" in SOURCE
    assert "addEventCallbackPivy" in SOURCE
    assert "getPointOnScreen" in SOURCE
    assert "JOINT_PICK_RADIUS" in SOURCE
    assert "self.panel._stage_joint_rotation(" in SOURCE
    assert "release to stage the pose" in SOURCE


def test_pose_mode_has_discoverable_joint_groups_and_presets():
    assert "self.joints = QtWidgets.QTreeWidget()" in SOURCE
    for group in ("Torso", "Left arm", "Right arm", "Left leg", "Right leg"):
        assert '"%s"' % group in SOURCE
    for preset in ("standing", "sewing", "sitting"):
        assert '"%s"' % preset in SOURCE


def test_pose_mode_keeps_precision_as_secondary_path():
    assert "self._sliders[axis]" in SOURCE
    assert 'for axis, text in (("x", "X"), ("y", "Y"), ("z", "Z"))' in SOURCE
    assert 'box.setSuffix("°")' in SOURCE
    assert 'self.precision.setChecked(False)' in SOURCE


def test_pose_mode_uses_persistent_fk_data_and_cancel_cleanup():
    assert "JointRotation" in SOURCE
    assert "joint_rotations_from_json" in SOURCE
    assert "joint_rotations_to_json" in SOURCE
    assert "self.avatar.JointPoseJSON =" in SOURCE
    assert "self.controller.deactivate()" in SOURCE
    assert "def reject(self):" in SOURCE


def test_avatar_editor_routes_posing_to_dedicated_mode():
    assert 'self.pose_mode_button = QtWidgets.QPushButton("3D Pose Mode…")' in AVATAR_GUI
    assert "self.pose_mode_button.clicked.connect(self._open_pose_mode)" in AVATAR_GUI
    assert "pose.setVisible(False)" in AVATAR_GUI
    assert "skeleton.setVisible(False)" in AVATAR_GUI


def test_pose_command_is_publicly_registered():
    assert "ClothFitting_PoseAvatar" in COMMANDS
    assert '"ClothFitting_PoseAvatar": pose_avatar' in COMMANDS


if __name__ == "__main__":
    for name, function in globals().copy().items():
        if name.startswith("test_"):
            function()
    print("avatar Pose Mode GUI contract checks passed")
