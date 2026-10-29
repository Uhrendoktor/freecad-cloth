# Copyright (C) 2026 FreeCAD Cloth contributors
"""Benchmark for the required SciPy/GEOS geometry implementations.

Run after installing package dependencies:
    python -m pip install -e .
    python tools/benchmarks/benchmark_geometry_libraries.py --sizes 128 512 1024

The benchmark checks result equivalence before printing timings. It does not impose
machine-dependent performance thresholds and is not part of the release gate.
"""

from __future__ import annotations

import argparse
import sys
from math import cos, dist, isclose, sin, tau
from time import perf_counter
from typing import TYPE_CHECKING

import numpy as np
from shapely.geometry import LineString

from freecad_cloth.common.MeshValidation import Point3, nearest_target_clearance

if TYPE_CHECKING:
    from collections.abc import Sequence

    from freecad_cloth.pattern.PatternGeometry import Point


SEGMENT_CROSS_PRODUCT_TOLERANCE = 1e-10
MINIMUM_BENCHMARK_SIZE = 32


def _point_cloud(count: int, seed: int, offset: float) -> tuple[Point3, ...]:
    """Generate a reproducible 3D point cloud for geometry timing comparisons.

    Args:
        count: Number of 3D points to generate.
        seed: Random-generator seed used to make the point cloud deterministic.
        offset: X-coordinate offset applied to every generated point.

    Returns:
        Immutable tuple of generated 3D points.
    """
    generator = np.random.default_rng(seed)
    return tuple(
        (
            generator.uniform(-100.0, 100.0) + offset,
            generator.uniform(-100.0, 100.0),
            generator.uniform(-100.0, 100.0),
        )
        for _ in range(count)
    )


def _simple_ring(count: int) -> tuple[Point, ...]:
    """Generate a regular counter-clockwise polygon for outline benchmarks.

    Args:
        count: Number of vertices to distribute around the ring.

    Returns:
        Immutable tuple of 2D vertices in counter-clockwise order.
    """
    return tuple(
        (100.0 * cos(tau * index / count), 100.0 * sin(tau * index / count))
        for index in range(count)
    )


def _reference_clearance(garment: Sequence[Point3], target: Sequence[Point3]) -> float:
    """Compute the scalar-reference clearance used to validate the optimized query.

    Args:
        garment: Garment mesh vertices represented as 3D points.
        target: Target surface vertices represented as 3D points.

    Returns:
        Minimum Euclidean distance between any garment and target point.
    """
    return min(dist(source, candidate) for source in garment for candidate in target)


def _python_self_intersects_reference(points: Sequence[Point]) -> bool:
    """Evaluate the former Python segment-intersection predicate as an oracle.

    Args:
        points: Ordered vertices describing a polygonal outline.

    Returns:
        True when non-adjacent segments intersect beyond the reference tolerance.
    """

    def cross(a: Point, b: Point, c: Point) -> float:
        """Return the signed 2D cross product for the directed segments AB and AC.

        Args:
            a: Shared origin point for the two directed segments.
            b: End point of the first directed segment.
            c: End point of the second directed segment.

        Returns:
            Signed twice-triangle area, whose sign gives the orientation.
        """
        return ((b[0] - a[0]) * (c[1] - a[1])) - ((b[1] - a[1]) * (c[0] - a[0]))

    for i in range(len(points)):
        a, b = points[i], points[(i + 1) % len(points)]
        for j in range(i + 1, len(points)):
            if j in {i, (i + 1) % len(points), (i - 1) % len(points)}:
                continue
            c, d = points[j], points[(j + 1) % len(points)]
            values = (cross(a, b, c), cross(a, b, d), cross(c, d, a), cross(c, d, b))
            if (
                values[0] * values[1] < -SEGMENT_CROSS_PRODUCT_TOLERANCE
                and values[2] * values[3] < -SEGMENT_CROSS_PRODUCT_TOLERANCE
            ):
                return True
    return False


def _time_clearance(count: int) -> None:
    """Measure the accelerated and scalar-reference nearest-point implementations.

    Args:
        count: Number of garment points and target points in the benchmark case.

    Raises:
        AssertionError: If the optimized and reference clearances differ beyond tolerance.
    """
    garment = _point_cloud(count, 1729, 0.0)
    target = _point_cloud(count, 2718, 300.0)

    started = perf_counter()
    accelerated = nearest_target_clearance(garment, target)
    accelerated_seconds = perf_counter() - started

    started = perf_counter()
    reference = _reference_clearance(garment, target)
    reference_seconds = perf_counter() - started

    if not isclose(accelerated, reference, rel_tol=1e-9, abs_tol=1e-9):
        msg = f"clearance mismatch for {count}x{count} points: {accelerated!r} != {reference!r}"
        raise AssertionError(msg)
    sys.stdout.write(
        f"clearance vertices={count}x{count} "
        f"optimized_ms={accelerated_seconds * 1000:.3f} "
        f"reference_ms={reference_seconds * 1000:.3f} "
        f"distance={accelerated:.9g}\n"
    )


def _time_outline(count: int) -> None:
    """Measure the GEOS-backed and Python polygon-simplicity predicates.

    Args:
        count: Number of vertices in the benchmark polygon.

    Raises:
        AssertionError: If the optimized and reference predicates return different results.
    """
    points = _simple_ring(count)

    started = perf_counter()
    accelerated = not LineString([*points, points[0]]).is_simple
    accelerated_seconds = perf_counter() - started

    started = perf_counter()
    reference = _python_self_intersects_reference(points)
    reference_seconds = perf_counter() - started

    if accelerated != reference:
        msg = f"outline predicate mismatch for {count} vertices: {accelerated!r} != {reference!r}"
        raise AssertionError(msg)
    sys.stdout.write(
        f"outline vertices={count} "
        f"optimized_ms={accelerated_seconds * 1000:.3f} "
        f"reference_ms={reference_seconds * 1000:.3f} "
        f"self_intersects={accelerated}\n"
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Validate equivalent geometry results before reporting performance timings.

    Args:
        argv: Optional command-line arguments; None uses the process arguments.

    Returns:
        Zero when all requested geometry benchmark cases complete successfully.

    Raises:
        SystemExit: If a requested benchmark size is below the minimum benchmark size.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", default=(128, 512, 1024))
    args = parser.parse_args(argv)

    for count in args.sizes:
        if count < MINIMUM_BENCHMARK_SIZE:
            msg = "each benchmark size must be at least 32"
            raise SystemExit(msg)
        _time_clearance(count)
        _time_outline(count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
