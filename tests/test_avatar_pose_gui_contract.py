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
    assert 'self.symmetry.setText("Mirror")' in SOURCE
    assert 'self.angle_snap.setText("5° Snap")' in SOURCE
    assert 'self.precision.setText("Exact angles…")' in SOURCE
    assert "self.precision_widget.setVisible(False)" in SOURCE
    preset_section = SOURCE.split("for preset, label in self.PRESETS:", 1)[1].split("presets.addStretch", 1)[0]
    assert "setCheckable(True)" not in preset_section
    assert 'self.joint_list_toggle.setText("Joint list")' in SOURCE
    assert "self.joint_list_widget.setVisible(False)" in SOURCE
    assert "modifyStandardButtons" in SOURCE
    assert "ok.setText(" in SOURCE
    assert "Do not draw a fake manipulator" in SOURCE
    assert "self.instruction_label.setText(" in SOURCE
    assert "self.panel.angle_snap.setEnabled(False)" in SOURCE


def test_pose_mode_is_viewport_first():
    assert "class SkeletonPoseController" in SOURCE
    assert 'coin.SoType.fromName("SoTransformDragger")' in SOURCE
    assert "hideTranslationX" in SOURCE
    assert "showRotationX" in SOURCE
    assert "coin.SoTrackballDragger()" in SOURCE
    assert "coin.SoDepthBuffer()" in SOURCE
    assert "depth.test = False" in SOURCE
    assert "depth.write = False" in SOURCE
    assert "addEventCallbackPivy" in SOURCE
    assert "SoLocation2Event" in SOURCE
    assert "_set_hover_bone" in SOURCE
    assert "_pick_bone" in SOURCE
    assert "getPointOnScreen" in SOURCE
    assert "_screen_segment_distance" in SOURCE
    assert "projected_segments" in SOURCE
    assert "JOINT_PICK_RADIUS" in SOURCE
    assert "skeleton_world_segments" in SOURCE
    assert "self._skeleton_segments" in SOURCE
    assert "self.panel._stage_joint_rotation(" in SOURCE
    assert "Click a bone to select it. Drag a colored ring to rotate that axis." in SOURCE


def test_pose_mode_has_discoverable_joint_groups_and_presets():
    assert "self.joints = QtWidgets.QTreeWidget()" in SOURCE
    for group in ("Torso", "Left arm", "Right arm", "Left leg", "Right leg"):
        assert '"%s"' % group in SOURCE
    for preset in ("standing", "sewing", "sitting"):
        assert '"%s"' % preset in SOURCE


def test_pose_mode_keeps_precision_as_secondary_path():
    assert "QSlider" not in SOURCE
    assert 'for axis in ("x", "y", "z")' in SOURCE
    assert 'box.setSuffix("°")' in SOURCE
    assert 'self.precision.setChecked(False)' in SOURCE
    assert "snap=False" in SOURCE


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
