# Copyright (C) 2026 FreeCAD Cloth contributors
"""Strict source contracts for the canonical tunic simulation audit."""

from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, cast

from freecad_cloth.shared.Collision import CollisionSurface

if TYPE_CHECKING:
    from collections.abc import Callable

    from freecad_cloth.simulation.PositionBasedDynamicsBackend import PositionBasedDynamicsBackend
    from freecad_cloth.simulation.SimulationObjects import SimulationProxy

ROOT = Path(__file__).resolve().parents[1]
_EXPECTED_TRIMESH_OVERRIDE_COUNT = 2
_SIMULATION_SCENE_MODULE = "freecad_cloth.simulation.SimulationCommands"
_SIMULATION_SCENE_NAME = "create_quality_simulation_scene"
_SIMULATION_SCENE_IMPORT = f"from {_SIMULATION_SCENE_MODULE} import {_SIMULATION_SCENE_NAME}"
_NECKLINE_RESOLUTION_PREFIX = "tunic-neckline-resolution piece=%s edge=%s"
_NECKLINE_RESOLUTION_SUFFIX = "method=%s chains=%d endpoint-error-mm=%.6f"
_NECKLINE_RESOLUTION_FRAGMENT = f"{_NECKLINE_RESOLUTION_PREFIX} {_NECKLINE_RESOLUTION_SUFFIX}"


def _require_source_contract(
    *,
    source: str,
    required: tuple[str, ...],
    forbidden: tuple[str, ...],
    contract: str,
) -> None:
    """Check required and forbidden literal fragments in source text.

    Args:
        source: Source text to inspect.
        required: Literal fragments that must remain present.
        forbidden: Literal fragments that must remain absent.
        contract: Label included in a source-contract failure message.
    """
    missing = tuple(fragment for fragment in required if fragment not in source)
    present = tuple(fragment for fragment in forbidden if fragment in source)
    assert not missing and not present, (
        f"{contract} source contract changed; missing={missing!r}; forbidden={present!r}"
    )


# The native-Sketcher fixture keeps explicit semantic edge IDs on each piece.
# The front/back pieces share the same authored topology, so corresponding shoulder
# and side edges must be paired by semantic position, not cross-paired.


def test_canonical_tunic_pairs_matching_front_back_semantic_edges() -> None:
    """Verify canonical tunic pairs matching front back semantic edges contract."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "front_edge_ids = tuple(" in source, (
        'Contract failed: "front_edge_ids = tuple(" in source'
    )
    assert "back_edge_ids = tuple(" in source, 'Contract failed: "back_edge_ids = tuple(" in source'
    assert '"SemanticEdgeIds"' in source, "Contract failed: '\"SemanticEdgeIds\"' in source"
    assert 'front_edge_ids[1], back_edge_ids[1], "TunicRightSide"' in source, (
        "Contract failed: 'front_edge_ids[1], back_edge_ids[1], \"..."
    )
    assert 'front_edge_ids[3], back_edge_ids[3], "TunicRightShoulder"' in source, (
        "Contract failed: 'front_edge_ids[3], back_edge_ids[3], \"..."
    )
    assert 'front_edge_ids[5], back_edge_ids[5], "TunicLeftShoulder"' in source, (
        "Contract failed: 'front_edge_ids[5], back_edge_ids[5], \"..."
    )
    assert 'front_edge_ids[7], back_edge_ids[7], "TunicLeftSide"' in source, (
        "Contract failed: 'front_edge_ids[7], back_edge_ids[7], \"..."
    )


def test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline() -> None:
    """Verify tunic fixture uses arrangement points and unpinned neckline contract."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "ArrangementPoint.from_string" in source, (
        'Contract failed: "ArrangementPoint.from_string" in source'
    )
    assert 'shoulder_left = arrangement_world("shoulder_left")' in source, (
        "Contract failed: 'shoulder_left = arrangement_world(\"sho..."
    )
    assert 'shoulder_right = arrangement_world("shoulder_right")' in source, (
        "Contract failed: 'shoulder_right = arrangement_world(\"sh..."
    )
    assert 'hip_point = arrangement_world("hip")' in source, (
        "Contract failed: 'hip_point = arrangement_world(\"hip\")' ..."
    )
    assert 'os.environ["CLOTH_PBD_COLLISION_MODE"] = "mesh"' in source, (
        'Contract failed: \'os.environ["CLOTH_PBD_COLLISION_MODE"]...'
    )
    assert "status = target_status(target)" in source, (
        'Contract failed: "status = target_status(target)" in source'
    )
    assert 'scene.PinMode = "None"' in source, (
        "Contract failed: 'scene.PinMode = \"None\"' in source"
    )
    assert 'scene.PinMode = "Explicit"' not in source, (
        "Contract failed: 'scene.PinMode = \"Explicit\"' not in source"
    )
    assert "scene.PinSelection = []" in source, (
        'Contract failed: "scene.PinSelection = []" in source'
    )
    assert "scene.PinSelection = [str(index) for index in expected_pins]" not in source, (
        'Contract failed: "scene.PinSelection = [str(index) for i...'
    )
    assert "if solver_pins:" in source, 'Contract failed: "if solver_pins:" in source'
    assert "base_proxy_getter().source_signature = None" in source, (
        'Contract failed: "base_proxy_getter().source_signature =...'
    )
    assert "tunic-neckline-midpoint piece=%s particle=%d snap-mm=%.2f" in source, (
        'Contract failed: "tunic-neckline-midpoint piece=%s parti...'
    )
    assert "panel_indices.get(panel.Name, ())" in source, (
        'Contract failed: "panel_indices.get(panel.Name, ())" in ...'
    )
    assert 'panel_objects = tuple(getattr(scene, "DrapePanels", ()))' in source, (
        "Contract failed: 'panel_objects = tuple(getattr(scene, \"..."
    )
    assert "scene.touch()" in source, 'Contract failed: "scene.touch()" in source'
    initial_piece_links = source.index("scene.ClothPieces = [front, back]")
    initial_cache_invalidation = source.index("base_proxy_getter().source_signature = None")
    first_panel_map = source.index('panel_piece_names = getattr(proxy, "panel_piece_names", {})')
    assert initial_piece_links < initial_cache_invalidation < first_panel_map, (
        "Contract failed: initial_piece_links < initial_cache_inv..."
    )
    assert "tunic-simulation-panel-map proxy=%s links=%d panels=%r map=%r particles=%d" in source, (
        'Contract failed: "tunic-simulation-panel-map proxy=%s li...'
    )
    assert "canonical tunic simulation did not build an authored pattern panel" in source, (
        'Contract failed: "canonical tunic simulation did not bui...'
    )
    assert "def _neckline_boundary_particles(" in source, (
        'Contract failed: "def _neckline_boundary_particles(" in ...'
    )
    assert '"semantic-chain-endpoints"' in source, (
        "Contract failed: '\"semantic-chain-endpoints\"' in source"
    )
    assert '"authored-edge-projection"' in source, (
        "Contract failed: '\"authored-edge-projection\"' in source"
    )
    assert _NECKLINE_RESOLUTION_FRAGMENT in source, (
        'Contract failed: "tunic-neckline-resolution piece=%s edg...'
    )
    assert "boundary_index >= len(boundary_chains)" not in source, (
        'Contract failed: "boundary_index >= len(boundary_chains)...'
    )
    assert "nearest_target_clearance" in source, (
        'Contract failed: "nearest_target_clearance" in source'
    )
    assert "step0-target-vertex-clearance-mm=" in source, (
        'Contract failed: "step0-target-vertex-clearance-mm=" in ...'
    )
    assert "authored_shoulder_pins" not in source, (
        'Contract failed: "authored_shoulder_pins" not in source'
    )
    assert "scene.PinSelection = [str(i) for i in front_pins]" not in source, (
        'Contract failed: "scene.PinSelection = [str(i) for i in ...'
    )
    assert "target_surface = collision_surface(" in source, (
        'Contract failed: "target_surface = collision_surface(" i...'
    )
    assert "target_source.Mesh.BoundBox" not in source, (
        'Contract failed: "target_source.Mesh.BoundBox" not in so...'
    )


def test_canonical_tunic_uses_matching_authored_mapping() -> None:
    """Verify canonical tunic uses matching authored mapping contract."""
    audit = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "required_indices = (1, 3, 5, 7)" in audit, (
        'Contract failed: "required_indices = (1, 3, 5, 7)" in audit'
    )
    assert 'front_edge_ids[1], back_edge_ids[1], "TunicRightSide"' in audit, (
        "Contract failed: 'front_edge_ids[1], back_edge_ids[1], \"..."
    )
    assert 'front_edge_ids[3], back_edge_ids[3], "TunicRightShoulder"' in audit, (
        "Contract failed: 'front_edge_ids[3], back_edge_ids[3], \"..."
    )
    assert 'front_edge_ids[5], back_edge_ids[5], "TunicLeftShoulder"' in audit, (
        "Contract failed: 'front_edge_ids[5], back_edge_ids[5], \"..."
    )
    assert 'front_edge_ids[7], back_edge_ids[7], "TunicLeftSide"' in audit, (
        "Contract failed: 'front_edge_ids[7], back_edge_ids[7], \"..."
    )
    assert 'front_edge_ids[3], back_edge_ids[5], "TunicRightShoulder"' not in audit, (
        "Contract failed: 'front_edge_ids[3], back_edge_ids[5], \"..."
    )


def test_canonical_tunic_shared_source_syntax_compiles() -> None:
    """Verify the canonical tunic audit source parses without launching FreeCAD."""
    wrapper = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    audit_path = ROOT / "tests" / "freecad_screenshot_source.py"
    audit_source = audit_path.read_text(encoding="utf-8")
    compile(audit_source, str(audit_path), "exec")
    assert '"--syntax-check"' in wrapper, (
        "The tunic wrapper must keep an explicit syntax-check mode."
    )
    assert '"tunic-audit-source-syntax=passed"' in wrapper, (
        "The tunic wrapper must retain its syntax-check success marker."
    )


def test_canonical_tunic_authoritative_gate_is_fail_closed() -> None:
    """Verify canonical tunic authoritative gate is fail closed contract."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert 'os.environ["CLOTH_PBD_COLLISION_MODE"] = "mesh"' in source, (
        'Contract failed: \'os.environ["CLOTH_PBD_COLLISION_MODE"]...'
    )
    assert "proxy=proxy" in source, 'Contract failed: "proxy=proxy" in source'
    assert "authoritative tunic seams did not converge" in source, (
        'Contract failed: "authoritative tunic seams did not conv...'
    )
    assert "if max_seam_gap > 35.0" in source, 'Contract failed: "if max_seam_gap > 35.0" in source'
    assert "authoritative-seam-gap seam=%s" in source, (
        'Contract failed: "authoritative-seam-gap seam=%s" in source'
    )


def test_canonical_tunic_has_two_curved_open_armholes() -> None:
    """Verify canonical tunic has two curved open armholes contract."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "elif index == 2:" in source, 'Contract failed: "elif index == 2:" in source'
    assert "elif index == 6:" in source, 'Contract failed: "elif index == 6:" in source'
    arc_helper = (ROOT / "tests" / "support" / "freecad_arc_geometry.py").read_text(
        encoding="utf-8"
    )
    assert "def arc_through_midpoint(" in arc_helper
    assert "part_api.ArcOfCircle(" in arc_helper
    assert "zero_point = _native_curve_value(circle, 0.0)" in arc_helper
    assert "quarter_point = _native_curve_value(circle, math.pi / 2.0)" in arc_helper
    assert 'getter = getattr(curve, "valueAt", None)' in arc_helper
    assert 'getter = getattr(curve, "value", None)' in arc_helper
    assert "tunic armhole curve has no native parameter evaluator" in arc_helper
    assert "tunic armhole arc lost authored {role}" in arc_helper
    sketch_builder = source.split("def _make_tunic_sketch(", 1)[1].split("\ndef _adopt_sketch", 1)[
        0
    ]
    assert (
        'sketch.addConstraint([Sketcher.Constraint("Block", index) '
        "for index in range(len(geometry))])" in sketch_builder
    ), "Contract failed: 'sketch.addConstraint([Sketcher.Constra..."
    assert 'Sketcher.Constraint("Coincident"' not in sketch_builder, (
        "Contract failed: 'Sketcher.Constraint(\"Coincident\"' not ..."
    )
    assert "tunic armhole collapsed during Sketcher recompute" in sketch_builder, (
        'Contract failed: "tunic armhole collapsed during Sketche...'
    )
    assert "armhole_z = 0.62 * float(garment_height)" in sketch_builder, (
        'Contract failed: "armhole_z = 0.62 * float(garment_heigh...'
    )
    assert "(x_offset + 0.74 * panel_width, armhole_z)" in sketch_builder, (
        'Contract failed: "(x_offset + 0.74 * panel_width, armhol...'
    )
    assert "shoulder_z = 0.94 * float(garment_height)" in sketch_builder, (
        'Contract failed: "shoulder_z = 0.94 * float(garment_heig...'
    )
    assert "(x_offset + 0.94 * panel_width, shoulder_z)" in sketch_builder, (
        'Contract failed: "(x_offset + 0.94 * panel_width, should...'
    )
    assert "if not (armhole_z < shoulder_z < neck_z)" in sketch_builder, (
        'Contract failed: "if not (armhole_z < shoulder_z < neck_...'
    )
    assert "shoulders must slope downward from neckline to shoulder tip" in sketch_builder, (
        'Contract failed: "shoulders must slope downward from nec...'
    )
    assert "points[3][0] - points[2][0] < 0.15 * float(panel_width)" in sketch_builder, (
        'Contract failed: "points[3][0] - points[2][0] < 0.15 * f...'
    )
    assert "shoulder_z - armhole_z < 0.20 * float(garment_height)" in sketch_builder, (
        'Contract failed: "shoulder_z - armhole_z < 0.20 * float(...'
    )
    assert "side_ease_mm = 4.0" in sketch_builder, (
        'Contract failed: "side_ease_mm = 4.0" in sketch_builder'
    )
    assert "if index == 1:" in sketch_builder, 'Contract failed: "if index == 1:" in sketch_builder'
    assert "elif index == 7:" in sketch_builder, (
        'Contract failed: "elif index == 7:" in sketch_builder'
    )
    assert "0.5 * (start[0] + end[0]) + side_ease_mm" in sketch_builder, (
        'Contract failed: "0.5 * (start[0] + end[0]) + side_ease_...'
    )
    assert "0.5 * (start[0] + end[0]) - side_ease_mm" in sketch_builder, (
        'Contract failed: "0.5 * (start[0] + end[0]) - side_ease_...'
    )
    assert "(x_offset + 0.06 * panel_width, shoulder_z)" in sketch_builder, (
        'Contract failed: "(x_offset + 0.06 * panel_width, should...'
    )
    assert "(x_offset + 0.26 * panel_width, armhole_z)" in sketch_builder, (
        'Contract failed: "(x_offset + 0.26 * panel_width, armhol...'
    )
    # Keep the inward-scooped arc inside the shoulder line; .73/.27 self-intersects.
    assert "x_offset + 0.741 * panel_width, armhole_mid_z" in sketch_builder, (
        'Contract failed: "x_offset + 0.741 * panel_width, armhol...'
    )
    assert "x_offset + 0.259 * panel_width, armhole_mid_z" in sketch_builder, (
        'Contract failed: "x_offset + 0.259 * panel_width, armhol...'
    )
    assert "for edge_index, inward in ((2, -1.0), (6, 1.0))" in source, (
        'Contract failed: "for edge_index, inward in ((2, -1.0), ...'
    )
    assert 'boundary.kind != "arc" or len(boundary.samples) < 8' in source, (
        'Contract failed: \'boundary.kind != "arc" or len(boundary...'
    )
    assert "armhole curve has insufficient inward clearance" in source, (
        'Contract failed: "armhole curve has insufficient inward ...'
    )
    assert 'front_edge_ids[1], back_edge_ids[1], "TunicRightSide", False' in source, (
        "Contract failed: 'front_edge_ids[1], back_edge_ids[1], \"..."
    )
    assert 'front_edge_ids[3], back_edge_ids[3], "TunicRightShoulder", False' in source, (
        "Contract failed: 'front_edge_ids[3], back_edge_ids[3], \"..."
    )
    assert 'front_edge_ids[5], back_edge_ids[5], "TunicLeftShoulder", False' in source, (
        "Contract failed: 'front_edge_ids[5], back_edge_ids[5], \"..."
    )
    assert 'front_edge_ids[7], back_edge_ids[7], "TunicLeftSide", False' in source, (
        "Contract failed: 'front_edge_ids[7], back_edge_ids[7], \"..."
    )
    assert 'front_edge_ids[2], back_edge_ids[2], "TunicRightArmhole"' not in source, (
        "Contract failed: 'front_edge_ids[2], back_edge_ids[2], \"..."
    )
    assert 'front_edge_ids[6], back_edge_ids[6], "TunicLeftArmhole"' not in source, (
        "Contract failed: 'front_edge_ids[6], back_edge_ids[6], \"..."
    )


def test_simulation_proxy_serializes_only_rebuildable_metadata() -> None:
    """Verify simulation proxy serializes only rebuildable metadata contract."""
    simulation_objects = import_module("freecad_cloth.simulation.SimulationObjects")
    simulation_proxy_type = cast(
        "type[SimulationProxy]",
        simulation_objects.SimulationProxy,
    )
    proxy = simulation_proxy_type()
    proxy.backend = cast("PositionBasedDynamicsBackend", object())
    proxy.panel_indices = {"panel": (1, 2)}
    proxy.seam_stitch_pairs = {"seam": ((0, 1),)}
    proxy.source_signature = ("derived",)
    proxy.last_steps = 17
    proxy.collision_surface = object()

    state = proxy.__getstate__()
    assert state == {"schema": 1}, 'Contract failed: state == {"schema": 1}'
    assert "backend" not in state, 'Contract failed: "backend" not in state'
    assert "seam_stitch_pairs" not in state, 'Contract failed: "seam_stitch_pairs" not in state'
    assert "collision_surface" not in state, 'Contract failed: "collision_surface" not in state'

    proxy.__setstate__(state)
    assert proxy.backend is None, "Contract failed: proxy.backend is None"
    assert proxy.panel_indices == {}, "Contract failed: proxy.panel_indices == {}"
    assert proxy.seam_stitch_pairs == {}, "Contract failed: proxy.seam_stitch_pairs == {}"
    assert proxy.source_signature is None, "Contract failed: proxy.source_signature is None"
    assert proxy.last_steps == 0, "Contract failed: proxy.last_steps == 0"
    assert proxy.collision_surface is None, "Contract failed: proxy.collision_surface is None"


def test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit() -> None:
    """Verify tunic realtime profile is bounded and mesh collision is explicit contract."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    assert "ParticleDistance = 24.0" in source, (
        'Contract failed: "ParticleDistance = 24.0" in source'
    )
    assert "SolverIterations = 8" in source, 'Contract failed: "SolverIterations = 8" in source'
    assert "SolverSubsteps = 4" in source, 'Contract failed: "SolverSubsteps = 4" in source'
    assert "CLOTH_PBD_COLLISION_MODE: mesh" in workflow, (
        'Contract failed: "CLOTH_PBD_COLLISION_MODE: mesh" in wor...'
    )
    assert "CLOTH_PBD_COLLISION_VOXEL_MM=8.0" in workflow, (
        'Contract failed: "CLOTH_PBD_COLLISION_VOXEL_MM=8.0" in w...'
    )
    assert "voxel_mm - 8.0" in source, 'Contract failed: "voxel_mm - 8.0" in source'
    assert "(span + 200.0) / 8.0" in source, 'Contract failed: "(span + 200.0) / 8.0" in source'
    assert "configured 8 mm voxel resolution" in source, (
        'Contract failed: "configured 8 mm voxel resolution" in s...'
    )
    tunic_workflow = workflow.split("  gui-tunic-visual:", 1)[1].split("  gui-turntables:", 1)[0]
    assert "CLOTH_PBD_SUBSTEPS=16" in tunic_workflow, (
        'Contract failed: "CLOTH_PBD_SUBSTEPS=16" in tunic_workflow'
    )
    assert 'os.environ["CLOTH_PBD_COLLISION_VOXEL_MM"]' not in source, (
        "Contract failed: 'os.environ[\"CLOTH_PBD_COLLISION_VOXEL_..."
    )
    assert "CLOTH_PBD_SUBSTEPS: 8" in workflow, (
        'Contract failed: "CLOTH_PBD_SUBSTEPS: 8" in workflow'
    )
    assert 'os.environ["CLOTH_PBD_SUBSTEPS"]' not in source, (
        "Contract failed: 'os.environ[\"CLOTH_PBD_SUBSTEPS\"]' not ..."
    )
    assert "CLOTH_PBD_COLLISION_TOLERANCE_MM: 12" not in workflow, (
        'Contract failed: "CLOTH_PBD_COLLISION_TOLERANCE_MM: 12" ...'
    )
    assert "tunic-collision-config target-thickness-mm=%.2f" in source, (
        'Contract failed: "tunic-collision-config target-thicknes...'
    )
    simulation_commands = (
        ROOT / "freecad_cloth" / "simulation" / "SimulationCommands.py"
    ).read_text(encoding="utf-8")
    assert "DEFAULT_MANNEQUIN_COLLISION_THICKNESS_MM" in simulation_commands, (
        'Contract failed: "DEFAULT_MANNEQUIN_COLLISION_THICKNESS_...'
    )
    assert "tunic-simulation-start" in source, 'Contract failed: "tunic-simulation-start" in source'
    assert 'configured_substeps = int(os.environ.get("CLOTH_PBD_SUBSTEPS", "8"))' in source, (
        "Contract failed: 'configured_substeps = int(os.environ.g..."
    )
    assert 'effective_substeps = int(getattr(active_backend, "_substeps", -1))' in source, (
        "Contract failed: 'effective_substeps = int(getattr(activ..."
    )
    assert "effective_substeps != configured_substeps" in source, (
        'Contract failed: "effective_substeps != configured_subst...'
    )
    assert "backend_substeps=%d configured_substeps=%d" in source, (
        'Contract failed: "backend_substeps=%d configured_substep...'
    )
    assert "realtime-preview=passed backend=position-based-dynamics" in source, (
        'Contract failed: "realtime-preview=passed backend=positi...'
    )
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    assert "tools/ci/validate_manifests.py tunic-production" in workflow, (
        'Contract failed: "tools/ci/validate_manifests.py tunic-p...'
    )
    validator = (ROOT / "tools" / "ci" / "validate_manifests.py").read_text(encoding="utf-8")
    assert "def validate_tunic_production()" in validator, (
        'Contract failed: "def validate_tunic_production()" in va...'
    )
    assert "runtime collision configuration evidence is invalid" in validator, (
        'Contract failed: "runtime collision configuration eviden...'
    )
    assert "expected_resolution = tuple(" in validator, (
        'Contract failed: "expected_resolution = tuple(" in valid...'
    )
    assert "def _validate_realtime_metrics(data: dict)" in validator, (
        'Contract failed: "def _validate_realtime_metrics(data: d...'
    )
    assert "_validate_realtime_metrics(data)" in validator, (
        'Contract failed: "_validate_realtime_metrics(data)" in v...'
    )
    assert "PBD SDF voxel must be 8 mm" in validator, (
        'Contract failed: "PBD SDF voxel must be 8 mm" in validator'
    )


def test_pbd_collision_body_uses_coarsened_solver_surface() -> None:
    """Verify pbd collision body uses coarsened solver surface contract."""
    backend = (ROOT / "freecad_cloth" / "simulation" / "PositionBasedDynamicsBackend.py").read_text(
        encoding="utf-8"
    )
    start = backend.index("    def _add_collision_body(")
    end = backend.index("    def _build(", start)
    body_builder = backend[start:end]
    assert "collision_surface = self._collision_surface" in body_builder, (
        'Contract failed: "collision_surface = self._collision_su...'
    )
    assert "collision_surface = self._source_collision_surface" not in body_builder, (
        'Contract failed: "collision_surface = self._source_colli...'
    )


def test_pbd_collision_sdf_resolution_and_tolerance_are_explicit() -> None:
    """Verify pbd collision sdf resolution and tolerance are explicit contract."""
    backend = (ROOT / "freecad_cloth" / "simulation" / "PositionBasedDynamicsBackend.py").read_text(
        encoding="utf-8"
    )
    assert "CLOTH_PBD_COLLISION_VOXEL_MM" in backend, (
        'Contract failed: "CLOTH_PBD_COLLISION_VOXEL_MM" in backend'
    )
    assert "def pbd_collision_resolution(surface: CollisionSurface)" in backend, (
        'Contract failed: "def _pbd_collision_resolution(surface:...'
    )
    assert "generateSDF(" in backend, 'Contract failed: "generateSDF(" in backend'
    assert "resolution," in backend, 'Contract failed: "resolution," in backend'
    assert "representation_margin = 0.5 * _pbd_collision_voxel_mm()" in backend, (
        'Contract failed: "representation_margin = 0.5 * _pbd_col...'
    )
    assert "max(configured, thickness, representation_margin)" in backend, (
        'Contract failed: "max(configured, thickness, representat...'
    )
    assert "self._collision_sdf_resolution = tuple(int(axis) for axis in resolution)" in backend, (
        'Contract failed: "self._collision_sdf_resolution = tuple...'
    )
    assert "effective_tolerance_mm / _MM" in backend, (
        'Contract failed: "effective_tolerance_mm / _MM" in backend'
    )
    assert "cloth-pbd-collision-config " in backend, (
        'Contract failed: "cloth-pbd-collision-config " in backend'
    )
    assert backend.index("timestep.step(self._model)") < backend.index(
        "self._project_collision_positions()"
    ), 'Contract failed: backend.index("timestep.step(self._mode...'
    assert "particles.setPosition(" in backend, (
        'Contract failed: "particles.setPosition(" in backend'
    )
    assert "inward_speed < 0.0" in backend, 'Contract failed: "inward_speed < 0.0" in backend'
    assert "project_stitched_pairs(" in backend, (
        'Contract failed: "project_stitched_pairs(" in backend'
    )
    assert backend.index("project_stitched_pairs(") < backend.index("moved_indices ="), (
        'Contract failed: backend.index("project_stitched_pairs("...'
    )


def test_pbd_collision_sdf_is_cached_outside_backend_instance() -> None:
    """Verify pbd collision sdf is cached outside backend instance contract."""
    backend = (ROOT / "freecad_cloth" / "simulation" / "PositionBasedDynamicsBackend.py").read_text(
        encoding="utf-8"
    )
    assert "_PBD_COLLISION_SDF_CACHE_KEY" in backend, (
        'Contract failed: "_PBD_COLLISION_SDF_CACHE_KEY" in backend'
    )
    assert "_PBD_COLLISION_SDF_CACHE" in backend, (
        'Contract failed: "_PBD_COLLISION_SDF_CACHE" in backend'
    )
    assert "cache-hit" in backend, 'Contract failed: "cache-hit" in backend'
    assert "generateSDF(" in backend, 'Contract failed: "generateSDF(" in backend'
    assert "self._collision_sdf" in backend, 'Contract failed: "self._collision_sdf" in backend'


def test_pbd_sdf_cache_key_is_stable_and_geometry_sensitive() -> None:
    """Verify pbd sdf cache key is stable and geometry sensitive contract."""
    backend_module = import_module("freecad_cloth.simulation.PositionBasedDynamicsBackend")
    cache_key_attribute = "_pbd_collision_sdf_cache_key"
    collision_sdf_cache_key = cast(
        "Callable[[CollisionSurface, list[int]], bytes]",
        getattr(backend_module, cache_key_attribute),
    )

    surface = CollisionSurface(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ((0, 1, 2),),
        thickness=1.0,
    ).validate()
    key = collision_sdf_cache_key(surface, [16, 16, 16])
    assert key == collision_sdf_cache_key(surface, [16, 16, 16]), (
        "Contract failed: key == _pbd_collision_sdf_cache_key(sur..."
    )

    moved = CollisionSurface(
        ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ((0, 1, 2),),
        thickness=1.0,
    ).validate()
    assert key != collision_sdf_cache_key(moved, [16, 16, 16]), (
        "Contract failed: key != _pbd_collision_sdf_cache_key(mov..."
    )
    assert key != collision_sdf_cache_key(surface, [17, 16, 16]), (
        "Contract failed: key != _pbd_collision_sdf_cache_key(sur..."
    )


def test_pbd_ci_image_is_pinned_and_preinstalled() -> None:
    """Verify pbd ci image is pinned and preinstalled contract."""
    dockerfile = (ROOT / "docker" / "freecad-ci" / "Dockerfile").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    assert "pypbd==2.2.2" in dockerfile, 'Contract failed: "pypbd==2.2.2" in dockerfile'
    assert "triangle==20250106" in dockerfile, 'Contract failed: "triangle==20250106" in dockerfile'
    assert "/opt/pypbd-provenance.txt" in dockerfile, (
        'Contract failed: "/opt/pypbd-provenance.txt" in dockerfile'
    )
    assert "makehuman-hm08-base.obj" in dockerfile, (
        'Contract failed: "makehuman-hm08-base.obj" in dockerfile'
    )
    assert (
        "FREECAD_CLOTH_AVATAR_MESH=/opt/freecad-cloth/assets/makehuman-hm08-base.obj" in dockerfile
    ), 'Contract failed: "FREECAD_CLOTH_AVATAR_MESH=/opt/freecad...'
    assert (
        "1f508f6083b2f823dab15de924b3bde72e08d77c9/makehuman/data/3dobjs/base.obj" in dockerfile
    ), 'Contract failed: "1f508f6083b2f823dab15de924b3bde72e08d7...'
    assert "8e761e6624b8f54536409135d1636da63b32486a90d4897f84e121d144f6fb4c" in dockerfile, (
        'Contract failed: "8e761e6624b8f54536409135d1636da63b3248...'
    )
    assert "pbd_validation_image:" in workflow, (
        'Contract failed: "pbd_validation_image:" in workflow'
    )
    assert "FREECAD_PBD_IMAGE" in workflow, 'Contract failed: "FREECAD_PBD_IMAGE" in workflow'
    assert "CLOTH_CI_ENABLE_PBD: 1" in workflow, (
        'Contract failed: "CLOTH_CI_ENABLE_PBD: 1" in workflow'
    )
    gui = workflow.split("  gui-tunic-visual:", 1)[1].split("  gui-turntables:", 1)[0]
    assert "image: ${{ env.FREECAD_PBD_IMAGE }}" in gui, (
        'Contract failed: "image: ${{ env.FREECAD_PBD_IMAGE }}" i...'
    )
    assert "capture_pypbd_provenance.py" in gui, (
        'Contract failed: "capture_pypbd_provenance.py" in gui'
    )
    assert "artifacts/pypbd-provenance.txt" in gui, (
        'Contract failed: "artifacts/pypbd-provenance.txt" in gui'
    )


def test_production_tunic_audit_runs_but_is_explicitly_advisory() -> None:
    """The full production audit runs but cannot block while throughput is deferred."""
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    gui = workflow.split("  gui-tunic-visual:", 1)[1].split("  gui-turntables:", 1)[0]
    benchmark_index = gui.index("test-script: tests/freecad_realtime_benchmark.py")
    metric_gate_index = gui.index(
        "tools/ci/validate_realtime_benchmark.py artifacts/freecad-realtime/metrics.json"
    )
    audit_index = gui.index("test-script: tests/freecad_tunic_audit_production.py")
    audit_action_index = gui.rfind("- uses: ./.github/actions/freecad-test", 0, audit_index)
    advisory_index = gui.index("      - name: Report production tunic audit as advisory", audit_action_index)
    audit_action = gui[audit_action_index:advisory_index]
    assert "CLOTH_REALTIME_FRAMES=120" in gui[benchmark_index:metric_gate_index]
    assert benchmark_index < metric_gate_index < audit_action_index < audit_index
    assert "if: always()" in audit_action, (
        "The production tunic audit must still execute after a failed realtime gate."
    )
    assert "id: production-tunic-audit" in audit_action
    assert "continue-on-error: true" in audit_action
    assert 'timeout-seconds: "360"' in audit_action
    advisory = gui.split("      - name: Report production tunic audit as advisory", 1)[1]
    assert "steps.production-tunic-audit.outcome" in advisory
    assert "this is not a pass" in advisory
    assert "#2839" in advisory
    assert "CLOTH_PBD_SUBSTEPS=16" in audit_action
    assert "CLOTH_PBD_COLLISION_TOLERANCE_MM=2.0" in audit_action
    validator = (ROOT / "tools" / "ci" / "validate_realtime_benchmark.py").read_text(
        encoding="utf-8"
    )
    assert "p95_frame_interval_ms exceeds the 30 FPS budget" in validator


def test_production_tunic_wrapper_dispatches_in_freecad_macro_host() -> None:
    """Verify production tunic wrapper dispatches in freecad macro host contract."""
    wrapper = (ROOT / "tests" / "freecad_tunic_audit_production.py").read_text(encoding="utf-8")
    assert 'importlib.import_module("freecad_tunic_audit").main' in wrapper, (
        "Contract failed: 'importlib.import_module(\"freecad_tunic..."
    )
    assert "main()" in wrapper, 'Contract failed: "main()" in wrapper'
    assert 'if __name__ == "__main__"' not in wrapper, (
        "Contract failed: 'if __name__ == \"__main__\"' not in wrapper"
    )


def test_canonical_tunic_fixture_matches_validated_start_geometry() -> None:
    """Verify canonical tunic fixture matches validated start geometry contract."""
    audit = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    audit_entry = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert "CLOTH_TUNIC_AUDIT_PROFILE" in audit_entry, (
        'Contract failed: "CLOTH_TUNIC_AUDIT_PROFILE" in audit_entry'
    )
    assert "TUNIC_PRODUCTION_AUDIT" in audit, 'Contract failed: "TUNIC_PRODUCTION_AUDIT" in audit'
    assert "SEAM_SOURCE = " not in audit_entry, (
        'Contract failed: "SEAM_SOURCE = " not in audit_entry'
    )
    assert "required_indices = (1, 3, 5, 7)" in audit, (
        'Contract failed: "required_indices = (1, 3, 5, 7)" in audit'
    )
    assert "TunicRightShoulder" in audit, 'Contract failed: "TunicRightShoulder" in audit'
    assert "TunicLeftShoulder" in audit, 'Contract failed: "TunicLeftShoulder" in audit'
    assert "ParticleDistance = 24.0" in audit, 'Contract failed: "ParticleDistance = 24.0" in audit'
    assert "SolverIterations = 8" in audit, 'Contract failed: "SolverIterations = 8" in audit'
    assert "SolverSubsteps = 4 if TUNIC_PRODUCTION_AUDIT else 1" in audit, (
        'Contract failed: "SolverSubsteps = 4 if TUNIC_PRODUCTION...'
    )
    assert "tunic-simulation-start" in audit, 'Contract failed: "tunic-simulation-start" in audit'
    assert "realtime-preview=passed backend=position-based-dynamics" in audit, (
        'Contract failed: "realtime-preview=passed backend=positi...'
    )


def test_tunic_penetration_audit_uses_safe_numpy_ray_parity_in_freecad_host() -> None:
    """Verify tunic penetration audit uses safe numpy ray parity in freecad host contract."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    inside_check = source.split("def _inside_target_count(", 1)[1].split(
        "\ndef write_drape_metrics(", 1
    )[0]
    assert "Trimesh/Rtree's native contains query" in inside_check, (
        'Contract failed: "Trimesh/Rtree\'s native contains query"...'
    )
    assert "target_mesh.contains" not in inside_check, (
        'Contract failed: "target_mesh.contains" not in inside_check'
    )
    assert "import trimesh" not in inside_check, (
        'Contract failed: "import trimesh" not in inside_check'
    )
    assert "chunk_size=4" in inside_check, 'Contract failed: "chunk_size=4" in inside_check'
    assert "points_inside_closed_mesh(" in inside_check, (
        'Contract failed: "points_inside_closed_mesh(" in inside_...'
    )
    assert "prefer_trimesh=False" in inside_check, (
        'Contract failed: "prefer_trimesh=False" in inside_check'
    )
    assert "penetration-check=numpy-ray-parity" in inside_check, (
        'Contract failed: "penetration-check=numpy-ray-parity" in...'
    )
    sanity = (ROOT / "freecad_cloth" / "simulation" / "DrapeVisualSanity.py").read_text(
        encoding="utf-8"
    )
    assert "prefer_trimesh: bool = True" in sanity, (
        'Contract failed: "prefer_trimesh: bool = True" in sanity'
    )
    assert "if prefer_trimesh:" in sanity, 'Contract failed: "if prefer_trimesh:" in sanity'
    assert "np.einsum" in sanity, 'Contract failed: "np.einsum" in sanity'


def test_penetration_evidence_stays_on_numpy_path_in_freecad_host() -> None:
    """Verify penetration evidence stays on numpy path in freecad host contract."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    audit = source.split("def write_drape_metrics(", 1)[1].split("\ndef _arc_through_midpoint(", 1)[
        0
    ]
    evidence = audit.split("inside_points = []", 1)[1].split(
        'log(\n                    "penetration-evidence', 1
    )[0]

    assert (
        "from freecad_cloth.simulation.DrapeVisualSanity import point_inside_closed_mesh"
        not in audit
    ), 'Contract failed: "from freecad_cloth.simulation.DrapeVis...'
    assert evidence.count("prefer_trimesh=False") == _EXPECTED_TRIMESH_OVERRIDE_COUNT, (
        'Contract failed: evidence.count("prefer_trimesh=False") ...'
    )
    assert "points_inside_closed_mesh(" in evidence, (
        'Contract failed: "points_inside_closed_mesh(" in evidence'
    )
    assert "point_inside_closed_mesh(" not in evidence, (
        'Contract failed: "point_inside_closed_mesh(" not in evid...'
    )


def test_tunic_visual_diagnostics_are_authoritative_after_persistence() -> None:
    """Verify tunic visual diagnostics are authoritative after persistence contract."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    metrics_write = source.index("json.dump(payload, handle, indent=2, sort_keys=True)")
    gate = source.index('allowed_diagnostics={"below-hem-candidate"}')
    screenshot = source.index('f"cloth-simulation-draped-{direction}.png"')
    assert metrics_write < screenshot < gate, "Contract failed: metrics_write < screenshot < gate"


def test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks() -> None:
    """Verify the diagnostic tunic profile stays aligned with canonical landmarks."""
    debug = (ROOT / "tests" / "freecad_drape_debug.py").read_text(encoding="utf-8")
    audit = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")

    _require_source_contract(
        source=debug,
        required=(
            _SIMULATION_SCENE_IMPORT,
            "neck_z = (1.0 - float(neckline_drop)) * h",
            "garment_height = max(560.0, (shoulder_z - hem_z + shoulder_headroom_mm) / 0.94)",
            "shoulder_headroom_mm = 20.0",
            "x_offset = 0.5 * (float(hem_width) - float(panel_width))",
            "armhole_z = 0.62 * h",
            "shoulder_z = 0.94 * h",
            "points[3][0] - points[2][0] < 0.15 * float(panel_width)",
            "shoulder_z - armhole_z < 0.20 * h",
            "side_ease_mm = 4.0",
            "if idx == 1:",
            "elif idx == 7:",
            "(x_offset + 0.74 * panel_width, armhole_z)",
            "(x_offset + 0.26 * panel_width, armhole_z)",
            "midpoint = App.Vector(x_offset + 0.741 * panel_width, armhole_mid_z, 0)",
            "midpoint = App.Vector(x_offset + 0.259 * panel_width, armhole_mid_z, 0)",
            "(x_offset + 0.06 * panel_width, 0.94 * garment_height)",
            "(x_offset + 0.94 * panel_width, 0.94 * garment_height)",
            "if not (armhole_z < shoulder_z < neck_z)",
            "neckline_scoop_depth = 0.12 * h",
            "neckline_scoop_z = neck_z - neckline_scoop_depth",
            "if not (armhole_z < neckline_scoop_z < shoulder_z)",
            "front_y = box.YMax + clearance",
            "back_y = box.YMin - clearance",
            'make_piece("DebugTunicFront", front_y, 0.72, 0.03)',
            'make_piece("DebugTunicBack", back_y, 0.72, 0.03)',
            "elif idx == 4:",
            "ArrangementPoint.from_string(raw)",
            "panel_width = max(420.0, shoulder_width + 105.0)",
            "clearance = max(20.0, 0.08 * body_depth)",
            "hem_width = max(500.0, panel_width + 100.0)",
            "panel_width *= 1.10",
            "hem_width *= 1.10",
        ),
        forbidden=("SimulationQualityRuntimeV2",),
        contract="canonical drape debug",
    )
    _require_source_contract(
        source=source,
        required=(
            "neckline_drop: float = 0.03",
            "shoulder_headroom_mm = 20.0",
            "garment_height = max(560.0, (shoulder_z - hem_z + shoulder_headroom_mm) / 0.94)",
            "neckline_scoop_depth = 0.12 * float(garment_height)",
            "neckline_scoop_z = neck_z - neckline_scoop_depth",
            '("back", "front") if TUNIC_PRODUCTION_AUDIT else ("front", "back")',
            'make_piece("VisualTunicFront", front_side, 0.72, 0.03)',
            'make_piece("VisualTunicBack", back_side, 0.72, 0.03)',
            "elif index == 4:",
            "true U-shaped neckline",
            "shoulder_width + 105.0",
            "else max(450.0, panel_width + 100.0)",
            "clearance = max(20.0, 0.08 * body_depth)",
            "panel_width *= 1.10",
            "hem_width *= 1.10",
        ),
        forbidden=(),
        contract="canonical tunic source",
    )
    _require_source_contract(
        source=audit,
        required=(
            "neckline_scoop_depth = 0.12 * float(garment_height)",
            '("back", "front") if TUNIC_PRODUCTION_AUDIT else ("front", "back")',
            'make_piece("VisualTunicFront", front_side, 0.72, 0.03)',
            'make_piece("VisualTunicBack", back_side, 0.72, 0.03)',
            "clearance = max(20.0, 0.08 * body_depth)",
            "panel_width = max(420.0, shoulder_width + 105.0)",
        ),
        forbidden=(
            "shoulder_span_ratio",
            '"panel_width = max(420.0, shoulder_width + 105.0":',
        ),
        contract="authoritative tunic audit",
    )


def test_tunic_visual_gate_preserves_failed_artifacts_before_exit() -> None:
    """Verify tunic visual gate preserves failed artifacts before exit contract."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    gate = source.index('allowed_diagnostics={"below-hem-candidate"}')
    assert "drape-metrics=" in source[:gate], 'Contract failed: "drape-metrics=" in source[:gate]'
    missing_manifest = "gui-screenshot-manifest" not in source[gate:]
    shows_task_dock = "task_dock.show()" in source[gate:]
    assert missing_manifest or shows_task_dock, (
        'Contract failed: "gui-screenshot-manifest" not in source...'
    )


def test_canonical_tunic_fixture_blocks_every_authored_segment() -> None:
    """Verify canonical tunic fixture blocks every authored segment contract."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    start = source.index("def _make_tunic_sketch(")
    end = source.index("\ndef _adopt_sketch(", start)
    fixture = source[start:end]

    # Fixing all authored segments prevents coincident-only constraints from
    # folding otherwise unconstrained straight edges across the pattern outline.
    expected_constraint = (
        'sketch.addConstraint([Sketcher.Constraint("Block", index) '
        "for index in range(len(geometry))])"
    )
    assert expected_constraint in fixture, "Contract failed: expected_constraint in fixture"
    assert 'Sketcher.Constraint("Coincident"' not in fixture, (
        "Contract failed: 'Sketcher.Constraint(\"Coincident\"' not ..."
    )


def test_tunic_scene_dossier_logs_sampled_topology_before_simulation() -> None:
    """The actual CI fixture must emit geometry evidence before downstream evaluation."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    simulation = source.split("def simulation() -> None:", 1)[1]
    topology_audit = simulation.index("def log_tunic_outline_topology(")
    sample_resolution = simulation.index("resolve_piece_ir(piece)", topology_audit)
    pattern_view = simulation.index(
        "capture_tunic_pattern_view(doc, front, back, hem_width)", topology_audit
    )
    sewing_view = simulation.index(
        "capture_tunic_sewing_view(doc, front, back, hem_width, seam_records)",
        pattern_view,
    )
    native_gate = simulation.index(
        "canonical tunic PatternIR boundary is invalid before simulation", sewing_view
    )
    simulation_start = simulation.index("scene.StartHeight = 0.0", native_gate)

    assert (
        topology_audit
        < sample_resolution
        < pattern_view
        < sewing_view
        < native_gate
        < simulation_start
    ), "Contract failed: topology_audit < sample_resolution < pa..."
    assert '"boundary-order=%r near-crossing=%r"' in simulation, (
        "Contract failed: '\"boundary-order=%r near-crossing=%r\"' ..."
    )
    assert "samples," in simulation, 'Contract failed: "samples," in simulation'
    # Keep geometric validity guards in FreeCAD, but keep report classification on the host.
    assert "canonical tunic derived pattern outline is invalid before simulation" in simulation, (
        'Contract failed: "canonical tunic derived pattern outlin...'
    )
    assert "fit_assessment" not in simulation, 'Contract failed: "fit_assessment" not in simulation'
    assert "review_required" not in simulation, (
        'Contract failed: "review_required" not in simulation'
    )
    assert 'status["result"]' not in simulation, (
        "Contract failed: 'status[\"result\"]' not in simulation"
    )
