"""Regression tests for the target-neutral draping contract."""
import unittest
from DrapeTarget import DrapeTargetSpec, source_signature, target_status

class _Vec:
    def __init__(self,x=0.0,y=0.0,z=0.0): self.x,self.y,self.z=x,y,z
class _Rotation:
    def __init__(self,angle=0.0): self.Angle=angle; self.Axis=_Vec(0,0,1)
class _Placement:
    def __init__(self,x=0.0,y=0.0,z=0.0,angle=0.0): self.Base=_Vec(x,y,z); self.Rotation=_Rotation(angle)
class _Shape:
    def __init__(self,value): self.value=value
    def isNull(self): return False
    def hashCode(self): return self.value
class _Target:
    Name="Chair"; Label="Chair target"; Placement=_Placement(); Shape=_Shape(1)
class _PersistentTarget:
    TargetType="FreeCAD Geometry"; Enabled=True; CollisionDeflection=1.0; CollisionThickness=2.0
    SourceObject=_Target(); CollisionVertexCount=8; CollisionTriangleCount=12
    SourceSignature=repr(source_signature(SourceObject,1.0,2.0))

class DrapeTargetTests(unittest.TestCase):
    def test_target_spec_accepts_supported_types(self):
        DrapeTargetSpec("Mannequin","ClothAvatar",1.0,2.0).validate(); DrapeTargetSpec("FreeCAD Geometry","Chair",0.5,1.5).validate()
    def test_target_spec_rejects_invalid_settings(self):
        for spec in (DrapeTargetSpec("Unknown","Chair"),DrapeTargetSpec("FreeCAD Geometry",""),DrapeTargetSpec("FreeCAD Geometry","Chair",0),DrapeTargetSpec("FreeCAD Geometry","Chair",1,-1)):
            with self.assertRaises(ValueError): spec.validate()
    def test_source_signature_tracks_geometry_placement_and_collision_settings(self):
        target=_Target(); baseline=source_signature(target,1,2); target.Shape.value=2; self.assertNotEqual(source_signature(target,1,2),baseline); target.Placement=_Placement(10,-5,0,15); moved=source_signature(target,1,2); self.assertNotEqual(moved,baseline); self.assertNotEqual(source_signature(target,.5,2),moved); self.assertNotEqual(source_signature(target,.5,4),source_signature(target,.5,2))
    def test_source_signature_is_stable(self):
        target=_Target(); self.assertEqual(source_signature(target,1,2),source_signature(target,1,2))
    def test_target_status_is_ready_when_signature_is_current(self):
        status=target_status(_PersistentTarget()); self.assertEqual(status["state"],"ready"); self.assertFalse(status["stale"])
    def test_target_status_reports_source_change_as_stale(self):
        target=_PersistentTarget(); target.SourceObject.Shape.value=99; status=target_status(target); self.assertEqual(status["state"],"stale"); self.assertTrue(status["stale"]); self.assertIn("source",status["reason"])
    def test_target_status_reports_missing_collision_cache(self):
        target=_PersistentTarget(); target.CollisionVertexCount=0; status=target_status(target); self.assertEqual(status["state"],"unbuilt"); self.assertTrue(status["stale"])

if __name__=="__main__": unittest.main()
