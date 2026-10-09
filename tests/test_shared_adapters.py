"""Focused behavior coverage for shared FreeCAD boundary adapters."""

from types import SimpleNamespace

import pytest

from freecad_cloth.common.FreeCADCollision import surface_from_freecad
from freecad_cloth.shared.SourceSignature import source_signature
from freecad_cloth.shared.seam_colors import (
    apply_seam_colors,
    register_seam_refresh_callback,
    seam_color_map,
    seam_color_highlighting_enabled,
    set_seam_color_highlighting_enabled,
)


class _Vertex:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


class _Shape:
    def __init__(self, vertices, triangles):
        self.vertices = tuple(vertices)
        self.triangles = tuple(triangles)

    def isNull(self):
        return False

    def tessellate(self, deflection):
        assert deflection == 0.5
        return self.vertices, self.triangles


def _mesh():
    return SimpleNamespace(
        Topology=(
            (_Vertex(0, 0, 0), _Vertex(1, 0, 0), _Vertex(0, 1, 0)),
            ((0, 1, 2),),
        )
    )


def test_freecad_collision_reads_mesh_or_tessellates_shape():
    mesh_surface = surface_from_freecad(
        SimpleNamespace(Mesh=_mesh(), Shape=SimpleNamespace(isNull=lambda: False), Label="mesh")
    )
    assert mesh_surface.vertices[1] == (1.0, 0.0, 0.0)

    shape_surface = surface_from_freecad(
        SimpleNamespace(
            Mesh=None,
            Shape=_Shape(
                (_Vertex(0, 0, 0), _Vertex(2, 0, 0), _Vertex(0, 2, 0)),
                ((0, 1, 2),),
            ),
            Label="shape",
        ),
        deflection=0.5,
    )
    assert shape_surface.triangles == ((0, 1, 2),)


def test_freecad_collision_fails_closed_for_bad_input():
    with pytest.raises(ValueError, match="deflection must be positive"):
        surface_from_freecad(SimpleNamespace(), deflection=0)

    with pytest.raises(TypeError, match="expected a FreeCAD shape or mesh object"):
        surface_from_freecad(SimpleNamespace())

    broken = SimpleNamespace(
        Mesh=SimpleNamespace(Topology=(("bad",), ((0, 1, 2),))),
        Label="broken",
    )
    with pytest.raises(ValueError, match="unusable Mesh topology"):
        surface_from_freecad(broken)


def test_source_signature_is_deterministic_and_tracks_mesh_content():
    first = source_signature(SimpleNamespace(Name="Body", Mesh=_mesh()))
    second = source_signature(SimpleNamespace(Name="Body", Mesh=_mesh()))
    assert first == second

    changed = _mesh()
    changed.Topology = (
        changed.Topology[0][:2] + (_Vertex(0, 2, 0),),
        changed.Topology[1],
    )
    assert source_signature(SimpleNamespace(Name="Body", Mesh=changed)) != first


def test_source_signature_preserves_makehuman_revision_and_shape_fallback():
    avatar = SimpleNamespace(
        Name="Avatar",
        AvatarType="ClothAvatar",
        AvatarMeshProvider="makehuman-hm08",
        AvatarMeshSource="base.obj",
        AvatarMeshLicense="CC0",
        AvatarRevision=7,
        MeshVertexCount=123,
        MeshTriangleCount=456,
    )
    assert source_signature(avatar)[1] == (
        "MakeHumanAvatar",
        "makehuman-hm08",
        "base.obj",
        "CC0",
        7,
        123,
        456,
    )

    shape = _Shape(
        (_Vertex(0, 0, 0), _Vertex(1, 0, 0), _Vertex(0, 1, 0)),
        ((0, 1, 2),),
    )
    signature = source_signature(SimpleNamespace(Name="Body", Shape=shape), deflection=0.5)
    assert signature[1][0] == "ShapeContent"
    assert signature[1][1][:3] == ("TessellatedShape", 3, 1)


def test_seam_colors_are_order_independent_and_reject_empty_identity():
    assert seam_color_map(["seam-b", "seam-a", "seam-a"]) == seam_color_map(["seam-a", "seam-b"])
    with pytest.raises(ValueError, match="identity must not be empty"):
        seam_color_map(["", "   "])


def test_apply_seam_colors_updates_only_objects_with_semantic_ids():
    colored_a = SimpleNamespace(SeamId="a", ViewObject=SimpleNamespace(LineColor=None))
    colored_b = SimpleNamespace(SeamId="b", ViewObject=SimpleNamespace(LineColor=None))
    untouched = SimpleNamespace(SeamId="", ViewObject=SimpleNamespace(LineColor=None))

    colors = apply_seam_colors((colored_b, untouched, colored_a))

    assert colored_a.ViewObject.LineColor == colors["a"]
    assert colored_b.ViewObject.LineColor == colors["b"]
    assert untouched.ViewObject.LineColor is None


def test_apply_seam_colors_uses_neutral_linework_when_highlights_are_disabled():
    seam = SimpleNamespace(SeamId="seam-1", ViewObject=SimpleNamespace(LineColor=None))
    original = seam_color_highlighting_enabled()
    try:
        set_seam_color_highlighting_enabled(False)
        colors = apply_seam_colors([seam])
        assert colors["seam-1"] == seam_color_map(["seam-1"])["seam-1"]
        assert seam.ViewObject.LineColor == (0.48, 0.48, 0.48)
    finally:
        set_seam_color_highlighting_enabled(original)


def test_apply_seam_colors_dispatches_refresh_through_registered_callback():
    document = SimpleNamespace(Name="doc")
    seam = SimpleNamespace(
        SeamId="seam-a",
        Document=document,
        ViewObject=SimpleNamespace(LineColor=None),
    )
    calls = []
    register_seam_refresh_callback(calls.append)
    try:
        apply_seam_colors([seam])
        assert calls == [document]
    finally:
        register_seam_refresh_callback(None)

