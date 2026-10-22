# Copyright (C) 2026 FreeCAD Cloth contributors
"""Static contracts for the canonical tunic fixture and PBD evidence gates."""

import subprocess
import sys
from pathlib import Path

from tests.support.assertions import require

ROOT: Path = Path(__file__).resolve().parents[1]


# The native-Sketcher fixture keeps explicit semantic edge IDs on each piece.
# The front/back pieces share the same authored topology, so corresponding shoulder
# and side edges must be paired by semantic position, not cross-paired.


def test_canonical_tunic_pairs_matching_front_back_semantic_edges() -> None:
    """Require matching front/back semantic edge IDs for the authored tunic panels."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    require(
        condition="front_edge_ids = tuple(" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="back_edge_ids = tuple(" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='"SemanticEdgeIds"' in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='front_edge_ids[1], back_edge_ids[1], "TunicRightSide"' in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='front_edge_ids[3], back_edge_ids[3], "TunicRightShoulder"' in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='front_edge_ids[5], back_edge_ids[5], "TunicLeftShoulder"' in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='front_edge_ids[7], back_edge_ids[7], "TunicLeftSide"' in source,
        message="Tunic audit source contract failed.",
    )


def test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline() -> None:
    """Verify the tunic fixture uses avatar arrangement points and leaves the neckline unpinned."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    require(
        condition="ArrangementPoint.from_string" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='shoulder_left = arrangement_world("shoulder_left")' in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='shoulder_right = arrangement_world("shoulder_right")' in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='hip_point = arrangement_world("hip")' in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='os.environ["CLOTH_PBD_COLLISION_MODE"] = "mesh"' in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="status = target_status(target)" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='scene.PinMode = "None"' in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='scene.PinMode = "Explicit"' not in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="scene.PinSelection = []" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="scene.PinSelection = [str(index) for index in expected_pins]" not in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="if solver_pins:" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="base_proxy_getter().source_signature = None" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="tunic-neckline-midpoint piece=%s particle=%d snap-mm=%.2f" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="panel_indices.get(panel.Name, ())" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='panel_objects = tuple(getattr(scene, "DrapePanels", ()))' in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="scene.touch()" in source,
        message="Tunic audit source contract failed.",
    )
    initial_piece_links = source.index("scene.ClothPieces = [front, back]")
    initial_cache_invalidation = source.index("base_proxy_getter().source_signature = None")
    first_panel_map = source.index('panel_piece_names = getattr(proxy, "panel_piece_names", {})')
    require(
        condition=initial_piece_links < initial_cache_invalidation < first_panel_map,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="tunic-simulation-panel-map proxy=%s links=%d panels=%r map=%r particles=%d" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="canonical tunic simulation did not build an authored pattern panel" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="def _neckline_boundary_particles(" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='"semantic-chain-endpoints"' in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='"authored-edge-projection"' in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition=(
            (
            "tunic-neckline-resolution piece=%s edge=%s method=%s chains=%d endpoint-error-mm=%.6f"
            in source
            )
        ),
        message="Tunic audit source contract failed.",
    )
    require(
        condition="boundary_index >= len(boundary_chains)" not in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="nearest_target_clearance" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="step0-target-vertex-clearance-mm=" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="authored_shoulder_pins" not in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="scene.PinSelection = [str(i) for i in front_pins]" not in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="target_surface = collision_surface(" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="target_source.Mesh.BoundBox" not in source,
        message="Tunic audit source contract failed.",
    )


def test_canonical_tunic_uses_matching_authored_mapping() -> None:
    """Verify the canonical fixture maps each front edge to its matching back edge."""
    audit = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    require(
        condition="required_indices = (1, 3, 5, 7)" in audit,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='front_edge_ids[1], back_edge_ids[1], "TunicRightSide"' in audit,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='front_edge_ids[3], back_edge_ids[3], "TunicRightShoulder"' in audit,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='front_edge_ids[5], back_edge_ids[5], "TunicLeftShoulder"' in audit,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='front_edge_ids[7], back_edge_ids[7], "TunicLeftSide"' in audit,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='front_edge_ids[3], back_edge_ids[5], "TunicRightShoulder"' not in audit,
        message="Tunic audit source contract failed.",
    )


def test_canonical_tunic_shared_source_syntax_compiles() -> None:
    """Verify the shared tunic-audit source passes its standalone syntax check."""
    audit_path = ROOT / "tests" / "freecad_tunic_audit.py"
    result = subprocess.run(
        [sys.executable, str(audit_path), "--syntax-check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    require(
        condition=result.returncode == 0,
        message=(
"shared tunic source syntax gate failed\n"
f"stdout:\n{result.stdout}\n"
f"stderr:\n{result.stderr}"
),
    )
    require(
        condition="tunic-audit-source-syntax=passed" in result.stdout,
        message="Tunic audit source contract failed.",
    )


def test_canonical_tunic_authoritative_gate_is_fail_closed() -> None:
    """Verify the authoritative seam and collision gates fail closed when their limits are exceeded."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    require(
        condition='os.environ["CLOTH_PBD_COLLISION_MODE"] = "mesh"' in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="proxy=proxy" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="authoritative tunic seams did not converge" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="if max_seam_gap > 35.0" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="authoritative-seam-gap seam=%s" in source,
        message="Tunic audit source contract failed.",
    )


def test_canonical_tunic_has_two_curved_open_armholes() -> None:
    """Verify the canonical pattern retains two valid curved armholes."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    require(
        condition="elif index == 2:" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="elif index == 6:" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="def _arc_through_midpoint(" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="Part.ArcOfCircle(circle, start_angle, start_angle + sweep)" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="zero_point = curve_value(circle, 0.0)" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="quarter_point = curve_value(circle, math.pi / 2.0)" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='getter = getattr(curve, "valueAt", None)' in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='getter = getattr(curve, "value", None)' in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="tunic armhole curve has no native parameter evaluator" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="tunic armhole arc lost authored %s" in source,
        message="Tunic audit source contract failed.",
    )
    sketch_builder = source.split("def _make_tunic_sketch(", 1)[1].split("\ndef _adopt_sketch", 1)[
        0
    ]
    require(
        condition=(
            (
            'sketch.addConstraint([Sketcher.Constraint("Block", index) '
            "for index in range(len(geometry))])"
            ) in sketch_builder
        ),
        message="Tunic audit source contract failed.",
    )
    require(
        condition='Sketcher.Constraint("Coincident"' not in sketch_builder,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="tunic armhole collapsed during Sketcher recompute" in sketch_builder,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="armhole_z = 0.62 * float(garment_height)" in sketch_builder,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="(x_offset + 0.74 * panel_width, armhole_z)" in sketch_builder,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="shoulder_z = 0.94 * float(garment_height)" in sketch_builder,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="(x_offset + 0.94 * panel_width, shoulder_z)" in sketch_builder,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="if not (armhole_z < shoulder_z < neck_z)" in sketch_builder,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="shoulders must slope downward from neckline to shoulder tip" in sketch_builder,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="points[3][0] - points[2][0] < 0.15 * float(panel_width)" in sketch_builder,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="shoulder_z - armhole_z < 0.20 * float(garment_height)" in sketch_builder,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="side_ease_mm = 4.0" in sketch_builder,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="if index == 1:" in sketch_builder,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="elif index == 7:" in sketch_builder,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="0.5 * (start[0] + end[0]) + side_ease_mm" in sketch_builder,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="0.5 * (start[0] + end[0]) - side_ease_mm" in sketch_builder,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="(x_offset + 0.06 * panel_width, shoulder_z)" in sketch_builder,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="(x_offset + 0.26 * panel_width, armhole_z)" in sketch_builder,
        message="Tunic audit source contract failed.",
    )
    # Keep the inward-scooped arc inside the shoulder line; .73/.27 self-intersects.
    require(
        condition="x_offset + 0.741 * panel_width, armhole_mid_z" in sketch_builder,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="x_offset + 0.259 * panel_width, armhole_mid_z" in sketch_builder,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="for edge_index, inward in ((2, -1.0), (6, 1.0))" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='boundary.kind != "arc" or len(boundary.samples) < 8' in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="armhole curve has insufficient inward clearance" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='front_edge_ids[1], back_edge_ids[1], "TunicRightSide", False' in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='front_edge_ids[3], back_edge_ids[3], "TunicRightShoulder", False' in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='front_edge_ids[5], back_edge_ids[5], "TunicLeftShoulder", False' in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='front_edge_ids[7], back_edge_ids[7], "TunicLeftSide", False' in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='front_edge_ids[2], back_edge_ids[2], "TunicRightArmhole"' not in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='front_edge_ids[6], back_edge_ids[6], "TunicLeftArmhole"' not in source,
        message="Tunic audit source contract failed.",
    )


def test_simulation_proxy_serializes_only_rebuildable_metadata() -> None:
    """Verify simulation proxies persist rebuildable metadata rather than native runtime state."""
    from freecad_cloth.simulation.SimulationObjects import SimulationProxy

    proxy = SimulationProxy()
    proxy.backend = object()
    proxy.panel_indices = {"panel": (1, 2)}
    proxy.seam_stitch_pairs = {"seam": ((0, 1),)}
    proxy.source_signature = ("derived",)
    proxy.last_steps = 17
    proxy.collision_surface = object()

    state = proxy.__getstate__()
    require(
        condition=state == {"schema": 1},
        message="Tunic audit source contract failed.",
    )
    require(
        condition="backend" not in state,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="seam_stitch_pairs" not in state,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="collision_surface" not in state,
        message="Tunic audit source contract failed.",
    )

    proxy.__setstate__(state)
    require(
        condition=proxy.backend is None,
        message="Tunic audit source contract failed.",
    )
    require(
        condition=proxy.panel_indices == {},
        message="Tunic audit source contract failed.",
    )
    require(
        condition=proxy.seam_stitch_pairs == {},
        message="Tunic audit source contract failed.",
    )
    require(
        condition=proxy.source_signature is None,
        message="Tunic audit source contract failed.",
    )
    require(
        condition=proxy.last_steps == 0,
        message="Tunic audit source contract failed.",
    )
    require(
        condition=proxy.collision_surface is None,
        message="Tunic audit source contract failed.",
    )


def test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit() -> None:
    """Verify the documented real-time simulation profile is bounded and uses mesh collision."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    require(
        condition="ParticleDistance = 24.0" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="SolverIterations = 8" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="SolverSubsteps = 4" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="CLOTH_PBD_COLLISION_MODE: mesh" in workflow,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="CLOTH_PBD_COLLISION_VOXEL_MM=8.0" in workflow,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="voxel_mm - 8.0" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="(span + 200.0) / 8.0" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="configured 8 mm voxel resolution" in source,
        message="Tunic audit source contract failed.",
    )
    tunic_workflow = workflow.split("  gui-tunic-visual:", 1)[1].split("  gui-turntables:", 1)[0]
    require(
        condition="CLOTH_PBD_SUBSTEPS=16" in tunic_workflow,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='os.environ["CLOTH_PBD_COLLISION_VOXEL_MM"]' not in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="CLOTH_PBD_SUBSTEPS: 8" in workflow,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='os.environ["CLOTH_PBD_SUBSTEPS"]' not in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="CLOTH_PBD_COLLISION_TOLERANCE_MM: 12" not in workflow,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="tunic-collision-config target-thickness-mm=%.2f" in source,
        message="Tunic audit source contract failed.",
    )
    simulation_commands = (
        ROOT / "freecad_cloth" / "simulation" / "SimulationCommands.py"
    ).read_text(encoding="utf-8")
    require(
        condition="DEFAULT_MANNEQUIN_COLLISION_THICKNESS_MM" in simulation_commands,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="tunic-simulation-start" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='configured_substeps = int(os.environ.get("CLOTH_PBD_SUBSTEPS", "8"))' in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='effective_substeps = int(getattr(active_backend, "_substeps", -1))' in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="effective_substeps != configured_substeps" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="backend_substeps=%d configured_substeps=%d" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="realtime-preview=passed backend=position-based-dynamics" in source,
        message="Tunic audit source contract failed.",
    )
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    require(
        condition="tools/ci/validate_manifests.py tunic-production" in workflow,
        message="Tunic audit source contract failed.",
    )
    validator = (ROOT / "tools" / "ci" / "validate_manifests.py").read_text(encoding="utf-8")
    require(
        condition="def validate_tunic_production()" in validator,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="runtime collision configuration evidence is invalid" in validator,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="expected_resolution = tuple(" in validator,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="def _validate_realtime_metrics(data: dict)" in validator,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="_validate_realtime_metrics(data)" in validator,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="PBD SDF voxel must be 8 mm" in validator,
        message="Tunic audit source contract failed.",
    )


def test_pbd_collision_body_uses_coarsened_solver_surface() -> None:
    """Verify the PBD collision body uses the explicit coarsened solver surface."""
    backend = (ROOT / "freecad_cloth" / "simulation" / "PositionBasedDynamicsBackend.py").read_text(
        encoding="utf-8"
    )
    start = backend.index("    def _add_collision_body(")
    end = backend.index("    def _build(", start)
    body_builder = backend[start:end]
    require(
        condition="collision_surface = self._collision_surface" in body_builder,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="collision_surface = self._source_collision_surface" not in body_builder,
        message="Tunic audit source contract failed.",
    )


def test_pbd_collision_sdf_resolution_and_tolerance_are_explicit() -> None:
    """Verify collision SDF resolution and tolerance remain explicit in the source contract."""
    backend = (ROOT / "freecad_cloth" / "simulation" / "PositionBasedDynamicsBackend.py").read_text(
        encoding="utf-8"
    )
    require(
        condition="CLOTH_PBD_COLLISION_VOXEL_MM" in backend,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="def _pbd_collision_resolution(surface: CollisionSurface)" in backend,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="generateSDF(" in backend,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="resolution," in backend,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="representation_margin = 0.5 * _pbd_collision_voxel_mm()" in backend,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="max(configured, thickness, representation_margin)" in backend,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="self._collision_sdf_resolution = tuple(int(axis) for axis in resolution)" in backend,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="effective_tolerance_mm / _MM" in backend,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="cloth-pbd-collision-config " in backend,
        message="Tunic audit source contract failed.",
    )
    require(
        condition=(
            backend.index("timestep.step(self._model)") < backend.index(
            "self._project_collision_positions()"
            )
        ),
        message="Tunic audit source contract failed.",
    )
    require(
        condition="particles.setPosition(" in backend,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="inward_speed < 0.0" in backend,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="project_stitched_pairs(" in backend,
        message="Tunic audit source contract failed.",
    )
    require(
        condition=backend.index("project_stitched_pairs(") < backend.index("moved_indices ="),
        message="Tunic audit source contract failed.",
    )


def test_pbd_collision_sdf_is_cached_outside_backend_instance() -> None:
    """Verify collision SDF cache ownership is independent of backend instances."""
    backend = (ROOT / "freecad_cloth" / "simulation" / "PositionBasedDynamicsBackend.py").read_text(
        encoding="utf-8"
    )
    require(
        condition="_PBD_COLLISION_SDF_CACHE_KEY" in backend,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="_PBD_COLLISION_SDF_CACHE" in backend,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="cache-hit" in backend,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="generateSDF(" in backend,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="self._collision_sdf" in backend,
        message="Tunic audit source contract failed.",
    )


def test_pbd_sdf_cache_key_is_stable_and_geometry_sensitive() -> None:
    """Verify SDF cache keys remain stable and respond to geometry changes."""
    from freecad_cloth.shared.collision import CollisionSurface
    from freecad_cloth.simulation.PositionBasedDynamicsBackend import (
        _pbd_collision_sdf_cache_key,
    )

    surface = CollisionSurface(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ((0, 1, 2),),
        thickness=1.0,
    ).validate()
    key = _pbd_collision_sdf_cache_key(surface, [16, 16, 16])
    require(
        condition=key == _pbd_collision_sdf_cache_key(surface, [16, 16, 16]),
        message="Tunic audit source contract failed.",
    )

    moved = CollisionSurface(
        ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ((0, 1, 2),),
        thickness=1.0,
    ).validate()
    require(
        condition=key != _pbd_collision_sdf_cache_key(moved, [16, 16, 16]),
        message="Tunic audit source contract failed.",
    )
    require(
        condition=key != _pbd_collision_sdf_cache_key(surface, [17, 16, 16]),
        message="Tunic audit source contract failed.",
    )


def test_pbd_ci_image_is_pinned_and_preinstalled() -> None:
    """Verify CI uses the pinned, preinstalled PBD runtime image."""
    dockerfile = (ROOT / "docker" / "freecad-ci" / "Dockerfile").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    require(
        condition="pypbd==2.2.2" in dockerfile,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="triangle==20250106" in dockerfile,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="/opt/pypbd-provenance.txt" in dockerfile,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="makehuman-hm08-base.obj" in dockerfile,
        message="Tunic audit source contract failed.",
    )
    require(
        condition=(
            (
            "FREECAD_CLOTH_AVATAR_MESH=/opt/freecad-cloth/assets/makehuman-hm08-base.obj" in dockerfile
            )
        ),
        message="Tunic audit source contract failed.",
    )
    require(
        condition="1f508f6083b2f823dab15de924b3bde72e08d77c9/makehuman/data/3dobjs/base.obj" in dockerfile,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="8e761e6624b8f54536409135d1636da63b32486a90d4897f84e121d144f6fb4c" in dockerfile,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="pbd_validation_image:" in workflow,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="FREECAD_PBD_IMAGE" in workflow,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="CLOTH_CI_ENABLE_PBD: 1" in workflow,
        message="Tunic audit source contract failed.",
    )
    gui = workflow.split("  gui-tunic-visual:", 1)[1].split("  gui-turntables:", 1)[0]
    require(
        condition="image: ${{ env.FREECAD_PBD_IMAGE }}" in gui,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="capture_pypbd_provenance.py" in gui,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="artifacts/pypbd-provenance.txt" in gui,
        message="Tunic audit source contract failed.",
    )


def test_production_tunic_audit_runs_even_if_performance_gate_fails() -> None:
    """Verify the authoritative tunic audit runs even when a separate performance gate fails."""
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    gui = workflow.split("  gui-tunic-visual:", 1)[1].split("  gui-turntables:", 1)[0]
    benchmark = gui.split(
        "      - uses: Uhrendoktor/freecad-cloth/.github/actions/freecad-test@", 1
    )[1].split("      - name: Independently validate realtime performance metrics", 1)[0]
    require(
        condition="test-script: tests/freecad_realtime_benchmark.py" in benchmark,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="CLOTH_REALTIME_FRAMES=120" in benchmark,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="tools/ci/validate_realtime_benchmark.py artifacts/freecad-realtime/metrics.json" in gui,
        message="Tunic audit source contract failed.",
    )
    audit_step = gui.split("      - uses: ./.github/actions/freecad-test", 1)[1]
    require(
        condition="if: always()" in audit_step.split("test-script:", 1)[0],
        message="Tunic audit source contract failed.",
    )
    require(
        condition="test-script: tests/freecad_tunic_audit_production.py" in audit_step,
        message="Tunic audit source contract failed.",
    )
    validator = (ROOT / "tools" / "ci" / "validate_realtime_benchmark.py").read_text(
        encoding="utf-8"
    )
    require(
        condition="p95_frame_interval_ms exceeds the 30 FPS budget" in validator,
        message="Tunic audit source contract failed.",
    )


def test_production_tunic_wrapper_dispatches_in_freecad_macro_host() -> None:
    """Verify the production tunic wrapper dispatches through the FreeCAD macro host."""
    wrapper = (ROOT / "tests" / "freecad_tunic_audit_production.py").read_text(encoding="utf-8")
    require(
        condition='importlib.import_module("freecad_tunic_audit").main' in wrapper,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="main()" in wrapper,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='if __name__ == "__main__"' not in wrapper,
        message="Tunic audit source contract failed.",
    )


def test_canonical_tunic_fixture_matches_validated_start_geometry() -> None:
    """Verify the canonical tunic fixture matches the geometry used for validation."""
    audit = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    audit_entry = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    require(
        condition="CLOTH_TUNIC_AUDIT_PROFILE" in audit_entry,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="TUNIC_PRODUCTION_AUDIT" in audit,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="SEAM_SOURCE = " not in audit_entry,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="required_indices = (1, 3, 5, 7)" in audit,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="TunicRightShoulder" in audit,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="TunicLeftShoulder" in audit,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="ParticleDistance = 24.0" in audit,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="SolverIterations = 8" in audit,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="SolverSubsteps = 4 if TUNIC_PRODUCTION_AUDIT else 1" in audit,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="tunic-simulation-start" in audit,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="realtime-preview=passed backend=position-based-dynamics" in audit,
        message="Tunic audit source contract failed.",
    )


def test_tunic_penetration_audit_uses_safe_numpy_ray_parity_in_freecad_host() -> None:
    """Verify penetration auditing uses the supported NumPy ray-parity path in FreeCAD."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    inside_check = source.split("def _inside_target_count(", 1)[1].split(
        "\ndef write_drape_metrics(", 1
    )[0]
    require(
        condition="Trimesh/Rtree's native contains query" in inside_check,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="target_mesh.contains" not in inside_check,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="import trimesh" not in inside_check,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="chunk_size=4" in inside_check,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="points_inside_closed_mesh(" in inside_check,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="prefer_trimesh=False" in inside_check,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="penetration-check=numpy-ray-parity" in inside_check,
        message="Tunic audit source contract failed.",
    )
    sanity = (ROOT / "freecad_cloth" / "simulation" / "DrapeVisualSanity.py").read_text(
        encoding="utf-8"
    )
    require(
        condition="prefer_trimesh: bool = True" in sanity,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="if prefer_trimesh:" in sanity,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="np.einsum" in sanity,
        message="Tunic audit source contract failed.",
    )


def test_penetration_evidence_stays_on_numpy_path_in_freecad_host() -> None:
    """Verify penetration evidence remains on the supported NumPy execution path."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    audit = source.split("def write_drape_metrics(", 1)[1].split("\ndef _arc_through_midpoint(", 1)[
        0
    ]
    evidence = audit.split("inside_points = []", 1)[1].split(
        'log(\n                    "penetration-evidence', 1
    )[0]

    require(
        condition=(
            (
            "from freecad_cloth.simulation.DrapeVisualSanity import point_inside_closed_mesh"
            not in audit
            )
        ),
        message="Tunic audit source contract failed.",
    )
    require(
        condition=evidence.count("prefer_trimesh=False") == 2,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="points_inside_closed_mesh(" in evidence,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="point_inside_closed_mesh(" not in evidence,
        message="Tunic audit source contract failed.",
    )


def test_tunic_visual_diagnostics_are_authoritative_after_persistence() -> None:
    """Verify visual diagnostics inspect the persisted simulation rather than a transient state."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    metrics_write = source.index("json.dump(payload, handle, indent=2, sort_keys=True)")
    gate = source.index('allowed_diagnostics={"below-hem-candidate"}')
    screenshot = source.index('f"cloth-simulation-draped-{direction}.png"')
    require(
        condition=metrics_write < screenshot < gate,
        message="Tunic audit source contract failed.",
    )


def test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks() -> None:
    """Verify drape debugging uses the canonical tunic profile and avatar landmarks."""
    debug = (ROOT / "tests" / "freecad_drape_debug.py").read_text(encoding="utf-8")
    audit = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")

    # Keep the diagnostic A/B garment aligned to current production geometry/scene APIs.
    require(
        condition=(
            (
            "from freecad_cloth.simulation.SimulationCommands import create_quality_simulation_scene"
            in debug
            )
        ),
        message="Tunic audit source contract failed.",
    )
    require(
        condition="SimulationQualityRuntimeV2" not in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="neck_z = (1.0 - float(neckline_drop)) * h" in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="neckline_drop=0.03" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="shoulder_headroom_mm = 20.0" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition=(
            (
            "garment_height = max(560.0, (shoulder_z - hem_z + shoulder_headroom_mm) / 0.94)" in source
            )
        ),
        message="Tunic audit source contract failed.",
    )
    require(
        condition="shoulder_headroom_mm = 20.0" in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition=(
            (
            "garment_height = max(560.0, (shoulder_z - hem_z + shoulder_headroom_mm) / 0.94)" in debug
            )
        ),
        message="Tunic audit source contract failed.",
    )
    require(
        condition="x_offset = 0.5 * (float(hem_width) - float(panel_width))" in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="armhole_z = 0.62 * h" in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="armhole_z = 0.62 * h" in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="shoulder_z = 0.94 * h" in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="points[3][0] - points[2][0] < 0.15 * float(panel_width)" in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="shoulder_z - armhole_z < 0.20 * h" in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="side_ease_mm = 4.0" in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="if idx == 1:" in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="elif idx == 7:" in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="(x_offset + 0.74 * panel_width, armhole_z)" in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="(x_offset + 0.26 * panel_width, armhole_z)" in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="midpoint = App.Vector(x_offset + 0.741 * panel_width, armhole_mid_z, 0)" in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="midpoint = App.Vector(x_offset + 0.259 * panel_width, armhole_mid_z, 0)" in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="(x_offset + 0.06 * panel_width, 0.94 * garment_height)" in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="(x_offset + 0.94 * panel_width, 0.94 * garment_height)" in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="if not (armhole_z < shoulder_z < neck_z)" in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="neckline_scoop_depth = 0.12 * h" in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="neckline_scoop_z = neck_z - neckline_scoop_depth" in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="if not (armhole_z < neckline_scoop_z < shoulder_z)" in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="neckline_scoop_depth = 0.12 * float(garment_height)" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="neckline_scoop_z = neck_z - neckline_scoop_depth" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="neckline_scoop_depth = 0.12 * float(garment_height)" in audit,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='("back", "front") if TUNIC_PRODUCTION_AUDIT else ("front", "back")' in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='make_piece("VisualTunicFront", front_side, 0.72, 0.03)' in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='make_piece("VisualTunicBack", back_side, 0.72, 0.03)' in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="elif idx == 4:" in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="elif index == 4:" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="true U-shaped neckline" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="ArrangementPoint.from_string(raw)" in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="panel_width = max(420.0, shoulder_width + 105.0)" in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="shoulder_width + 105.0" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="else max(450.0, panel_width + 100.0)" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="shoulder_span_ratio" not in audit,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='"panel_width = max(420.0, shoulder_width + 105.0)":' not in audit,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="clearance = max(20.0, 0.08 * body_depth)" in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="clearance = max(20.0, 0.08 * body_depth)" in audit,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="clearance = max(20.0, 0.08 * body_depth)" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="panel_width = max(420.0, shoulder_width + 105.0)" in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="panel_width = max(420.0, shoulder_width + 105.0)" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="panel_width = max(420.0, shoulder_width + 105.0)" in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="panel_width = max(420.0, shoulder_width + 105.0)" in audit,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="hem_width = max(500.0, panel_width + 100.0)" in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='make_piece("DebugTunicFront", front_y, 0.72, 0.03)' in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="panel_width *= 1.10" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="hem_width *= 1.10" in source,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="panel_width *= 1.10" in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="hem_width *= 1.10" in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='make_piece("DebugTunicBack", back_y, 0.72, 0.03)' in debug,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='("back", "front") if TUNIC_PRODUCTION_AUDIT else ("front", "back")' in audit,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='make_piece("VisualTunicFront", front_side, 0.72, 0.03)' in audit,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='make_piece("VisualTunicBack", back_side, 0.72, 0.03)' in audit,
        message="Tunic audit source contract failed.",
    )


def test_tunic_visual_gate_preserves_failed_artifacts_before_exit() -> None:
    """Verify failed visual acceptance preserves its diagnostic artifacts before exiting."""
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    gate = source.index('allowed_diagnostics={"below-hem-candidate"}')
    require(
        condition="drape-metrics=" in source[:gate],
        message="Tunic audit source contract failed.",
    )
    require(
        condition="gui-screenshot-manifest" not in source[gate:] or "task_dock.show()" in source[gate:],
        message="Tunic audit source contract failed.",
    )


def test_canonical_tunic_fixture_blocks_every_authored_segment() -> None:
    """Verify every authored tunic segment receives the required pattern constraint."""
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
        condition=expected_constraint in fixture,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='Sketcher.Constraint("Coincident"' not in fixture,
        message="Tunic audit source contract failed.",
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
            (
            topology_audit
            < sample_resolution
            < pattern_view
            < sewing_view
            < native_gate
            < simulation_start
            )
        ),
        message="Tunic audit source contract failed.",
    )
    require(
        condition='"boundary-order=%r near-crossing=%r"' in simulation,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="samples," in simulation,
        message="Tunic audit source contract failed.",
    )
    # Keep geometric validity guards in FreeCAD, but keep report classification on the host.
    require(
        condition="canonical tunic derived pattern outline is invalid before simulation" in simulation,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="fit_assessment" not in simulation,
        message="Tunic audit source contract failed.",
    )
    require(
        condition="review_required" not in simulation,
        message="Tunic audit source contract failed.",
    )
    require(
        condition='status["result"]' not in simulation,
        message="Tunic audit source contract failed.",
    )
