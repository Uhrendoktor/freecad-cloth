from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freecad_cloth.pattern.PatternModel import Seam
from freecad_cloth.sewing.SewingNetwork import SewingMember, SewingNetworkProxy, build_mn_seams, network_invalid_reason


def lengths(mapping):
    return lambda piece, edge: mapping[(piece, edge)]


class _SeamStatus:
    def __init__(self, seam_id, status):
        self.SeamId = seam_id
        self.Status = status


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
        self.assertEqual([round(seam.start_b, 8) for seam in seams], [0.0, 0.0])
        self.assertEqual([round(seam.end_b, 8) for seam in seams], [1.0, 1.0])
        self.assertEqual([round(seam.start_a, 8) for seam in seams], [0.0, round(1 / 3, 8)])
        self.assertEqual([round(seam.end_a, 8) for seam in seams], [round(1 / 3, 8), 1.0])
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

    def test_two_to_two_physical_member_ranges_are_proportional():
        seams = build_mn_seams(
            "mn-22",
            [SewingMember("A", 0), SewingMember("A", 1)],
            [SewingMember("B", 0), SewingMember("B", 1)],
            lengths({
                ("A", 0): 150.0, ("A", 1): 100.0,
                ("B", 0): 100.0, ("B", 1): 150.0,
            }),
            reversed_b=True,
            alignment="uniform",
        )
        assert len(seams) == 3
        assert [
            (round(seam.start_a, 8), round(seam.end_a, 8), round(seam.start_b, 8), round(seam.end_b, 8))
            for seam in seams
        ] == [
            (0.0, round(2 / 3, 8), 0.0, 1.0),
            (round(2 / 3, 8), 1.0, 0.0, round(1 / 3, 8)),
            (0.0, 1.0, round(1 / 3, 8), 1.0),
        ]
        assert all(seam.reversed_b for seam in seams)
        assert all(seam.alignment == "uniform" for seam in seams)


    def test_members_must_belong_to_one_piece_per_side(self):
        with self.assertRaisesRegex(ValueError, "exactly one pattern piece"):
            build_mn_seams(
                "bad",
                [SewingMember("A", 0), SewingMember("A2", 1)],
                [SewingMember("B", 0)],
                lengths({("A", 0): 10, ("A2", 1): 10, ("B", 0): 20}),
            )

    def test_invalid_member_status_is_deterministic_and_user_visible(self):
        seam = _SeamStatus("rel-1-1-1", "Changed reference")
        self.assertEqual(
            network_invalid_reason([seam]),
            "Invalid member seam(s): rel-1-1-1: Changed reference",
        )

    def test_changed_reference_member_invalidates_network_deterministically(self):
        seam = SimpleNamespace(SeamId="rel-1-1-1", Status="Changed reference", StitchGroup="rel-1")
        network = SimpleNamespace(
            Seams=(seam,),
            RelationshipId="rel-1",
            Status="Valid",
            InvalidReason="",
            SegmentCount=0,
            LengthA=0.0,
            LengthB=0.0,
            LengthDifference=0.0,
        )
        SewingNetworkProxy().execute(network)
        self.assertEqual(network.Status, "Invalid")
        self.assertEqual(network.InvalidReason, "Invalid member seam(s): rel-1-1-1: Changed reference")

    def test_all_valid_member_statuses_have_no_invalid_reason(self):
        seam = _SeamStatus("rel-1-1-1", "Valid")
        self.assertEqual(network_invalid_reason([seam]), "")

    def test_network_uses_shared_relative_mismatch_contract(self):
        class Doc:
            Objects = ()
        a = SimpleNamespace(
            SeamId="rel-1-1-1", Status="Valid", StitchGroup="rel-1", Document=Doc(),
            PieceA="A", PieceB="B", EdgeA=0, EdgeB=0, StartA=0.0, EndA=1.0, StartB=0.0, EndB=1.0,
        )
        network = SimpleNamespace(
            Seams=(a,), RelationshipId="rel-1", Status="Valid", InvalidReason="",
            SegmentCount=1, LengthA=100.0, LengthB=106.0, LengthDifference=6.0,
            RelativeTolerance=0.05,
        )
        import freecad_cloth.sewing.SewingNetwork as module
        old = module._network_lengths
        module._network_lengths = lambda seams: (100.0, 106.0)
        try:
            SewingNetworkProxy().execute(network)
        finally:
            module._network_lengths = old
        self.assertEqual(network.Status, "Length mismatch")
        self.assertEqual(network.CorrespondenceStatus, "length_mismatch")
        self.assertEqual(network.CorrespondenceSeverity, "error")
        self.assertEqual(
            network.CorrespondenceRecovery,
            "edit the pattern geometry or seam ranges; do not hide the mismatch with tolerance",
        )


if __name__ == "__main__":
    unittest.main()
