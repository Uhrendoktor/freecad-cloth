import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from SewingNetworkGui import network_reference_errors, validate_network_for_edit


class _Seam:
    def __init__(self, seam_id, status="Valid"):
        self.SeamId = seam_id
        self.Status = status


class _Network:
    def __init__(self, seams):
        self.Seams = seams


class SewingNetworkGuiContractTests(unittest.TestCase):
    def test_valid_network_has_no_reference_errors(self):
        network = _Network([_Seam("s1"), _Seam("s2")])
        self.assertEqual(network_reference_errors(network), ())
        self.assertTrue(validate_network_for_edit(network))

    def test_invalid_reference_is_reported_with_seam_identity(self):
        network = _Network([_Seam("s1"), _Seam("s2", "Changed reference")])
        self.assertEqual(network_reference_errors(network), (("s2", "Changed reference"),))
        with self.assertRaisesRegex(ValueError, r"s2: Changed reference"):
            validate_network_for_edit(network)

    def test_missing_reference_is_reported_without_silent_edit(self):
        network = _Network([_Seam("s-missing", "Missing reference")])
        with self.assertRaisesRegex(ValueError, r"invalid seam references.*s-missing: Missing reference"):
            validate_network_for_edit(network)


if __name__ == "__main__":
    unittest.main()
