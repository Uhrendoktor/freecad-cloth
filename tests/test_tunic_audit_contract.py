from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# The native-Sketcher fixture keeps explicit semantic edge IDs on each piece.
# The front/back pieces share the same authored topology, so corresponding shoulder
# and side edges must be paired by semantic position, not cross-paired.


def test_canonical_tunic_pairs_matching_front_back_semantic_edges():
    source = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert (
        'front_edge_ids = tuple(str(value) for value in getattr(front.Sketch, "SemanticEdgeIds", ()) or ())'
        in source
    )
    assert (
        'back_edge_ids = tuple(str(value) for value in getattr(back.Sketch, "SemanticEdgeIds", ()) or ())'
        in source
    )
    assert 'front_edge_ids[1], back_edge_ids[1], "TunicRightSide"' in source
    assert 'front_edge_ids[2], back_edge_ids[2], "TunicRightShoulder"' in source
    assert 'front_edge_ids[6], back_edge_ids[6], "TunicLeftShoulder"' in source
    assert 'front_edge_ids[7], back_edge_ids[7], "TunicLeftSide"' in source


def test_canonical_tunic_uses_arrangement_points_target_collision_and_no_pins():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "ArrangementPoint.from_string" in source
    assert 'shoulder_left = arrangement_world("shoulder_left")' in source
    assert 'shoulder_right = arrangement_world("shoulder_right")' in source
    assert 'hip_point = arrangement_world("hip")' in source
    assert 'os.environ["CLOTH_PBD_COLLISION_MODE"] = "mesh"' in source
    assert "status = target_status(target)" in source
    assert 'scene.PinMode = "None"' in source
    assert "scene.PinSelection = []" in source
    assert "if solver_pins:" in source
    assert "nearest_target_clearance" in source
    assert "step0-target-vertex-clearance-mm=" in source
    assert "authored_shoulder_pins" not in source
    assert "scene.PinSelection = [str(i) for i in front_pins]" not in source
    assert "target_surface = collision_surface(" in source
    assert "target_source.Mesh.BoundBox" not in source


def test_canonical_tunic_uses_matching_authored_mapping():
    audit = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert "required_indices = (1, 2, 6, 7)" in audit
    assert 'front_edge_ids[1], back_edge_ids[1], "TunicRightSide"' in audit
    assert 'front_edge_ids[2], back_edge_ids[2], "TunicRightShoulder"' in audit
    assert 'front_edge_ids[6], back_edge_ids[6], "TunicLeftShoulder"' in audit
    assert 'front_edge_ids[7], back_edge_ids[7], "TunicLeftSide"' in audit
    assert 'front_edge_ids[2], back_edge_ids[6], "TunicRightShoulder"' not in audit


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
    assert "SolverIterations = 1" in source
    assert "SolverSubsteps = 1" in source
    assert "CLOTH_PBD_COLLISION_MODE: mesh" in workflow
    assert "CLOTH_PBD_SUBSTEPS: 8" in workflow
    assert 'os.environ["CLOTH_PBD_SUBSTEPS"]' not in source
    assert "CLOTH_PBD_COLLISION_TRIANGLES: 8192" in workflow
    assert "CLOTH_PBD_COLLISION_VOXEL_MM: 8" in workflow
    assert "CLOTH_PBD_COLLISION_TOLERANCE_MM: 12" not in workflow
    assert "tunic-simulation-start" in source
    assert "realtime-preview=passed backend=position-based-dynamics" in source


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
    assert "resolution=resolution" in backend
    assert "max(configured_tolerance, surface_thickness)" in backend


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
    assert "CLOTH_CI_ENABLE_PBD=1" in workflow
    gui = workflow.split("  gui-tunic-visual:", 1)[1].split(
        "      - name: Stage workspace in Docker volume", 1
    )[0]
    provenance = gui.split("      - name: Pull pinned PositionBasedDynamics validation image", 1)[1]
    assert "run: |" in provenance
    assert "mkdir -p artifacts" in provenance


def test_canonical_tunic_fixture_matches_validated_start_geometry():
    audit = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert 'source_path = Path(__file__).with_name("freecad_screenshot_source.py")' in audit
    assert "SEAM_SOURCE = " in audit
    assert "required_indices = (1, 2, 6, 7)" in audit
    assert "TunicRightShoulder" in audit
    assert "TunicLeftShoulder" in audit
    assert "ParticleDistance = 32.0" in audit
    assert "SolverIterations = 1" in audit
    assert "SolverSubsteps = 1" in audit
    assert "tunic-simulation-start" in audit
    assert "realtime-preview=passed backend=position-based-dynamics" in audit


def test_tunic_visual_diagnostics_are_authoritative_after_persistence():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    metrics_write = source.index("json.dump(payload, handle, indent=2, sort_keys=True)")
    gate = source.index('assert_drape_diagnostics(json.load(handle).get("panels", ()))')
    screenshot = source.index('f"cloth-simulation-draped-{direction}.png"')
    assert metrics_write < screenshot < gate


def test_tunic_visual_gate_preserves_failed_artifacts_before_exit():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    gate = source.index('assert_drape_diagnostics(json.load(handle).get("panels", ()))')
    assert "drape-metrics=" in source[:gate]
    assert "gui-screenshot-manifest" not in source[gate:] or "task_dock.show()" in source[gate:]
