# Copyright (C) 2026 FreeCAD Cloth contributors
"""Deterministic source signatures shared by Cloth domains.

This module intentionally depends only on the Python standard library so
Pattern and Simulation can use the same stale-reference contract without a
cross-domain import.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Sequence
from typing import Protocol, cast

from freecad_cloth.common.garment_document import FreeCADDocumentObjectProtocol

POINT_COORDINATE_COUNT = 3

type _SignatureValue = str | int | float | bool | None | tuple["_SignatureValue", ...]
TESSELLATION_COMPONENT_COUNT = 2


class _VectorCoordinates(Protocol):
    """Coordinate attributes exposed by FreeCAD vector-like values."""

    @property
    def x(self) -> float:
        """Return the X coordinate in model units."""
        ...

    @property
    def y(self) -> float:
        """Return the Y coordinate in model units."""
        ...

    @property
    def z(self) -> float:
        """Return the Z coordinate in model units."""
        ...


class _FreeCADShape(Protocol):
    """Native shape capability used for stable geometry signatures."""

    def isNull(self) -> bool:
        """Return whether the shape contains no geometric content."""
        ...

    @property
    def BoundBox(self) -> _BoundBox:
        """Return the axis-aligned bounds of the native shape."""
        ...


class _BoundBox(Protocol):
    """Axis-aligned bound coordinates exported by a native FreeCAD shape."""

    XMin: float
    XMax: float
    YMin: float
    YMax: float
    ZMin: float
    ZMax: float


def _point_coordinates(
    point: Iterable[float] | _VectorCoordinates,
) -> tuple[float, float, float]:
    """Normalize iterable or FreeCAD-vector coordinates into a rounded triple.

    Args:
        point: Iterable three-coordinate value or FreeCAD vector-like object.

    Returns:
        Coordinates rounded to six decimal places.
    """
    try:
        values = tuple(cast("Iterable[float]", point))
    except TypeError:
        values = None
    if values is not None and len(values) >= POINT_COORDINATE_COUNT:
        return (
            round(float(values[0]), 6),
            round(float(values[1]), 6),
            round(float(values[2]), 6),
        )
    vector = cast("_VectorCoordinates", point)
    return (
        round(float(vector.x), 6),
        round(float(vector.y), 6),
        round(float(vector.z), 6),
    )


def _digest_surface(
    vertices: Sequence[Iterable[float] | _VectorCoordinates],
    triangles: Sequence[Sequence[int]],
) -> str:
    """Return a deterministic SHA-256 digest of surface coordinates and topology.

    Args:
        vertices: Ordered mesh vertices, either coordinate sequences or FreeCAD vectors.
        triangles: Ordered triangle vertex indices.

    Returns:
        Hexadecimal digest sensitive to coordinate, connectivity, and ordering changes.
    """
    payload = {
        "vertices": [_point_coordinates(vertex) for vertex in vertices],
        "triangles": [tuple(int(i) for i in triangle) for triangle in triangles],
    }
    encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _mesh_signature(target: FreeCADDocumentObjectProtocol) -> tuple[_SignatureValue, ...] | None:
    """Return the stable authored-avatar or complete mesh-topology signature.

    Args:
        target: FreeCAD document object that may expose avatar identity or mesh topology.

    Returns:
        Authored revision fields for MakeHuman avatars, a topology digest for a
        mesh target, or None when no usable mesh topology is exposed.
    """
    # MakeHuman avatars retain a stable authored revision instead of depending
    # on FreeCAD's internal Mesh::Feature topology ordering across recomputes.
    if (
        str(getattr(target, "AvatarType", "")) == "ClothAvatar"
        or str(getattr(target, "AvatarMeshProvider", "")) == "makehuman-hm08"
    ):
        return (
            "MakeHumanAvatar",
            str(getattr(target, "AvatarMeshProvider", "")),
            str(getattr(target, "AvatarMeshSource", "")),
            str(getattr(target, "AvatarMeshLicense", "")),
            int(getattr(target, "AvatarRevision", 0)),
            int(getattr(target, "MeshVertexCount", 0)),
            int(getattr(target, "MeshTriangleCount", 0)),
        )
    mesh = getattr(target, "Mesh", None)
    topology = getattr(mesh, "Topology", None) if mesh is not None else None
    if topology is None:
        return None
    try:
        vertices, triangles = topology
        return ("Mesh", len(vertices), len(triangles), _digest_surface(vertices, triangles))
    except (TypeError, ValueError, AttributeError):
        return None


def _brep_signature(
    exporter: Callable[[], str | bytes | bytearray | memoryview],
) -> tuple[str, str]:
    """Hash the serialized BRep payload returned by a shape exporter.

    Args:
        exporter: Bound native shape method that returns a BRep representation.

    Returns:
        A BRepHash tag and the payload's SHA-256 digest.

    Raises:
        TypeError: If the exporter returns a value that is neither text nor bytes.
    """
    payload = exporter()
    if isinstance(payload, str):
        encoded = payload.encode("utf-8")
    elif isinstance(payload, (bytes, bytearray, memoryview)):
        encoded = bytes(payload)
    else:
        msg = "BRep exporter must return text or bytes"
        raise TypeError(msg)
    return "BRepHash", hashlib.sha256(encoded).hexdigest()


def _shape_content_signature(
    shape: _FreeCADShape,
    deflection: float = 1.0,
) -> tuple[_SignatureValue, ...]:
    """Return a deterministic BRep or tessellation signature for a FreeCAD shape.

    Args:
        shape: Native FreeCAD TopoShape or another object exposing geometry APIs.
        deflection: Linear tessellation deflection used when BRep export is unavailable.

    Returns:
        A stable signature containing the BRep hash, tessellated surface digest,
        native shape hash, or an explicit unknown marker.
    """
    exporter = getattr(shape, "exportBrepToString", None)
    if callable(exporter):
        try:
            return _brep_signature(cast("Callable[[], str | bytes | bytearray | memoryview]", exporter))
        except (TypeError, ValueError, AttributeError, RuntimeError):
            pass

    tessellate = getattr(shape, "tessellate", None)
    if callable(tessellate):
        try:
            tessellation = tessellate(float(deflection))
            if (
                isinstance(tessellation, tuple)
                and len(tessellation) == TESSELLATION_COMPONENT_COUNT
                and isinstance(tessellation[0], Sequence)
                and isinstance(tessellation[1], Sequence)
            ):
                vertices, triangles = tessellation
                return (
                    "TessellatedShape",
                    len(vertices),
                    len(triangles),
                    _digest_surface(vertices, triangles),
                )
        except (TypeError, ValueError, AttributeError, RuntimeError):
            pass

    hash_code = getattr(shape, "hashCode", None)
    if callable(hash_code):
        try:
            hash_value = hash_code()
            if isinstance(hash_value, int) and not isinstance(hash_value, bool):
                return ("ShapeHash", hash_value)
        except (TypeError, ValueError, RuntimeError):
            pass
    return ("Unknown",)


def _geometry_signature(
    target: FreeCADDocumentObjectProtocol,
    deflection: float = 1.0,
) -> tuple[_SignatureValue, ...]:
    """Return the strongest available geometry-content signature.

    Args:
        target: FreeCAD document object exposing a Mesh or TopoShape.
        deflection: Tessellation tolerance used only when BRep export is unavailable.

    Returns:
        A signature based on authored avatar identity, complete mesh topology,
        shape bounds and content, a native shape hash, or an explicit unknown marker.
    """
    mesh_signature = _mesh_signature(target)
    if mesh_signature is not None:
        return mesh_signature
    shape = getattr(target, "Shape", None)
    if shape is not None:
        try:
            if not shape.isNull():
                box = shape.BoundBox
                return (
                    "Shape",
                    len(getattr(shape, "Solids", ())),
                    len(getattr(shape, "Faces", ())),
                    len(getattr(shape, "Edges", ())),
                    len(getattr(shape, "Vertexes", ())),
                    round(float(box.XMin), 6),
                    round(float(box.XMax), 6),
                    round(float(box.YMin), 6),
                    round(float(box.YMax), 6),
                    round(float(box.ZMin), 6),
                    round(float(box.ZMax), 6),
                    _shape_content_signature(shape, deflection),
                )
        except (AttributeError, TypeError, ValueError):
            pass
        return ("ShapeContent", _shape_content_signature(shape, deflection))
    return ("Unknown",)


def source_signature(
    target: FreeCADDocumentObjectProtocol,
    deflection: float = 1.0,
    thickness: float = 0.0,
) -> tuple[_SignatureValue, ...]:
    """Build a deterministic signature for geometry, placement, and collision settings.

    Args:
        target: FreeCAD document object whose source identity is being tracked.
        deflection: Tessellation deflection used when stable BRep export is unavailable.
        thickness: Collision thickness included in the signature to invalidate stale caches.

    Returns:
        A tuple containing object identity, geometry-content signature, placement,
        deflection, and collision thickness.
    """
    placement = getattr(target, "Placement", None)
    base = getattr(placement, "Base", None) if placement is not None else None
    rotation = getattr(placement, "Rotation", None) if placement is not None else None
    axis = getattr(rotation, "Axis", None) if rotation is not None else None
    return (
        str(getattr(target, "Name", "")),
        _geometry_signature(target, float(deflection)),
        round(float(getattr(base, "x", 0.0)), 6),
        round(float(getattr(base, "y", 0.0)), 6),
        round(float(getattr(base, "z", 0.0)), 6),
        round(float(getattr(rotation, "Angle", 0.0)), 6) if rotation is not None else 0.0,
        round(float(getattr(axis, "x", 0.0)), 6) if axis is not None else 0.0,
        round(float(getattr(axis, "y", 0.0)), 6) if axis is not None else 0.0,
        round(float(getattr(axis, "z", 1.0)), 6) if axis is not None else 1.0,
        float(deflection),
        float(thickness),
    )


__all__ = ["source_signature"]
