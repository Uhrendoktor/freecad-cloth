from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# The native-Sketcher fixture keeps explicit semantic edge IDs on each piece.
# The front/back pieces share the same authored topology, so corresponding shoulder
# and side edges must be paired by semantic position, not cross-paired.


def test_tunic_penetration_audit_prefers_native_mesh_and_batch_evidence():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "def _native_mesh_inside_states(points, vertices, triangles):" in source
    inside_count = source.split("def _inside_target_count(", 1)[1].split(
        "def write_drape_metrics(", 1
    )[0]
    assert "_native_mesh_inside_states(points, vertices, triangles)" in inside_count
    assert "penetration-check=FreeCAD-Mesh.isInside" in inside_count
    metrics = source.split("def write_drape_metrics(", 1)[1]
    assert "_native_mesh_inside_states(" in metrics
    assert "point_inside_closed_mesh(point_tuple" not in metrics
    assert "if len(inside_points) >= 12:" in metrics


def test_canonical_tunic_pairs_matching_front_back_semantic_edges():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert (
        'front_edge_ids = tuple(str(value) for value in getattr(front.Sketch, "SemanticEdgeIds", ()) or ())'
        in source
    )
    assert (
        'back_edge_ids = tuple(str(value) for value in getattr(back.Sketch, "SemanticEdgeIds", ()) or ())'
        in source
    )
    assert '(front_edge_ids[1], back_edge_ids[1], "TunicRightSide", False)' in source
    assert '(front_edge_ids[3], back_edge_ids[3], "TunicRightShoulder", False)' in source
    assert '(front_edge_ids[5], back_edge_ids[5], "TunicLeftShoulder", False)' in source
    assert '(front_edge_ids[7], back_edge_ids[7], "TunicLeftSide", False)' in source


def test_canonical_tunic_pattern_is_centered_and_shallow_at_the_armholes():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "x_offset = 0.5 * (float(hem_width) - float(panel_width))" in source
    assert "armhole_z = 0.88 * garment_height" in source
    assert "shoulder_z = 0.98 * garment_height" in source
    assert "canonical tunic pattern lost bilateral symmetry" in source


def test_canonical_tunic_panel_width_matches_authoritative_shoulder_span():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "shoulder_span_ratio = 0.86 - 0.14" in source
    assert "panel_width = max(420.0, shoulder_width / shoulder_span_ratio + 20.0)" in source


def test_tunic_panel_placement_uses_silhouette_local_torso_depth():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "def _projected_point_within_outline_margin(" in source
    placement = source.split("def target_relative_piece_placement(side, outline):", 1)[1].split(
        "def make_piece(", 1
    )[0]
    assert "torso_half_width = max(80.0, 0.30 * shoulder_width)" in source
    assert "abs(float(vertex[0]) - x_mid) <= torso_half_width" in placement
    assert "_projected_point_within_outline_margin(" in placement
    assert "target_front_y = min(projected_target_ys)" in placement
    assert "target_back_y = max(projected_target_ys)" in placement
    assert "target_front_y - clearance" in placement
    assert "target_back_y + clearance" in placement
    assert "torso-x=[%.2f, %.2f]" in placement
    assert "min(target_ys)" not in placement
    assert "max(target_ys)" not in placement


def test_tunic_projection_filter_keeps_pattern_and_clearance_band():
    import ast

    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    helper = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_projected_point_within_outline_margin"
    )
    namespace = {}
    module = ast.Module(body=[helper], type_ignores=[])
    exec(compile(module, "freecad_screenshot_source.py", "exec"), namespace, namespace)
    overlaps = namespace["_projected_point_within_outline_margin"]
    outline = ((0, 0), (10, 0), (10, 10), (0, 10))
    assert overlaps(5, 5, outline, 2)
    assert overlaps(-1, 5, outline, 2)
    assert not overlaps(-3, 5, outline, 2)
    assert not overlaps(13, 5, outline, 2)


def test_canonical_tunic_uses_avatar_surface_attachments_not_world_side_pins():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert 'scene.PinMode = "Avatar Attachment"' in source
    assert "scene.AttachmentOffset" in source
    assert "support_pins =" not in source
    assert "support_pins =" not in source
    assert "front_right_shoulder" not in source
    assert "front_left_shoulder" not in source
    assert "back_right_shoulder" not in source
    assert "back_left_shoulder" not in source
    assert "scene.AvatarAttachmentAnchors = [" in source

def test_canonical_tunic_rejects_skirt_like_final_height():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "tunic-upper-support=" in source
    assert "minimum_top_z = float(shoulder_z) - 30.0" in source
    assert "simulated tunic slipped below the shoulder line" in source


def test_canonical_tunic_uses_arrangement_points_collision_and_named_avatar_anchors():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "arrangement_world" in source
    assert "collision_surface(" in source
    assert 'scene.PinMode = "Avatar Attachment"' in source
    assert "scene.AvatarAttachmentAnchors = [" in source
    assert '"%s|%s|shoulder_right" % (front.PieceId, front_edge_ids[3])' in source
    assert '"%s|%s|shoulder_left" % (front.PieceId, front_edge_ids[5])' in source
    assert '"%s|%s|shoulder_right" % (back.PieceId, back_edge_ids[3])' in source
    assert '"%s|%s|shoulder_left" % (back.PieceId, back_edge_ids[5])' in source
    assert "scene.PinSelection = [str(index) for index in anchor_indices]" not in source
    assert "AttachmentOffset" in source
    assert "side-support-pins" not in source

def test_tunic_audit_runs_the_production_source_without_rewriting_it():
    audit = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "replacements =" not in audit
    assert "source.replace(" not in audit
    assert 'exec(compiled_source, namespace, namespace)' in audit
    assert "required_indices = (1, 3, 5, 7)" in source
    assert "authoritative tunic seams did not converge" in source
    assert "if max_seam_gap > 35.0" in source
    assert "collision_surface=target_surface" in source


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
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    audit = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert 'os.environ["CLOTH_PBD_COLLISION_MODE"] = "mesh"' in audit
    assert "seam_gap_diagnostics(" in source
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
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    assert "scene.ParticleDistance = 24.0" in source
    assert "scene.SolverIterations = 8" in source
    assert "scene.SolverSubsteps = 1" in source
    assert "CLOTH_PBD_COLLISION_MODE: mesh" in workflow
    assert "CLOTH_PBD_SUBSTEPS: 8" in workflow
    assert 'os.environ["CLOTH_PBD_SUBSTEPS"]' not in source
    assert "CLOTH_PBD_COLLISION_TOLERANCE_MM: 12" not in workflow
    assert 'scene.PinMode = "Avatar Attachment"' in source
    assert "tunic-upper-support=" in source
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
    gui = workflow.split("  gui-tunic-visual:", 1)[1].split(
        "  gui-turntables:", 1
    )[0]
    assert "image: ${{ env.FREECAD_PBD_IMAGE }}" in gui
    assert "capture_pypbd_provenance.py" in gui
    assert "artifacts/pypbd-provenance.txt" in gui


def test_canonical_tunic_fixture_matches_validated_start_geometry():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    audit = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert 'source_path = Path(__file__).with_name("freecad_screenshot_source.py")' in audit
    assert "exec(compiled_source, namespace, namespace)" in audit
    assert "seam_specs = (" in source
    assert "required_indices = (1, 3, 5, 7)" in source
    assert "TunicRightShoulder" in source
    assert "TunicLeftShoulder" in source
    assert "scene.ParticleDistance = 24.0" in source
    assert "scene.SolverIterations = 8" in source
    assert "scene.SolverSubsteps = 1" in source
    assert 'scene.PinMode = "Avatar Attachment"' in source
    assert "scene.AvatarAttachmentAnchors = [" in source


def test_tunic_penetration_audit_prefers_vectorized_trimesh_with_python_fallback():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "import trimesh" in source
    assert "target_mesh.contains(np.asarray(points, dtype=float))" in source
    assert "penetration-check=numpy-ray-parity" in source
    sanity = (ROOT / "freecad_cloth" / "simulation" / "DrapeVisualSanity.py").read_text(
        encoding="utf-8"
    )
    assert "def points_inside_closed_mesh(" in sanity
    assert "np.einsum" in sanity


def test_tunic_visual_diagnostics_are_authoritative_after_persistence():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    metrics_write = source.index("json.dump(payload, handle, indent=2, sort_keys=True)")
    gate = source.index('allowed_diagnostics={"below-hem-candidate"}')
    screenshot = source.index('f"cloth-simulation-draped-{direction}.png"')
    assert metrics_write < screenshot < gate


def test_tunic_visual_gate_preserves_failed_artifacts_before_exit():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    gate = source.index('allowed_diagnostics={"below-hem-candidate"}')
    assert "drape-metrics=" in source[:gate]
    assert "gui-screenshot-manifest" not in source[gate:] or "task_dock.show()" in source[gate:]

def test_canonical_tunic_anchors_to_avatar_surface_by_semantic_shoulder_edges():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "scene.AvatarAttachmentAnchors = [" in source
    assert 'scene.PinMode = "Avatar Attachment"' in source
    assert "scene.AttachmentOffset" in source
    assert '"%s|%s|shoulder_right" % (front.PieceId, front_edge_ids[3])' in source
    assert '"%s|%s|shoulder_left" % (front.PieceId, front_edge_ids[5])' in source
    assert '"%s|%s|shoulder_right" % (back.PieceId, back_edge_ids[3])' in source
    assert '"%s|%s|shoulder_left" % (back.PieceId, back_edge_ids[5])' in source
    assert "select_support_vertex_below_highest" not in source
    assert '(front_edge_ids[1], back_edge_ids[1], "TunicRightSide", False)' in source
    assert '(front_edge_ids[7], back_edge_ids[7], "TunicLeftSide", False)' in source
    assert '(front_edge_ids[3], back_edge_ids[3], "TunicRightShoulder", False)' in source
    assert '(front_edge_ids[5], back_edge_ids[5], "TunicLeftShoulder", False)' in source

def test_canonical_tunic_shoulder_endpoints_match_between_front_and_back():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert 'front, front_outline = make_piece("VisualTunicFront", "front", 0.64, 0.10)' in source
    assert 'back, back_outline = make_piece("VisualTunicBack", "back", 0.64, 0.10)' in source


def test_tunic_attachment_selection_uses_semantic_shoulder_landmarks():
    import ast

    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    assignments = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Attribute)
            and target.attr == "AvatarAttachmentAnchors"
            for target in node.targets
        )
    ]
    assert len(assignments) == 1
    anchors = assignments[0]
    assert isinstance(anchors, ast.List)
    assert len(anchors.elts) == 4
    formats = tuple(
        element.left.value
        for element in anchors.elts
        if isinstance(element, ast.BinOp)
        and isinstance(element.left, ast.Constant)
        and isinstance(element.left.value, str)
    )
    assert formats.count("%s|%s|shoulder_right") == 2
    assert formats.count("%s|%s|shoulder_left") == 2
    assert "side-support-pins" not in source



def test_avatar_projection_records_survive_pattern_scene_build():
    simulation = (
        ROOT / "freecad_cloth" / "simulation" / "SimulationObjects.py"
    ).read_text(encoding="utf-8")
    build = simulation.split("def _build_pattern_scene", 1)[1].split("def _build_demo", 1)[0]
    record_assignment = build.index("self.attachment_projections = tuple(projections)")
    backend_build = build.index("self.backend = PositionBasedDynamicsBackend(")
    panel_metadata = build.index("self.panel_indices = {}")
    assert record_assignment < backend_build < panel_metadata
    assert "self.attachment_projections = ()" not in build[backend_build:panel_metadata]


def test_tunic_side_seams_keep_the_authored_edge_direction():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert '(front_edge_ids[1], back_edge_ids[1], "TunicRightSide", False)' in source
    assert '(front_edge_ids[7], back_edge_ids[7], "TunicLeftSide", False)' in source
    assert '(front_edge_ids[1], back_edge_ids[1], "TunicRightSide", True)' not in source
    assert '(front_edge_ids[7], back_edge_ids[7], "TunicLeftSide", True)' not in source
