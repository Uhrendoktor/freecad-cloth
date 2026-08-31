"""Real FreeCAD smoke test for the optional MeshPart pattern adapter."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freecad_cloth.pattern.PatternGeometry import rectangle
from freecad_cloth.pattern.PatternMeshFreeCAD import mesh_from_pattern
from freecad_cloth.pattern.PatternModel import Seam
from freecad_cloth.sewing.SewingConstraints import build_sewing_constraints


def main():
    pattern = rectangle(100.0, 50.0)
    first = mesh_from_pattern(pattern, linear_deflection=0.5, angular_deflection=0.5)
    second = mesh_from_pattern(pattern, linear_deflection=0.5, angular_deflection=0.5)
    first.validate()
    second.validate()
    assert abs(first.area - 5000.0) < 1e-5
    assert first.vertices == second.vertices
    assert first.triangles == second.triangles
    assert first.boundary_vertex_indices == second.boundary_vertex_indices
    assert first.boundary_edge_segment_ids == ("bottom", "right", "top", "left")
    constraints = build_sewing_constraints(
        pattern,
        first,
        pattern,
        second,
        Seam("front", 1, "back", 3, id="meshpart-smoke"),
        samples=5,
    )
    constraints.validate()
    assert len(constraints.stitches) >= 2
    print("FreeCAD MeshPart adapter smoke test passed")


if __name__ == "__main__":
    main()
