"""Focused behavior coverage for shared, host-boundary test infrastructure."""

from types import SimpleNamespace

import pytest

from freecad_cloth.common.FreeCADCollision import surface_from_freecad
from freecad_cloth.shared.SourceSignature import source_signature
from freecad_cloth.shared.seam_colors import apply_seam_colors, seam_color_map


class _Vertex:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


class _Shape:
    def __init__(self, vertices, triangles):
        self._vertices = tuple(vertices)
        self._triangles = tuple(triangles)

    def isNull(self):
        return False

    def tessellate(self, deflection):
        assert deflection == 0.5
        return self._vertices, self._triangles


def test_freecad_collision_prefers_existing_mesh_topology():
    mesh = SimpleNamespace(
        Topology=(
            (_Vertex(0, 0, 0), _Vertex(1, 0, 0), _Vertex(0, 1, 0)),
            ((0, 1, 2),),
        )
    )
    obj = SimpleNamespace(Mesh=mesh, Shape=SimpleNamespace(isNull=lambda: False), Label="mesh")
    surface = surface_from_freecad(obj, deflection=0.5, thickness=1.25)

    assert surface.region == "mesh"
    assert surface.thickness == 1.25
    assert surface.vertices == ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    assert surface.triangles == ((0, 1, 2),)


def test_freecad_collision_tessellates_shape_when_mesh_topology_is_absent():
    obj = SimpleNamespace(
        Mesh=None,
        Shape=_Shape(
            (_Vertex(0, 0, 0), _Vertex(2, 0, 0), _Vertex(0, 2, 0)),
            ((0, 1, 2),),
        ),
        Label="shape",
    )
    surface = surface_from_freecad(obj, deflection=0.5)

    assert surface.region == "shape"
    assert surface.vertices[1] == (2.0, 0.0, 0.0)
    assert surface.triangles == ((0, 1, 2),)


def test_freecad_collision_rejects_invalid_deflection_and_missing_geometry():
    with pytest.raises(ValueError, match="deflection must be positive"):
        surface_from_freecad(SimpleNamespace(), deflection=0)

    with pytest.raises(TypeError, match="expected a FreeCAD shape or mesh object"):
        surface_from_freecad(SimpleNamespace())


def test_freecad_collision_rejects_malformed_mesh_topology():
    obj = SimpleNamespace(
        Mesh=SimpleNamespace(Topology=(("bad",), ((0, 1, 2),))),
        Label="broken",
    )
    with pytest.raises(ValueError, match="unusable Mesh topology"):
        surface_from_freecad(obj)


def test_source_signature_is_deterministic_and_sensitive_to_mesh_content():
    mesh_a = SimpleNamespace(
        Topology=(
            (
                _Vertex(0, 0, 0),
                _Vertex(1, 0, 0),
                _Vertex(0, 1, 0),
            ),
            ((0, 1, 2),),
        )
    )
    first = source_signature(SimpleNamespace(Name="Body", Mesh=mesh_a))
    second = source_signature(SimpleNamespace(Name="Body", Mesh=mesh_a))
    assert first == second

    mesh_b = SimpleNamespace(
        Topology=(
            (
                _Vertex(0, 0, 0),
                _Vertex(1, 0, 0),
                _Vertex(0, 2, 0),
            ),
            ((0, 1, 2),),
        )
    )
    assert source_signature(SimpleNamespace(Name="Body", Mesh=mesh_b)) != first


def test_source_signature_uses_shape_content_when_mesh_is_unavailable():
    shape = _Shape(
        (_Vertex(0, 0, 0), _Vertex(1, 0, 0), _Vertex(0, 1, 0)),
        ((0, 1, 2),),
    )
    signature = source_signature(SimpleNamespace(Name="Body", Shape=shape), deflection=0.5)
    assert signature[1][0] == "Shape"
    assert signature[1][-1][0] == "TessellatedShape"


def test_makehuman_signature_uses_authored_revision_metadata():
    target = SimpleNamespace(
        Name="Avatar",
        AvatarType="ClothAvatar",
        AvatarMeshProvider="makehuman-hm08",
        AvatarMeshSource="base.obj",
        AvatarMeshLicense="CC0",
        AvatarRevision=7,
        MeshVertexCount=123,
        MeshTriangleCount=456,
    )
    signature = source_signature(target)
    assert signature[1] == (
        "MakeHumanAvatar",
        "makehuman-hm08",
        "base.obj",
        "CC0",
        7,
        123,
        456,
    )


def test_seam_colors_are_order_independent_and_reject_empty_identity():
    first = seam_color_map(["seam-b", "seam-a", "seam-a"])
    second = seam_color_map(["seam-a", "seam-b"])
    assert first == second
    assert set(first) == {"seam-a", "seam-b"}

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
