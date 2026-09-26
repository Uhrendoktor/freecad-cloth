from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


# The canonical native-Sketcher outline uses edges 3/5 as the shoulder seams.
# Keep front/back semantic edge IDs independent; never fall back to one piece's IDs.

def test_canonical_tunic_uses_independent_front_back_semantic_edge_ids():
    source = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert 'front_edge_ids = tuple(str(value) for value in getattr(front.Sketch, "SemanticEdgeIds", ()) or ())' in source
    assert 'back_edge_ids = tuple(str(value) for value in getattr(back.Sketch, "SemanticEdgeIds", ()) or ())' in source
    assert 'front_edge_ids[1], back_edge_ids[1], "TunicRightSide"' in source
    assert 'front_edge_ids[2], back_edge_ids[2], "TunicRightShoulder"' in source
    assert 'front_edge_ids[6], back_edge_ids[6], "TunicLeftShoulder"' in source
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
    assert "required_indices = (1, 2, 6, 7)" in audit
    assert 'front_edge_ids[1], back_edge_ids[1], "TunicRightSide"' in audit
    assert 'front_edge_ids[2], back_edge_ids[2], "TunicRightShoulder"' in audit
    assert 'front_edge_ids[6], back_edge_ids[6], "TunicLeftShoulder"' in audit
    assert 'front_edge_ids[7], back_edge_ids[7], "TunicLeftSide"' in audit
    assert 'front_edge_ids[3], back_edge_ids[3], "TunicRightShoulder"' not in audit


def test_canonical_tunic_source_rewrite_compiles():
    import ast
    audit_path = ROOT / "tests" / "freecad_tunic_audit.py"
    audit_source = audit_path.read_text(encoding="utf-8")
    module = ast.parse(audit_source, filename=str(audit_path))
    replacements = None
    for node in module.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "replacements"
            for target in node.targets
        ):
            replacements = ast.literal_eval(node.value)
            break
    assert replacements is not None
    seam_keys = [key for key in replacements if "for edge_a, edge_b, seam_id" in key]
    assert seam_keys == [
        '    for edge_a, edge_b, seam_id in ((2,2,"TunicRightShoulder"),(5,5,"TunicLeftShoulder")):\n'
        '        seam = Seam(str(front.PieceId), edge_a, str(back.PieceId), edge_b, id=seam_id, alignment="uniform", stitch_group="TunicAssembly")\n'
        '        add_seam(doc, seam)\n'
        '        seam_obj = next(o for o in doc.Objects if getattr(o, "SeamId", "") == seam_id)\n'
        '        seam_records.append((seam_obj, front, back))'
    ]
    source_path = ROOT / "tests" / "freecad_screenshot_source.py"
    source = source_path.read_text(encoding="utf-8")
    for old, new in replacements.items():
        assert old in source
        source = source.replace(old, new, 1)
    compile(source, str(source_path), "exec")


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
    assert "SolverIterations = 1" in source
    assert "SolverSubsteps = 1" in source
    assert 'CLOTH_TISSU_COLLISION_MODE: mesh' in workflow
    assert 'CLOTH_TISSU_COLLISION_TRIANGLES: 2048' in workflow
    assert 'tunic-simulation-start' in source
