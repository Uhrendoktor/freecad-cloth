# Copyright (C) 2026 FreeCAD Cloth contributors
"""Shared fixtures for semantic PatternIR edge-reference tests."""

from freecad_cloth.pattern.PatternIR import BoundaryIR
from freecad_cloth.pattern.SeamReference import capture_edge_reference


def edge_reference_signature(piece_id: str, boundary: BoundaryIR) -> str:
    """Capture native provenance for a semantic PatternIR boundary.

    Args:
        piece_id: Persistent identity of the PatternPiece that owns the boundary.
        boundary: Resolved PatternIR boundary used by the seam fixture.

    Returns:
        Native Sketcher edge-reference signature for the boundary endpoints.
    """
    samples = tuple(tuple(point) for point in boundary.samples)
    points = ((samples[0][0], samples[0][1]), (samples[-1][0], samples[-1][1]))
    provenance = (
        "PatternIR",
        "Sketcher",
        boundary.kind,
        tuple(float(value) for value in boundary.parameter_range),
        samples,
    )
    return capture_edge_reference(piece_id, boundary.id, points, provenance).signature
