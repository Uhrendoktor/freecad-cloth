# Copyright (C) 2026 FreeCAD Cloth contributors
"""Strict source contracts for the canonical tunic simulation audit."""

from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, cast

from freecad_cloth.shared.collision import CollisionSurface
from tests.support.assertions import require

if TYPE_CHECKING:
    from collections.abc import Callable

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
    require(
        condition=not missing and not present,
        message=f"{contract} source contract changed; missing={missing!r}; forbidden={present!r}",
    )


# The native-Sketcher fixture keeps explicit semantic edge IDs on each piece.
# The front/back pieces share the same authored topology, so corresponding shoulder
# and side edges must be paired by semantic position, not cross-paired.


def test_canonical_tunic_pairs_matching_front_back_semantic_edges() -> None:
    """Verify canonical tunic pairs matching front back semantic edges contract."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    require(
        condition=("front_edge_ids = tuple(" in source),
        message='Contract failed: "front_edge_ids = tuple(" in source',
    )
    require(
        condition=("back_edge_ids = tuple(" in source),
        message='Contract failed: "back_edge_ids = tuple(" in source',
    )
    require(
        condition=('"SemanticEdgeIds"' in source),
        message="Contract failed: '\"SemanticEdgeIds\"' in source",
    )
    require(
        condition=('front_edge_ids[1], back_edge_ids[1], "TunicRightSide"' in source),
        message="Contract failed: 'front_edge_ids[1], back_edge_ids[1], \"...",
    )
    require(
        condition=('front_edge_ids[3], back_edge_ids[3], "TunicRightShoulder"' in source),
        message="Contract failed: 'front_edge_ids[3], back_edge_ids[3], \"...",
    )
    require(
        condition=('front_edge_ids[5], back_edge_ids[5], "TunicLeftShoulder"' in source),
        message="Contract failed: 'front_edge_ids[5], back_edge_ids[5], \"...",
    )
    require(
        condition=('front_edge_ids[7], back_edge_ids[7], "TunicLeftSide"' in source),
        message="Contract failed: 'front_edge_ids[7], back_edge_ids[7], \"...",
    )


def test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline() -> None:
    """Verify tunic fixture uses arrangement points and unpinned neckline contract."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    require(
        condition=("ArrangementPoint.from_string" in source),
        message='Contract failed: "ArrangementPoint.from_string" in source',
    )
    require(
        condition=('shoulder_left = arrangement_world("shoulder_left")' in source),
        message="Contract failed: 'shoulder_left = arrangement_world(\"sho...",
    )
    require(
        condition=('shoulder_right = arrangement_world("shoulder_right")' in source),
        message="Contract failed: 'shoulder_right = arrangement_world(\"sh...",
    )
    require(
        condition=('hip_point = arrangement_world("hip")' in source),
        message="Contract failed: 'hip_point = arrangement_world(\"hip\")' ...",
    )
    require(
        condition=('os.environ["CLOTH_PBD_COLLISION_MODE"] = "mesh"' in source),
        message='Contract failed: \'os.environ["CLOTH_PBD_COLLISION_MODE"]...',
    )
    require(
        condition=("status = target_status(target)" in source),
        message='Contract failed: "status = target_status(target)" in source',
    )
    require(
        condition=('scene.PinMode = "None"' in source),
        message="Contract failed: 'scene.PinMode = \"None\"' in source",
    )
    require(
        condition=('scene.PinMode = "Explicit"' not in source),
        message="Contract failed: 'scene.PinMode = \"Explicit\"' not in source",
    )
    require(
        condition=("scene.PinSelection = []" in source),
        message='Contract failed: "scene.PinSelection = []" in source',
    )
    require(
        condition=("scene.PinSelection = [str(index) for index in expected_pins]" not in source),
        message='Contract failed: "scene.PinSelection = [str(index) for i...',
    )
    require(
        condition=("if solver_pins:" in source),
        message='Contract failed: "if solver_pins:" in source',
    )
    require(
        condition=("base_proxy_getter().source_signature = None" in source),
        message='Contract failed: "base_proxy_getter().source_signature =...',
    )
    require(
        condition=("tunic-neckline-midpoint piece=%s particle=%d snap-mm=%.2f" in source),
        message='Contract failed: "tunic-neckline-midpoint piece=%s parti...',
    )
    require(
        condition=("panel_indices.get(panel.Name, ())" in source),
        message='Contract failed: "panel_indices.get(panel.Name, ())" in ...',
    )
    require(
        condition=('panel_objects = tuple(getattr(scene, "DrapePanels", ()))' in source),
        message="Contract failed: 'panel_objects = tuple(getattr(scene, \"...",
    )
    require(
        condition=("scene.touch()" in source),
        message='Contract failed: "scene.touch()" in source',
    )
    initial_piece_links = source.index("scene.ClothPieces = [front, back]")
    initial_cache_invalidation = source.index("base_proxy_getter().source_signature = None")
    first_panel_map = source.index('panel_piece_names = getattr(proxy, "panel_piece_names", {})')
    require(
        condition=(initial_piece_links < initial_cache_invalidation < first_panel_map),
        message="Contract failed: initial_piece_links < initial_cache_inv...",
    )
    require(
        condition=(
            "tunic-simulation-panel-map proxy=%s links=%d panels=%r map=%r particles=%d" in source
        ),
        message='Contract failed: "tunic-simulation-panel-map proxy=%s li...',
    )
    require(
        condition=("canonical tunic simulation did not build an authored pattern panel" in source),
        message='Contract failed: "canonical tunic simulation did not bui...',
    )
    require(
        condition=("def _neckline_boundary_particles(" in source),
        message='Contract failed: "def _neckline_boundary_particles(" in ...',
    )
    require(
        condition=('"semantic-chain-endpoints"' in source),
        message="Contract failed: '\"semantic-chain-endpoints\"' in source",
    )
    require(
        condition=('"authored-edge-projection"' in source),
        message="Contract failed: '\"authored-edge-projection\"' in source",
    )
    require(
        condition=_NECKLINE_RESOLUTION_FRAGMENT in source,
        message='Contract failed: "tunic-neckline-resolution piece=%s edg...',
    )
    require(
        condition=("boundary_index >= len(boundary_chains)" not in source),
        message='Contract failed: "boundary_index >= len(boundary_chains)...',
    )
    require(
        condition=("nearest_target_clearance" in source),
        message='Contract failed: "nearest_target_clearance" in source',
    )
    require(
        condition=("step0-target-vertex-clearance-mm=" in source),
        message='Contract failed: "step0-target-vertex-clearance-mm=" in ...',
    )
    require(
        condition=("authored_shoulder_pins" not in source),
        message='Contract failed: "authored_shoulder_pins" not in source',
    )
    require(
        condition=("scene.PinSelection = [str(i) for i in front_pins]" not in source),
        message='Contract failed: "scene.PinSelection = [str(i) for i in ...',
    )
    require(
        condition=("target_surface = collision_surface(" in source),
        message='Contract failed: "target_surface = collision_surface(" i...',
    )
    require(
        condition=("target_source.Mesh.BoundBox" not in source),
        message='Contract failed: "target_source.Mesh.BoundBox" not in so...',
    )


def test_canonical_tunic_uses_matching_authored_mapping() -> None:
    """Verify canonical tunic uses matching authored mapping contract."""
    audit = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    require(
        condition=("required_indices = (1, 3, 5, 7)" in audit),
        message='Contract failed: "required_indices = (1, 3, 5, 7)" in audit',
    )
    require(
        condition=('front_edge_ids[1], back_edge_ids[1], "TunicRightSide"' in audit),
        message="Contract failed: 'front_edge_ids[1], back_edge_ids[1], \"...",
    )
    require(
        condition=('front_edge_ids[3], back_edge_ids[3], "TunicRightShoulder"' in audit),
        message="Contract failed: 'front_edge_ids[3], back_edge_ids[3], \"...",
    )
    require(
        condition=('front_edge_ids[5], back_edge_ids[5], "TunicLeftShoulder"' in audit),
        message="Contract failed: 'front_edge_ids[5], back_edge_ids[5], \"...",
    )
    require(
        condition=('front_edge_ids[7], back_edge_ids[7], "TunicLeftSide"' in audit),
        message="Contract failed: 'front_edge_ids[7], back_edge_ids[7], \"...",
    )
    require(
        condition=('front_edge_ids[3], back_edge_ids[5], "TunicRightShoulder"' not in audit),
        message="Contract failed: 'front_edge_ids[3], back_edge_ids[5], \"...",
    )


def test_canonical_tunic_shared_source_syntax_compiles() -> None:
    """Verify the canonical tunic audit source parses without launching FreeCAD."""
    wrapper = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    audit_path = ROOT / "tests" / "freecad_screenshot_source.py"
    audit_source = audit_path.read_text(encoding="utf-8")
    compile(audit_source, str(audit_path), "exec")
    require(
        condition='"--syntax-check"' in wrapper,
        message="The tunic wrapper must keep an explicit syntax-check mode.",
    )
    require(
        condition='"tunic-audit-source-syntax=passed"' in wrapper,
        message="The tunic wrapper must retain its syntax-check success marker.",
    )


def test_canonical_tunic_authoritative_gate_is_fail_closed() -> None:
    """Verify canonical tunic authoritative gate is fail closed contract."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    require(
        condition=('os.environ["CLOTH_PBD_COLLISION_MODE"] = "mesh"' in source),
        message='Contract failed: \'os.environ["CLOTH_PBD_COLLISION_MODE"]...',
    )
    require(
        condition=("proxy=proxy" in source),
        message='Contract failed: "proxy=proxy" in source',
    )
    require(
        condition=("authoritative tunic seams did not converge" in source),
        message='Contract failed: "authoritative tunic seams did not conv...',
    )
    require(
        condition=("if max_seam_gap > 35.0" in source),
        message='Contract failed: "if max_seam_gap > 35.0" in source',
    )
    require(
        condition=("authoritative-seam-gap seam=%s" in source),
        message='Contract failed: "authoritative-seam-gap seam=%s" in source',
    )


def test_canonical_tunic_has_two_curved_open_armholes() -> None:
    """Verify canonical tunic has two curved open armholes contract."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    require(
        condition=("elif index == 2:" in source),
        message='Contract failed: "elif index == 2:" in source',
    )
    require(
        condition=("elif index == 6:" in source),
        message='Contract failed: "elif index == 6:" in source',
    )
    require(
        condition=("def _arc_through_midpoint(" in source),
        message='Contract failed: "def _arc_through_midpoint(" in source',
    )
    require(
        condition=("Part.ArcOfCircle(circle, start_angle, start_angle + sweep)" in source),
        message='Contract failed: "Part.ArcOfCircle(circle, start_angle, ...',
    )
    require(
        condition=("zero_point = curve_value(circle, 0.0)" in source),
        message='Contract failed: "zero_point = curve_value(circle, 0.0)"...',
    )
    require(
        condition=("quarter_point = curve_value(circle, math.pi / 2.0)" in source),
        message='Contract failed: "quarter_point = curve_value(circle, ma...',
    )
    require(
        condition=('getter = getattr(curve, "valueAt", None)' in source),
        message='Contract failed: \'getter = getattr(curve, "valueAt", Non...',
    )
    require(
        condition=('getter = getattr(curve, "value", None)' in source),
        message='Contract failed: \'getter = getattr(curve, "value", None)...',
    )
    require(
        condition=("tunic armhole curve has no native parameter evaluator" in source),
        message='Contract failed: "tunic armhole curve has no native para...',
    )
    require(
        condition=("tunic armhole arc lost authored %s" in source),
        message='Contract failed: "tunic armhole arc lost authored %s" in...',
    )
    sketch_builder = source.split("def _make_tunic_sketch(", 1)[1].split("\ndef _adopt_sketch", 1)[
        0
    ]
    require(
        condition=(
            'sketch.addConstraint([Sketcher.Constraint("Block", index) '
            "for index in range(len(geometry))])" in sketch_builder
        ),
        message="Contract failed: 'sketch.addConstraint([Sketcher.Constra...",
    )
    require(
        condition=('Sketcher.Constraint("Coincident"' not in sketch_builder),
        message="Contract failed: 'Sketcher.Constraint(\"Coincident\"' not ...",
    )
    require(
        condition=("tunic armhole collapsed during Sketcher recompute" in sketch_builder),
        message='Contract failed: "tunic armhole collapsed during Sketche...',
    )
    require(
        condition=("armhole_z = 0.62 * float(garment_height)" in sketch_builder),
        message='Contract failed: "armhole_z = 0.62 * float(garment_heigh...',
    )
    require(
        condition=("(x_offset + 0.74 * panel_width, armhole_z)" in sketch_builder),
        message='Contract failed: "(x_offset + 0.74 * panel_width, armhol...',
    )
    require(
        condition=("shoulder_z = 0.94 * float(garment_height)" in sketch_builder),
        message='Contract failed: "shoulder_z = 0.94 * float(garment_heig...',
    )
    require(
        condition=("(x_offset + 0.94 * panel_width, shoulder_z)" in sketch_builder),
        message='Contract failed: "(x_offset + 0.94 * panel_width, should...',
    )
    require(
        condition=("if not (armhole_z < shoulder_z < neck_z)" in sketch_builder),
        message='Contract failed: "if not (armhole_z < shoulder_z < neck_...',
    )
    require(
        condition=("shoulders must slope downward from neckline to shoulder tip" in sketch_builder),
        message='Contract failed: "shoulders must slope downward from nec...',
    )
    require(
        condition=("points[3][0] - points[2][0] < 0.15 * float(panel_width)" in sketch_builder),
        message='Contract failed: "points[3][0] - points[2][0] < 0.15 * f...',
    )
    require(
        condition=("shoulder_z - armhole_z < 0.20 * float(garment_height)" in sketch_builder),
        message='Contract failed: "shoulder_z - armhole_z < 0.20 * float(...',
    )
    require(
        condition=("side_ease_mm = 4.0" in sketch_builder),
        message='Contract failed: "side_ease_mm = 4.0" in sketch_builder',
    )
    require(
        condition=("if index == 1:" in sketch_builder),
        message='Contract failed: "if index == 1:" in sketch_builder',
    )
    require(
        condition=("elif index == 7:" in sketch_builder),
        message='Contract failed: "elif index == 7:" in sketch_builder',
    )
    require(
        condition=("0.5 * (start[0] + end[0]) + side_ease_mm" in sketch_builder),
        message='Contract failed: "0.5 * (start[0] + end[0]) + side_ease_...',
    )
    require(
        condition=("0.5 * (start[0] + end[0]) - side_ease_mm" in sketch_builder),
        message='Contract failed: "0.5 * (start[0] + end[0]) - side_ease_...',
    )
    require(
        condition=("(x_offset + 0.06 * panel_width, shoulder_z)" in sketch_builder),
        message='Contract failed: "(x_offset + 0.06 * panel_width, should...',
    )
    require(
        condition=("(x_offset + 0.26 * panel_width, armhole_z)" in sketch_builder),
        message='Contract failed: "(x_offset + 0.26 * panel_width, armhol...',
    )
    # Keep the inward-scooped arc inside the shoulder line; .73/.27 self-intersects.
    require(
        condition=("x_offset + 0.741 * panel_width, armhole_mid_z" in sketch_builder),
        message='Contract failed: "x_offset + 0.741 * panel_width, armhol...',
    )
    require(
        condition=("x_offset + 0.259 * panel_width, armhole_mid_z" in sketch_builder),
        message='Contract failed: "x_offset + 0.259 * panel_width, armhol...',
    )
    require(
        condition=("for edge_index, inward in ((2, -1.0), (6, 1.0))" in source),
        message='Contract failed: "for edge_index, inward in ((2, -1.0), ...',
    )
    require(
        condition=('boundary.kind != "arc" or len(boundary.samples) < 8' in source),
        message='Contract failed: \'boundary.kind != "arc" or len(boundary...',
    )
    require(
        condition=("armhole curve has insufficient inward clearance" in source),
        message='Contract failed: "armhole curve has insufficient inward ...',
    )
    require(
        condition=('front_edge_ids[1], back_edge_ids[1], "TunicRightSide", False' in source),
        message="Contract failed: 'front_edge_ids[1], back_edge_ids[1], \"...",
    )
    require(
        condition=('front_edge_ids[3], back_edge_ids[3], "TunicRightShoulder", False' in source),
        message="Contract failed: 'front_edge_ids[3], back_edge_ids[3], \"...",
    )
    require(
        condition=('front_edge_ids[5], back_edge_ids[5], "TunicLeftShoulder", False' in source),
        message="Contract failed: 'front_edge_ids[5], back_edge_ids[5], \"...",
    )
    require(
        condition=('front_edge_ids[7], back_edge_ids[7], "TunicLeftSide", False' in source),
        message="Contract failed: 'front_edge_ids[7], back_edge_ids[7], \"...",
    )
    require(
        condition=('front_edge_ids[2], back_edge_ids[2], "TunicRightArmhole"' not in source),
        message="Contract failed: 'front_edge_ids[2], back_edge_ids[2], \"...",
    )
    require(
        condition=('front_edge_ids[6], back_edge_ids[6], "TunicLeftArmhole"' not in source),
        message="Contract failed: 'front_edge_ids[6], back_edge_ids[6], \"...",
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
    require(
        condition=(state == {"schema": 1}),
        message='Contract failed: state == {"schema": 1}',
    )
    require(
        condition=("backend" not in state),
        message='Contract failed: "backend" not in state',
    )
    require(
        condition=("seam_stitch_pairs" not in state),
        message='Contract failed: "seam_stitch_pairs" not in state',
    )
    require(
        condition=("collision_surface" not in state),
        message='Contract failed: "collision_surface" not in state',
    )

    proxy.__setstate__(state)
    require(
        condition=(proxy.backend is None),
        message="Contract failed: proxy.backend is None",
    )
    require(
        condition=(proxy.panel_indices == {}),
        message="Contract failed: proxy.panel_indices == {}",
    )
    require(
        condition=(proxy.seam_stitch_pairs == {}),
        message="Contract failed: proxy.seam_stitch_pairs == {}",
    )
    require(
        condition=(proxy.source_signature is None),
        message="Contract failed: proxy.source_signature is None",
    )
    require(
        condition=(proxy.last_steps == 0),
        message="Contract failed: proxy.last_steps == 0",
    )
    require(
        condition=(proxy.collision_surface is None),
        message="Contract failed: proxy.collision_surface is None",
    )


def test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit() -> None:
    """Verify tunic realtime profile is bounded and mesh collision is explicit contract."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    require(
        condition=("ParticleDistance = 24.0" in source),
        message='Contract failed: "ParticleDistance = 24.0" in source',
    )
    require(
        condition=("SolverIterations = 8" in source),
        message='Contract failed: "SolverIterations = 8" in source',
    )
    require(
        condition=("SolverSubsteps = 4" in source),
        message='Contract failed: "SolverSubsteps = 4" in source',
    )
    require(
        condition=("CLOTH_PBD_COLLISION_MODE: mesh" in workflow),
        message='Contract failed: "CLOTH_PBD_COLLISION_MODE: mesh" in wor...',
    )
    require(
        condition=("CLOTH_PBD_COLLISION_VOXEL_MM=8.0" in workflow),
        message='Contract failed: "CLOTH_PBD_COLLISION_VOXEL_MM=8.0" in w...',
    )
    require(
        condition=("voxel_mm - 8.0" in source),
        message='Contract failed: "voxel_mm - 8.0" in source',
    )
    require(
        condition=("(span + 200.0) / 8.0" in source),
        message='Contract failed: "(span + 200.0) / 8.0" in source',
    )
    require(
        condition=("configured 8 mm voxel resolution" in source),
        message='Contract failed: "configured 8 mm voxel resolution" in s...',
    )
    tunic_workflow = workflow.split("  gui-tunic-visual:", 1)[1].split("  gui-turntables:", 1)[0]
    require(
        condition=("CLOTH_PBD_SUBSTEPS=16" in tunic_workflow),
        message='Contract failed: "CLOTH_PBD_SUBSTEPS=16" in tunic_workflow',
    )
    require(
        condition=('os.environ["CLOTH_PBD_COLLISION_VOXEL_MM"]' not in source),
        message="Contract failed: 'os.environ[\"CLOTH_PBD_COLLISION_VOXEL_...",
    )
    require(
        condition=("CLOTH_PBD_SUBSTEPS: 8" in workflow),
        message='Contract failed: "CLOTH_PBD_SUBSTEPS: 8" in workflow',
    )
    require(
        condition=('os.environ["CLOTH_PBD_SUBSTEPS"]' not in source),
        message="Contract failed: 'os.environ[\"CLOTH_PBD_SUBSTEPS\"]' not ...",
    )
    require(
        condition=("CLOTH_PBD_COLLISION_TOLERANCE_MM: 12" not in workflow),
        message='Contract failed: "CLOTH_PBD_COLLISION_TOLERANCE_MM: 12" ...',
    )
    require(
        condition=("tunic-collision-config target-thickness-mm=%.2f" in source),
        message='Contract failed: "tunic-collision-config target-thicknes...',
    )
    simulation_commands = (
        ROOT / "freecad_cloth" / "simulation" / "SimulationCommands.py"
    ).read_text(encoding="utf-8")
    require(
        condition=("DEFAULT_MANNEQUIN_COLLISION_THICKNESS_MM" in simulation_commands),
        message='Contract failed: "DEFAULT_MANNEQUIN_COLLISION_THICKNESS_...',
    )
    require(
        condition=("tunic-simulation-start" in source),
        message='Contract failed: "tunic-simulation-start" in source',
    )
    require(
        condition=(
            'configured_substeps = int(os.environ.get("CLOTH_PBD_SUBSTEPS", "8"))' in source
        ),
        message="Contract failed: 'configured_substeps = int(os.environ.g...",
    )
    require(
        condition=('effective_substeps = int(getattr(active_backend, "_substeps", -1))' in source),
        message="Contract failed: 'effective_substeps = int(getattr(activ...",
    )
    require(
        condition=("effective_substeps != configured_substeps" in source),
        message='Contract failed: "effective_substeps != configured_subst...',
    )
    require(
        condition=("backend_substeps=%d configured_substeps=%d" in source),
        message='Contract failed: "backend_substeps=%d configured_substep...',
    )
    require(
        condition=("realtime-preview=passed backend=position-based-dynamics" in source),
        message='Contract failed: "realtime-preview=passed backend=positi...',
    )
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    require(
        condition=("tools/ci/validate_manifests.py tunic-production" in workflow),
        message='Contract failed: "tools/ci/validate_manifests.py tunic-p...',
    )
    validator = (ROOT / "tools" / "ci" / "validate_manifests.py").read_text(encoding="utf-8")
    require(
        condition=("def validate_tunic_production()" in validator),
        message='Contract failed: "def validate_tunic_production()" in va...',
    )
    require(
        condition=("runtime collision configuration evidence is invalid" in validator),
        message='Contract failed: "runtime collision configuration eviden...',
    )
    require(
        condition=("expected_resolution = tuple(" in validator),
        message='Contract failed: "expected_resolution = tuple(" in valid...',
    )
    require(
        condition=("def _validate_realtime_metrics(data: dict)" in validator),
        message='Contract failed: "def _validate_realtime_metrics(data: d...',
    )
    require(
        condition=("_validate_realtime_metrics(data)" in validator),
        message='Contract failed: "_validate_realtime_metrics(data)" in v...',
    )
    require(
        condition=("PBD SDF voxel must be 8 mm" in validator),
        message='Contract failed: "PBD SDF voxel must be 8 mm" in validator',
    )


def test_pbd_collision_body_uses_coarsened_solver_surface() -> None:
    """Verify pbd collision body uses coarsened solver surface contract."""
    backend = (ROOT / "freecad_cloth" / "simulation" / "PositionBasedDynamicsBackend.py").read_text(
        encoding="utf-8"
    )
    start = backend.index("    def _add_collision_body(")
    end = backend.index("    def _build(", start)
    body_builder = backend[start:end]
    require(
        condition=("collision_surface = self._collision_surface" in body_builder),
        message='Contract failed: "collision_surface = self._collision_su...',
    )
    require(
        condition=("collision_surface = self._source_collision_surface" not in body_builder),
        message='Contract failed: "collision_surface = self._source_colli...',
    )


def test_pbd_collision_sdf_resolution_and_tolerance_are_explicit() -> None:
    """Verify pbd collision sdf resolution and tolerance are explicit contract."""
    backend = (ROOT / "freecad_cloth" / "simulation" / "PositionBasedDynamicsBackend.py").read_text(
        encoding="utf-8"
    )
    require(
        condition=("CLOTH_PBD_COLLISION_VOXEL_MM" in backend),
        message='Contract failed: "CLOTH_PBD_COLLISION_VOXEL_MM" in backend',
    )
    require(
        condition=("def _pbd_collision_resolution(surface: CollisionSurface)" in backend),
        message='Contract failed: "def _pbd_collision_resolution(surface:...',
    )
    require(
        condition=("generateSDF(" in backend),
        message='Contract failed: "generateSDF(" in backend',
    )
    require(
        condition=("resolution," in backend),
        message='Contract failed: "resolution," in backend',
    )
    require(
        condition=("representation_margin = 0.5 * _pbd_collision_voxel_mm()" in backend),
        message='Contract failed: "representation_margin = 0.5 * _pbd_col...',
    )
    require(
        condition=("max(configured, thickness, representation_margin)" in backend),
        message='Contract failed: "max(configured, thickness, representat...',
    )
    require(
        condition=(
            "self._collision_sdf_resolution = tuple(int(axis) for axis in resolution)" in backend
        ),
        message='Contract failed: "self._collision_sdf_resolution = tuple...',
    )
    require(
        condition=("effective_tolerance_mm / _MM" in backend),
        message='Contract failed: "effective_tolerance_mm / _MM" in backend',
    )
    require(
        condition=("cloth-pbd-collision-config " in backend),
        message='Contract failed: "cloth-pbd-collision-config " in backend',
    )
    require(
        condition=(
            backend.index("timestep.step(self._model)")
            < backend.index("self._project_collision_positions()")
        ),
        message='Contract failed: backend.index("timestep.step(self._mode...',
    )
    require(
        condition=("particles.setPosition(" in backend),
        message='Contract failed: "particles.setPosition(" in backend',
    )
    require(
        condition=("inward_speed < 0.0" in backend),
        message='Contract failed: "inward_speed < 0.0" in backend',
    )
    require(
        condition=("project_stitched_pairs(" in backend),
        message='Contract failed: "project_stitched_pairs(" in backend',
    )
    require(
        condition=(backend.index("project_stitched_pairs(") < backend.index("moved_indices =")),
        message='Contract failed: backend.index("project_stitched_pairs("...',
    )


def test_pbd_collision_sdf_is_cached_outside_backend_instance() -> None:
    """Verify pbd collision sdf is cached outside backend instance contract."""
    backend = (ROOT / "freecad_cloth" / "simulation" / "PositionBasedDynamicsBackend.py").read_text(
        encoding="utf-8"
    )
    require(
        condition=("_PBD_COLLISION_SDF_CACHE_KEY" in backend),
        message='Contract failed: "_PBD_COLLISION_SDF_CACHE_KEY" in backend',
    )
    require(
        condition=("_PBD_COLLISION_SDF_CACHE" in backend),
        message='Contract failed: "_PBD_COLLISION_SDF_CACHE" in backend',
    )
    require(
        condition=("cache-hit" in backend),
        message='Contract failed: "cache-hit" in backend',
    )
    require(
        condition=("generateSDF(" in backend),
        message='Contract failed: "generateSDF(" in backend',
    )
    require(
        condition=("self._collision_sdf" in backend),
        message='Contract failed: "self._collision_sdf" in backend',
    )


def test_pbd_sdf_cache_key_is_stable_and_geometry_sensitive() -> None:
    """Verify pbd sdf cache key is stable and geometry sensitive contract."""
    backend_module = import_module("freecad_cloth.simulation.PositionBasedDynamicsBackend")
    cache_key_attribute = "_pbd_collision_sdf_cache_key"
    collision_sdf_cache_key = cast(
        "Callable[[CollisionSurface, list[int]], object]",
        getattr(backend_module, cache_key_attribute),
    )

    surface = CollisionSurface(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ((0, 1, 2),),
        thickness=1.0,
    ).validate()
    key = collision_sdf_cache_key(surface, [16, 16, 16])
    require(
        condition=(key == collision_sdf_cache_key(surface, [16, 16, 16])),
        message="Contract failed: key == _pbd_collision_sdf_cache_key(sur...",
    )

    moved = CollisionSurface(
        ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ((0, 1, 2),),
        thickness=1.0,
    ).validate()
    require(
        condition=(key != collision_sdf_cache_key(moved, [16, 16, 16])),
        message="Contract failed: key != _pbd_collision_sdf_cache_key(mov...",
    )
    require(
        condition=(key != collision_sdf_cache_key(surface, [17, 16, 16])),
        message="Contract failed: key != _pbd_collision_sdf_cache_key(sur...",
    )


def test_pbd_ci_image_is_pinned_and_preinstalled() -> None:
    """Verify pbd ci image is pinned and preinstalled contract."""
    dockerfile = (ROOT / "docker" / "freecad-ci" / "Dockerfile").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    require(
        condition=("pypbd==2.2.2" in dockerfile),
        message='Contract failed: "pypbd==2.2.2" in dockerfile',
    )
    require(
        condition=("triangle==20250106" in dockerfile),
        message='Contract failed: "triangle==20250106" in dockerfile',
    )
    require(
        condition=("/opt/pypbd-provenance.txt" in dockerfile),
        message='Contract failed: "/opt/pypbd-provenance.txt" in dockerfile',
    )
    require(
        condition=("makehuman-hm08-base.obj" in dockerfile),
        message='Contract failed: "makehuman-hm08-base.obj" in dockerfile',
    )
    require(
        condition=(
            "FREECAD_CLOTH_AVATAR_MESH=/opt/freecad-cloth/assets/makehuman-hm08-base.obj"
            in dockerfile
        ),
        message='Contract failed: "FREECAD_CLOTH_AVATAR_MESH=/opt/freecad...',
    )
    require(
        condition=(
            "1f508f6083b2f823dab15de924b3bde72e08d77c9/makehuman/data/3dobjs/base.obj" in dockerfile
        ),
        message='Contract failed: "1f508f6083b2f823dab15de924b3bde72e08d7...',
    )
    require(
        condition=(
            "8e761e6624b8f54536409135d1636da63b32486a90d4897f84e121d144f6fb4c" in dockerfile
        ),
        message='Contract failed: "8e761e6624b8f54536409135d1636da63b3248...',
    )
    require(
        condition=("pbd_validation_image:" in workflow),
        message='Contract failed: "pbd_validation_image:" in workflow',
    )
    require(
        condition=("FREECAD_PBD_IMAGE" in workflow),
        message='Contract failed: "FREECAD_PBD_IMAGE" in workflow',
    )
    require(
        condition=("CLOTH_CI_ENABLE_PBD: 1" in workflow),
        message='Contract failed: "CLOTH_CI_ENABLE_PBD: 1" in workflow',
    )
    gui = workflow.split("  gui-tunic-visual:", 1)[1].split("  gui-turntables:", 1)[0]
    require(
        condition=("image: ${{ env.FREECAD_PBD_IMAGE }}" in gui),
        message='Contract failed: "image: ${{ env.FREECAD_PBD_IMAGE }}" i...',
    )
    require(
        condition=("capture_pypbd_provenance.py" in gui),
        message='Contract failed: "capture_pypbd_provenance.py" in gui',
    )
    require(
        condition=("artifacts/pypbd-provenance.txt" in gui),
        message='Contract failed: "artifacts/pypbd-provenance.txt" in gui',
    )


def test_production_tunic_audit_runs_even_if_performance_gate_fails() -> None:
    """Verify production tunic audit runs even if performance gate fails contract."""
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    gui = workflow.split("  gui-tunic-visual:", 1)[1].split("  gui-turntables:", 1)[0]
    benchmark = gui.split(
        "      - uses: Uhrendoktor/freecad-cloth/.github/actions/freecad-test@", 1
    )[1].split("      - name: Independently validate realtime performance metrics", 1)[0]
    require(
        condition=("test-script: tests/freecad_realtime_benchmark.py" in benchmark),
        message='Contract failed: "test-script: tests/freecad_realtime_be...',
    )
    require(
        condition=("CLOTH_REALTIME_FRAMES=120" in benchmark),
        message='Contract failed: "CLOTH_REALTIME_FRAMES=120" in benchmark',
    )
    require(
        condition=(
            "tools/ci/validate_realtime_benchmark.py artifacts/freecad-realtime/metrics.json" in gui
        ),
        message='Contract failed: "tools/ci/validate_realtime_benchmark.p...',
    )
    audit_step = gui.split("      - uses: ./.github/actions/freecad-test", 1)[1]
    require(
        condition=("if: always()" in audit_step.split("test-script:", 1)[0]),
        message='Contract failed: "if: always()" in audit_step.split("tes...',
    )
    require(
        condition=("test-script: tests/freecad_tunic_audit_production.py" in audit_step),
        message='Contract failed: "test-script: tests/freecad_tunic_audit...',
    )
    validator = (ROOT / "tools" / "ci" / "validate_realtime_benchmark.py").read_text(
        encoding="utf-8"
    )
    require(
        condition=("p95_frame_interval_ms exceeds the 30 FPS budget" in validator),
        message='Contract failed: "p95_frame_interval_ms exceeds the 30 F...',
    )


def test_production_tunic_wrapper_dispatches_in_freecad_macro_host() -> None:
    """Verify production tunic wrapper dispatches in freecad macro host contract."""
    wrapper = (ROOT / "tests" / "freecad_tunic_audit_production.py").read_text(encoding="utf-8")
    require(
        condition=('importlib.import_module("freecad_tunic_audit").main' in wrapper),
        message="Contract failed: 'importlib.import_module(\"freecad_tunic...",
    )
    require(
        condition=("main()" in wrapper),
        message='Contract failed: "main()" in wrapper',
    )
    require(
        condition=('if __name__ == "__main__"' not in wrapper),
        message="Contract failed: 'if __name__ == \"__main__\"' not in wrapper",
    )


def test_canonical_tunic_fixture_matches_validated_start_geometry() -> None:
    """Verify canonical tunic fixture matches validated start geometry contract."""
    audit = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    audit_entry = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    require(
        condition=("CLOTH_TUNIC_AUDIT_PROFILE" in audit_entry),
        message='Contract failed: "CLOTH_TUNIC_AUDIT_PROFILE" in audit_entry',
    )
    require(
        condition=("TUNIC_PRODUCTION_AUDIT" in audit),
        message='Contract failed: "TUNIC_PRODUCTION_AUDIT" in audit',
    )
    require(
        condition=("SEAM_SOURCE = " not in audit_entry),
        message='Contract failed: "SEAM_SOURCE = " not in audit_entry',
    )
    require(
        condition=("required_indices = (1, 3, 5, 7)" in audit),
        message='Contract failed: "required_indices = (1, 3, 5, 7)" in audit',
    )
    require(
        condition=("TunicRightShoulder" in audit),
        message='Contract failed: "TunicRightShoulder" in audit',
    )
    require(
        condition=("TunicLeftShoulder" in audit),
        message='Contract failed: "TunicLeftShoulder" in audit',
    )
    require(
        condition=("ParticleDistance = 24.0" in audit),
        message='Contract failed: "ParticleDistance = 24.0" in audit',
    )
    require(
        condition=("SolverIterations = 8" in audit),
        message='Contract failed: "SolverIterations = 8" in audit',
    )
    require(
        condition=("SolverSubsteps = 4 if TUNIC_PRODUCTION_AUDIT else 1" in audit),
        message='Contract failed: "SolverSubsteps = 4 if TUNIC_PRODUCTION...',
    )
    require(
        condition=("tunic-simulation-start" in audit),
        message='Contract failed: "tunic-simulation-start" in audit',
    )
    require(
        condition=("realtime-preview=passed backend=position-based-dynamics" in audit),
        message='Contract failed: "realtime-preview=passed backend=positi...',
    )


def test_tunic_penetration_audit_uses_safe_numpy_ray_parity_in_freecad_host() -> None:
    """Verify tunic penetration audit uses safe numpy ray parity in freecad host contract."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    inside_check = source.split("def _inside_target_count(", 1)[1].split(
        "\ndef write_drape_metrics(", 1
    )[0]
    require(
        condition=("Trimesh/Rtree's native contains query" in inside_check),
        message='Contract failed: "Trimesh/Rtree\'s native contains query"...',
    )
    require(
        condition=("target_mesh.contains" not in inside_check),
        message='Contract failed: "target_mesh.contains" not in inside_check',
    )
    require(
        condition=("import trimesh" not in inside_check),
        message='Contract failed: "import trimesh" not in inside_check',
    )
    require(
        condition=("chunk_size=4" in inside_check),
        message='Contract failed: "chunk_size=4" in inside_check',
    )
    require(
        condition=("points_inside_closed_mesh(" in inside_check),
        message='Contract failed: "points_inside_closed_mesh(" in inside_...',
    )
    require(
        condition=("prefer_trimesh=False" in inside_check),
        message='Contract failed: "prefer_trimesh=False" in inside_check',
    )
    require(
        condition=("penetration-check=numpy-ray-parity" in inside_check),
        message='Contract failed: "penetration-check=numpy-ray-parity" in...',
    )
    sanity = (ROOT / "freecad_cloth" / "simulation" / "DrapeVisualSanity.py").read_text(
        encoding="utf-8"
    )
    require(
        condition=("prefer_trimesh: bool = True" in sanity),
        message='Contract failed: "prefer_trimesh: bool = True" in sanity',
    )
    require(
        condition=("if prefer_trimesh:" in sanity),
        message='Contract failed: "if prefer_trimesh:" in sanity',
    )
    require(
        condition=("np.einsum" in sanity),
        message='Contract failed: "np.einsum" in sanity',
    )


def test_penetration_evidence_stays_on_numpy_path_in_freecad_host() -> None:
    """Verify penetration evidence stays on numpy path in freecad host contract."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    audit = source.split("def write_drape_metrics(", 1)[1].split("\ndef _arc_through_midpoint(", 1)[
        0
    ]
    evidence = audit.split("inside_points = []", 1)[1].split(
        'log(\n                    "penetration-evidence', 1
    )[0]

    require(
        condition=(
            "from freecad_cloth.simulation.DrapeVisualSanity import point_inside_closed_mesh"
            not in audit
        ),
        message='Contract failed: "from freecad_cloth.simulation.DrapeVis...',
    )
    require(
        condition=(evidence.count("prefer_trimesh=False") == _EXPECTED_TRIMESH_OVERRIDE_COUNT),
        message='Contract failed: evidence.count("prefer_trimesh=False") ...',
    )
    require(
        condition=("points_inside_closed_mesh(" in evidence),
        message='Contract failed: "points_inside_closed_mesh(" in evidence',
    )
    require(
        condition=("point_inside_closed_mesh(" not in evidence),
        message='Contract failed: "point_inside_closed_mesh(" not in evid...',
    )


def test_tunic_visual_diagnostics_are_authoritative_after_persistence() -> None:
    """Verify tunic visual diagnostics are authoritative after persistence contract."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    metrics_write = source.index("json.dump(payload, handle, indent=2, sort_keys=True)")
    gate = source.index('allowed_diagnostics={"below-hem-candidate"}')
    screenshot = source.index('f"cloth-simulation-draped-{direction}.png"')
    require(
        condition=(metrics_write < screenshot < gate),
        message="Contract failed: metrics_write < screenshot < gate",
    )


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
            '("back", "front") if TUNIC_PRODUCTION_AUDIT else ("front", "back")',
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
            "neckline_drop=0.03",
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
    require(
        condition=("drape-metrics=" in source[:gate]),
        message='Contract failed: "drape-metrics=" in source[:gate]',
    )
    missing_manifest = "gui-screenshot-manifest" not in source[gate:]
    shows_task_dock = "task_dock.show()" in source[gate:]
    require(
        condition=missing_manifest or shows_task_dock,
        message='Contract failed: "gui-screenshot-manifest" not in source...',
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
    require(
        condition=(expected_constraint in fixture),
        message="Contract failed: expected_constraint in fixture",
    )
    require(
        condition=('Sketcher.Constraint("Coincident"' not in fixture),
        message="Contract failed: 'Sketcher.Constraint(\"Coincident\"' not ...",
    )


def test_tunic_scene_dossier_logs_sampled_topology_before_simulation() -> None:
    """The actual CI fixture must emit geometry evidence before downstream evaluation."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    simulation = source.split("def simulation():", 1)[1]
    topology_audit = simulation.index("def log_tunic_outline_topology(piece):")
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

    require(
        condition=(
            topology_audit
            < sample_resolution
            < pattern_view
            < sewing_view
            < native_gate
            < simulation_start
        ),
        message="Contract failed: topology_audit < sample_resolution < pa...",
    )
    require(
        condition=('"boundary-order=%r near-crossing=%r"' in simulation),
        message="Contract failed: '\"boundary-order=%r near-crossing=%r\"' ...",
    )
    require(
        condition=("samples," in simulation),
        message='Contract failed: "samples," in simulation',
    )
    # Keep geometric validity guards in FreeCAD, but keep report classification on the host.
    require(
        condition=(
            "canonical tunic derived pattern outline is invalid before simulation" in simulation
        ),
        message='Contract failed: "canonical tunic derived pattern outlin...',
    )
    require(
        condition=("fit_assessment" not in simulation),
        message='Contract failed: "fit_assessment" not in simulation',
    )
    require(
        condition=("review_required" not in simulation),
        message='Contract failed: "review_required" not in simulation',
    )
    require(
        condition=('status["result"]' not in simulation),
        message="Contract failed: 'status[\"result\"]' not in simulation",
    )
