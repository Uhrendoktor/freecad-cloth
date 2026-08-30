"""Persistent DrapeTarget lifecycle and dependency invalidation tests."""
import unittest
from types import SimpleNamespace
from DrapeTarget import DrapeTargetSpec, STATES, source_signature, target_status, invalidate_drape_target, set_drape_target_dependencies

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
class _Obj:
    def __init__(self,name,**props):
        self.Name=name; self.Label=name; self.PropertiesList=tuple(props); self.Placement=_Placement(); self.Shape=_Shape(1)
        for key,value in props.items(): setattr(self,key,value)

class _Target:
    TargetType="FreeCAD Geometry"; Enabled=True; CollisionDeflection=1.0; CollisionThickness=2.0
    SourceObject=_Obj("Chair")
    CollisionVertexCount=8; CollisionTriangleCount=12
    PatternDependencies=(); SewingDependencies=(); AvatarDependencies=(); ArrangementDependencies=()
    DependencySignature=""; PatternSignature=""; SewingSignature=""; AvatarSignature=""; ArrangementSignature=""; CollisionParametersSignature=""; SourcePlacementSignature=""
    LifecycleState="STALE"; TargetStatus="STALE"; InvalidationReason="collision cache missing"

class DrapeTargetLifecycleTests(unittest.TestCase):
    def _ready(self):
        from DrapeTarget import dependency_signatures, _dependency_digest, _set_signatures
        target=_Target(); current=dependency_signatures(target); _set_signatures(target,current); target.LifecycleState="READY_FOR_SIMULATION"; target.TargetStatus="READY_FOR_SIMULATION"; return target

    def test_state_model_is_persistent_and_exact(self):
        self.assertEqual(STATES,("VALID","STALE","INVALID","REFRESHING","READY_FOR_SIMULATION"))
        target=self._ready(); self.assertEqual(target.LifecycleState,"READY_FOR_SIMULATION")
        invalidate_drape_target(target,"pattern geometry")
        self.assertEqual(target.LifecycleState,"STALE"); self.assertEqual(target.InvalidationReason,"pattern geometry")

    def test_pattern_geometry_invalidates(self):
        target=self._ready(); pattern=_Obj("Pattern",Geometry="outline-v1"); set_drape_target_dependencies(target,pattern=pattern)
        from DrapeTarget import dependency_signatures, _set_signatures
        _set_signatures(target,dependency_signatures(target)); target.LifecycleState="READY_FOR_SIMULATION"
        pattern.Geometry="outline-v2"; status=target_status(target)
        self.assertEqual(status["lifecycle_state"],"STALE"); self.assertIn("pattern geometry",status["reason"])

    def test_sewing_topology_invalidates(self):
        target=self._ready(); seam=_Obj("Seam",Topology="A-B"); set_drape_target_dependencies(target,sewing=seam)
        from DrapeTarget import dependency_signatures, _set_signatures
        _set_signatures(target,dependency_signatures(target)); target.LifecycleState="READY_FOR_SIMULATION"
        seam.Topology="A-C"; status=target_status(target)
        self.assertEqual(status["lifecycle_state"],"STALE"); self.assertIn("sewing topology",status["reason"])

    def test_avatar_invalidates(self):
        target=self._ready(); avatar=_Obj("Avatar",Pose="standing"); set_drape_target_dependencies(target,avatar=avatar)
        from DrapeTarget import dependency_signatures, _set_signatures
        _set_signatures(target,dependency_signatures(target)); target.LifecycleState="READY_FOR_SIMULATION"
        avatar.Pose="raised-arm"; status=target_status(target)
        self.assertEqual(status["lifecycle_state"],"STALE"); self.assertIn("avatar",status["reason"])

    def test_arrangement_invalidates(self):
        target=self._ready(); arrangement=_Obj("Arrangement",Offset="0,0"); set_drape_target_dependencies(target,arrangement=arrangement)
        from DrapeTarget import dependency_signatures, _set_signatures
        _set_signatures(target,dependency_signatures(target)); target.LifecycleState="READY_FOR_SIMULATION"
        arrangement.Offset="10,0"; status=target_status(target)
        self.assertEqual(status["lifecycle_state"],"STALE"); self.assertIn("arrangement",status["reason"])

    def test_collision_parameters_invalidates(self):
        target=self._ready(); target.CollisionThickness=3.0; status=target_status(target)
        self.assertEqual(status["lifecycle_state"],"STALE"); self.assertIn("collision parameters",status["reason"])

    def test_source_placement_invalidates(self):
        target=self._ready(); target.SourceObject.Placement=_Placement(10,0,0); status=target_status(target)
        self.assertEqual(status["lifecycle_state"],"STALE"); self.assertIn("source placement",status["reason"])

    def test_source_geometry_invalidates_and_is_reported_as_source_placement_boundary(self):
        target=self._ready(); target.SourceObject.Shape.value=99; status=target_status(target)
        self.assertEqual(status["lifecycle_state"],"STALE"); self.assertIn("source placement",status["reason"])

    def test_invalid_target_is_not_simulatable(self):
        target=self._ready(); target.TargetType="Unknown"; status=target_status(target)
        self.assertEqual(status["lifecycle_state"],"INVALID"); self.assertTrue(status["stale"])

    def test_persisted_fields_are_reload_safe(self):
        target=self._ready(); persisted={name:getattr(target,name) for name in ("LifecycleState","InvalidationReason","DependencySignature","PatternSignature","SewingSignature","AvatarSignature","ArrangementSignature","CollisionParametersSignature","SourcePlacementSignature")}
        reloaded=SimpleNamespace(**persisted,TargetType="FreeCAD Geometry",Enabled=True,SourceObject=target.SourceObject,CollisionVertexCount=8,CollisionTriangleCount=12,CollisionDeflection=1.0,CollisionThickness=2.0,PatternDependencies=(),SewingDependencies=(),AvatarDependencies=(),ArrangementDependencies=())
        self.assertEqual(target_status(reloaded)["lifecycle_state"],"READY_FOR_SIMULATION")

    def test_legacy_spec_contract_remains(self):
        DrapeTargetSpec("Mannequin","ClothAvatar",1.0,2.0).validate(); DrapeTargetSpec("FreeCAD Geometry","Chair",0.5,1.5).validate()

if __name__=="__main__": unittest.main()
