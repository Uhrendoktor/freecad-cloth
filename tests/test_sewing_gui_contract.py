import sys
from pathlib import Path
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from SewingGui import seam_reference_status, validate_seam_for_accept


class SewingGuiContractTests(unittest.TestCase):
    def test_valid_seam_can_be_accepted(self):
        seam = SimpleNamespace(SeamId="s1", Status="Valid")
        self.assertEqual(seam_reference_status(seam), "Valid")
        self.assertTrue(validate_seam_for_accept(seam))

    def test_missing_seam_is_rejected_with_context(self):
        self.assertEqual(seam_reference_status(None), "Missing seam")
        with self.assertRaisesRegex(ValueError, r"s.*<unnamed>.*Missing seam"):
            validate_seam_for_accept(None)

    def test_changed_reference_is_rejected_with_identity(self):
        seam = SimpleNamespace(SeamId="s-changed", Status="Changed reference")
        with self.assertRaisesRegex(ValueError, r"s-changed: Changed reference"):
            validate_seam_for_accept(seam)

    def test_missing_reference_is_rejected_with_identity(self):
        seam = SimpleNamespace(SeamId="s-missing", Status="Missing reference")
        with self.assertRaisesRegex(ValueError, r"s-missing: Missing reference"):
            validate_seam_for_accept(seam)


if __name__ == "__main__":
    unittest.main()
