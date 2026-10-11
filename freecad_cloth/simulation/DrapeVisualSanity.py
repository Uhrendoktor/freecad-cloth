"""Solver-neutral visual sanity metrics for generated garment drapes."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import dist, isfinite
from statistics import median

from freecad_cloth.common.ValidationModels import MeshArrays, validate_points3d

Point3 = tuple[float, float, float]
Triangle3 = tuple[int, int, int]


def maximum_box_penetration(
    points: Sequence[Point3],
    bounds: tuple[float, float, float, float, float, float],
) -> float:
    """Return the deepest point inside an axis-aligned target box."""
    xmin, xmax, ymin, ymax, zmin, zmax = (float(value) for value in bounds)
    return max(
        (
            min(
                float(point[0]) - xmin,
                xmax - float(point[0]),
                float(point[1]) - ymin,
                ymax - float(point[1]),
                float(point[2]) - zmin,
                zmax - float(point[2]),
            )
            for point in points
            if xmin < float(point[0]) < xmax
            and ymin < float(point[1]) < ymax
            and zmin < float(point[2]) < zmax
        ),
        default=0.0,
    )


@dataclass(frozen=True)
class DrapeVisualMetrics:
    """Public data model or service class for DrapeVisualMetrics."""

    vertices: int
    bounds: tuple[float, float, float, float, float, float]
    spans: tuple[float, float, float]
    centroid: Point3
    vertical_span_ratio: float
    lateral_span_ratio: float
    target_vertex_clearance: float | None
    finite: bool
    state: str


def _bounds(vertices: Sequence[Point3]) -> tuple[float, float, float, float, float, float]:
    if not vertices:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    xs = [float(v[0]) for v in vertices]
    ys = [float(v[1]) for v in vertices]
    zs = [float(v[2]) for v in vertices]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def _centroid(vertices: Sequence[Point3]) -> Point3:
    count = float(len(vertices))
    return (
        sum(float(v[0]) for v in vertices) / count,
        sum(float(v[1]) for v in vertices) / count,
        sum(float(v[2]) for v in vertices) / count,
    )


def minimum_vertex_distance(
    source: Sequence[Point3], target: Sequence[Point3], *, chunk_size: int = 64
) -> float | None:
    """Return exact nearest vertex distance using the canonical SciPy KD-tree query."""
    if not source or not target:
        return None

    # Keep the legacy keyword accepted; the exact KD-tree query no longer allocates
    # source-by-target pairwise distance matrices, so chunk_size is not needed.
    del chunk_size
    from freecad_cloth.common.MeshValidation import nearest_target_clearance

    return nearest_target_clearance(source, target)


def point_inside_closed_mesh(
    point: Point3, vertices: Sequence[Point3], triangles: Sequence[Triangle3]
) -> bool:
    """Return whether one validated point is inside a closed triangle mesh."""
    return points_inside_closed_mesh((point,), vertices, triangles)[0]


def points_inside_closed_mesh(
    points: Sequence[Point3],
    vertices: Sequence[Point3],
    triangles: Sequence[Triangle3],
    *,
    chunk_size: int = 32,
    prefer_trimesh: bool = True,
) -> tuple[bool, ...]:
    """Classify points with optional Trimesh acceleration and a vectorized ray fallback.

    Pydantic validates finite coordinates and strict, in-range triangle indices once at
    the boundary. The native-host caller may bypass Trimesh acceleration when its
    optional spatial-query backend is unsafe; NumPy ray parity retains the containment
    check without changing its acceptance criterion.
    """
    validated_mesh = MeshArrays.model_validate({"vertices": vertices, "triangles": triangles})
    validated_points = validate_points3d(points)
    if not validated_points:
        return ()
    if not validated_mesh.triangles:
        return tuple(False for _ in validated_points)

    import numpy as np

    vertex_data = np.asarray(validated_mesh.vertices, dtype=np.float64)
    faces = np.asarray(validated_mesh.triangles, dtype=np.int64).reshape((-1, 3))
    point_data = np.asarray(validated_points, dtype=np.float64)
    if prefer_trimesh:
        try:
            import trimesh

            mesh = trimesh.Trimesh(vertices=vertex_data, faces=faces, process=False)
            if mesh.is_watertight:
                try:
                    contained = mesh.contains(point_data)
                except (ImportError, RuntimeError, ValueError):
                    # Trimesh's spatial-index backend is optional for diagnostics.
                    pass
                else:
                    if len(contained) == len(validated_points):
                        return tuple(bool(value) for value in contained)
        except ImportError:
            pass

    # Compatibility path for installations without trimesh/rtree or for open meshes.
    a = vertex_data[faces[:, 0]]
    b = vertex_data[faces[:, 1]]
    c = vertex_data[faces[:, 2]]
    edge_one = b - a
    edge_two = c - a
    ray = np.asarray((1.0, 0.3713906763541037, 0.1932424973120743), dtype=np.float64)
    pvec = np.cross(ray, edge_two)
    determinant = np.einsum("ij,ij->i", edge_one, pvec)
    usable = np.abs(determinant) > 1e-9
    if not bool(np.any(usable)):
        return tuple(False for _ in validated_points)
    a = a[usable]
    edge_one = edge_one[usable]
    edge_two = edge_two[usable]
    pvec = pvec[usable]
    determinant = determinant[usable]
    results = np.zeros(len(point_data), dtype=bool)
    step = max(1, int(chunk_size))
    for start in range(0, len(point_data), step):
        chunk = point_data[start : start + step]
        tvec = chunk[:, None, :] - a[None, :, :]
        u = np.einsum("ctd,td->ct", tvec, pvec) / determinant[None, :]
        qvec = np.cross(tvec, edge_one[None, :, :])
        v = np.einsum("d,ctd->ct", ray, qvec) / determinant[None, :]
        distance = np.einsum("td,ctd->ct", edge_two, qvec) / determinant[None, :]
        hits = (
            (u >= -1e-9)
            & (u <= 1.0 + 1e-9)
            & (v >= -1e-9)
            & (u + v <= 1.0 + 1e-9)
            & (distance > 1e-9)
        )
        results[start : start + len(chunk)] = np.count_nonzero(hits, axis=1) % 2 == 1
    return tuple(bool(value) for value in results)


def seam_correspondence_gap(
    boundary_a: Sequence[Point3],
    boundary_b: Sequence[Point3],
    edge_a: int,
    edge_b: int,
    *,
    reversed_b: bool = False,
    start_a: float = 0.0,
    end_a: float = 1.0,
    start_b: float = 0.0,
    end_b: float = 1.0,
    samples: int = 5,
) -> float:
    """Return deterministic max positional gap along one authored seam correspondence."""
    if not boundary_a or not boundary_b:
        raise ValueError("seam boundaries are required")
    if samples < 2:
        raise ValueError("at least two seam samples are required")
    if not 0 <= int(edge_a) < len(boundary_a) or not 0 <= int(edge_b) < len(boundary_b):
        raise ValueError("seam edge index is out of range")
    a0 = boundary_a[int(edge_a)]
    a1 = boundary_a[(int(edge_a) + 1) % len(boundary_a)]
    b0 = boundary_b[int(edge_b)]
    b1 = boundary_b[(int(edge_b) + 1) % len(boundary_b)]
    if reversed_b:
        b0, b1 = b1, b0
        start_b, end_b = 1.0 - float(end_b), 1.0 - float(start_b)

    def interpolate(left: Point3, right: Point3, fraction: float) -> Point3:
        return (
            float(left[0]) + (float(right[0]) - float(left[0])) * fraction,
            float(left[1]) + (float(right[1]) - float(left[1])) * fraction,
            float(left[2]) + (float(right[2]) - float(left[2])) * fraction,
        )

    maximum = 0.0
    for sample in range(int(samples)):
        fraction = sample / float(samples - 1)
        point_a = interpolate(a0, a1, float(start_a) + (float(end_a) - float(start_a)) * fraction)
        point_b = interpolate(b0, b1, float(start_b) + (float(end_b) - float(start_b)) * fraction)
        gap = dist(point_a, point_b)
        maximum = max(maximum, gap)
    return maximum


def inspect_drape(
    garment_vertices: Sequence[Point3],
    target_vertices: Sequence[Point3],
    *,
    target_height: float | None = None,
    target_width: float | None = None,
) -> DrapeVisualMetrics:
    """Return deterministic structural evidence for a generated drape.

    This is deliberately diagnostic rather than prescriptive: it does not
    claim that a geometrically plausible drape is physically correct.

    Coordinates follow the FreeCAD garment convention used by the canonical
    visual fixture: X/Y form the garment footprint and Z is vertical. The
    ratios therefore intentionally use Z for vertical coverage and the larger
    of X/Y for lateral coverage; using the largest or second-smallest axis can
    make a wide, flattened or side-on garment look healthy by mistake.
    """
    if not garment_vertices:
        return DrapeVisualMetrics(
            0, (0.0,) * 6, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 0.0, 0.0, None, False, "empty"
        )
    finite = all(isfinite(float(c)) for v in garment_vertices for c in v)
    if not finite:
        return DrapeVisualMetrics(
            len(garment_vertices),
            _bounds(garment_vertices),
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
            0.0,
            0.0,
            None,
            False,
            "nonfinite",
        )

    b = _bounds(garment_vertices)
    spans = (b[1] - b[0], b[3] - b[2], b[5] - b[4])
    vertical = spans[2]
    lateral_width = max(spans[0], spans[1])
    vertical_span_ratio = (
        vertical / float(target_height) if target_height and target_height > 0 else 0.0
    )
    lateral_span_ratio = (
        lateral_width / float(target_width) if target_width and target_width > 0 else 0.0
    )
    clearance = minimum_vertex_distance(garment_vertices, target_vertices)
    centroid = _centroid(garment_vertices)

    state = "structurally-plausible"
    if not target_vertices:
        state = "missing-target"
    elif vertical <= 1e-9:
        state = "flat-or-collapsed"
    elif target_height and vertical_span_ratio < 0.15:
        state = "short-drape-candidate"
    elif (
        clearance is not None and target_width and clearance > max(float(target_width) * 0.30, 1.0)
    ):
        state = "detached-candidate"

    return DrapeVisualMetrics(
        len(garment_vertices),
        b,
        spans,
        centroid,
        vertical_span_ratio,
        lateral_span_ratio,
        clearance,
        True,
        state,
    )


def summarize(metrics: DrapeVisualMetrics) -> dict:
    """Provide the public summarize operation."""
    return {
        "state": metrics.state,
        "vertices": metrics.vertices,
        "bounds": metrics.bounds,
        "spans": metrics.spans,
        "centroid": metrics.centroid,
        "vertical_span_ratio": metrics.vertical_span_ratio,
        "lateral_span_ratio": metrics.lateral_span_ratio,
        "target_vertex_clearance": metrics.target_vertex_clearance,
        "finite": metrics.finite,
    }


_FATAL_VISUAL_STATES = frozenset({"detached-candidate"})
_FATAL_VISUAL_DIAGNOSTICS = frozenset(
    {
        "lateral-detached-candidate",
        "collapsed-candidate",
        "below-hem-candidate",
    }
)


def assert_drape_diagnostics(
    records: Sequence[dict], *, allowed_diagnostics: Sequence[str] = ()
) -> None:
    """Fail closed while allowing explicitly documented diagnostic exceptions."""
    failures = []
    allowed = {str(item) for item in allowed_diagnostics}
    fatal_diagnostics = _FATAL_VISUAL_DIAGNOSTICS - allowed
    for record in records:
        classification = record.get("failure_classification", {})
        state = str(classification.get("state", ""))
        diagnostics = {str(item) for item in record.get("diagnostics", ())}
        if state in _FATAL_VISUAL_STATES or diagnostics & fatal_diagnostics:
            failures.append(
                "{}: classification={} diagnostics={}".format(
                    str(record.get("panel", "<unknown>")),
                    state or "none",
                    ",".join(sorted(diagnostics)),
                )
            )
    if failures:
        raise RuntimeError("drape visual acceptance failed closed: " + "; ".join(failures))


def mesh_shape_sanity(
    vertices: Sequence[Point3], triangles: Sequence[Triangle3]
) -> dict[str, bool | int | float]:
    """Return deterministic mesh-shape health metrics for visual regression.

    The metrics intentionally describe geometry rather than deciding whether a
    cloth result is physically correct. They catch the two failure modes that
    are easy to miss in a camera-only regression: isolated long-edge spikes
    and an unexpectedly extreme lateral footprint.
    """
    if not vertices:
        return {
            "finite": False,
            "vertices": 0,
            "faces": 0,
            "median_edge_length": 0.0,
            "max_edge_length": 0.0,
            "edge_spike_ratio": float("inf"),
            "spike_edge_fraction": 1.0,
            "footprint_aspect_ratio": float("inf"),
        }

    finite = all(isfinite(float(c)) for vertex in vertices for c in vertex)
    if not finite:
        return {
            "finite": False,
            "vertices": len(vertices),
            "faces": len(triangles),
            "median_edge_length": 0.0,
            "max_edge_length": 0.0,
            "edge_spike_ratio": float("inf"),
            "spike_edge_fraction": 1.0,
            "footprint_aspect_ratio": float("inf"),
        }

    unique_edges = set()
    lengths = []
    for triangle in triangles:
        if len(triangle) != 3:
            continue
        a, b, c = (int(index) for index in triangle)
        for left, right in ((a, b), (b, c), (c, a)):
            edge = (min(left, right), max(left, right))
            if edge in unique_edges:
                continue
            unique_edges.add(edge)
            p = vertices[left]
            q = vertices[right]
            lengths.append(dist(p, q))

    if not lengths:
        median_edge = 0.0
        max_edge = 0.0
        spike_ratio = float("inf")
        spike_fraction = 1.0
    else:
        median_edge = float(median(lengths))
        max_edge = float(max(lengths))
        spike_ratio = max_edge / median_edge if median_edge > 1e-12 else float("inf")
        spike_fraction = sum(1 for value in lengths if value > 4.0 * median_edge) / float(
            len(lengths)
        )

    xs = [float(vertex[0]) for vertex in vertices]
    ys = [float(vertex[1]) for vertex in vertices]
    span_x = max(xs) - min(xs)
    span_y = max(ys) - min(ys)
    if span_x <= 1e-12 or span_y <= 1e-12:
        aspect = float("inf")
    else:
        aspect = max(span_x, span_y) / min(span_x, span_y)

    return {
        "finite": True,
        "vertices": len(vertices),
        "faces": len(triangles),
        "median_edge_length": median_edge,
        "max_edge_length": max_edge,
        "edge_spike_ratio": spike_ratio,
        "spike_edge_fraction": spike_fraction,
        "footprint_aspect_ratio": aspect,
    }
