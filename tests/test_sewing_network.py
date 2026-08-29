from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PatternModel import Seam
from SewingNetwork import SewingMember, build_mn_seams


def lengths(mapping):
    return lambda piece, edge: mapping[(piece, edge)]


class SewingNetworkTests(unittest.TestCase):
    def test_two_to_one_partitions_long_edge_deterministically(self):
        seams = build_mn_seams(
            "rel-1",
            [SewingMember("A", 0), SewingMember("A", 1)],
            [SewingMember("B", 2)],
            lengths({("A", 0): 100, ("A", 1): 50, ("B", 2): 150}),
        )
        self.assertEqual(len(seams), 2)
        self.assertTrue(all(isinstance(seam, Seam) for seam in seams))
        self.assertEqual(
            [(s.edge_a, s.start_a, s.end_a, s.edge_b, s.start_b, s.end_b) for s in seams],
            [(0, 0.0, 1.0, 2, 0.0, 2 / 3), (1, 0.0, 1.0, 2, 2 / 3, 1.0)],
        )
        self.assertTrue(all(seam.stitch_group == "rel-1" for seam in seams))

    def test_one_to_two_supports_reversal_and_uniform_alignment(self):
        seams = build_mn_seams(
            "rel-2",
            [SewingMember("A", 0)],
            [SewingMember("B", 1), SewingMember("B", 2)],
            lengths({("A", 0): 120, ("B", 1): 40, ("B", 2): 80}),
            reversed_b=True,
            alignment="uniform",
        )
        self.assertEqual(len(seams), 2)
        self.assertEqual([round(seam.start_b, 8) for seam in seams], [0.0, round(1 / 3, 8)])
        self.assertEqual([round(seam.end_b, 8) for seam in seams], [round(1 / 3, 8), 1.0])
        self.assertTrue(all(seam.reversed_b for seam in seams))
        self.assertTrue(all(seam.alignment == "uniform" for seam in seams))

    def test_free_sewing_uses_partial_member_ranges(self):
        seams = build_mn_seams(
            "free-1",
            [SewingMember("A", 0, 0.2, 0.8)],
            [SewingMember("B", 1, 0.1, 0.7)],
            lengths({("A", 0): 100, ("B", 1): 120}),
        )
        self.assertEqual(len(seams), 1)
        seam = seams[0]
        self.assertAlmostEqual(seam.start_a, 0.2)
        self.assertAlmostEqual(seam.end_a, 0.8)
        self.assertAlmostEqual(seam.start_b, 0.1)
        self.assertAlmostEqual(seam.end_b, 0.7)

    def test_members_must_belong_to_one_piece_per_side(self):
        with self.assertRaisesRegex(ValueError, "exactly one pattern piece"):
            build_mn_seams(
                "bad",
                [SewingMember("A", 0), SewingMember("A2", 1)],
                [SewingMember("B", 0)],
                lengths({("A", 0): 10, ("A2", 1): 10, ("B", 0): 20}),
            )


if __name__ == "__main__":
    unittest.main()
