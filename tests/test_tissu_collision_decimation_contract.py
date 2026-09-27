import sys
import types

import pytest

from freecad_cloth.avatar.AvatarCollision import CollisionSurface
from freecad_cloth.avatar.AvatarCollisionRuntime import (
    collision_topology,
    decimate_collision_surface_native,
)


class FakeVector:
    def __init__(self, x, y, z):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)


def _octahedron():
    vertices = [
        (1.0, 0.0, 0.0),
        (-1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, -1.0, 0.0),
        (0.0, 0.0, 1.0),
        (0.0, 0.0, -1.0),
    ]
    faces = [
        (0, 4, 2), (2, 4, 1), (1, 4, 3), (3, 4, 0),
        (2, 5, 0), (1, 5, 2), (3, 5, 1), (0, 5, 3),
    ]
    return vertices, faces


def _subdivide(vertices, faces):
    vertices = list(vertices)
    edge_midpoints = {}

    def midpoint(a, b):
        key = tuple(sorted((a, b)))
        if key in edge_midpoints:
            return edge_midpoints[key]
        pa, pb = vertices[a], vertices[b]
        x, y, z = ((pa[i] + pb[i]) * 0.5 for i in range(3))
        length = (x * x + y * y + z * z) ** 0.5
        index = len(vertices)
        vertices.append((x / length, y / length, z / length))
        edge_midpoints[key] = index
        return index

    result = []
    for a, b, c in faces:
        ab = midpoint(a, b)
        bc = midpoint(b, c)
        ca = midpoint(c, a)
        result.extend(((a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)))
    return tuple(vertices), tuple(result)


def _sphere(level):
    vertices, faces = _octahedron()
    for _ in range(level):
        vertices, faces = _subdivide(vertices, faces)
    return vertices, faces


class FakeNativeMesh:
    def __init__(self, output_vertices, output_faces):
        self._topology = (
            [FakeVector(*vertex) for vertex in output_vertices],
            [tuple(face) for face in output_faces],
        )

    def addFacets(self, facets):
        self._input_facet_count = len(facets)

    @property
    def Topology(self):
        return self._topology

    def decimate(self, target):
        assert target == len(self._topology[1])
        return None


class FakeMeshModule:
    def __init__(self, output_vertices, output_faces):
        self._output_vertices = output_vertices
        self._output_faces = output_faces

    def Mesh(self):
        return FakeNativeMesh(self._output_vertices, self._output_faces)


def _install_fake_freecad(monkeypatch, mesh_module):
    freecad = types.ModuleType("FreeCAD")
    freecad.Vector = FakeVector
    monkeypatch.setitem(sys.modules, "FreeCAD", freecad)
    monkeypatch.setitem(sys.modules, "Mesh", mesh_module)


def _tetra(offset):
    base = [
        (0.0 + offset, 0.0, 0.0),
        (1.0 + offset, 0.0, 0.0),
        (0.0 + offset, 1.0, 0.0),
        (0.0 + offset, 0.0, 1.0),
    ]
    faces = ((0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3))
    return base, faces


def test_native_decimation_hits_exact_2048_and_is_deterministic(monkeypatch):
    source_vertices, source_faces = _sphere(5)
    expected_vertices, expected_faces = _sphere(4)
    mesh = FakeMeshModule(expected_vertices, expected_faces)
    _install_fake_freecad(monkeypatch, mesh)
    source = CollisionSurface(tuple(source_vertices), tuple(source_faces))

    first = decimate_collision_surface_native(source, 2048)
    second = decimate_collision_surface_native(source, 2048)

    assert len(first.triangles) == 2048
    assert first == second
    report = collision_topology(first)
    assert report.faces == 2048
    assert report.components == 1
    assert report.boundary_edges == 0
    assert report.nonmanifold_edges == 0
    assert report.finite is True


def test_native_decimation_fails_closed_when_api_is_unavailable(monkeypatch):
    class NoDecimateMesh:
        def addFacets(self, facets):
            self._facets = facets

    class NoDecimateModule:
        Mesh = NoDecimateMesh

    _install_fake_freecad(monkeypatch, NoDecimateModule())
    vertices, faces = _sphere(1)
    source = CollisionSurface(tuple(vertices), tuple(faces))

    with pytest.raises(RuntimeError, match="decimation API is unavailable"):
        decimate_collision_surface_native(source, 8)


def test_native_decimation_rejects_fragmented_output(monkeypatch):
    source_vertices, source_faces = _sphere(1)
    tetra_a, tetra_faces_a = _tetra(0.0)
    tetra_b, tetra_faces_b = _tetra(3.0)
    expected_vertices = tuple(tetra_a + tetra_b)
    expected_faces = tuple(
        tetra_faces_a
        + tuple((a + 4, b + 4, c + 4) for a, b, c in tetra_faces_b)
    )
    _install_fake_freecad(monkeypatch, FakeMeshModule(expected_vertices, expected_faces))
    source = CollisionSurface(tuple(source_vertices), tuple(source_faces))

    with pytest.raises(RuntimeError, match="fragmented"):
        decimate_collision_surface_native(source, 8)


def test_native_decimation_preserves_closed_source_contract(monkeypatch):
    source_vertices, source_faces = _sphere(1)
    open_vertices = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0))
    open_faces = ((0, 1, 2), (0, 2, 3))
    _install_fake_freecad(monkeypatch, FakeMeshModule(open_vertices, open_faces))
    source = CollisionSurface(tuple(source_vertices), tuple(source_faces))

    with pytest.raises(RuntimeError, match="closed connected"):
        decimate_collision_surface_native(source, 2)
