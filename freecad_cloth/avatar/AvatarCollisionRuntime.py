"""FreeCAD-native collision mesh simplification for runtime-only paths.

This module deliberately owns the FreeCAD/Mesh dependency so the immutable,
solver-independent CollisionSurface contract stays importable without FreeCAD.
"""
from dataclasses import dataclass
from math import isfinite
from time import perf_counter
from typing import Dict, Tuple

from freecad_cloth.avatar.AvatarCollision import CollisionSurface, surface_from_triangles


@dataclass(frozen=True)
class CollisionTopology:
    vertices: int
    faces: int
    components: int
    boundary_edges: int
    nonmanifold_edges: int
    finite: bool


def collision_topology(surface: CollisionSurface) -> CollisionTopology:
    """Return deterministic topology/finiteness facts for a collision surface."""
    surface.validate()
    edge_to_faces: Dict[Tuple[int, int], list[int]] = {}
    finite = True
    for vertex in surface.vertices:
        finite = finite and all(isfinite(float(coord)) for coord in vertex)

    for face_index, (a, b, c) in enumerate(surface.triangles):
        if a == b or b == c or a == c:
            raise ValueError("collision surface contains a degenerate triangle")
        p, q, r = surface.vertices[a], surface.vertices[b], surface.vertices[c]
        ux, uy, uz = (q[i] - p[i] for i in range(3))
        vx, vy, vz = (r[i] - p[i] for i in range(3))
        area2 = (uy * vz - uz * vy) ** 2 + (uz * vx - ux * vz) ** 2 + (ux * vy - uy * vx) ** 2
        if not isfinite(area2) or area2 <= 1e-18:
            raise ValueError("collision surface contains a zero-area triangle")
        for edge in ((a, b), (b, c), (c, a)):
            key = tuple(sorted(edge))
            edge_to_faces.setdefault(key, []).append(face_index)

    parent = list(range(len(surface.triangles)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    boundary_edges = 0
    nonmanifold_edges = 0
    for faces in edge_to_faces.values():
        if len(faces) == 1:
            boundary_edges += 1
        elif len(faces) == 2:
            union(faces[0], faces[1])
        else:
            nonmanifold_edges += 1
            for index in faces[1:]:
                union(faces[0], index)

    components = len({find(index) for index in range(len(surface.triangles))})
    return CollisionTopology(
        vertices=len(surface.vertices),
        faces=len(surface.triangles),
        components=components,
        boundary_edges=boundary_edges,
        nonmanifold_edges=nonmanifold_edges,
        finite=finite,
    )


def _freecad_mesh(surface: CollisionSurface):
    try:
        import FreeCAD as App
        import Mesh
    except ImportError as exc:
        raise RuntimeError("FreeCAD Mesh decimation is unavailable") from exc

    native = Mesh.Mesh()
    vectors = [App.Vector(*vertex) for vertex in surface.vertices]
    native.addFacets([(vectors[a], vectors[b], vectors[c]) for a, b, c in surface.triangles])
    return native


def decimate_collision_surface_native(
    surface: CollisionSurface,
    target_triangles: int,
) -> CollisionSurface:
    """Simplify a collision surface using FreeCAD Mesh's absolute face target.

    The operation is fail-closed: the exact target count, finite geometry, and
    source-compatible topology must all survive native decimation. There is no
    sparse-face fallback.
    """
    target = int(target_triangles)
    surface.validate()
    if target < 1:
        raise ValueError("target_triangles must be positive")
    if len(surface.triangles) < target:
        raise RuntimeError(
            "native decimation cannot reach the requested face target without adding geometry"
        )
    if len(surface.triangles) == target:
        report = collision_topology(surface)
        if not report.finite:
            raise RuntimeError("collision surface contains non-finite coordinates")
        return surface

    source_report = collision_topology(surface)
    if not source_report.finite:
        raise RuntimeError("source collision surface contains non-finite coordinates")

    started = perf_counter()
    native = _freecad_mesh(surface)
    decimate = getattr(native, "decimate", None)
    if not callable(decimate):
        raise RuntimeError("FreeCAD Mesh decimation API is unavailable")

    try:
        result = decimate(target)
    except Exception as exc:
        raise RuntimeError("FreeCAD Mesh decimation failed") from exc
    if result is not None and hasattr(result, "Topology"):
        native = result

    try:
        raw_vertices, raw_faces = native.Topology
        vertices = tuple(
            (float(vertex.x), float(vertex.y), float(vertex.z))
            for vertex in raw_vertices
        )
        triangles = tuple(
            tuple(int(index) for index in face)
            for face in raw_faces
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise RuntimeError("FreeCAD decimation returned unusable topology") from exc

    simplified = surface_from_triangles(
        vertices,
        triangles,
        region=surface.region,
        thickness=surface.thickness,
    )
    result_report = collision_topology(simplified)
    elapsed_ms = (perf_counter() - started) * 1000.0

    if result_report.faces != target:
        raise RuntimeError(
            "FreeCAD decimation did not produce the exact face target: "
            f"{result_report.faces} != {target}"
        )
    if not result_report.finite:
        raise RuntimeError("FreeCAD decimation produced non-finite coordinates")
    if result_report.nonmanifold_edges:
        raise RuntimeError("FreeCAD decimation produced non-manifold topology")
    if result_report.components > source_report.components:
        raise RuntimeError(
            "FreeCAD decimation fragmented the collision surface: "
            f"{result_report.components} > {source_report.components}"
        )
    source_is_closed = (
        source_report.components == 1
        and source_report.boundary_edges == 0
        and source_report.nonmanifold_edges == 0
    )
    if source_is_closed and (
        result_report.components != 1 or result_report.boundary_edges != 0
    ):
        raise RuntimeError(
            "FreeCAD decimation failed to preserve a closed connected source surface"
        )

    print(
        "cloth-tissu-collision-native "
        f"source_vertices={source_report.vertices} "
        f"source_faces={source_report.faces} "
        f"solver_vertices={result_report.vertices} "
        f"solver_faces={result_report.faces} "
        f"components={result_report.components} "
        f"boundary_edges={result_report.boundary_edges} "
        f"nonmanifold_edges={result_report.nonmanifold_edges} "
        f"decimation_ms={elapsed_ms:.3f}",
        flush=True,
    )
    return simplified
