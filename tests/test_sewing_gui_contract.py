# Copyright (C) 2026 FreeCAD Cloth contributors
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freecad_cloth.sewing.SewingCorrespondence import analyze_correspondence
from freecad_cloth.sewing.SewingGui import (
    SewingTaskPanel,
    repair_correspondence_settings,
    seam_reference_status,
    validate_seam_for_accept,
)


class SewingGuiContractTests(unittest.TestCase):
    def test_valid_seam_can_be_accepted(self):
        seam = SimpleNamespace(SeamId="s1", Status="Valid")
        self.assertEqual(seam_reference_status(seam), "Valid")
        self.assertTrue(validate_seam_for_accept(seam))

    def test_missing_seam_is_rejected_with_context(self):
        self.assertEqual(seam_reference_status(None), "Missing seam")
        with self.assertRaisesRegex(ValueError, r"invalid seam reference <unnamed>: Missing seam"):
            validate_seam_for_accept(None)

    def test_changed_reference_is_rejected_with_identity(self):
        seam = SimpleNamespace(SeamId="s-changed", Status="Changed reference")
        with self.assertRaisesRegex(ValueError, r"s-changed: Changed reference"):
            validate_seam_for_accept(seam)

    def test_missing_reference_is_rejected_with_identity(self):
        seam = SimpleNamespace(SeamId="s-missing", Status="Missing reference")
        with self.assertRaisesRegex(ValueError, r"s-missing: Missing reference"):
            validate_seam_for_accept(seam)

    def test_reverse_repair_is_explicit_and_reversible(self):
        seam = SimpleNamespace(ReversedB=True, StartA=0.0, EndA=1.0, StartB=0.0, EndB=1.0)
        report = analyze_correspondence(100.0, 100.0, reversed_b=True)
        self.assertEqual(
            repair_correspondence_settings(seam, report), "reversed correspondence repaired"
        )
        self.assertFalse(seam.ReversedB)

    def test_range_repair_resets_both_sides(self):
        seam = SimpleNamespace(ReversedB=False, StartA=0.2, EndA=0.8, StartB=0.1, EndB=0.9)
        report = analyze_correspondence(100.0, 100.0, start_a=0.8, end_a=0.2)
        self.assertEqual(
            repair_correspondence_settings(seam, report), "invalid ranges reset to full seam edges"
        )
        self.assertEqual((seam.StartA, seam.EndA, seam.StartB, seam.EndB), (0.0, 1.0, 0.0, 1.0))

    def test_length_mismatch_is_never_silently_repaired(self):
        seam = SimpleNamespace(ReversedB=False, StartA=0.0, EndA=1.0, StartB=0.0, EndB=1.0)
        report = analyze_correspondence(100.0, 130.0)
        with self.assertRaisesRegex(ValueError, "length mismatch requires editing"):
            repair_correspondence_settings(seam, report)

    def test_refresh_accepts_and_preserves_action_feedback(self) -> None:
        """Keep seam validity visible when a navigation action completes."""
        panel = SewingTaskPanel.__new__(SewingTaskPanel)
        panel.obj = SimpleNamespace(
            Status="Valid",
            LengthA=100.0,
            LengthB=100.0,
            LengthDifference=0.0,
            RelativeTolerance=0.05,
        )
        panel.seam = None
        panel.status = SimpleNamespace(status=None)
        panel.action_feedback = SimpleNamespace(status=None)
        panel.lengths = SimpleNamespace(text="")
        panel.lengths.setText = lambda text: setattr(panel.lengths, "text", text)
        panel.correspondence = SimpleNamespace(status=None)
        updates = []

        def set_status(label: SimpleNamespace, message: str, state: str = "info") -> None:
            """Capture validation and action status assignments."""
            label.status = (message, state)
            updates.append((label, message, state))

        with patch("freecad_cloth.common.UiDesign.set_status", side_effect=set_status):
            panel._refresh("Focus seam in the 3D view.")

        self.assertEqual(panel.lengths.text, "100.00 / 100.00 mm (Δ 0.00)")
        self.assertEqual(panel.correspondence.status, ("No seam correspondence", "warning"))
        self.assertEqual(panel.status.status, ("Valid", "success"))
        self.assertEqual(
            panel.action_feedback.status,
            ("Focus seam in the 3D view.", "info"),
        )
        self.assertEqual(
            updates[-1],
            (panel.action_feedback, "Focus seam in the 3D view.", "info"),
        )


if __name__ == "__main__":
    unittest.main()
