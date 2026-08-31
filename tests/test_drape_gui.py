"""Headless contract tests for the native DrapeTarget task-panel frontend."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
GUI = (ROOT / "DrapeGui.py").read_text(encoding="utf-8")
COMMANDS = (ROOT / "DrapeCommands.py").read_text(encoding="utf-8")


class DrapeGuiTests(unittest.TestCase):
    def test_panel_has_grouped_collision_controls(self):
        for text in ("Collision object", "Collision quality", "Target state"):
            self.assertIn(text, GUI)
        for text in ("Provider", "Source", "Preset", "Tessellation", "Collision thickness"):
            self.assertIn(text, GUI)

    def test_panel_uses_staged_apply_and_cancel(self):
        self.assertIn("Apply & Refresh", GUI)
        self.assertIn('self.cancel_button = QtWidgets.QPushButton("Cancel")', GUI)
        self.assertIn("def accept(self):", GUI)
        self.assertIn("def reject(self):", GUI)
        self.assertIn("getStandardButtons", GUI)

    def test_panel_exposes_both_target_providers(self):
        self.assertIn('(\"Mannequin\", \"FreeCAD Geometry\")', GUI)
        self.assertIn('getattr(obj, "AvatarType", "") == "ClothAvatar"', GUI)
        self.assertIn("hasattr(obj, \"Shape\") or hasattr(obj, \"Mesh\")", GUI)

    def test_quality_presets_are_explicit(self):
        self.assertIn('(\"Preview\", 2.5)', GUI)
        self.assertIn('(\"Normal\", 1.0)', GUI)
        self.assertIn('(\"Final\", 0.35)', GUI)

    def test_public_edit_and_refresh_commands_are_registered(self):
        for command in ("ClothDrape_EditTarget", "ClothDrape_RefreshTarget"):
            self.assertIn(command, COMMANDS)
        self.assertIn("show_drape_target_task", COMMANDS)
        self.assertIn("assign_drape_target", GUI)


if __name__ == "__main__":
    unittest.main()
