import sys
from pathlib import Path
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from SewingCorrespondence import analyze_correspondence
from SewingGui import repair_correspondence_settings, seam_reference_status, validate_seam_for_accept


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
        self.assertEqual(repair_correspondence_settings(seam, report), "reversed correspondence repaired")
        self.assertFalse(seam.ReversedB)

    def test_range_repair_resets_both_sides(self):
        seam = SimpleNamespace(ReversedB=False, StartA=0.2, EndA=0.8, StartB=0.1, EndB=0.9)
        report = analyze_correspondence(100.0, 100.0, start_a=0.8, end_a=0.2)
        self.assertEqual(repair_correspondence_settings(seam, report), "invalid ranges reset to full seam edges")
        self.assertEqual((seam.StartA, seam.EndA, seam.StartB, seam.EndB), (0.0, 1.0, 0.0, 1.0))

    def test_length_mismatch_is_never_silently_repaired(self):
        seam = SimpleNamespace(ReversedB=False, StartA=0.0, EndA=1.0, StartB=0.0, EndB=1.0)
        report = analyze_correspondence(100.0, 130.0)
        with self.assertRaisesRegex(ValueError, "length mismatch requires editing"):
            repair_correspondence_settings(seam, report)


if __name__ == "__main__":
    unittest.main()
