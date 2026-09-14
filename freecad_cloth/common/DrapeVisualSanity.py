"""Compatibility facade for solver-neutral drape visual sanity metrics."""
from __future__ import annotations

from freecad_cloth.common.MeshValidation import (
    DrapeVisualMetrics,
    measure_drape_visual_sanity,
    nearest_target_clearance,
    summarize_drape_visual_metrics,
)


def minimum_vertex_distance(source, target):
    """Return minimum vertex-to-vertex distance for legacy callers."""
    if not source or not target:
        return None
    return nearest_target_clearance(source, target)


def inspect_drape(garment_vertices, target_vertices, *, target_height=None, target_width=None):
    """Compatibility wrapper around the canonical MeshValidation metric."""
    return measure_drape_visual_sanity(
        garment_vertices,
        target_vertices,
        target_height=target_height,
        target_width=target_width,
    )


def summarize(metrics: DrapeVisualMetrics) -> dict:
    """Return the stable JSON-ready representation used by acceptance tooling."""
    return summarize_drape_visual_metrics(metrics)


__all__ = [
    "DrapeVisualMetrics",
    "inspect_drape",
    "minimum_vertex_distance",
    "summarize",
]
