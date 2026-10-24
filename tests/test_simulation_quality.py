# Copyright (C) 2026 FreeCAD Cloth contributors
"""Verify material, tessellation, solver, and readiness contracts."""

from itertools import pairwise
from math import dist
from types import SimpleNamespace
from typing import Never, cast

import pytest
from tests.support.assertions import require

from freecad_cloth.pattern.PatternModel import PatternPiece
from freecad_cloth.simulation.ClothBackend import validate_pinned_stitch_pairs
from freecad_cloth.simulation.SimulationMeshQuality import quality_piece_mesh
from freecad_cloth.simulation.SimulationQuality import (
    QUALITY_PRESETS,
    FabricMaterial,
    normalize_color_rgb,
    preset,
    solver_parameters,
)
from freecad_cloth.simulation.SimulationQualityRuntime import (
    QualitySimulationProxy,
    quality_discretization,
)
from freecad_cloth.simulation.WorkflowReadinessGui import (
    WorkflowStep,
    build_workflow_checklist,
)


_EXPECTED_QUALITY_NAMES = ("Fast", "Balanced", "Final")
_EXPECTED_FINAL_PARTICLE_DISTANCE_MM = 2.0
_EXPECTED_FINAL_ITERATIONS = 16
_EXPECTED_FINAL_SUBSTEPS = 2
_EXPECTED_DENSITY_G_M2 = 150.0
_EXPECTED_THICKNESS_MM = 0.5
_EXPECTED_SPECULAR = 0.25
_EXPECTED_ROUGHNESS = 0.65
_EXPECTED_TRANSPARENCY = 0.0
_EXPECTED_BYTE_COLOR = (184 / 255.0, 87 / 255.0, 117 / 255.0)
_MINIMUM_EDGE_PARTICLES = 3
_EXPECTED_BOUNDARY_EDGE_COUNT = 4
_MINIMUM_REFINED_TRIANGLES = 100
_MINIMUM_BOUNDARY_CHAIN_POINTS = 2
_MAXIMUM_EDGE_SPAN_MM = 20.000001
_PROXY_SCHEMA_VERSION = 1
_COLOR_NORMALIZATION_MESSAGE = "Normalize supported color formats and reject invalid channels."
_BOUNDARY_CONTRACT_MESSAGE = "Preserve authored boundaries and require material tessellation."
_PINNED_STITCH_ERROR_PATTERN = (
    r"impossible pinned-pinned sewing constraint: seam=TunicRightShoulder "
    r"particle_a=0 particle_b=1 initial_separation=327\.943695000 mm"
)


def _quality_piece_object(piece: PatternPiece) -> SimpleNamespace:
    """Adapt an authored piece to the minimal mesh-builder document contract.

    Args:
        piece: Authored pattern piece whose identity and outline are preserved.

    Returns:
        A FreeCAD-like namespace exposing the outline, identifier, and placement.
    """
    return SimpleNamespace(
        SewingOutline=repr(piece.outline),
        DraftingBoundary=repr(piece.outline),
        PieceId=piece.id,
        Placement=None,
    )


def test_quality_presets_are_monotonic_and_distinct() -> None:
    """Keep presets ordered from fast/coarse to final/fine."""
    require(
        condition=(set(QUALITY_PRESETS) == set(_EXPECTED_QUALITY_NAMES)),
        message="Quality presets must remain distinct and ordered from coarse to fine.",
    )
    require(
        condition=(preset("Fast").particle_distance > preset("Balanced").particle_distance),
        message="Quality presets must remain distinct and ordered from coarse to fine.",
    )
    require(
        condition=(preset("Balanced").particle_distance > preset("Final").particle_distance),
        message="Quality presets must remain distinct and ordered from coarse to fine.",
    )
    require(
        condition=(preset("Fast").solver_iterations < preset("Final").solver_iterations),
        message="Quality presets must remain distinct and ordered from coarse to fine.",
    )


def test_material_defaults_and_solver_parameters() -> None:
    """Preserve default material measurements and the Final solver controls."""
    material = FabricMaterial()
    params = solver_parameters(preset("Final"), material)
    require(
        condition=(params["particle_distance"] == _EXPECTED_FINAL_PARTICLE_DISTANCE_MM),
        message="The Final preset and default fabric must retain canonical solver parameters.",
    )
    require(
        condition=(params["iterations"] == _EXPECTED_FINAL_ITERATIONS),
        message="The Final preset and default fabric must retain canonical solver parameters.",
    )
    require(
        condition=(params["substeps"] == _EXPECTED_FINAL_SUBSTEPS),
        message="The Final preset and default fabric must retain canonical solver parameters.",
    )
    require(
        condition=(params["density_g_m2"] == _EXPECTED_DENSITY_G_M2),
        message="The Final preset and default fabric must retain canonical solver parameters.",
    )
    require(
        condition=(params["thickness_mm"] == _EXPECTED_THICKNESS_MM),
        message="The Final preset and default fabric must retain canonical solver parameters.",
    )


def test_material_validation_rejects_invalid_values() -> None:
    """Reject material parameters outside supported physical ranges."""
    invalid = (
        (lambda: FabricMaterial(density_g_m2=0).validate(), "density must be positive"),
        (lambda: FabricMaterial(thickness_mm=0).validate(), "thickness must be positive"),
        (lambda: FabricMaterial(stretch=1.1).validate(), "stretch must be between"),
        (lambda: FabricMaterial(shear=-0.1).validate(), "shear must be between"),
        (lambda: FabricMaterial(bend=2).validate(), "bend must be between"),
        (lambda: FabricMaterial(friction=-1).validate(), "friction must be between"),
    )
    for construct, expected_message in invalid:
        with pytest.raises(ValueError, match=expected_message):
            construct()


def test_material_validation_rejects_nonfinite_density_and_thickness() -> None:
    """Reject non-finite density and thickness measurements."""
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="density must be positive and finite"):
            FabricMaterial(density_g_m2=value).validate()
        with pytest.raises(ValueError, match="thickness must be positive and finite"):
            FabricMaterial(thickness_mm=value).validate()


def test_material_presentation_defaults_and_validation() -> None:
    """Preserve presentation defaults and reject malformed display values."""
    material = FabricMaterial()
    require(
        condition=(material.color_rgb == (0.72, 0.34, 0.46)),
        message="Material presentation defaults must stay stable and malformed values must fail.",
    )
    require(
        condition=(material.specular == _EXPECTED_SPECULAR),
        message="Material presentation defaults must stay stable and malformed values must fail.",
    )
    require(
        condition=(material.roughness == _EXPECTED_ROUGHNESS),
        message="Material presentation defaults must stay stable and malformed values must fail.",
    )
    require(
        condition=(material.transparency == _EXPECTED_TRANSPARENCY),
        message="Material presentation defaults must stay stable and malformed values must fail.",
    )
    require(
        condition=(material.validate() is material),
        message="Material presentation defaults must stay stable and malformed values must fail.",
    )
    with pytest.raises(ValueError, match="at least three channels"):
        FabricMaterial(color_rgb=cast("tuple[float, float, float]", (1.0, 0.0))).validate()
    with pytest.raises(ValueError, match="roughness must be between"):
        FabricMaterial(roughness=1.1).validate()
    with pytest.raises(ValueError, match="transparency must be between"):
        FabricMaterial(transparency=101).validate()


def test_material_color_normalizes_freecad_property_color_shapes() -> None:
    """Normalize FreeCAD RGBA and byte-channel colors into RGB floats."""
    require(
        condition=(normalize_color_rgb((0.72, 0.34, 0.46, 0.0)) == (0.72, 0.34, 0.46)),
        message=_COLOR_NORMALIZATION_MESSAGE,
    )
    require(
        condition=(normalize_color_rgb((184, 87, 117, 255)) == _EXPECTED_BYTE_COLOR),
        message=_COLOR_NORMALIZATION_MESSAGE,
    )
    with pytest.raises(ValueError, match="color_rgb channels must be between"):
        normalize_color_rgb((300, 0, 0))


def test_unknown_quality_rejected() -> None:
    """Reject a quality name outside the supported preset set."""
    with pytest.raises(ValueError, match="unknown simulation quality preset"):
        preset("Ultra")


def test_quality_discretization_increases_with_smaller_particle_distance() -> None:
    """Refine the mesh when target particle distance decreases."""
    coarse = quality_discretization(4, 320.0, preset("Fast").particle_distance)
    fine = quality_discretization(4, 320.0, preset("Final").particle_distance)
    require(
        condition=(fine > coarse),
        message="Smaller particle distance must increase mesh discretization.",
    )


def test_pattern_mesh_density_changes_with_particle_distance() -> None:
    """Show that finer particle spacing generates more mesh points."""
    piece = PatternPiece("Test", [(0, 0), (100, 0), (100, 60), (0, 60)], id="test")
    piece_obj = _quality_piece_object(piece)
    coarse = quality_piece_mesh(piece_obj, 100.0, 20.0)
    fine = quality_piece_mesh(piece_obj, 100.0, 5.0)
    require(
        condition=(len(fine[0]) > len(coarse[0])),
        message="Finer particle spacing must produce more mesh vertices.",
    )


def test_quality_seam_edges_have_interior_particles() -> None:
    """Populate refined seam boundaries with interior edge particles."""
    piece = PatternPiece("Test", [(0, 0), (120, 0), (120, 60), (0, 60)], id="test")
    piece_obj = _quality_piece_object(piece)
    positions, _triangles, boundary = quality_piece_mesh(piece_obj, 100.0, 20.0)
    require(
        condition=(len(boundary) == _EXPECTED_BOUNDARY_EDGE_COUNT),
        message="Refined seam edges must contain interior particles within the spacing budget.",
    )
    require(
        condition=all(len(edge) >= _MINIMUM_EDGE_PARTICLES for edge in boundary),
        message="Refined seam edges must contain interior particles within the spacing budget.",
    )
    for edge in boundary:
        maximum_edge_span = max(
            dist(positions[first], positions[second]) for first, second in pairwise(edge)
        )
        require(
            condition=(maximum_edge_span <= _MAXIMUM_EDGE_SPAN_MM),
            message="Refined seam edges must contain interior particles within the spacing budget.",
        )


def test_refinement_preserves_authored_boundary_and_materially_tessellates() -> None:
    """Preserve authored edge endpoints while refining faces and vertices."""
    piece = PatternPiece("Test", [(0, 0), (100, 0), (100, 60), (0, 60)], id="test")
    piece_obj = _quality_piece_object(piece)
    positions, triangles, boundary = quality_piece_mesh(piece_obj, 100.0, 2.0)
    # Constrained Delaunay preserves the authored outline as semantic
    # boundary chains; refinement adds interior vertices and triangles.
    require(
        condition=(len(boundary) == len(piece.outline)),
        message=_BOUNDARY_CONTRACT_MESSAGE,
    )
    require(
        condition=(len(triangles) > _MINIMUM_REFINED_TRIANGLES),
        message=_BOUNDARY_CONTRACT_MESSAGE,
    )
    require(
        condition=(sum(len(chain) for chain in boundary) > len(piece.outline)),
        message=_BOUNDARY_CONTRACT_MESSAGE,
    )
    require(
        condition=(len(positions) > len(piece.outline)),
        message=_BOUNDARY_CONTRACT_MESSAGE,
    )
    for edge_index, chain in enumerate(boundary):
        expected_start = piece.outline[edge_index]
        expected_end = piece.outline[(edge_index + 1) % len(piece.outline)]
        require(
            condition=(len(chain) >= _MINIMUM_BOUNDARY_CHAIN_POINTS),
            message=_BOUNDARY_CONTRACT_MESSAGE,
        )
        require(
            condition=(positions[chain[0]][:2] == expected_start),
            message=_BOUNDARY_CONTRACT_MESSAGE,
        )
        require(
            condition=(positions[chain[-1]][:2] == expected_end),
            message=_BOUNDARY_CONTRACT_MESSAGE,
        )


def test_quality_proxy_keeps_solver_state_outside_serialized_object_dict() -> None:
    """Keep rebuildable solver state out of serialized proxy attributes."""
    proxy = QualitySimulationProxy()
    require(
        condition=(proxy.__getstate__() == {"schema": _PROXY_SCHEMA_VERSION}),
        message="Solver state must stay out of serialization and be reset after restore.",
    )
    require(
        condition=("_base" not in proxy.__dict__),
        message="Solver state must stay out of serialization and be reset after restore.",
    )
    require(
        condition=(proxy.last_steps == 0),
        message="Solver state must stay out of serialization and be reset after restore.",
    )
    proxy.onDocumentRestored(None)
    require(
        condition=(proxy.last_steps == 0),
        message="Solver state must stay out of serialization and be reset after restore.",
    )


def test_pinned_pinned_stitch_rejects_nonzero_initial_separation() -> None:
    """Reject a pinned stitch whose initial endpoints are far apart."""
    positions = ((0.0, 0.0, 0.0), (327.943695, 0.0, 0.0))
    records = (("TunicRightShoulder", "Front", "Back", ((0, 1),)),)
    with pytest.raises(ValueError, match=_PINNED_STITCH_ERROR_PATTERN):
        validate_pinned_stitch_pairs(positions, (0, 1), records)


def test_pinned_pinned_stitch_allows_numerical_zero() -> None:
    """Allow pinned stitch separation within numerical-zero tolerance."""
    positions = ((0.0, 0.0, 0.0), (1.0e-12, 0.0, 0.0))
    records = (("test-seam", "A", "B", ((0, 1),)),)
    validate_pinned_stitch_pairs(positions, (0, 1), records)


def _readiness_piece(name: str) -> SimpleNamespace:
    """Create a minimal PatternPiece-like object for readiness tests.

    Args:
        name: Stable fake document-object name.

    Returns:
        A namespace exposing the PatternPiece discriminator and name.
    """
    return SimpleNamespace(Name=name, PatternType="PatternPiece")


def _readiness_scene(
    pieces: tuple[object, ...] = (),
    extra_objects: tuple[object, ...] = (),
    *,
    fitting: object | None = None,
) -> SimpleNamespace:
    """Create a minimal simulation/document pair for readiness tests.

    Args:
        pieces: Pattern pieces assigned to the fake simulation.
        extra_objects: Other document objects, such as semantic seams.
        fitting: Optional persistent fitting-scene stand-in.

    Returns:
        A namespace exposing a simulation, its target and its document.
    """
    objects = (*pieces, *extra_objects)
    if fitting is not None:
        objects = (*objects, fitting)
    document = SimpleNamespace(Objects=objects)
    return SimpleNamespace(
        Document=document,
        ClothPieces=pieces,
        DrapeTarget=object(),
    )


def _readiness_target_status(
    _target: object | None,
    state: str = "ready",
) -> dict[str, object]:
    """Return a deterministic fake target status.

    Args:
        _target: Target reference, unused by this deterministic fixture.
        state: Status string to return.

    Returns:
        The target state and its user-facing message.
    """
    return {
        "state": state,
        "message": (
            "Drape target is current" if state == "ready" else "Drape target needs refresh"
        ),
    }


def _readiness_rows(
    scene: object | None,
    state: str = "ready",
) -> dict[str, WorkflowStep]:
    """Index checklist rows by their stable key.

    Args:
        scene: Simulation scene being checked, or None.
        state: Target state returned by the fake status provider.

    Returns:
        Checklist steps indexed by their stable key.
    """
    return {
        step.key: step
        for step in build_workflow_checklist(
            scene,
            target_status_fn=lambda target: _readiness_target_status(target, state),
        )
    }


def test_readiness_missing_scene_explains_first_steps_and_blocks_simulation() -> None:
    """A missing scene produces setup guidance and blocks simulation."""
    rows = {step.key: step for step in build_workflow_checklist(None)}
    require(
        condition=rows["patterns"].state == "next",
        message="A missing scene must direct users to setup and block simulation.",
    )
    require(
        condition=rows["target"].state == "blocked",
        message="A missing scene must direct users to setup and block simulation.",
    )
    require(
        condition=rows["simulation"].state == "blocked",
        message="A missing scene must direct users to setup and block simulation.",
    )
    require(
        condition="Cloth Pattern" in rows["patterns"].message,
        message="A missing scene must direct users to setup and block simulation.",
    )


def test_readiness_distinguishes_unassigned_document_pieces() -> None:
    """Existing but unassigned pieces receive a specific actionable message."""
    piece = _readiness_piece("Front")
    scene = _readiness_scene((), (piece,))
    rows = _readiness_rows(scene, "stale")
    require(
        condition=rows["patterns"].state == "next",
        message="Unassigned pieces must be distinguished and simulation must remain blocked.",
    )
    require(
        condition="exist in the document" in rows["patterns"].message,
        message="Unassigned pieces must be distinguished and simulation must remain blocked.",
    )
    require(
        condition=rows["target"].state == "blocked",
        message="Unassigned pieces must be distinguished and simulation must remain blocked.",
    )
    require(
        condition=rows["simulation"].state == "blocked",
        message="Unassigned pieces must be distinguished and simulation must remain blocked.",
    )


def test_readiness_unsewn_multi_piece_setup_is_reviewable() -> None:
    """Missing sewing prompts a review without hard-blocking diagnostic cases."""
    scene = _readiness_scene((_readiness_piece("Front"), _readiness_piece("Back")))
    rows = _readiness_rows(scene)
    require(
        condition=rows["patterns"].state == "ready",
        message="Unsewn multi-piece setup must remain reviewable without blocking simulation.",
    )
    require(
        condition=rows["sewing"].state == "review",
        message="Unsewn multi-piece setup must remain reviewable without blocking simulation.",
    )
    require(
        condition=rows["target"].state == "ready",
        message="Unsewn multi-piece setup must remain reviewable without blocking simulation.",
    )
    require(
        condition=rows["simulation"].state == "ready",
        message="Unsewn multi-piece setup must remain reviewable without blocking simulation.",
    )
    require(
        condition="unsewn tests remain valid" in rows["sewing"].message,
        message="Unsewn multi-piece setup must remain reviewable without blocking simulation.",
    )


def test_readiness_reports_fully_placed_sewn_garment() -> None:
    """Sewing relationships and saved placements report a ready arrangement."""
    front = _readiness_piece("Front")
    back = _readiness_piece("Back")
    seam = SimpleNamespace(
        SewingType="Seam",
        SeamId="seam-front-back",
        PieceA=front,
        PieceB=back,
    )
    fitting = SimpleNamespace(
        FittingType="FittingScene",
        PatternPieces=(front, back),
        PiecePlacements=(object(), object()),
    )
    rows = _readiness_rows(_readiness_scene((front, back), (seam,), fitting=fitting))
    require(
        condition=rows["sewing"].state == "ready",
        message="Sewn pieces with saved placements must report readiness.",
    )
    require(
        condition=rows["arrangement"].state == "ready",
        message="Sewn pieces with saved placements must report readiness.",
    )
    require(
        condition="2 saved placement(s)" in rows["arrangement"].message,
        message="Sewn pieces with saved placements must report readiness.",
    )


def test_readiness_target_inspection_failure_blocks_simulation() -> None:
    """Target-inspection failure never advertises simulation readiness."""

    def fail(_target: object | None) -> Never:
        """Simulate a target inspection error.

        Args:
            _target: Target reference, unused by this failing fixture.

        Raises:
            RuntimeError: Always, emulating a stale collision-cache inspection failure.
        """
        msg = "stale collision cache"
        raise RuntimeError(msg)

    rows = {
        step.key: step
        for step in build_workflow_checklist(
            _readiness_scene((_readiness_piece("Panel"),)),
            target_status_fn=fail,
        )
    }
    require(
        condition=rows["target"].state == "blocked",
        message="A target inspection error must block simulation and preserve its diagnostic.",
    )
    require(
        condition=rows["simulation"].state == "blocked",
        message="A target inspection error must block simulation and preserve its diagnostic.",
    )
    require(
        condition="stale collision cache" in rows["target"].message,
        message="A target inspection error must block simulation and preserve its diagnostic.",
    )
