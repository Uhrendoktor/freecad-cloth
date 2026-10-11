from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# The native-Sketcher fixture keeps explicit semantic edge IDs on each piece.
# The front/back pieces share the same authored topology, so corresponding shoulder
# and side edges must be paired by semantic position, not cross-paired.


def test_canonical_tunic_pairs_matching_front_back_semantic_edges():
    source = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert "front_edge_ids = tuple(" in source
    assert "back_edge_ids = tuple(" in source
    assert '"SemanticEdgeIds"' in source
    assert 'front_edge_ids[1], back_edge_ids[1], "TunicRightSide"' in source
    assert 'front_edge_ids[3], back_edge_ids[3], "TunicRightShoulder"' in source
    assert 'front_edge_ids[5], back_edge_ids[5], "TunicLeftShoulder"' in source
    assert 'front_edge_ids[7], back_edge_ids[7], "TunicLeftSide"' in source


def test_tunic_fixture_uses_arrangement_points_and_unpinned_neckline() -> None:
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "ArrangementPoint.from_string" in source
    assert 'shoulder_left = arrangement_world("shoulder_left")' in source
    assert 'shoulder_right = arrangement_world("shoulder_right")' in source
    assert 'hip_point = arrangement_world("hip")' in source
    assert 'os.environ["CLOTH_PBD_COLLISION_MODE"] = "mesh"' in source
    assert "status = target_status(target)" in source
    assert 'scene.PinMode = "None"' in source
    assert 'scene.PinMode = "Explicit"' not in source
    assert "scene.PinSelection = []" in source
    assert "scene.PinSelection = [str(index) for index in expected_pins]" not in source
    assert "if solver_pins:" in source
    assert "base_proxy_getter().source_signature = None" in source
    assert "tunic-neckline-midpoint piece=%s particle=%d snap-mm=%.2f" in source
    assert "panel_indices.get(panel.Name, ())" in source
    assert 'panel_objects = tuple(getattr(scene, "DrapePanels", ()))' in source
    assert "scene.touch()" in source
    initial_piece_links = source.index("scene.ClothPieces = [front, back]")
    initial_cache_invalidation = source.index("base_proxy_getter().source_signature = None")
    first_panel_map = source.index('panel_piece_names = getattr(proxy, "panel_piece_names", {})')
    assert initial_piece_links < initial_cache_invalidation < first_panel_map
    assert "tunic-simulation-panel-map proxy=%s links=%d panels=%r map=%r particles=%d" in source
    assert "canonical tunic simulation did not build an authored pattern panel" in source
    assert "def _neckline_boundary_particles(" in source
    assert '"semantic-chain-endpoints"' in source
    assert '"authored-edge-projection"' in source
    assert (
        "tunic-neckline-resolution piece=%s edge=%s method=%s chains=%d endpoint-error-mm=%.6f"
        in source
    )
    assert "boundary_index >= len(boundary_chains)" not in source
    assert "nearest_target_clearance" in source
    assert "step0-target-vertex-clearance-mm=" in source
    assert "authored_shoulder_pins" not in source
    assert "scene.PinSelection = [str(i) for i in front_pins]" not in source
    assert "target_surface = collision_surface(" in source
    assert "target_source.Mesh.BoundBox" not in source


def test_canonical_tunic_uses_matching_authored_mapping():
    audit = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert "required_indices = (1, 3, 5, 7)" in audit
    assert 'front_edge_ids[1], back_edge_ids[1], "TunicRightSide"' in audit
    assert 'front_edge_ids[3], back_edge_ids[3], "TunicRightShoulder"' in audit
    assert 'front_edge_ids[5], back_edge_ids[5], "TunicLeftShoulder"' in audit
    assert 'front_edge_ids[7], back_edge_ids[7], "TunicLeftSide"' in audit
    assert 'front_edge_ids[3], back_edge_ids[5], "TunicRightShoulder"' not in audit


def test_canonical_tunic_source_rewrite_compiles():
    import subprocess
    import sys

    audit_path = ROOT / "tests" / "freecad_tunic_audit.py"
    result = subprocess.run(
        [sys.executable, str(audit_path), "--syntax-check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "generated tunic source syntax gate failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    assert "tunic-audit-source-syntax=passed" in result.stdout


def test_canonical_tunic_authoritative_gate_is_fail_closed():
    source = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert 'os.environ["CLOTH_PBD_COLLISION_MODE"] = "mesh"' in source
    assert "proxy=proxy" in source
    assert "authoritative tunic seams did not converge" in source
    assert "if max_seam_gap > 35.0" in source
    assert "authoritative-seam-gap seam=%s" in source


def test_canonical_tunic_has_two_curved_open_armholes() -> None:
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "elif index == 2:" in source
    assert "elif index == 6:" in source
    assert "def _arc_through_midpoint(" in source
    assert "Part.ArcOfCircle(circle, start_angle, start_angle + sweep)" in source
    assert "zero_point = curve_value(circle, 0.0)" in source
    assert "quarter_point = curve_value(circle, math.pi / 2.0)" in source
    assert 'getter = getattr(curve, "valueAt", None)' in source
    assert 'getter = getattr(curve, "value", None)' in source
    assert "tunic armhole curve has no native parameter evaluator" in source
    assert "tunic armhole arc lost authored %s" in source
    sketch_builder = source.split("def _make_tunic_sketch(", 1)[1].split("\ndef _adopt_sketch", 1)[
        0
    ]
    assert (
        'sketch.addConstraint([Sketcher.Constraint("Block", index) '
        "for index in range(len(geometry))])"
    ) in sketch_builder
    assert 'Sketcher.Constraint("Coincident"' not in sketch_builder
    assert "tunic armhole collapsed during Sketcher recompute" in sketch_builder
    assert "armhole_z = 0.62 * float(garment_height)" in sketch_builder
    assert "(x_offset + 0.74 * panel_width, armhole_z)" in sketch_builder
    assert "shoulder_z = 0.94 * float(garment_height)" in sketch_builder
    assert "(x_offset + 0.94 * panel_width, shoulder_z)" in sketch_builder
    assert "if not (armhole_z < shoulder_z < neck_z)" in sketch_builder
    assert "shoulders must slope downward from neckline to shoulder tip" in sketch_builder
    assert "points[3][0] - points[2][0] < 0.15 * float(panel_width)" in sketch_builder
    assert "shoulder_z - armhole_z < 0.20 * float(garment_height)" in sketch_builder
    assert "side_ease_mm = 4.0" in sketch_builder
    assert "if index == 1:" in sketch_builder
    assert "elif index == 7:" in sketch_builder
    assert "0.5 * (start[0] + end[0]) + side_ease_mm" in sketch_builder
    assert "0.5 * (start[0] + end[0]) - side_ease_mm" in sketch_builder
    assert "(x_offset + 0.06 * panel_width, shoulder_z)" in sketch_builder
    assert "(x_offset + 0.26 * panel_width, armhole_z)" in sketch_builder
    # Keep the inward-scooped arc inside the shoulder line; .73/.27 self-intersects.
    assert "x_offset + 0.741 * panel_width, armhole_mid_z" in sketch_builder
    assert "x_offset + 0.259 * panel_width, armhole_mid_z" in sketch_builder
    assert "for edge_index, inward in ((2, -1.0), (6, 1.0))" in source
    assert 'boundary.kind != "arc" or len(boundary.samples) < 8' in source
    assert "armhole curve has insufficient inward clearance" in source
    assert 'front_edge_ids[1], back_edge_ids[1], "TunicRightSide", False' in source
    assert 'front_edge_ids[3], back_edge_ids[3], "TunicRightShoulder", False' in source
    assert 'front_edge_ids[5], back_edge_ids[5], "TunicLeftShoulder", False' in source
    assert 'front_edge_ids[7], back_edge_ids[7], "TunicLeftSide", False' in source
    assert 'front_edge_ids[2], back_edge_ids[2], "TunicRightArmhole"' not in source
    assert 'front_edge_ids[6], back_edge_ids[6], "TunicLeftArmhole"' not in source


def test_simulation_proxy_serializes_only_rebuildable_metadata():
    from freecad_cloth.simulation.SimulationObjects import SimulationProxy

    proxy = SimulationProxy()
    proxy.backend = object()
    proxy.panel_indices = {"panel": (1, 2)}
    proxy.seam_stitch_pairs = {"seam": ((0, 1),)}
    proxy.source_signature = ("derived",)
    proxy.last_steps = 17
    proxy.collision_surface = object()

    state = proxy.__getstate__()
    assert state == {"schema": 1}
    assert "backend" not in state
    assert "seam_stitch_pairs" not in state
    assert "collision_surface" not in state

    proxy.__setstate__(state)
    assert proxy.backend is None
    assert proxy.panel_indices == {}
    assert proxy.seam_stitch_pairs == {}
    assert proxy.source_signature is None
    assert proxy.last_steps == 0
    assert proxy.collision_surface is None


def test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit():
    source = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    assert "ParticleDistance = 24.0" in source
    assert "SolverIterations = 8" in source
    assert "SolverSubsteps = 4" in source
    assert "CLOTH_PBD_COLLISION_MODE: mesh" in workflow
    assert "CLOTH_PBD_COLLISION_VOXEL_MM=8.0" in workflow
    assert "collision_voxel_mm - 8.0" in source
    assert "(span + 200.0) / 8.0" in source
    assert "configured 8 mm voxel resolution" in source
    tunic_workflow = workflow.split("  gui-tunic-visual:", 1)[1].split("  gui-turntables:", 1)[0]
    assert "CLOTH_PBD_SUBSTEPS=16" in tunic_workflow
    assert 'os.environ["CLOTH_PBD_COLLISION_VOXEL_MM"]' not in source
    assert "CLOTH_PBD_SUBSTEPS: 8" in workflow
    assert 'os.environ["CLOTH_PBD_SUBSTEPS"]' not in source
    assert "CLOTH_PBD_COLLISION_TOLERANCE_MM: 12" not in workflow
    assert "tunic-collision-config target-thickness-mm=%.2f" in source
    simulation_commands = (
        ROOT / "freecad_cloth" / "simulation" / "SimulationCommands.py"
    ).read_text(encoding="utf-8")
    assert "DEFAULT_MANNEQUIN_COLLISION_THICKNESS_MM" in simulation_commands
    assert "tunic-simulation-start" in source
    assert 'configured_substeps = int(os.environ.get("CLOTH_PBD_SUBSTEPS", "8"))' in source
    assert 'effective_substeps = int(getattr(active_backend, "_substeps", -1))' in source
    assert "effective_substeps != configured_substeps" in source
    assert "backend_substeps=%d configured_substeps=%d" in source
    assert "realtime-preview=passed backend=position-based-dynamics" in source
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    assert "tools/ci/validate_manifests.py tunic-production" in workflow
    validator = (ROOT / "tools" / "ci" / "validate_manifests.py").read_text(encoding="utf-8")
    assert "def validate_tunic_production()" in validator
    assert "runtime collision configuration evidence is invalid" in validator
    assert "expected_resolution = tuple(" in validator
    assert "def _validate_realtime_metrics(data: dict)" in validator
    assert "_validate_realtime_metrics(data)" in validator
    assert "PBD SDF voxel must be 8 mm" in validator


def test_pbd_collision_body_uses_coarsened_solver_surface():
    backend = (ROOT / "freecad_cloth" / "simulation" / "PositionBasedDynamicsBackend.py").read_text(
        encoding="utf-8"
    )
    start = backend.index("    def _add_collision_body(")
    end = backend.index("    def _build(", start)
    body_builder = backend[start:end]
    assert "collision_surface = self._collision_surface" in body_builder
    assert "collision_surface = self._source_collision_surface" not in body_builder


def test_pbd_collision_sdf_resolution_and_tolerance_are_explicit():
    backend = (ROOT / "freecad_cloth" / "simulation" / "PositionBasedDynamicsBackend.py").read_text(
        encoding="utf-8"
    )
    assert "CLOTH_PBD_COLLISION_VOXEL_MM" in backend
    assert "def _pbd_collision_resolution(surface: CollisionSurface)" in backend
    assert "generateSDF(" in backend
    assert "resolution," in backend
    assert "representation_margin = 0.5 * _pbd_collision_voxel_mm()" in backend
    assert "max(configured, thickness, representation_margin)" in backend
    assert "self._collision_sdf_resolution = tuple(int(axis) for axis in resolution)" in backend
    assert "effective_tolerance_mm / _MM" in backend
    assert "cloth-pbd-collision-config " in backend
    assert backend.index("timestep.step(self._model)") < backend.index(
        "self._project_collision_positions()"
    )
    assert "particles.setPosition(" in backend
    assert "inward_speed < 0.0" in backend
    assert "project_stitched_pairs(" in backend
    assert backend.index("project_stitched_pairs(") < backend.index("moved_indices =")


def test_pbd_collision_sdf_is_cached_outside_backend_instance():
    backend = (ROOT / "freecad_cloth" / "simulation" / "PositionBasedDynamicsBackend.py").read_text(
        encoding="utf-8"
    )
    assert "_PBD_COLLISION_SDF_CACHE_KEY" in backend
    assert "_PBD_COLLISION_SDF_CACHE" in backend
    assert "cache-hit" in backend
    assert "generateSDF(" in backend
    assert "self._collision_sdf" in backend


def test_pbd_sdf_cache_key_is_stable_and_geometry_sensitive():
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
    assert key == _pbd_collision_sdf_cache_key(surface, [16, 16, 16])

    moved = CollisionSurface(
        ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ((0, 1, 2),),
        thickness=1.0,
    ).validate()
    assert key != _pbd_collision_sdf_cache_key(moved, [16, 16, 16])
    assert key != _pbd_collision_sdf_cache_key(surface, [17, 16, 16])


def test_pbd_ci_image_is_pinned_and_preinstalled():
    dockerfile = (ROOT / "docker" / "freecad-ci" / "Dockerfile").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    assert "pypbd==2.2.2" in dockerfile
    assert "triangle==20250106" in dockerfile
    assert "/opt/pypbd-provenance.txt" in dockerfile
    assert "makehuman-hm08-base.obj" in dockerfile
    assert (
        "FREECAD_CLOTH_AVATAR_MESH=/opt/freecad-cloth/assets/makehuman-hm08-base.obj" in dockerfile
    )
    assert "1f508f6083b2f823dab15de924b3bde72e08d77c9/makehuman/data/3dobjs/base.obj" in dockerfile
    assert "8e761e6624b8f54536409135d1636da63b32486a90d4897f84e121d144f6fb4c" in dockerfile
    assert "pbd_validation_image:" in workflow
    assert "FREECAD_PBD_IMAGE" in workflow
    assert "CLOTH_CI_ENABLE_PBD: 1" in workflow
    gui = workflow.split("  gui-tunic-visual:", 1)[1].split("  gui-turntables:", 1)[0]
    assert "image: ${{ env.FREECAD_PBD_IMAGE }}" in gui
    assert "capture_pypbd_provenance.py" in gui
    assert "artifacts/pypbd-provenance.txt" in gui


def test_canonical_tunic_fixture_matches_validated_start_geometry():
    audit = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert 'source_path = Path(__file__).with_name("freecad_screenshot_source.py")' in audit
    assert "SEAM_SOURCE = " in audit
    assert "required_indices = (1, 3, 5, 7)" in audit
    assert "TunicRightShoulder" in audit
    assert "TunicLeftShoulder" in audit
    assert "ParticleDistance = 24.0" in audit
    assert "SolverIterations = 8" in audit
    assert "SolverSubsteps = 4" in audit
    assert "tunic-simulation-start" in audit
    assert "realtime-preview=passed backend=position-based-dynamics" in audit


def test_tunic_penetration_audit_uses_safe_numpy_ray_parity_in_freecad_host() -> None:
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    inside_check = source.split("def _inside_target_count(", 1)[1].split(
        "\ndef write_drape_metrics(", 1
    )[0]
    assert "Trimesh/Rtree's native contains query" in inside_check
    assert "target_mesh.contains" not in inside_check
    assert "import trimesh" not in inside_check
    assert "chunk_size=4" in inside_check
    assert "points_inside_closed_mesh(" in inside_check
    assert "prefer_trimesh=False" in inside_check
    assert "penetration-check=numpy-ray-parity" in inside_check
    sanity = (ROOT / "freecad_cloth" / "simulation" / "DrapeVisualSanity.py").read_text(
        encoding="utf-8"
    )
    assert "prefer_trimesh: bool = True" in sanity
    assert "if prefer_trimesh:" in sanity
    assert "np.einsum" in sanity


def test_penetration_evidence_stays_on_numpy_path_in_freecad_host() -> None:
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
    )
    assert evidence.count("prefer_trimesh=False") == 2
    assert "points_inside_closed_mesh(" in evidence
    assert "point_inside_closed_mesh(" not in evidence


def test_tunic_visual_diagnostics_are_authoritative_after_persistence():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    metrics_write = source.index("json.dump(payload, handle, indent=2, sort_keys=True)")
    gate = source.index('allowed_diagnostics={"below-hem-candidate"}')
    screenshot = source.index('f"cloth-simulation-draped-{direction}.png"')
    assert metrics_write < screenshot < gate


def test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks():
    debug = (ROOT / "tests" / "freecad_drape_debug.py").read_text(encoding="utf-8")
    audit = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")

    # Keep the diagnostic A/B garment aligned to current production geometry/scene APIs.
    assert (
        "from freecad_cloth.simulation.SimulationCommands import create_quality_simulation_scene"
        in debug
    )
    assert "SimulationQualityRuntimeV2" not in debug
    assert "neck_z = (1.0 - float(neckline_drop)) * h" in debug
    assert "neckline_drop=0.03" in source
    assert "shoulder_headroom_mm = 20.0" in source
    assert (
        "garment_height = max(560.0, (shoulder_z - hem_z + shoulder_headroom_mm) / 0.94)" in source
    )
    assert "shoulder_headroom_mm = 20.0" in debug
    assert (
        "garment_height = max(560.0, (shoulder_z - hem_z + shoulder_headroom_mm) / 0.94)" in debug
    )
    assert "x_offset = 0.5 * (float(hem_width) - float(panel_width))" in debug
    assert "armhole_z = 0.62 * h" in debug
    assert "armhole_z = 0.62 * h" in debug
    assert "shoulder_z = 0.94 * h" in debug
    assert "points[3][0] - points[2][0] < 0.15 * float(panel_width)" in debug
    assert "shoulder_z - armhole_z < 0.20 * h" in debug
    assert "side_ease_mm = 4.0" in debug
    assert "if idx == 1:" in debug
    assert "elif idx == 7:" in debug
    assert "(x_offset + 0.74 * panel_width, armhole_z)" in debug
    assert "(x_offset + 0.26 * panel_width, armhole_z)" in debug
    assert "midpoint = App.Vector(x_offset + 0.741 * panel_width, armhole_mid_z, 0)" in debug
    assert "midpoint = App.Vector(x_offset + 0.259 * panel_width, armhole_mid_z, 0)" in debug
    assert "(x_offset + 0.06 * panel_width, 0.94 * garment_height)" in debug
    assert "(x_offset + 0.94 * panel_width, 0.94 * garment_height)" in debug
    assert "if not (armhole_z < shoulder_z < neck_z)" in debug
    assert "neckline_scoop_depth = 0.12 * h" in debug
    assert "neckline_scoop_z = neck_z - neckline_scoop_depth" in debug
    assert "if not (armhole_z < neckline_scoop_z < shoulder_z)" in debug
    assert "neckline_scoop_depth = 0.12 * float(garment_height)" in source
    assert "neckline_scoop_z = neck_z - neckline_scoop_depth" in source
    assert "neckline_scoop_depth = 0.12 * float(garment_height)" in audit
    assert 'make_piece("VisualTunicFront", "front", 0.72, 0.03)' in source
    assert 'make_piece("VisualTunicBack", "back", 0.72, 0.03)' in source
    assert "elif idx == 4:" in debug
    assert "elif index == 4:" in source
    assert "true U-shaped neckline" in source
    assert "ArrangementPoint.from_string(raw)" in debug
    assert "panel_width = max(420.0, shoulder_width + 105.0)" in debug
    assert "shoulder_width + 105.0" in source
    assert "hem_width = max(450.0, panel_width + 100.0)" in source
    assert "shoulder_span_ratio" not in audit
    assert '"panel_width = max(420.0, shoulder_width + 105.0)":' not in audit
    assert "clearance = max(20.0, 0.08 * body_depth)" in debug
    assert (
        '"clearance = max(20.0, 0.08 * body_depth)": "clearance = max(20.0, 0.08 * body_depth);"'
        in audit
    )
    assert "clearance = max(20.0, 0.08 * body_depth)" in source
    assert "panel_width = max(420.0, shoulder_width + 105.0)" in debug
    assert "panel_width = max(420.0, shoulder_width + 105.0)" in source
    assert "panel_width = max(420.0, shoulder_width + 105.0)" in debug
    assert "panel_width = max(420.0, shoulder_width + 105.0)" not in audit
    assert "hem_width = max(500.0, panel_width + 100.0)" in debug
    assert 'make_piece("DebugTunicFront", front_y, 0.72, 0.03)' in debug
    assert "panel_width *= 1.10" in source
    assert "hem_width *= 1.10" in source
    assert "panel_width *= 1.10" in debug
    assert "hem_width *= 1.10" in debug
    assert 'make_piece("DebugTunicBack", back_y, 0.72, 0.03)' in debug
    assert 'make_piece("VisualTunicFront", "back", 0.72, 0.03)' in audit
    assert 'make_piece("VisualTunicBack", "front", 0.72, 0.03)' in audit


def test_tunic_visual_gate_preserves_failed_artifacts_before_exit():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    gate = source.index('allowed_diagnostics={"below-hem-candidate"}')
    assert "drape-metrics=" in source[:gate]
    assert "gui-screenshot-manifest" not in source[gate:] or "task_dock.show()" in source[gate:]


def test_canonical_tunic_fixture_blocks_every_authored_segment() -> None:
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
    assert expected_constraint in fixture
    assert 'Sketcher.Constraint("Coincident"' not in fixture


def test_tunic_scene_dossier_logs_sampled_topology_before_simulation():
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

    assert (
        topology_audit
        < sample_resolution
        < pattern_view
        < sewing_view
        < native_gate
        < simulation_start
    )
    assert '"boundary-order=%r near-crossing=%r"' in simulation
    assert "samples," in simulation
    # Keep geometric validity guards in FreeCAD, but keep report classification on the host.
    assert "canonical tunic derived pattern outline is invalid before simulation" in simulation
    assert "fit_assessment" not in simulation
    assert "review_required" not in simulation
    assert 'status["result"]' not in simulation
