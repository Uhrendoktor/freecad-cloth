"""Regression coverage for the persistent DrapeTarget state contract."""
from types import SimpleNamespace

from freecad_cloth.simulation.DrapeTarget import source_signature, target_status


class _Shape:
    def __init__(self, value):
        self.value = value

    def isNull(self):
        return False

    def hashCode(self):
        return self.value


def _target(source, **overrides):
    values = dict(
        Enabled=True,
        TargetType="FreeCAD Geometry",
        SourceObject=source,
        CollisionDeflection=1.0,
        CollisionThickness=0.0,
        SourceSignature=repr(source_signature(source, 1.0, 0.0)),
        CollisionVertexCount=8,
        CollisionTriangleCount=12,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_target_status_requires_a_built_collision_cache():
    source = SimpleNamespace(Name="Body", Label="Body", Shape=_Shape(1))
    target = _target(source, SourceSignature="", CollisionVertexCount=0, CollisionTriangleCount=0)
    status = target_status(target)
    assert status == {
        "state": "unbuilt",
        "message": "Drape target collision surface needs to be built",
        "stale": True,
        "reason": "collision cache missing",
    }


def test_target_status_detects_geometry_change_without_silent_retargeting():
    source = SimpleNamespace(Name="Body", Label="Body", Shape=_Shape(1))
    target = _target(source)
    assert target_status(target)["state"] == "ready"

    source.Shape = _Shape(2)
    status = target_status(target)
    assert status["state"] == "stale"
    assert status["stale"] is True
    assert "rebuild collision surface" in status["message"]
    assert "source" in status["reason"]


def test_target_status_reports_disabled_without_calling_it_stale():
    source = SimpleNamespace(Name="Body", Label="Body", Shape=_Shape(1))
    target = _target(source, Enabled=False)
    status = target_status(target)
    assert status["state"] == "disabled"
    assert status["stale"] is False
    assert status["reason"] == "target disabled"


def test_target_status_detects_collision_parameter_change():
    source = SimpleNamespace(Name="Body", Label="Body", Shape=_Shape(1))
    target = _target(source)
    target.CollisionDeflection = 0.5
    status = target_status(target)
    assert status["state"] == "stale"
    assert status["stale"] is True
    assert "tessellation" in status["reason"]
