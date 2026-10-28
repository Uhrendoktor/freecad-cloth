# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression contracts for stable source geometry signatures."""

from types import SimpleNamespace
from typing import cast

from freecad_cloth.shared.SourceSignature import source_signature
from tests.support.assertions import require

_TRIANGLES: tuple[tuple[int, int, int], ...] = ((0, 1, 2),)
_COORDINATES: tuple[tuple[float, float, float], ...] = (
    (0.0, 0.0, 0.0),
    (1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
)


def _mesh_target(
    coordinates: tuple[tuple[float, float, float], ...],
) -> SimpleNamespace:
    """Build a document-object fixture with mesh coordinates and topology.

    Args:
        coordinates: Ordered vertex coordinates included in the target mesh.

    Returns:
        A target namespace exposing native-style mesh topology.
    """
    vertices = tuple(SimpleNamespace(x=x, y=y, z=z) for x, y, z in coordinates)
    mesh = SimpleNamespace(Topology=(vertices, _TRIANGLES))
    return SimpleNamespace(Name="SignatureBody", Mesh=mesh, Shape=None)


def test_mesh_signature_tracks_vector_coordinates_and_is_deterministic() -> None:
    """Require stable signatures until vector coordinates or topology change."""
    original = source_signature(_mesh_target(_COORDINATES))
    repeat = source_signature(_mesh_target(_COORDINATES))
    moved_coordinates = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 2.0, 0.0))
    moved = source_signature(_mesh_target(moved_coordinates))

    require(
        condition=original == repeat,
        message="Identical mesh vertices and triangles must produce a stable signature.",
    )
    require(
        condition=original != moved,
        message="A changed vector coordinate must invalidate the source signature.",
    )


def test_shape_signature_falls_back_to_tessellation_after_invalid_brep() -> None:
    """Use mesh tessellation when a native BRep exporter returns an unsupported value."""
    bounds = SimpleNamespace(
        XMin=0.0,
        XMax=1.0,
        YMin=0.0,
        YMax=1.0,
        ZMin=0.0,
        ZMax=0.0,
    )
    shape = SimpleNamespace(
        isNull=lambda: False,
        BoundBox=bounds,
        Solids=(),
        Faces=(),
        Edges=(),
        Vertexes=(),
        exportBrepToString=lambda: object(),
        tessellate=lambda _deflection: (_COORDINATES, _TRIANGLES),
    )
    signature = source_signature(SimpleNamespace(Name="ShapeBody", Mesh=None, Shape=shape))
    geometry = cast("tuple[object, ...]", signature[1])
    shape_content = cast("tuple[object, ...]", geometry[-1])

    require(
        condition=shape_content[0] == "TessellatedShape",
        message="Invalid BRep output must fall back to the tessellated geometry signature.",
    )
