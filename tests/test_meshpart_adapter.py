import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PatternGeometry import rectangle
from PatternMeshFreeCAD import _canonical_triangle_mesh


def test_native_mesh_adapter_canonicalizes_vertex_order_and_provenance():
    pattern = rectangle(100.0, 50.0)
    vertices = [(100.0, 50.0), (0.0, 0.0), (0.0, 50.0), (100.0, 0.0)]
    triangles = [(1, 3, 0), (1, 0, 2)]
    mesh = _canonical_triangle_mesh(pattern, vertices, triangles)
    assert mesh.vertices == ((0.0, 0.0), (0.0, 50.0), (100.0, 0.0), (100.0, 50.0))
    assert abs(mesh.area - 5000.0) < 1e-7
    assert len(mesh.boundary_vertex_indices) == 4
    assert mesh.boundary_edge_segment_ids == ("bottom", "right", "top", "left")
    mesh.validate()


def test_native_mesh_adapter_is_repeatable_for_same_topology():
    pattern = rectangle(100.0, 50.0)
    vertices = [(100.0, 50.0), (0.0, 0.0), (0.0, 50.0), (100.0, 0.0)]
    triangles = [(1, 3, 0), (1, 0, 2)]
    first = _canonical_triangle_mesh(pattern, vertices, triangles)
    second = _canonical_triangle_mesh(pattern, list(reversed(vertices)), [(2, 0, 3), (2, 3, 1)])
    assert first.vertices == second.vertices
    assert first.triangles == second.triangles
    assert first.boundary_vertex_indices == second.boundary_vertex_indices
    assert first.boundary_edge_segment_ids == second.boundary_edge_segment_ids


if __name__ == "__main__":
    test_native_mesh_adapter_canonicalizes_vertex_order_and_provenance()
    test_native_mesh_adapter_is_repeatable_for_same_topology()
    print("MeshPart adapter tests passed")
