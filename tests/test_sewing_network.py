from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PatternModel import Seam
from SewingCorrespondence import analyze_correspondence
from SewingNetwork import SewingMember, build_mn_seams, network_invalid_reason
from SewingValidation import seam_diagnostic, validate_sewing_graph

def lengths(mapping): return lambda piece, edge: mapping[(piece, edge)]
class _SeamStatus:
    def __init__(self, seam_id, status): self.SeamId, self.Status = seam_id, status
class SewingNetworkTests(unittest.TestCase):
    def test_two_to_one_partitions_long_edge_deterministically(self):
        seams=build_mn_seams("rel-1",[SewingMember("A",0),SewingMember("A",1)],[SewingMember("B",2)],lengths({("A",0):100,("A",1):50,("B",2):150}))
        self.assertEqual(len(seams),2); self.assertTrue(all(isinstance(seam,Seam) for seam in seams))
        self.assertEqual([(s.edge_a,s.start_a,s.end_a,s.edge_b,s.start_b,s.end_b) for s in seams],[(0,0.0,1.0,2,0.0,2/3),(1,0.0,1.0,2,2/3,1.0)])
        self.assertTrue(all(seam.stitch_group=="rel-1" for seam in seams))
    def test_one_to_two_supports_reversal_and_uniform_alignment(self):
        seams=build_mn_seams("rel-2",[SewingMember("A",0)],[SewingMember("B",1),SewingMember("B",2)],lengths({("A",0):120,("B",1):40,("B",2):80}),reversed_b=True,alignment="uniform")
        self.assertEqual(len(seams),2); self.assertEqual([round(seam.start_b,8) for seam in seams],[0.0,0.0]); self.assertEqual([round(seam.end_b,8) for seam in seams],[1.0,1.0]); self.assertEqual([round(seam.start_a,8) for seam in seams],[0.0,round(1/3,8)]); self.assertEqual([round(seam.end_a,8) for seam in seams],[round(1/3,8),1.0]); self.assertTrue(all(seam.reversed_b for seam in seams)); self.assertTrue(all(seam.alignment=="uniform" for seam in seams))
    def test_free_sewing_uses_partial_member_ranges(self):
        seams=build_mn_seams("free-1",[SewingMember("A",0,.2,.8)],[SewingMember("B",1,.1,.7)],lengths({("A",0):100,("B",1):120}))
        self.assertEqual(len(seams),1); seam=seams[0]; self.assertAlmostEqual(seam.start_a,.2); self.assertAlmostEqual(seam.end_a,.8); self.assertAlmostEqual(seam.start_b,.1); self.assertAlmostEqual(seam.end_b,.7)
    def test_members_must_belong_to_one_piece_per_side(self):
        with self.assertRaisesRegex(ValueError,"exactly one pattern piece"): build_mn_seams("bad",[SewingMember("A",0),SewingMember("A2",1)],[SewingMember("B",0)],lengths({("A",0):10,("A2",1):10,("B",0):20}))
    def test_invalid_member_status_is_deterministic_and_user_visible(self):
        self.assertEqual(network_invalid_reason([_SeamStatus("rel-1-1-1","Changed reference")]),"Invalid member seam(s): rel-1-1-1: Changed reference")
    def test_all_valid_member_statuses_have_no_invalid_reason(self): self.assertEqual(network_invalid_reason([_SeamStatus("rel-1-1-1","Valid")]),"")
    def test_valid_and_reversed_seam_diagnostics(self):
        self.assertEqual(seam_diagnostic(SimpleNamespace(SeamId="s1",PieceA="A",PieceB="B",Status="Valid"))["status"],"Valid")
        self.assertTrue(seam_diagnostic(SimpleNamespace(SeamId="s2",PieceA="A",PieceB="B",Status="Valid",ReversedB=True))["reversed"])
        self.assertEqual(analyze_correspondence(100,100,reversed_b=True).status,"reversed")
    def test_mismatched_lengths_are_explicit(self):
        report=analyze_correspondence(100,112,length_tolerance=.05); self.assertEqual(report.status,"length_mismatch"); self.assertFalse(report.valid)
    def test_one_to_many_and_many_to_many_partition_counts(self):
        one=build_mn_seams("1n",[SewingMember("A",0)],[SewingMember("B",0),SewingMember("B",1)],{("A",0):100,("B",0):40,("B",1):60})
        many=build_mn_seams("mn",[SewingMember("A",0),SewingMember("A",1)],[SewingMember("B",0),SewingMember("B",1)],{("A",0):60,("A",1):40,("B",0):30,("B",1):70})
        self.assertEqual(len(one),2); self.assertEqual(len(many),3); self.assertTrue(all(s.stitch_group=="mn" for s in many))
    def test_complete_graph_and_isolated_piece_diagnostics(self):
        def piece(pid): return SimpleNamespace(PatternType="PatternPiece",PieceId=pid)
        def seam(sid,a,b,status="Valid"): return SimpleNamespace(SeamId=sid,PieceA=a,PieceB=b,EdgeA=0,EdgeB=0,EdgeAId="",EdgeBId="",Status=status,StartA=0.0,EndA=1.0,StartB=0.0,EndB=1.0)
        complete=SimpleNamespace(Objects=[piece("A"),piece("B"),piece("C"),seam("s1","A","B"),seam("s2","B","C")]); self.assertEqual(validate_sewing_graph(complete)["status"],"Valid")
        incomplete=SimpleNamespace(Objects=[piece("A"),piece("B"),piece("C"),seam("s1","A","B")]); report=validate_sewing_graph(incomplete); self.assertEqual(report["status"],"Incomplete"); self.assertEqual(report["isolated"],("C",))
        invalid=SimpleNamespace(Objects=[piece("A"),piece("B"),seam("broken","A","B","Changed reference")]); self.assertEqual(validate_sewing_graph(invalid)["status"],"Invalid")
    def test_network_graph_members_are_inspectable(self):
        def piece(pid): return SimpleNamespace(PatternType="PatternPiece",PieceId=pid)
        def seam(sid): return SimpleNamespace(SeamId=sid,PieceA="A",PieceB="B",Status="Valid")
        members=(seam("mn-1"),seam("mn-2")); network=SimpleNamespace(SewingType="SewingNetwork",RelationshipId="rel",Seams=members,Status="Valid",LengthDifference=0.0,InvalidReason="",Name="Network")
        report=validate_sewing_graph(SimpleNamespace(Objects=[piece("A"),piece("B"),*members,network])); self.assertEqual(report["network_count"],1); self.assertEqual(report["networks"][0]["segments"],2)
if __name__ == "__main__": unittest.main()
