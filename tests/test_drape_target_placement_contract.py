from types import SimpleNamespace

import pytest

from freecad_cloth.simulation.DrapeTarget import resolve_authoritative_target, source_signature


def _source(name="Avatar"):
    return SimpleNamespace(
        Name=name,
        Placement=SimpleNamespace(
            Base=SimpleNamespace(x=0.0, y=0.0, z=0.0),
            Rotation=SimpleNamespace(Angle=0.0, Axis=SimpleNamespace(x=0.0, y=0.0, z=1.0)),
        ),
    )


def _target(source, signature=None):
    if signature is None:
        signature = repr(source_signature(source, 1.0, 0.0))
    return SimpleNamespace(
        TargetType="Mannequin",
        SourceObject=source,
        CollisionDeflection=1.0,
        CollisionThickness=0.0,
        Enabled=True,
        CollisionVertexCount=4,
        CollisionTriangleCount=2,
        SourceSignature=signature,
    )


def test_missing_target_fails_closed():
    with pytest.raises(ValueError, match="no DrapeTarget"):
        resolve_authoritative_target(SimpleNamespace(Objects=[]))


def test_ambiguous_targets_fail_closed():
    first = _target(_source("A"))
    second = _target(_source("B"))
    with pytest.raises(ValueError, match="ambiguous"):
        resolve_authoritative_target(SimpleNamespace(Objects=[first, second]))


def test_stale_target_fails_closed():
    target = _target(_source(), signature="stale")
    with pytest.raises(ValueError, match="not current"):
        resolve_authoritative_target(SimpleNamespace(Objects=[target]))


def test_current_target_is_selected_deterministically():
    target = _target(_source())
    assert resolve_authoritative_target(SimpleNamespace(Objects=[target])) is target


def test_explicit_target_must_belong_to_document():
    target = _target(_source())
    other = SimpleNamespace(Objects=[])
    with pytest.raises(ValueError, match="active document"):
        resolve_authoritative_target(other, target)
