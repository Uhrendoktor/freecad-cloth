# Copyright (C) 2026 FreeCAD Cloth contributors
"""Focused behavior coverage for shared FreeCAD boundary adapters."""

from collections.abc import Sequence
from types import SimpleNamespace

import pytest

from freecad_cloth.common.FreeCADCollision import surface_from_freecad
from freecad_cloth.shared.SeamColors import (
    apply_seam_colors,
    register_seam_refresh_callback,
    seam_color_highlighting_enabled,
    seam_color_map,
    set_seam_color_highlighting_enabled,
)
from freecad_cloth.shared.SourceSignature import source_signature
from tests.support.assertions import require
from tests.support.closed_mesh_fixtures import CUBE_TRIANGLES


class _Vertex:
    """FreeCAD-compatible 3D point fixture for mesh and shape adapters."""

    x: float
    y: float
    z: float

    def __init__(self, x: float, y: float, z: float) -> None:
        """Initialize the three coordinate values.

        Args:
            x: Horizontal coordinate.
            y: Depth coordinate.
            z: Vertical coordinate.
        """
        self.x, self.y, self.z = x, y, z


class _Shape:
    """Small tessellatable shape fixture with deterministic triangle data."""

    vertices: tuple[_Vertex, ...]
    triangles: tuple[tuple[int, int, int], ...]

    def __init__(
        self,
        vertices: Sequence[_Vertex],
        triangles: Sequence[tuple[int, int, int]],
    ) -> None:
        """Store the topology exposed by the fake native shape.

        Args:
            vertices: Ordered points returned by shape tessellation.
            triangles: Triangle indices referencing the supplied points.
        """
        self.vertices = tuple(vertices)
        self.triangles = tuple(triangles)
        self.isNull = bool
        self.tessellate = self._tessellate

    def _tessellate(
        self,
        deflection: float,
    ) -> tuple[tuple[_Vertex, ...], tuple[tuple[int, int, int], ...]]:
        """Return stored mesh data after checking the requested deflection.

        Args:
            deflection: Tessellation resolution requested by the caller.

        Returns:
            The vertex coordinates and face indices stored by this fixture.
        """
        require(
            condition=deflection == pytest.approx(0.5),
            message="Shape tessellation must receive the caller's deflection.",
        )
        return self.vertices, self.triangles


def _mesh() -> SimpleNamespace:
    """Build a native-style mesh topology fixture containing one open triangle.

    Returns:
        A namespace with ordered vector-like vertices and one face.
    """
    return SimpleNamespace(
        Topology=(
            (_Vertex(0, 0, 0), _Vertex(1, 0, 0), _Vertex(0, 1, 0)),
            ((0, 1, 2),),
        )
    )


def test_freecad_collision_reads_mesh_or_tessellates_shape() -> None:
    """Read mesh topology directly or tessellate when only a Shape is available."""
    mesh_surface = surface_from_freecad(
        SimpleNamespace(Mesh=_mesh(), Shape=SimpleNamespace(isNull=bool), Label="mesh")
    )
    require(
        condition=mesh_surface.vertices[1] == (1.0, 0.0, 0.0),
        message="Mesh-backed surfaces must preserve the source vertex coordinates.",
    )

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
    require(
        condition=shape_surface.triangles == ((0, 1, 2),),
        message="Shape-backed surfaces must retain the tessellated triangle indices.",
    )


def test_freecad_collision_fails_closed_for_bad_input() -> None:
    """Reject invalid deflection values, absent geometry, and malformed topology."""
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


def test_source_signature_is_deterministic_and_tracks_mesh_content() -> None:
    """Require a stable signature for identical topology and a change for moved vertices."""
    first = source_signature(SimpleNamespace(Name="Body", Mesh=_mesh()))
    second = source_signature(SimpleNamespace(Name="Body", Mesh=_mesh()))
    require(
        condition=first == second,
        message="Repeated source geometry must produce the same signature.",
    )
    changed = _mesh()
    changed.Topology = (
        changed.Topology[0][:2] + (_Vertex(0, 2, 0),),
        changed.Topology[1],
    )
    require(
        condition=source_signature(SimpleNamespace(Name="Body", Mesh=changed)) != first,
        message="Moving a source vertex must invalidate the cached mesh signature.",
    )


def test_source_signature_preserves_makehuman_revision_and_shape_fallback() -> None:
    """Preserve provider metadata and the tessellated signature fallback."""
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
    require(
        condition=source_signature(avatar)[1]
        == (
            "MakeHumanAvatar",
            "makehuman-hm08",
            "base.obj",
            "CC0",
            7,
            123,
            456,
        ),
        message="Avatar signatures must retain provider identity, revision, and counts.",
    )
    shape = _Shape(
        (_Vertex(0, 0, 0), _Vertex(1, 0, 0), _Vertex(0, 1, 0)),
        ((0, 1, 2),),
    )
    signature = source_signature(SimpleNamespace(Name="Body", Shape=shape), deflection=0.5)
    require(
        condition=signature[1][0] == "ShapeContent",
        message="Shape-only sources must retain the ShapeContent signature kind.",
    )
    require(
        condition=signature[1][1][:3] == ("TessellatedShape", 3, 1),
        message="Shape signatures must include the tessellation kind and topology counts.",
    )


def test_seam_colors_are_order_independent_and_reject_empty_identity() -> None:
    """Require identity-based colors to ignore order and reject empty IDs."""
    require(
        condition=seam_color_map(["seam-b", "seam-a", "seam-a"])
        == seam_color_map(["seam-a", "seam-b"]),
        message="Seam colors must be deterministic and independent of input ordering.",
    )
    with pytest.raises(ValueError, match="identity must not be empty"):
        seam_color_map(["", "   "])


def test_apply_seam_colors_updates_only_objects_with_semantic_ids() -> None:
    """Color identified seam objects without changing objects that have no identity."""
    colored_a = SimpleNamespace(SeamId="a", ViewObject=SimpleNamespace(LineColor=None))
    colored_b = SimpleNamespace(SeamId="b", ViewObject=SimpleNamespace(LineColor=None))
    untouched = SimpleNamespace(SeamId="", ViewObject=SimpleNamespace(LineColor=None))
    colors = apply_seam_colors((colored_b, untouched, colored_a))
    require(
        condition=colored_a.ViewObject.LineColor == colors["a"],
        message="The first identified seam must receive its semantic color.",
    )
    require(
        condition=colored_b.ViewObject.LineColor == colors["b"],
        message="The second identified seam must receive its semantic color.",
    )
    require(
        condition=untouched.ViewObject.LineColor is None,
        message="Objects without seam identities must remain untouched.",
    )


def test_apply_seam_colors_uses_neutral_linework_when_highlights_are_disabled() -> None:
    """Use neutral linework while retaining the deterministic color lookup."""
    seam = SimpleNamespace(SeamId="seam-1", ViewObject=SimpleNamespace(LineColor=None))
    original = seam_color_highlighting_enabled()
    try:
        set_seam_color_highlighting_enabled(False)
        colors = apply_seam_colors([seam])
        require(
            condition=colors["seam-1"] == seam_color_map(["seam-1"])["seam-1"],
            message="Disabling highlights must not change the semantic color mapping.",
        )
        require(
            condition=seam.ViewObject.LineColor == (0.48, 0.48, 0.48),
            message="Disabled highlights must use neutral linework.",
        )
    finally:
        set_seam_color_highlighting_enabled(original)


def test_apply_seam_colors_dispatches_refresh_through_registered_callback() -> None:
    """Refresh only the owning document after seam colors have been applied."""
    document = SimpleNamespace(Name="doc")
    seam = SimpleNamespace(
        SeamId="seam-a",
        Document=document,
        ViewObject=SimpleNamespace(LineColor=None),
    )
    calls: list[object] = []
    register_seam_refresh_callback(calls.append)
    try:
        apply_seam_colors([seam])
        require(
            condition=calls == [document],
            message="The registered refresh callback must receive the owning document.",
        )
    finally:
        register_seam_refresh_callback(None)


def test_freecad_collision_repairs_winding_after_native_mesh_conversion() -> None:
    """Restore coherent shared-edge direction after native mesh conversion."""
    vertices = (
        _Vertex(0, 0, 0),
        _Vertex(100, 0, 0),
        _Vertex(100, 100, 0),
        _Vertex(0, 100, 0),
        _Vertex(0, 0, 100),
        _Vertex(100, 0, 100),
        _Vertex(100, 100, 100),
        _Vertex(0, 100, 100),
    )
    inconsistent = tuple(
        (a, c, b) if face_index == 2 else (a, b, c)
        for face_index, (a, b, c) in enumerate(CUBE_TRIANGLES)
    )
    surface = surface_from_freecad(
        SimpleNamespace(
            Mesh=SimpleNamespace(Topology=(vertices, inconsistent)),
            Label="mannequin",
        ),
        thickness=5.0,
    )
    edge_owners: dict[tuple[int, int], list[int]] = {}
    for triangle in surface.triangles:
        for first, second in (
            (triangle[0], triangle[1]),
            (triangle[1], triangle[2]),
            (triangle[2], triangle[0]),
        ):
            edge = (min(first, second), max(first, second))
            direction = 1 if first < second else -1
            edge_owners.setdefault(edge, []).append(direction)
    require(
        condition=bool(edge_owners),
        message="The repaired closed mesh must expose shared edges.",
    )
    require(
        condition=all(len(directions) == 2 for directions in edge_owners.values()),
        message="Every undirected edge in a closed surface must have two owners.",
    )
    require(
        condition=all(sum(directions) == 0 for directions in edge_owners.values()),
        message="Adjacent closed-surface faces must traverse shared edges oppositely.",
    )
    require(
        condition=surface.thickness == 5.0,
        message="Collision thickness must survive winding normalization.",
    )


def test_freecad_collision_does_not_invent_closure_for_open_mesh() -> None:
    """Leave open collision meshes untouched rather than forcing manifold winding."""
    surface = surface_from_freecad(SimpleNamespace(Mesh=_mesh(), Label="open triangle"))
    require(
        condition=surface.triangles == ((0, 1, 2),),
        message="An open triangle surface must retain its authored connectivity.",
    )
