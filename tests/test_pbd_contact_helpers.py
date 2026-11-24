# Copyright (C) 2026 FreeCAD Cloth contributors
"""Tests for the import-safe shared PBD diagnostic helpers."""

from types import ModuleType, SimpleNamespace
from typing import TYPE_CHECKING, Never, NoReturn, cast

import numpy as np
import pytest

from freecad_cloth.shared.Collision import CollisionSurface
from freecad_cloth.simulation.InterClothContact import (
    InterClothContactMetrics,
    _candidate_edge_triangle_pairs,
    _closest_segment_triangle,
    _closest_segment_triangles_batch,
    _surface_index,
    measure_inter_cloth_contacts,
    measure_inter_cloth_contacts_with_constraints,
    project_inter_cloth_contacts,
    project_measured_inter_cloth_contacts,
)
from freecad_cloth.simulation.PositionBasedDynamicsBackend import (
    PositionBasedDynamicsBackend,
    _pbd_stitch_stiffness,
    pbd_collision_resolution,
)
from freecad_cloth.simulation.SimulationObjects import (
    _resolve_garment_body_clearance_by_particle,
    _resolve_inter_cloth_groups,
)
from tests.support.pbd_contact_helpers import (
    LADDER_STITCH_SAMPLES,
    append_optional_ladder_piece,
    configure_ladder_scene,
    events,
    nearest_surface_distance,
    position_bounds,
)

PBD_COLLISION_AXIS_COUNT = 3
PBD_COLLISION_MIN_CELLS = 16
PBD_COLLISION_MAX_CELLS = 256

if TYPE_CHECKING:
    from tests.support.pbd_contact_helpers import _EventApplication


def test_surface_distance_fallback_uses_spatial_index() -> None:
    """Missing exact point-to-triangle queries must not fall back to a quadratic Python loop."""

    def unavailable(*_args: Never, **_kwargs: Never) -> NoReturn:
        """Simulate an unavailable query so spatial-index fallback behavior is tested.

        Args:
            _args: Positional query arguments, intentionally ignored.
            _kwargs: Keyword query options, intentionally ignored.

        Raises:
            RuntimeError: Always, to force the spatial-index fallback path.
        """
        msg = "surface query backend unavailable"
        raise RuntimeError(msg)

    vertices = tuple((float(index), 0.0, 0.0) for index in range(5000))
    garment_points = tuple((float(index), 0.0, 5.0) for index in range(5000))
    surface = SimpleNamespace(vertices=vertices, triangles=((0, 1, 2),))
    actual_distance = nearest_surface_distance(
        garment_points, surface, surface_clearance_fn=unavailable
    )

    assert actual_distance == pytest.approx(5.0), (
        "the spatial-index fallback should find the five-millimetre separation"
    )


def test_events_processes_qt_events_after_one_gui_refresh() -> None:
    """Avoid a second synchronous FreeCAD refresh during each simulation checkpoint."""
    calls: list[str] = []
    gui = ModuleType("FreeCADGui")
    gui.__dict__["updateGui"] = lambda: calls.append("gui-update")
    application = cast(
        "_EventApplication",
        SimpleNamespace(processEvents=lambda: calls.append("qt-events")),
    )

    events(gui=gui, application=application)

    assert calls == ["gui-update", "qt-events"], (
        "GUI refresh must precede Qt event processing exactly once"
    )


def test_zero_stitch_compliance_selects_the_native_hard_xpbd_path() -> None:
    """Zero compliance must use pyPBD's alpha-zero hard-constraint branch."""
    assert _pbd_stitch_stiffness(0.0) == 0.0
    assert _pbd_stitch_stiffness(0.01) == pytest.approx(100.0)
    assert _pbd_stitch_stiffness(1e-8) == 100000.0
    with pytest.raises(ValueError, match="compliance must be finite and non-negative"):
        _pbd_stitch_stiffness(-1.0)


def test_pbd_collision_resolution_uses_axis_spans_and_handles_empty_surfaces() -> None:
    """Preserve bounded per-axis grid sizing while calculating spans in NumPy."""
    surface = CollisionSurface(
        vertices=((-10.0, 1.0, 2.0), (10.0, 51.0, 4.0), (0.0, 20.0, 3.0)),
        triangles=((0, 1, 2),),
    )
    resolution = pbd_collision_resolution(surface)
    assert len(resolution) == PBD_COLLISION_AXIS_COUNT and all(
        PBD_COLLISION_MIN_CELLS <= cells <= PBD_COLLISION_MAX_CELLS for cells in resolution
    ), "collision-grid resolution must remain bounded on each axis."
    assert resolution[1] >= resolution[0] >= resolution[2], (
        "larger coordinate spans must not receive smaller grid resolutions."
    )
    empty_resolution = pbd_collision_resolution(CollisionSurface(vertices=(), triangles=()))
    assert empty_resolution == [PBD_COLLISION_MIN_CELLS] * PBD_COLLISION_AXIS_COUNT, (
        "empty collision surfaces must retain the minimum grid resolution."
    )


def test_ladder_scene_helpers_add_only_requested_pieces_and_keep_scene_state_coherent() -> None:
    """Configure common cloth state and add a second panel only for two-piece cases."""
    left = SimpleNamespace()
    right = SimpleNamespace()
    pieces = [left]
    seams: list[tuple[SimpleNamespace, SimpleNamespace]] = []
    append_optional_ladder_piece(
        spec={"piece_count": 2, "seam_mode": "large"},
        pieces=pieces,
        create_right_piece=lambda: right,
        add_seam=lambda first, second: seams.append((first, second)),
    )
    scene = SimpleNamespace()
    configure_ladder_scene(scene, pieces, {"pin_mode": "hem"})
    assert pieces == [left, right] and seams == [(left, right)], (
        "the shared ladder helper must add a right panel and seam only as requested"
    )
    assert (
        scene.ClothPieces is pieces
        and scene.SeamSelection == []
        and scene.PinMode == "hem"
        and scene.PinSelection == []
        and scene.StitchSamples == LADDER_STITCH_SAMPLES
        and scene.Steps == 0
    ), "the shared ladder helper must initialize common scene controls consistently"


def test_position_bounds_uses_vectorized_axis_reductions() -> None:
    """Compute all six particle bounds from one coordinate array."""
    actual = position_bounds(((-2.0, 1.0, 5.0), (4.0, -3.0, 9.0)))
    assert actual == {
        "x_min": -2.0,
        "x_max": 4.0,
        "y_min": -3.0,
        "y_max": 1.0,
        "z_min": 5.0,
        "z_max": 9.0,
    }, "axis bounds must match the full particle coordinate set"
    with pytest.raises(ValueError, match="empty PBD position set"):
        position_bounds(())


def _parallel_cloth_groups(
    offset_mm: float = 0.25,
) -> tuple[tuple[tuple[float, float, float], ...], dict[str, tuple[tuple[int, int, int], ...]]]:
    """Create two independent, identically triangulated square cloth surfaces."""
    positions = (
        (0.0, 0.0, 0.0),
        (10.0, 0.0, 0.0),
        (10.0, 10.0, 0.0),
        (0.0, 10.0, 0.0),
        (0.0, 0.0, offset_mm),
        (10.0, 0.0, offset_mm),
        (10.0, 10.0, offset_mm),
        (0.0, 10.0, offset_mm),
    )
    triangles = ((0, 1, 2), (0, 2, 3))
    return positions, {
        "shirt": triangles,
        "skirt": tuple(tuple(index + 4 for index in triangle) for triangle in triangles),
    }


def test_vectorized_inter_cloth_narrow_phase_matches_scalar_reference() -> None:
    """Batch closest geometry must match the scalar segment/triangle definition."""
    random = np.random.default_rng(20261117)
    triangles = random.normal(size=(48, 3, 3)) * 20.0
    starts = random.normal(size=(48, 3)) * 20.0
    ends = random.normal(size=(48, 3)) * 20.0
    triangles[:3] = np.asarray(
        (
            ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 10.0, 0.0)),
            ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 10.0, 0.0)),
            ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 10.0, 0.0)),
        ),
        dtype=np.float64,
    )
    starts[:3] = np.asarray(
        (
            (2.0, 2.0, -5.0),
            (2.0, 2.0, 2.0),
            (-2.0, 5.0, 0.0),
        ),
        dtype=np.float64,
    )
    ends[:3] = np.asarray(
        (
            (2.0, 2.0, 5.0),
            (8.0, 2.0, 2.0),
            (-2.0, 8.0, 0.0),
        ),
        dtype=np.float64,
    )

    actual = _closest_segment_triangles_batch(starts, ends, triangles)
    expected = [
        _closest_segment_triangle(starts[index], ends[index], triangles[index])
        for index in range(len(starts))
    ]
    expected_distance_squared = np.asarray(
        [
            np.dot(edge_point - face_point, edge_point - face_point)
            for edge_point, face_point, _factor, _weights, _normal in expected
        ],
        dtype=np.float64,
    )

    for actual_values, expected_values in zip(
        actual[:5],
        (
            np.asarray([item[0] for item in expected]),
            np.asarray([item[1] for item in expected]),
            np.asarray([item[2] for item in expected]),
            np.asarray([item[3] for item in expected]),
            np.asarray([item[4] for item in expected]),
        ),
        strict=True,
    ):
        np.testing.assert_allclose(actual_values, expected_values, rtol=1e-10, atol=1e-10)
    np.testing.assert_allclose(
        actual[5],
        expected_distance_squared,
        rtol=1e-10,
        atol=1e-10,
    )


def test_garment_body_clearances_resolve_to_the_exact_particle_order() -> None:
    """Per-garment standoffs must cover every particle exactly once."""
    scene = SimpleNamespace(GarmentBodyClearanceByGroup=("shirt|14.0", "skirt|6.0"))
    groups = {
        "shirt": ((0, 1, 2), (2, 3, 0)),
        "skirt": ((4, 5, 6), (6, 7, 4)),
    }

    actual = _resolve_garment_body_clearance_by_particle(scene, groups, 8)

    assert actual == (14.0, 14.0, 14.0, 14.0, 6.0, 6.0, 6.0, 6.0)


def test_garment_body_clearances_require_exact_group_coverage() -> None:
    """Reject missing or extra garment standoffs instead of silently using defaults."""
    groups = {"shirt": ((0, 1, 2),), "skirt": ((3, 4, 5),)}

    with pytest.raises(ValueError, match="classify every garment group"):
        _resolve_garment_body_clearance_by_particle(
            SimpleNamespace(GarmentBodyClearanceByGroup=("shirt|6.0",)),
            groups,
            6,
        )


def test_garment_body_clearances_reject_duplicate_and_invalid_values() -> None:
    """Garment standoff values must be unique, finite positive millimetres."""
    groups = {"shirt": ((0, 1, 2),), "skirt": ((3, 4, 5),)}
    with pytest.raises(ValueError, match="duplicate mannequin body clearance"):
        _resolve_garment_body_clearance_by_particle(
            SimpleNamespace(GarmentBodyClearanceByGroup=("shirt|6.0", "shirt|7.0", "skirt|14.0")),
            groups,
            6,
        )
    with pytest.raises(ValueError, match="positive and finite"):
        _resolve_garment_body_clearance_by_particle(
            SimpleNamespace(GarmentBodyClearanceByGroup=("shirt|6.0", "skirt|nan")),
            groups,
            6,
        )


def test_inter_cloth_aabb_broad_phase_keeps_every_exact_near_contact() -> None:
    """Expanded edge/triangle AABBs must retain every pair within clearance."""
    positions, groups = _parallel_cloth_groups(offset_mm=0.25)
    source = _surface_index(np.asarray(positions, dtype=np.float64), np.asarray(groups["shirt"]))
    target = _surface_index(np.asarray(positions, dtype=np.float64), np.asarray(groups["skirt"]))
    edge_indices, triangle_indices, _raw_count, _query_s, _filter_s = (
        _candidate_edge_triangle_pairs(source, target, 1.0)
    )
    retained = set(zip(edge_indices.tolist(), triangle_indices.tolist(), strict=True))
    points = np.asarray(positions, dtype=np.float64)
    for edge_index, edge in enumerate(source.edges):
        for triangle_index, triangle_ids in enumerate(target.triangles):
            closest = _closest_segment_triangle(
                points[int(edge[0])],
                points[int(edge[1])],
                points[triangle_ids],
            )
            edge_point, face_point = closest[0], closest[1]
            distance = float(np.linalg.norm(edge_point - face_point))
            if distance <= 1.0 + 1e-10:
                assert (edge_index, triangle_index) in retained, (
                    "AABB broad phase dropped an edge/triangle pair within clearance"
                )


def test_inter_cloth_projection_separates_parallel_independent_surfaces() -> None:
    """Two garment groups must separate by the requested clearance, not by sewing."""
    positions, groups = _parallel_cloth_groups()
    corrected, directions, metrics = project_inter_cloth_contacts(
        positions,
        groups,
        (1.0,) * len(positions),
        clearance_mm=1.0,
        iterations=16,
    )

    assert metrics.contact_count > 0
    assert metrics.corrected_particle_count == len(positions)
    assert metrics.remaining_contact_count == 0
    assert metrics.max_penetration_after_mm <= 1e-7
    assert all(abs(float(value[2])) > 0.0 for value in directions)
    assert all(corrected[index][2] < 0.0 for index in range(4))
    assert all(corrected[index][2] > 0.25 for index in range(4, 8))


def test_inter_cloth_projection_uses_one_nearest_contact_per_source_edge() -> None:
    """Duplicate target faces must not multiply one edge's correction weight."""
    positions, groups = _parallel_cloth_groups(offset_mm=0.25)
    duplicated_groups = {
        "shirt": groups["shirt"],
        "skirt": groups["skirt"] * 8,
    }
    corrected, _directions, metrics = project_inter_cloth_contacts(
        positions,
        duplicated_groups,
        (1.0,) * len(positions),
        clearance_mm=1.0,
        iterations=8,
    )

    assert metrics.contact_count <= 10
    assert metrics.corrected_particle_count > 0
    assert metrics.remaining_contact_count == 0
    assert metrics.max_penetration_after_mm <= 1e-7
    assert not np.allclose(corrected, np.asarray(positions))


def test_inter_cloth_projection_separates_exactly_coincident_parallel_groups() -> None:
    """Coincident sheets need deterministic opposite corrections when centroids overlap."""
    positions, groups = _parallel_cloth_groups(offset_mm=0.0)
    corrected, directions, metrics = project_inter_cloth_contacts(
        positions,
        groups,
        (1.0,) * len(positions),
        clearance_mm=1.0,
        iterations=16,
    )

    assert metrics.contact_count > 0
    assert metrics.corrected_particle_count == len(positions)
    assert metrics.remaining_contact_count == 0
    assert metrics.max_penetration_after_mm <= 1e-7
    assert all(corrected[index][2] > 0.0 for index in range(4))
    assert all(corrected[index][2] < 0.0 for index in range(4, 8))
    assert all(abs(float(value[2])) > 0.0 for value in directions)


def test_inter_cloth_projection_preserves_pins_and_leaves_separated_surfaces_alone() -> None:
    """Pinned garment particles stay fixed and non-contacting layers are unchanged."""
    positions, groups = _parallel_cloth_groups(offset_mm=0.25)
    pinned, _directions, _metrics = project_inter_cloth_contacts(
        positions,
        groups,
        (0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0),
        clearance_mm=1.0,
        iterations=4,
    )
    np.testing.assert_allclose(pinned[:4], positions[:4])
    assert np.any(np.asarray(pinned[4:]) != np.asarray(positions[4:]))

    separated_positions, separated_groups = _parallel_cloth_groups(offset_mm=20.0)
    untouched, _directions, separated_metrics = project_inter_cloth_contacts(
        separated_positions,
        separated_groups,
        (1.0,) * len(separated_positions),
        clearance_mm=1.0,
    )
    np.testing.assert_allclose(untouched, separated_positions)
    assert separated_metrics.contact_count == 0
    assert separated_metrics.corrected_particle_count == 0


def test_inter_cloth_edge_triangle_query_detects_an_edge_piercing_a_face() -> None:
    """Exact segment/triangle closest points detect an interior face crossing."""
    positions = (
        (-10.0, -10.0, 0.0),
        (10.0, -10.0, 0.0),
        (0.0, 10.0, 0.0),
        (0.0, -10.0, -10.0),
        (0.0, 10.0, -10.0),
        (0.0, 0.0, 10.0),
    )
    corrected, _directions, metrics = project_inter_cloth_contacts(
        positions,
        {
            "horizontal": ((0, 1, 2),),
            "vertical": ((3, 4, 5),),
        },
        (1.0,) * len(positions),
        clearance_mm=1.0,
        iterations=4,
    )

    assert metrics.contact_count > 0, "crossing edge/face contacts must be observed"
    assert not np.allclose(corrected, np.asarray(positions)), (
        "the detected surface crossing must change solver particles"
    )


def test_inter_cloth_projection_rejects_shared_particles_and_invalid_clearance() -> None:
    """Independent garments cannot alias solver particles or request invalid clearance."""
    positions, groups = _parallel_cloth_groups()
    shared = {
        "outer": ((0, 1, 2),),
        "inner": ((0, 2, 3),),
    }
    with pytest.raises(ValueError, match="must not share solver particles"):
        project_inter_cloth_contacts(
            positions,
            shared,
            (1.0,) * len(positions),
            clearance_mm=1.0,
        )
    with pytest.raises(ValueError, match="positive and finite"):
        project_inter_cloth_contacts(
            positions,
            groups,
            (1.0,) * len(positions),
            clearance_mm=0.0,
        )


def test_simulation_scene_resolves_several_panels_into_two_garment_groups() -> None:
    """Combine sewn panel triangles under stable garment IDs without joining groups."""
    panel_data = {
        "shirt-front": {"triangles": ((0, 1, 2), (0, 2, 3))},
        "shirt-back": {"triangles": ((4, 5, 6), (4, 6, 7))},
        "skirt-front": {"triangles": ((8, 9, 10), (8, 10, 11))},
        "skirt-back": {"triangles": ((12, 13, 14), (12, 14, 15))},
    }
    scene = SimpleNamespace(
        GarmentGroups=(
            "shirt|shirt-front",
            "shirt|shirt-back",
            "skirt|skirt-front",
            "skirt|skirt-back",
        ),
        InterClothClearance=1.0,
    )

    actual = _resolve_inter_cloth_groups(scene, panel_data)

    assert actual == {
        "shirt": ((0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7)),
        "skirt": ((8, 9, 10), (8, 10, 11), (12, 13, 14), (12, 14, 15)),
    }, "each garment group must combine panels while retaining global solver indices"


def test_simulation_scene_rejects_incomplete_or_duplicate_garment_group_assignments() -> None:
    """Every current simulated panel must belong to one and only one garment."""
    panel_data = {
        "shirt-front": {"triangles": ((0, 1, 2),)},
        "skirt-front": {"triangles": ((3, 4, 5),)},
    }

    with pytest.raises(ValueError, match="classify every simulated piece"):
        _resolve_inter_cloth_groups(
            SimpleNamespace(GarmentGroups=("shirt|shirt-front",)),
            panel_data,
        )
    with pytest.raises(ValueError, match="more than one garment group"):
        _resolve_inter_cloth_groups(
            SimpleNamespace(
                GarmentGroups=(
                    "shirt|shirt-front",
                    "skirt|shirt-front",
                    "skirt|skirt-front",
                )
            ),
            panel_data,
        )


def test_inter_cloth_projection_rejects_stitches_between_independent_garments() -> None:
    """A contact configuration must never sew two separate garment groups together."""
    positions, groups = _parallel_cloth_groups()
    with pytest.raises(ValueError, match="cannot connect independent garment groups"):
        project_inter_cloth_contacts(
            positions,
            groups,
            (1.0,) * len(positions),
            clearance_mm=1.0,
            stitches=((0, 4),),
        )


def test_inter_cloth_measurement_reports_post_projection_clearance_deficit() -> None:
    """A later body projection that closes the fabric gap must be observable."""
    positions, groups = _parallel_cloth_groups(offset_mm=0.25)
    corrected, _directions, _metrics = project_inter_cloth_contacts(
        positions,
        groups,
        (1.0,) * len(positions),
        clearance_mm=1.0,
        iterations=16,
    )
    residual_count, residual_deficit = measure_inter_cloth_contacts(
        corrected,
        groups,
        clearance_mm=1.0,
    )
    assert residual_count == 0
    assert residual_deficit == 0.0

    moved_back = np.asarray(corrected).copy()
    moved_back[4:, 2] -= 2.0
    residual_count, residual_deficit = measure_inter_cloth_contacts(
        moved_back,
        groups,
        clearance_mm=1.0,
    )
    assert residual_count > 0
    assert residual_deficit > 0.5


def test_measured_inter_cloth_constraints_repair_only_residual_pairs() -> None:
    """Exact residual edge/triangle pairs can be corrected without rebuilding broad phase."""
    positions, groups = _parallel_cloth_groups(offset_mm=0.25)
    residual_count, residual_deficit, constraints = measure_inter_cloth_contacts_with_constraints(
        positions,
        groups,
        clearance_mm=1.0,
    )

    assert residual_count > 0
    assert residual_deficit > 0.5
    assert len(constraints) == residual_count, (
        "the measurement must retain every exact edge/triangle pair it counted"
    )

    corrected, _directions, metrics = project_measured_inter_cloth_contacts(
        positions,
        (1.0,) * len(positions),
        constraints,
        clearance_mm=1.0,
        relaxation=1.0,
    )
    remaining_count, remaining_deficit = measure_inter_cloth_contacts(
        corrected,
        groups,
        clearance_mm=1.0,
    )
    assert metrics.contact_count > 0
    assert metrics.corrected_particle_count > 0
    assert remaining_count == 0
    assert remaining_deficit == 0.0


def test_measured_inter_cloth_projection_preserves_pinned_particles() -> None:
    """Targeted residual-pair repair must not move a fixed garment particle."""
    positions, groups = _parallel_cloth_groups(offset_mm=0.25)
    _count, _deficit, constraints = measure_inter_cloth_contacts_with_constraints(
        positions,
        groups,
        clearance_mm=1.0,
    )
    masses = np.ones(len(positions), dtype=np.float64)
    masses[0] = 0.0

    corrected, _directions, _metrics = project_measured_inter_cloth_contacts(
        positions,
        masses,
        constraints,
        clearance_mm=1.0,
        relaxation=1.0,
    )

    assert np.array_equal(corrected[0], np.asarray(positions[0])), (
        "targeted cloth contact repair must preserve pinned particles exactly"
    )


def _install_inter_cloth_body_reconciliation_mocks(
    monkeypatch: pytest.MonkeyPatch,
    backend: PositionBasedDynamicsBackend,
    *,
    residual_measurements: tuple[tuple[int, float], ...],
    projected_metrics: InterClothContactMetrics,
    projected_residual: bool,
    track_measurement_calls: bool = False,
) -> dict[str, int]:
    """Install deterministic body/cloth projection doubles for reconciliation tests."""
    calls = {"project": 0, "body": 0}
    if track_measurement_calls:
        calls["measure"] = 0
    measurements = iter(residual_measurements)

    def measure_residual() -> None:
        if track_measurement_calls:
            calls["measure"] += 1
        remaining, deficit = next(measurements)
        backend._inter_cloth_residual_constraints = (object(),) if remaining else ()
        metrics = backend._inter_cloth_metrics
        backend._inter_cloth_metrics = metrics._replace(
            remaining_contact_count=remaining,
            max_penetration_after_mm=deficit,
        )

    def project_full_broad_phase(
        *, iterations: int, measure_residual: bool
    ) -> InterClothContactMetrics:
        calls["project"] += 1
        assert iterations == 8
        assert not measure_residual
        backend._inter_cloth_residual_constraints = (object(),) if projected_residual else ()
        backend._inter_cloth_metrics = projected_metrics
        return backend._inter_cloth_metrics

    def project_body(*, stage: str = "unspecified") -> None:
        _ = stage
        calls["body"] += 1

    monkeypatch.setattr(backend, "_measure_inter_cloth_residual", measure_residual)
    monkeypatch.setattr(backend, "_project_inter_cloth_positions", project_full_broad_phase)
    monkeypatch.setattr(backend, "_project_collision_positions", project_body)
    return calls


def test_backend_reconciles_cloth_contacts_reintroduced_by_body_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only measured residual contacts trigger one fresh cloth/body correction."""
    backend = object.__new__(PositionBasedDynamicsBackend)
    backend._inter_cloth_metrics = InterClothContactMetrics(100, 50, 12, 7.1, 0.71)
    backend._inter_cloth_residual_constraints = ()
    calls = _install_inter_cloth_body_reconciliation_mocks(
        monkeypatch,
        backend,
        residual_measurements=((12, 0.71), (0, 0.0)),
        projected_metrics=InterClothContactMetrics(10, 8, 0, 0.71, 0.0),
        projected_residual=False,
        track_measurement_calls=True,
    )

    backend._resolve_inter_cloth_body_contacts()

    assert calls == {"project": 1, "body": 1, "measure": 2}, (
        "a post-body residual must trigger one fresh bounded broad-phase correction"
    )
    assert backend._inter_cloth_metrics == InterClothContactMetrics(110, 58, 0, 7.1, 0.0), (
        "final metrics must retain initial and corrective contact activity and report "
        "the post-body residual"
    )


def test_backend_bounds_inter_cloth_body_reconciliation_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Never loop indefinitely when body and garment constraints remain coupled."""
    backend = object.__new__(PositionBasedDynamicsBackend)
    backend._inter_cloth_metrics = InterClothContactMetrics(10, 5, 3, 1.0, 0.2)
    backend._inter_cloth_residual_constraints = ()
    calls = _install_inter_cloth_body_reconciliation_mocks(
        monkeypatch,
        backend,
        residual_measurements=((3, 0.2), (2, 0.1), (1, 0.05)),
        projected_metrics=InterClothContactMetrics(1, 1, 0, 0.2, 0.0),
        projected_residual=True,
    )

    backend._resolve_inter_cloth_body_contacts()

    assert calls == {"project": 2, "body": 2}, (
        "coupled contact correction must stop after the configured bounded retry count"
    )
    assert backend._inter_cloth_metrics.remaining_contact_count == 1, (
        "an unresolved residual must remain visible instead of being reported as clear"
    )


def test_inter_cloth_coincident_sheets_receive_opposite_stable_corrections() -> None:
    """Exact overlap uses group ordering to avoid cancelling zero-distance normals."""
    triangle = (
        (0.0, 0.0, 0.0),
        (10.0, 0.0, 0.0),
        (0.0, 10.0, 0.0),
    )
    positions = triangle + triangle
    corrected, _directions, metrics = project_inter_cloth_contacts(
        positions,
        {"alpha": ((0, 1, 2),), "beta": ((3, 4, 5),)},
        (1.0,) * 6,
        clearance_mm=1.0,
        iterations=8,
    )

    assert metrics.contact_count > 0
    assert metrics.corrected_particle_count == 6
    assert all(corrected[index][2] > 0.0 for index in range(3))
    assert all(corrected[index][2] < 0.0 for index in range(3, 6))
