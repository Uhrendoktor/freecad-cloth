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


def test_canonical_tunic_uses_arrangement_points_target_collision_and_unpinned_neckline_diagnostics():
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


def test_canonical_tunic_has_two_curved_open_armholes():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "if index == 2:" in source
    assert "elif index == 6:" in source
    assert "def _arc_through_midpoint(Part, start, end, midpoint):" in source
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
    assert "armhole_z = 0.66 * float(garment_height)" in sketch_builder
    assert "(x_offset + 0.82 * panel_width, armhole_z)" in sketch_builder
    assert "shoulder_z = 0.86 * float(garment_height)" in sketch_builder
    assert "(x_offset + 0.94 * panel_width, shoulder_z)" in sketch_builder
    assert "if not (armhole_z < shoulder_z < neck_z)" in sketch_builder
    assert "shoulders must slope downward from neckline to shoulder tip" in sketch_builder
    assert "points[3][0] - points[2][0] < 0.10 * float(panel_width)" in sketch_builder
    assert "shoulder_z - armhole_z < 0.15 * float(garment_height)" in sketch_builder
    assert "(x_offset + 0.06 * panel_width, shoulder_z)" in sketch_builder
    assert "(x_offset + 0.18 * panel_width, armhole_z)" in sketch_builder
    assert "x_offset + 0.83 * panel_width, armhole_mid_z" in sketch_builder
    assert "x_offset + 0.17 * panel_width, armhole_mid_z" in sketch_builder
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
    assert "ParticleDistance = 32.0" in source
    assert "SolverIterations = 4" in source
    assert "SolverSubsteps = 1" in source
    assert "CLOTH_PBD_COLLISION_MODE: mesh" in workflow
    assert "CLOTH_PBD_SUBSTEPS: 8" in workflow
    assert 'os.environ["CLOTH_PBD_SUBSTEPS"]' not in source
    assert "CLOTH_PBD_COLLISION_TOLERANCE_MM: 12" not in workflow
    assert "tunic-simulation-start" in source
    assert "realtime-preview=passed backend=position-based-dynamics" in source
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    assert "tools/ci/validate_manifests.py tunic-production" in workflow
    validator = (ROOT / "tools" / "ci" / "validate_manifests.py").read_text(encoding="utf-8")
    assert "def validate_tunic_production()" in validator


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
    assert "ParticleDistance = 32.0" in audit
    assert "SolverIterations = 4" in audit
    assert "SolverSubsteps = 1" in audit
    assert "tunic-simulation-start" in audit
    assert "realtime-preview=passed backend=position-based-dynamics" in audit


def test_tunic_penetration_audit_uses_safe_numpy_ray_parity_in_freecad_host():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    inside_check = source.split("def _inside_target_count(", 1)[1].split(
        "\ndef write_drape_metrics(", 1
    )[0]
    assert "Trimesh/Rtree's native contains query" in inside_check
    assert "target_mesh.contains" not in inside_check
    assert "import trimesh" not in inside_check
    assert (
        "points_inside_closed_mesh(points, vertices, triangles, prefer_trimesh=False)"
        in inside_check
    )
    assert "penetration-check=numpy-ray-parity" in inside_check
    sanity = (ROOT / "freecad_cloth" / "simulation" / "DrapeVisualSanity.py").read_text(
        encoding="utf-8"
    )
    assert "prefer_trimesh: bool = True" in sanity
    assert "if prefer_trimesh:" in sanity
    assert "np.einsum" in sanity


def test_tunic_visual_diagnostics_are_authoritative_after_persistence():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    metrics_write = source.index("json.dump(payload, handle, indent=2, sort_keys=True)")
    gate = source.index('allowed_diagnostics={"below-hem-candidate"}')
    screenshot = source.index('f"cloth-simulation-draped-{direction}.png"')
    assert metrics_write < screenshot < gate


def test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks():
    debug = (ROOT / "tests" / "freecad_drape_debug.py").read_text(encoding="utf-8")
    audit = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")

    # Keep the diagnostic A/B garment aligned to current production geometry/scene APIs.
    assert (
        "from freecad_cloth.simulation.SimulationCommands import create_quality_simulation_scene"
        in debug
    )
    assert "SimulationQualityRuntimeV2" not in debug
    assert "neck_z = (1.0 - float(neckline_drop)) * h" in debug
    assert "x_offset = 0.5 * (float(hem_width) - float(panel_width))" in debug
    assert "armhole_z = 0.66 * h" in debug
    assert "armhole_z = 0.66 * h" in debug
    assert "shoulder_z = 0.86 * h" in debug
    assert "(x_offset + 0.82 * panel_width, armhole_z)" in debug
    assert "(x_offset + 0.18 * panel_width, armhole_z)" in debug
    assert "midpoint = App.Vector(x_offset + 0.83 * panel_width, armhole_mid_z, 0)" in debug
    assert "midpoint = App.Vector(x_offset + 0.17 * panel_width, armhole_mid_z, 0)" in debug
    assert "(x_offset + 0.06 * panel_width, 0.86 * garment_height)" in debug
    assert "(x_offset + 0.94 * panel_width, 0.86 * garment_height)" in debug
    assert "if not (armhole_z < shoulder_z < neck_z)" in debug
    assert "ArrangementPoint.from_string(raw)" in debug
    assert "shoulder_width / shoulder_span_ratio + 20.0" in debug
    assert "hem_width = max(500.0, panel_width + 80.0)" in debug
    assert 'make_piece("DebugTunicFront", front_y, 0.64, 0.10)' in debug
    assert 'make_piece("DebugTunicBack", back_y, 0.64, 0.10)' in debug
    assert 'make_piece("VisualTunicFront", "back", 0.64, 0.10)' in audit
    assert 'make_piece("VisualTunicBack", "front", 0.64, 0.10)' in audit


def test_tunic_visual_gate_preserves_failed_artifacts_before_exit():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    gate = source.index('allowed_diagnostics={"below-hem-candidate"}')
    assert "drape-metrics=" in source[:gate]
    assert "gui-screenshot-manifest" not in source[gate:] or "task_dock.show()" in source[gate:]


def test_canonical_tunic_fixture_blocks_every_authored_segment():
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
