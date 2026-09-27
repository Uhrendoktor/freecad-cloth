import sys
import types

import pytest

from freecad_cloth.avatar.AvatarCollision import CollisionSurface
from freecad_cloth.simulation.TissuBackend import (
    _decimate_collision_surface_native,
    _surface_topology_stats,
)


class _Vector:
    def __init__(self, x, y, z):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)


class _DecimatingMesh:
    def __init__(self):
        self._points = ()
        self._faces = ()

    @property
    def Topology(self):
        return self._points, self._faces

    def addFacets(self, facets):
        point_ids = {}
        points = []

        def point_id(point):
            key = (float(point.x), float(point.y), float(point.z))
            index = point_ids.get(key)
            if index is None:
                index = len(points)
                point_ids[key] = index
                points.append(_Vector(*key))
            return index

        self._faces = tuple(
            tuple(point_id(vertex) for vertex in facet)
            for facet in facets
        )
        self._points = tuple(points)

    def decimate(self, target_size):
        if int(target_size) != 4:
            raise AssertionError("unexpected target size")
        self._points = (
            _Vector(0, 0, 0),
            _Vector(2, 0, 0),
            _Vector(1, 0, 2),
            _Vector(1, 2, 1),
        )
        self._faces = (
            (0, 2, 1),
            (0, 1, 3),
            (1, 2, 3),
            (0, 3, 2),
        )


class _ShortDecimatingMesh(_DecimatingMesh):
    def decimate(self, target_size):
        super().decimate(target_size)
        self._faces = self._faces[:-1]


def _closed_octahedron():
    vertices = (
        (1, 0, 0), (-1, 0, 0),
        (0, 1, 0), (0, -1, 0),
        (0, 0, 1), (0, 0, -1),
    )
    triangles = (
        (0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4),
        (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5),
    )
    return CollisionSurface(vertices, triangles, "fixture", 1.0)


def _freecad_modules(mesh_class):
    return (
        types.SimpleNamespace(Vector=_Vector),
        types.SimpleNamespace(Mesh=mesh_class),
    )


def test_surface_topology_stats_identifies_closed_mesh():
    stats = _surface_topology_stats(_closed_octahedron())
    assert stats["finite"] is True
    assert stats["components"] == 1
    assert stats["boundary_edges"] == 0
    assert stats["nonmanifold_edges"] == 0
    assert stats["closed_manifold"] is True


def test_native_decimation_is_exact_deterministic_and_closed(monkeypatch):
    freecad, mesh = _freecad_modules(_DecimatingMesh)
    monkeypatch.setitem(sys.modules, "FreeCAD", freecad)
    monkeypatch.setitem(sys.modules, "Mesh", mesh)

    surface = _closed_octahedron()
    first, first_stats = _decimate_collision_surface_native(surface, 4)
    second, second_stats = _decimate_collision_surface_native(surface, 4)

    assert first.triangles == second.triangles
    assert first.vertices == second.vertices
    assert first_stats["faces"] == 4
    assert second_stats["faces"] == 4
    assert first_stats["components"] == 1
    assert first_stats["boundary_edges"] == 0
    assert first_stats["nonmanifold_edges"] == 0
    assert first_stats["closed_manifold"] is True
    assert first_stats["method"] == "freecad-mesh-decimate"
    assert first_stats["decimation_ms"] >= 0.0


def test_native_decimation_fails_closed_on_exact_budget_violation(monkeypatch):
    freecad, mesh = _freecad_modules(_ShortDecimatingMesh)
    monkeypatch.setitem(sys.modules, "FreeCAD", freecad)
    monkeypatch.setitem(sys.modules, "Mesh", mesh)

    with pytest.raises(RuntimeError, match="exact collision budget"):
        _decimate_collision_surface_native(_closed_octahedron(), 4)


def test_native_decimation_fails_closed_when_mesh_api_is_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "FreeCAD", types.SimpleNamespace(Vector=_Vector))
    monkeypatch.setitem(sys.modules, "Mesh", types.SimpleNamespace(Mesh=lambda: object()))

    with pytest.raises(RuntimeError, match="absolute decimation"):
        _decimate_collision_surface_native(_closed_octahedron(), 4)


def test_native_decimation_passthrough_keeps_small_authoritative_mesh():
    surface = _closed_octahedron()
    result, stats = _decimate_collision_surface_native(surface, 8)
    assert result is surface
    assert stats["method"] == "passthrough"
    assert stats["faces"] == 8
