# Copyright (C) 2026 FreeCAD Cloth contributors
"""Real FreeCAD smoke test for the optional MeshPart pattern adapter."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freecad_cloth.pattern.PatternGeometry import rectangle
from freecad_cloth.pattern.PatternMeshFreeCAD import mesh_from_pattern
from freecad_cloth.pattern.PatternModel import Seam
from freecad_cloth.sewing.SewingConstraints import SewingPatternMesh, build_sewing_constraints
from tests.support.assertions import require

EXPECTED_AREA_MM2 = 5000.0
AREA_TOLERANCE_MM2 = 1e-5
MINIMUM_STITCH_COUNT = 2
EXPECTED_BOUNDARY_SEGMENT_IDS = ("bottom", "right", "top", "left")


def main() -> None:
    """Exercise the optional MeshPart adapter and deterministic sewing constraints."""
    pattern = rectangle(100.0, 50.0)
    first = mesh_from_pattern(pattern, linear_deflection=0.5, angular_deflection=0.5)
    second = mesh_from_pattern(pattern, linear_deflection=0.5, angular_deflection=0.5)
    first.validate()
    second.validate()
    require(
        condition=abs(first.area - EXPECTED_AREA_MM2) < AREA_TOLERANCE_MM2,
        message="MeshPart triangulation must preserve the authored rectangle area.",
    )
    require(
        condition=first.vertices == second.vertices,
        message="Repeated MeshPart triangulation must produce identical vertices.",
    )
    require(
        condition=first.triangles == second.triangles,
        message="Repeated MeshPart triangulation must produce identical faces.",
    )
    require(
        condition=first.boundary_vertex_indices == second.boundary_vertex_indices,
        message="Repeated MeshPart triangulation must preserve boundary index order.",
    )
    require(
        condition=first.boundary_edge_segment_ids == EXPECTED_BOUNDARY_SEGMENT_IDS,
        message="MeshPart boundary provenance must follow authored segment identity.",
    )
    constraints = build_sewing_constraints(
        SewingPatternMesh(pattern, first),
        SewingPatternMesh(pattern, second),
        Seam("front", 1, "back", 3, id="meshpart-smoke"),
        samples=5,
    )
    constraints.validate()
    require(
        condition=len(constraints.stitches) >= MINIMUM_STITCH_COUNT,
        message="MeshPart sewing must create at least two stitch links.",
    )
    sys.stdout.write("FreeCAD MeshPart adapter smoke test passed\n")


if __name__ == "__main__":
    main()
