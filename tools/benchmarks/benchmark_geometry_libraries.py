"""Optional benchmark for the SciPy/GEOS geometry accelerations.

Run after installing the optional extra:
    python -m pip install -e ".[geometry]"
    python tools/benchmarks/benchmark_geometry_libraries.py --sizes 128 512 1024

The benchmark checks result equivalence before printing timings. It does not impose
machine-dependent performance thresholds and is not part of the release gate.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from importlib.util import find_spec
from math import cos, isclose, sin, tau
from random import Random
from time import perf_counter

from freecad_cloth.common.MeshValidation import (
    Point3,
    _nearest_target_clearance_bruteforce,
    nearest_target_clearance,
)
from freecad_cloth.pattern.PatternGeometry import Point
from freecad_cloth.pattern.PatternMesh import _self_intersects, _self_intersects_python


def _point_cloud(count: int, seed: int, offset: float) -> tuple[Point3, ...]:
    """Create a deterministic 3D cloud for comparable benchmark runs."""
    generator = Random(seed)
    return tuple(
        (
            generator.uniform(-100.0, 100.0) + offset,
            generator.uniform(-100.0, 100.0),
            generator.uniform(-100.0, 100.0),
        )
        for _ in range(count)
    )


def _simple_ring(count: int) -> tuple[Point, ...]:
    """Create a counter-clockwise polygon with no self-intersections."""
    return tuple(
        (100.0 * cos(tau * index / count), 100.0 * sin(tau * index / count))
        for index in range(count)
    )


def _time_clearance(count: int) -> None:
    """Compare optimized nearest-point query time and scalar reference time."""
    garment = _point_cloud(count, 1729, 0.0)
    target = _point_cloud(count, 2718, 300.0)

    started = perf_counter()
    accelerated = nearest_target_clearance(garment, target)
    accelerated_seconds = perf_counter() - started

    started = perf_counter()
    reference = _nearest_target_clearance_bruteforce(garment, target)
    reference_seconds = perf_counter() - started

    if not isclose(accelerated, reference, rel_tol=1e-9, abs_tol=1e-9):
        raise AssertionError(
            f"clearance mismatch for {count}x{count} points: "
            f"{accelerated!r} != {reference!r}"
        )
    print(
        f"clearance vertices={count}x{count} "
        f"optimized_ms={accelerated_seconds * 1000:.3f} "
        f"reference_ms={reference_seconds * 1000:.3f} "
        f"distance={accelerated:.9g}"
    )


def _time_outline(count: int) -> None:
    """Compare GEOS-backed simplicity check with the Python reference predicate."""
    points = _simple_ring(count)

    started = perf_counter()
    accelerated = _self_intersects(points)
    accelerated_seconds = perf_counter() - started

    started = perf_counter()
    reference = _self_intersects_python(points)
    reference_seconds = perf_counter() - started

    if accelerated != reference:
        raise AssertionError(
            f"outline predicate mismatch for {count} vertices: "
            f"{accelerated!r} != {reference!r}"
        )
    print(
        f"outline vertices={count} "
        f"optimized_ms={accelerated_seconds * 1000:.3f} "
        f"reference_ms={reference_seconds * 1000:.3f} "
        f"self_intersects={accelerated}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Validate and time optional accelerated geometry implementations."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", default=(128, 512, 1024))
    args = parser.parse_args(argv)

    missing = [package for package in ("scipy", "shapely") if find_spec(package) is None]
    if missing:
        raise SystemExit(
            "Missing optional geometry libraries: "
            + ", ".join(missing)
            + '; install with: python -m pip install -e ".[geometry]"'
        )

    for count in args.sizes:
        if count < 32:
            raise SystemExit("each benchmark size must be at least 32")
        _time_clearance(count)
        _time_outline(count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
