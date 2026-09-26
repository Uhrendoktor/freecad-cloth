from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


# The A/B path binds the right shoulder to semantic edge 3/3; keep front/back IDs independent.
# The left shoulder remains on the existing 6/2 correspondence for this bounded experiment.

def test_canonical_tunic_uses_independent_front_back_semantic_edge_ids():
    source = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert 'front_edge_ids = tuple(str(value) for value in getattr(front.Sketch, "SemanticEdgeIds", ()) or ())' in source
    assert 'back_edge_ids = tuple(str(value) for value in getattr(back.Sketch, "SemanticEdgeIds", ()) or ())' in source
    assert 'front_edge_ids[1], back_edge_ids[1], "TunicRightSide"' in source
    assert 'front_edge_ids[3], back_edge_ids[3], "TunicRightShoulder"' in source
    assert 'front_edge_ids[6], back_edge_ids[2], "TunicLeftShoulder"' in source
    assert 'front_edge_ids[7], back_edge_ids[7], "TunicLeftSide"' in source


def test_canonical_tunic_uses_arrangement_points_target_collision_and_no_pins():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert 'ArrangementPoint.from_string' in source
    assert 'shoulder_left = arrangement_world("shoulder_left")' in source
    assert 'shoulder_right = arrangement_world("shoulder_right")' in source
    assert 'hip_point = arrangement_world("hip")' in source
    assert 'os.environ["CLOTH_TISSU_COLLISION_MODE"] = "mesh"' in source
    assert 'status = target_status(target)' in source
    assert 'scene.PinMode = "None"' in source
    assert 'scene.PinSelection = []' in source
    assert 'if solver_pins:' in source
    assert 'nearest_target_clearance' in source
    assert 'step0-target-vertex-clearance-mm=' in source
    assert 'authored_shoulder_pins' not in source
    assert 'scene.PinSelection = [str(i) for i in front_pins]' not in source
    assert 'target_surface = collision_surface(' in source
    assert 'target_source.Mesh.BoundBox' not in source


def test_canonical_tunic_uses_validated_authored_mapping():
    audit = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert "required_indices = (1, 2, 3, 6, 7)" in audit
    assert 'front_edge_ids[1], back_edge_ids[1], "TunicRightSide"' in audit
    assert 'front_edge_ids[3], back_edge_ids[3], "TunicRightShoulder"' in audit
    assert 'front_edge_ids[6], back_edge_ids[2], "TunicLeftShoulder"' in audit
    assert 'front_edge_ids[7], back_edge_ids[7], "TunicLeftSide"' in audit
    assert 'front_edge_ids[3], back_edge_ids[3], "TunicRightShoulder"' in audit
    assert 'front_edge_ids[3], back_edge_ids[3], "TunicRightShoulder"' not in audit


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
        "stdout:\n%s\n"
        "stderr:\n%s"
        % (result.stdout, result.stderr)
    )
    assert "tunic-audit-source-syntax=passed" in result.stdout

def test_canonical_tunic_authoritative_gate_is_fail_closed():
    source = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert 'os.environ["CLOTH_TISSU_COLLISION_MODE"] = "mesh"' in source
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
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    assert "ParticleDistance = 32.0" in source
    assert "SolverIterations = 2" in source
    assert "SolverSubsteps = 1" in source
    assert 'CLOTH_TISSU_COLLISION_MODE: mesh' in workflow
    assert 'CLOTH_TISSU_COLLISION_TRIANGLES: 2048' in workflow
    assert 'tunic-simulation-start' in source
    assert "anchor = '''    for batch in (15,15,15,15,15,15):" in source
    assert "        simulation_panel.step(batch); doc.recompute(); events()" in source
    assert "source = source.replace(anchor, preview_probe + '\\n' + timed_anchor, 1)" in source


def test_tissu_collision_cap_is_derived_without_mutating_authoritative_surface():
    from freecad_cloth.avatar.AvatarCollision import CollisionSurface, coarsen_collision_surface

    vertices = tuple((float(i % 5), float((i // 5) % 5), float(i // 25)) for i in range(75))
    triangles = tuple(
        (row * 5 + col, row * 5 + col + 1, (row + 1) * 5 + col)
        for row in range(14)
        for col in range(4)
    )
    source = CollisionSurface(vertices, triangles, "DrapeTarget", 0.5)
    derived = coarsen_collision_surface(source, 8)

    assert len(source.triangles) == 56
    assert len(derived.triangles) == 8
    assert derived is not source
    assert derived.vertices is source.vertices
    assert derived.region == source.region
    assert derived.thickness == source.thickness
    assert set(derived.triangles).issubset(set(source.triangles))


def test_tissu_backend_keeps_authoritative_mesh_separate_from_solver_surface():
    source = (ROOT / "freecad_cloth" / "simulation" / "TissuBackend.py").read_text(encoding="utf-8")
    assert "self._source_collision_surface = collision_surface" in source
    assert 'collision_mode == "mesh"' in source
    assert "collision_surface = coarsen_collision_surface(collision_surface, collision_limit)" in source
    assert "self._collision_surface = collision_surface" in source
    assert "source_triangles=%d solver_triangles=%d limit=%d" in source


def test_tunic_step_zero_clearance_gate_is_preserved_and_fixture_starts_outside_target():
    audit = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert "clearance = max(8.0, 0.025 * body_depth)" in audit
    assert "'            y = (shoulder_left.y + shoulder_right.y) / 2.0 - clearance': '            y = min(target_ys) - clearance'," in audit
    assert "'            y = (shoulder_left.y + shoulder_right.y) / 2.0 + clearance': '            y = max(target_ys) + clearance'," in audit


def test_tunic_seam_mapping_uses_opposite_shoulder_edges():
    audit = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert 'seam_specs = ((front_edge_ids[1], back_edge_ids[1], "TunicRightSide"),(front_edge_ids[3], back_edge_ids[3], "TunicRightShoulder"),(front_edge_ids[6], back_edge_ids[2], "TunicLeftShoulder"),(front_edge_ids[7], back_edge_ids[7], "TunicLeftSide"))' in audit


def test_canonical_tunic_fixture_matches_validated_orientation():
    audit = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert 'front, front_outline = make_piece("VisualTunicFront", "back", 0.78, 0.18); back, back_outline = make_piece("VisualTunicBack", "front", 0.76, 0.12)' in audit
    assert "ParticleDistance = 32.0" in audit
    assert "SolverIterations = 2" in audit
    assert "SolverSubsteps = 1" in audit
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "scene.TimeStep = 1.0 / 120.0;" in source

if __name__ == "__main__":
    test_canonical_tunic_uses_independent_front_back_semantic_edge_ids()
    test_canonical_tunic_uses_arrangement_points_target_collision_and_no_pins()
    test_canonical_tunic_uses_validated_authored_mapping()
    test_canonical_tunic_source_rewrite_compiles()
    test_canonical_tunic_authoritative_gate_is_fail_closed()
    test_simulation_proxy_serializes_only_rebuildable_metadata()
    test_tunic_realtime_profile_is_bounded_and_mesh_collision_is_explicit()
    test_tissu_collision_cap_is_derived_without_mutating_authoritative_surface()
    test_tissu_backend_keeps_authoritative_mesh_separate_from_solver_surface()
    test_tunic_step_zero_clearance_gate_is_preserved_and_fixture_starts_outside_target()
    test_tunic_seam_mapping_uses_opposite_shoulder_edges()
    test_canonical_tunic_fixture_matches_validated_orientation()
    print("tunic-audit-contract=passed")
