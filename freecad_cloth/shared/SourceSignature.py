"""Deterministic source signatures shared by Cloth domains.

This module intentionally depends only on the Python standard library so
Pattern and Simulation can use the same stale-reference contract without a
cross-domain import.
"""

from __future__ import annotations

import hashlib
import json


def _point_coordinates(point):
    """Normalize iterable and FreeCAD-vector points to deterministic triples."""
    try:
        values = tuple(point)
    except TypeError:
        values = None
    if values is not None and len(values) >= 3:
        return tuple(round(float(c), 6) for c in values[:3])
    return (
        round(float(point.x), 6),
        round(float(point.y), 6),
        round(float(point.z), 6),
    )


def _digest_surface(vertices, triangles):
    """Return a deterministic digest of the complete collision topology."""
    payload = {
        "vertices": [_point_coordinates(vertex) for vertex in vertices],
        "triangles": [tuple(int(i) for i in triangle) for triangle in triangles],
    }
    encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _mesh_signature(target):
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


def _shape_content_signature(shape):
    """Return a persistent geometry-content digest for a FreeCAD TopoShape."""
    exporter = getattr(shape, "exportBrepToString", None)
    if callable(exporter):
        try:
            payload = exporter()
            if isinstance(payload, str):
                payload = payload.encode("utf-8")
            else:
                payload = bytes(payload)
            return ("BRepHash", hashlib.sha256(payload).hexdigest())
        except (TypeError, ValueError, AttributeError, RuntimeError):
            pass
    hash_code = getattr(shape, "hashCode", None)
    if callable(hash_code):
        try:
            return ("ShapeHash", int(hash_code()))
        except (TypeError, ValueError, RuntimeError):
            pass
    return ("Unknown",)


def _geometry_signature(target):
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
                    int(len(getattr(shape, "Solids", ()))),
                    int(len(getattr(shape, "Faces", ()))),
                    int(len(getattr(shape, "Edges", ()))),
                    int(len(getattr(shape, "Vertexes", ()))),
                    round(float(box.XMin), 6),
                    round(float(box.XMax), 6),
                    round(float(box.YMin), 6),
                    round(float(box.YMax), 6),
                    round(float(box.ZMin), 6),
                    round(float(box.ZMax), 6),
                    _shape_content_signature(shape),
                )
        except (AttributeError, TypeError, ValueError):
            pass
        return ("ShapeContent", _shape_content_signature(shape))
    return ("Unknown",)


def source_signature(target, deflection=1.0, thickness=0.0) -> tuple:
    """Provide the public source signature operation."""
    placement = getattr(target, "Placement", None)
    base = getattr(placement, "Base", None) if placement is not None else None
    rotation = getattr(placement, "Rotation", None) if placement is not None else None
    axis = getattr(rotation, "Axis", None) if rotation is not None else None
    return (
        str(getattr(target, "Name", "")),
        _geometry_signature(target),
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
