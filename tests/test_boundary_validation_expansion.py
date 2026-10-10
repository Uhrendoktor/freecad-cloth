"""Regression tests for additional numerical and topology boundaries."""

import math
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from freecad_cloth.common.ValidationModels import (
    CollisionSurfaceInput,
    PBDStepInput,
    PatternPieceInput,
    SimulationMeshQualityInput,
    ParticleIndexInput,
    ParticlePairInput,
)
from freecad_cloth.common.FreeCADCollision import surface_from_freecad
from freecad_cloth.pattern.PatternModel import PatternPiece, Seam
from freecad_cloth.shared.collision import CollisionSurface, surface_from_triangles
from freecad_cloth.simulation.PositionBasedDynamicsBackend import (
    _pbd_collision_resolution,
    _pbd_collision_tolerance_mm,
    _pbd_collision_voxel_mm,
    _pbd_substeps,
)
from freecad_cloth.simulation.SimulationMeshQuality import quality_piece_mesh


def test_collision_surface_rejects_nonfinite_vertices_thickness_and_fractional_indices():
    with pytest.raises(ValidationError):
        CollisionSurfaceInput.model_validate(
            {"vertices": ((0, 0, 0), (1, 0, 0), (0, math.nan, 0)),
             "triangles": ((0, 1, 2),)}
        )
    with pytest.raises(ValidationError):
        CollisionSurface(
            ((0, 0, 0), (1, 0, 0), (0, 1, 0)),
            ((0, 1, 2),), thickness=math.inf,
        ).validate()
    with pytest.raises(ValidationError):
        surface_from_triangles(
            ((0, 0, 0), (1, 0, 0), (0, 1, 0)), ((0, 1.5, 2),)
        )
    with pytest.raises(ValidationError):
        surface_from_triangles(
            ((0, 0, 0), (1, 0, 0), (0, 1, 0)), ((0, True, 2),)
        )


def test_freecad_collision_adapter_does_not_truncate_fractional_face_indices():
    class Vertex:
        def __init__(self, x, y, z):
            self.x, self.y, self.z = x, y, z

    broken = SimpleNamespace(
        Mesh=SimpleNamespace(
            Topology=(
                (Vertex(0, 0, 0), Vertex(1, 0, 0), Vertex(0, 1, 0)),
                ((0, 1.5, 2),),
            )
        ),
        Label="bad mesh",
    )
    with pytest.raises((ValidationError, ValueError)):
        surface_from_freecad(broken)


@pytest.mark.parametrize("dt", [math.nan, math.inf, -math.inf, 0.0])
def test_pbd_step_schema_rejects_invalid_timestep(dt):
    with pytest.raises(ValidationError):
        PBDStepInput(dt=dt, iterations=8)


@pytest.mark.parametrize("iterations", [0, 1.5, True, math.inf])
def test_pbd_step_schema_requires_positive_strict_integer_iterations(iterations):
    with pytest.raises(ValidationError):
        PBDStepInput(dt=1 / 60, iterations=iterations)


def test_pbd_step_schema_rejects_nonfinite_gravity():
    with pytest.raises(ValidationError):
        PBDStepInput(dt=1 / 60, iterations=8, gravity=(0.0, math.nan, -9810.0))


def test_pbd_config_rejects_nonfinite_environment_settings(monkeypatch):
    monkeypatch.setenv("CLOTH_PBD_COLLISION_TOLERANCE_MM", "nan")
    with pytest.raises(ValidationError):
        _pbd_collision_tolerance_mm()
    monkeypatch.setenv("CLOTH_PBD_COLLISION_TOLERANCE_MM", "1.0")
    monkeypatch.setenv("CLOTH_PBD_COLLISION_VOXEL_MM", "inf")
    with pytest.raises(ValidationError):
        _pbd_collision_voxel_mm()
    monkeypatch.setenv("CLOTH_PBD_COLLISION_VOXEL_MM", "12")
    monkeypatch.setenv("CLOTH_PBD_SUBSTEPS", "0")
    with pytest.raises(ValidationError):
        _pbd_substeps()


@pytest.mark.parametrize("index", [1.5, True, -1, "1"])
def test_solver_index_schemas_reject_coercion(index):
    with pytest.raises(ValidationError):
        ParticleIndexInput.model_validate({"index": index})
    with pytest.raises(ValidationError):
        ParticlePairInput.model_validate({"a": 0, "b": index})


def test_pattern_piece_and_ir_schemas_reject_nonfinite_geometry():
    with pytest.raises(ValidationError):
        PatternPieceInput.model_validate(
            {"name": "piece", "id": "piece",
             "outline": ((0, 0), (1, math.inf), (0, 1))}
        )
    with pytest.raises(ValueError):
        PatternPiece("piece", [(0, 0), (1, math.nan), (0, 1)], id="piece").validate()


def test_pattern_seam_rejects_unsupported_edge_reference_type():
    seam = Seam("front", 1.5, "back", 0, id="seam")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="edge references"):
        seam.validate()




def test_drape_target_and_quality_mesh_settings_reject_nonfinite_values():
    with pytest.raises(ValidationError):
        SimulationMeshQualityInput(start_height=math.nan, particle_distance=5.0)
    with pytest.raises(ValidationError):
        SimulationMeshQualityInput(start_height=0.0, particle_distance=math.inf)
    with pytest.raises(ValidationError):
        quality_piece_mesh(SimpleNamespace(), math.nan, 5.0)


def test_collision_sdf_resolution_follows_pbd_coordinate_axis_order(monkeypatch):
    # PBD coordinates swap FreeCAD Y/Z, so a tall FreeCAD Z axis must receive
    # the large grid dimension after it becomes PBD Y.
    monkeypatch.setenv("CLOTH_PBD_COLLISION_VOXEL_MM", "8")
    surface = CollisionSurface(
        vertices=(
            (0.0, 0.0, 0.0),
            (100.0, 0.0, 0.0),
            (100.0, 200.0, 0.0),
            (0.0, 200.0, 0.0),
            (0.0, 0.0, 1000.0),
            (100.0, 0.0, 1000.0),
            (100.0, 200.0, 1000.0),
            (0.0, 200.0, 1000.0),
        ),
        triangles=((0, 1, 2),),
    )

    # ceil((span + 200 mm) / 8 mm), ordered as PBD X, Z, Y.
    assert _pbd_collision_resolution(surface) == [38, 150, 50]

