"""Fast regression tests for compact FreeCAD display-mesh topology."""

from freecad_cloth.simulation.SimulationObjects import _indexed_mesh_topology


def test_indexed_mesh_topology_reuses_shared_vertices_and_remaps_faces() -> None:
    triangles = ((0, 1, 2), (0, 2, 3), (5, 6, 7), (3, 2, 0))

    result = _indexed_mesh_topology(triangles)
    vertex_indices, faces = result

    assert vertex_indices == (0, 1, 2, 3, 5, 6, 7)
    assert faces == ((0, 1, 2), (0, 2, 3), (4, 5, 6), (3, 2, 0))
    assert _indexed_mesh_topology(triangles) is result
