from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# The native-Sketcher fixture keeps explicit semantic edge IDs on each piece.
# The front/back pieces share the same authored topology, so corresponding shoulder
# and side edges must be paired by semantic position, not cross-paired.


def test_tunic_penetration_audit_logs_topology_and_reuses_batch_evidence():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "def _inside_target_states(points, target, collision_surface=None):" in source
    inside_states = source.split("def _inside_target_states(", 1)[1].split(
        "def write_drape_metrics(", 1
    )[0]
    assert "penetration-target-topology watertight=%s" in inside_states
    assert "penetration-trimesh-contains-fallback reason=target-not-watertight" in inside_states
    assert "penetration-check=numpy-ray-parity points=%d triangles=%d" in inside_states
    assert "def _native_mesh_inside_states(" not in source
    metrics = source.split("def write_drape_metrics(", 1)[1]
    assert "inside_flags = _inside_target_states(vertices, avatar, collision_surface)" in metrics
    assert "for point, authoritative_inside in zip(vertices, inside_flags, strict=False):" in metrics
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
    assert '(front_edge_ids[6], back_edge_ids[6], "TunicLeftShoulder", False)' in source
    assert '(front_edge_ids[8], back_edge_ids[8], "TunicLeftSide", False)' in source


def test_canonical_garment_pattern_has_scooped_open_armholes():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "x_offset = 0.5 * (float(hem_width) - float(panel_width))" in source
    assert "(x_offset + 0.5 * panel_width, neck_z)" in source
    assert "if abs(points[5][0] - center_x)" in source
    assert 'Sketcher.Constraint("Coincident", 8, 2, 0, 1)' in source
    assert "0.68 * garment_height" in source
    assert "0.78 * garment_height" in source
    assert "(x_offset + 0.95 * panel_width, armhole_z)" in source
    assert "(x_offset + 0.05 * panel_width, armhole_z)" in source
    assert "scoop_ratio = 0.83 if index == 2 else 0.17" in source
    assert "geometry.append(Part.Arc(end_vector, midpoint, start_vector))" in source
    assert 'Sketcher.Constraint("Coincident", 1, 2, 2, 2)' in source
    assert 'Sketcher.Constraint("Coincident", 2, 1, 3, 1)' in source
    assert 'Sketcher.Constraint("Coincident", 6, 2, 7, 2)' in source
    assert 'Sketcher.Constraint("Coincident", 7, 1, 8, 1)' in source
    assert "boundary.kind != \"arc\" or len(boundary.samples) < 8" in source
    assert "armhole curve has insufficient inward clearance" in source
    assert "shoulder_height=authored_shoulder_height" in source
    assert "neckline_height=authored_neckline_height" in source
    assert "armhole_height=armhole_height" in source
    assert "canonical tunic pattern lost bilateral symmetry" in source


def test_canonical_tunic_panel_width_matches_authoritative_shoulder_span():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "shoulder_span_ratio = 0.86 - 0.14" in source
    assert "panel_width = max(420.0, shoulder_width / shoulder_span_ratio)" in source


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
    assert 'mesh_normal_offset = float(getattr(scene, "StartHeight", 0.0))' in placement
    assert "target_front_y - clearance + mesh_normal_offset" in placement
    assert "target_back_y + clearance + mesh_normal_offset" in placement
    assert "placement Y origin is already the solver mesh world-space panel plane" in placement
    assert "torso-x=[%.2f, %.2f]" in placement
    assert "min(target_ys)" not in placement
    assert "max(target_ys)" not in placement




def test_tunic_start_height_is_set_before_target_relative_placement():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    simulation_start = source.index("def simulation(")
    start_height_assignment = source.index("scene.StartHeight = 0.0", simulation_start)
    placement_helper = source.index(
        "def target_relative_piece_placement(side, outline):", simulation_start
    )
    assert start_height_assignment < placement_helper
    assert source.count("scene.StartHeight = 0.0") == 1
    assert "normal_offset_y = -float(start_height)" in source
    assert (
        "canonical tunic fixture requires StartHeight=0 before target-relative placement"
        in source
    )
    assert (
        "canonical tunic panel selection depth is on the wrong side of the mannequin center plane"
        in source
    )


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
    assert '"%s|%s|shoulder_left" % (front.PieceId, front_edge_ids[6])' in source
    assert '"%s|%s|shoulder_right" % (back.PieceId, back_edge_ids[3])' in source
    assert '"%s|%s|shoulder_left" % (back.PieceId, back_edge_ids[6])' in source
    assert '"%s|%s|neck_right" % (front.PieceId, front_edge_ids[3])' in source
    assert '"%s|%s|neck_left" % (front.PieceId, front_edge_ids[6])' in source
    assert '"%s|%s|neck_center" % (front.PieceId, front_edge_ids[5])' in source
    assert '"%s|%s|neck_right" % (back.PieceId, back_edge_ids[3])' in source
    assert '"%s|%s|neck_left" % (back.PieceId, back_edge_ids[6])' in source
    assert '"%s|%s|neck_center" % (back.PieceId, back_edge_ids[5])' in source
    assert "scene.PinSelection = [str(index) for index in anchor_indices]" not in source
    assert "AttachmentOffset" in source
    assert "side-support-pins" not in source

def test_tunic_audit_runs_the_production_source_without_rewriting_it():
    audit = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "replacements =" not in audit
    assert "source.replace(" not in audit
    assert 'exec(compiled_source, namespace, namespace)' in audit
    assert "required_indices = (1, 3, 6, 8)" in source
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


def test_tunic_initial_projection_preserves_panel_topology_and_limits_arm_mapping():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    mapping = source.split("    def tunic_initial_surface_mesh(", 1)[1].split(
        "    # Refreshing DrapeTarget", 1
    )[0]
    assert "projection_fade_mm = max(1.0, float(scene.ParticleDistance))" in mapping
    assert "maximum_projection_delta_mm = 2.0 * projection_fade_mm" in mapping
    assert "lateral_distance = abs(x - float(x_mid))" in mapping
    assert "float(torso_half_width) + projection_fade_mm - lateral_distance" in mapping
    assert "projected_y = float(surface_point[1]) + direction * (" in mapping
    assert "point = (x, blended_y, z)" in mapping
    assert "triangle_index, surface_point = hit\n                    point = _fit_surface_point(" not in mapping


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
    assert "required_indices = (1, 3, 6, 8)" in source
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


def test_drape_debug_uses_the_canonical_tunic_profile_and_landmarks():
    debug = (ROOT / "tests" / "freecad_drape_debug.py").read_text(encoding="utf-8")
    audit = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")

    # Keep the diagnostic A/B garment on the same authored silhouette, dimensions,
    # avatar landmarks, and front/back neckline profile as the production tunic.
    assert "neck_z = (1.0 - float(neckline_drop)) * h" in debug
    assert "x_offset = 0.5 * (float(hem_width) - float(panel_width))" in debug
    assert "armhole_z = 0.88 * h" in debug
    assert "shoulder_z = 0.98 * h" in debug
    assert 'ArrangementPoint.from_string(raw)' in debug
    assert "shoulder_width / shoulder_span_ratio + 20.0" in debug
    assert "hem_width = max(500.0, panel_width + 80.0)" in debug
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert 'make_piece("DebugTunicFront", front_y, 0.61, 0.10)' in debug
    assert 'make_piece("DebugTunicBack", back_y, 0.61, 0.10)' in debug
    assert 'front, front_outline = make_piece("VisualTunicFront", "front", 0.61, 0.10)' in source
    assert 'back, back_outline = make_piece("VisualTunicBack", "back", 0.61, 0.10)' in source
    assert 'source_path = Path(__file__).with_name("freecad_screenshot_source.py")' in audit



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
    assert '"%s|%s|shoulder_left" % (front.PieceId, front_edge_ids[6])' in source
    assert '"%s|%s|shoulder_right" % (back.PieceId, back_edge_ids[3])' in source
    assert '"%s|%s|shoulder_left" % (back.PieceId, back_edge_ids[6])' in source
    assert "select_support_vertex_below_highest" not in source
    assert '(front_edge_ids[1], back_edge_ids[1], "TunicRightSide", False)' in source
    assert '(front_edge_ids[8], back_edge_ids[8], "TunicLeftSide", False)' in source
    assert '(front_edge_ids[3], back_edge_ids[3], "TunicRightShoulder", False)' in source
    assert '(front_edge_ids[6], back_edge_ids[6], "TunicLeftShoulder", False)' in source

def test_canonical_tunic_shoulder_endpoints_match_between_front_and_back():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert 'front, front_outline = make_piece("VisualTunicFront", "front", 0.61, 0.10)' in source
    assert 'back, back_outline = make_piece("VisualTunicBack", "back", 0.61, 0.10)' in source


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
    assert len(anchors.elts) == 10
    formats = tuple(
        element.left.value
        for element in anchors.elts
        if isinstance(element, ast.BinOp)
        and isinstance(element.left, ast.Constant)
        and isinstance(element.left.value, str)
    )
    assert formats.count("%s|%s|shoulder_right") == 2
    assert formats.count("%s|%s|shoulder_left") == 2
    assert formats.count("%s|%s|neck_right") == 2
    assert formats.count("%s|%s|neck_left") == 2
    assert formats.count("%s|%s|neck_center") == 2
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


def test_tunic_seams_preserve_normalized_boundary_traversal():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert '(front_edge_ids[1], back_edge_ids[1], "TunicRightSide", False)' in source
    assert '(front_edge_ids[8], back_edge_ids[8], "TunicLeftSide", False)' in source
    assert '(front_edge_ids[3], back_edge_ids[3], "TunicRightShoulder", False)' in source
    assert '(front_edge_ids[6], back_edge_ids[6], "TunicLeftShoulder", False)' in source


def test_canonical_tunic_maps_seams_to_shared_surface_positions_before_build():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "def tunic_initial_surface_mesh(" in source
    assert "is_front = piece_id == str(front.PieceId)" in source
    assert "from freecad_cloth.simulation.SimulationMeshQuality import quality_piece_mesh" in source
    assert "return quality_piece_mesh(" in source
    assert "float(scene.ParticleDistance)" in source
    assert "native_avatar_mesh.nearestFacetOnRay(origin, vector)" in source
    assert 'def _as_coordinates3(value, label):' in source
    assert 'coordinates = tuple(float(component) for component in raw)' in source
    assert 'normal = _as_coordinates3(facet_normal, "DrapeTarget facet normal")' in source
    assert 'point = _as_coordinates3(hit, "Mesh ray intersection")' in source
    assert 'points = tuple(_as_coordinates3(point, "mesh vertex") for point in vertices)' in source
    assert "tunic initialization received an invalid DrapeTarget facet normal" in source
    assert 'sewn_ids.add(str(getattr(seam_obj, "EdgeAId", "")).strip())' in source
    assert 'sewn_ids.add(str(getattr(seam_obj, "EdgeBId", "")).strip())' in source
    assert "missing_sewn_ids = sorted(sewn_ids - set(chain_by_id))" in source
    assert "tunic-debug-boundary piece=%s edge=%s count=%d vertices=%s" in source
    assert "if piece_id in {str(front.PieceId), str(back.PieceId)}:" in source
    assert "target_vertex_tree = cKDTree(target_surface.vertices)" in source
    assert 'fit_counts["clearance-correction"] += 1' in source
    assert 'clearance_inside_flags = _inside_target_states(' in source
    assert '"tunic-initial-clearance-direction inside=%d points=%d"' in source
    assert 'if inside' in source
    assert 'float(corrected[axis]) - float(closest[axis])' in source
    assert '"tunic-initial-min-vertex-clearance-mm=%.2f required-offset-mm=%.2f points=%d"' in source
    assert '"tunic-initial-clearance-residual sample=%s" % (residual_sample,)' in source
    assert 'for _clearance_attempt in range(5):' in source
    assert '"tunic-initial-clearance-repair attempt=%d inside=%d below-offset=%d"' in source
    assert "repair_inside_flags = _inside_target_states(" in source
    assert "target_vertex_index = int(repair_target_indices[index])" in source
    assert "target_vertex[axis]" in source and "required_offset * correction_vector[axis] / correction_length" in source
    assert '"tunic-initial-inside-residual sample=%s" % (residual_sample,)' in source
    assert "canonical tunic surface mapping leaves %d cloth vertices below configured outward offset" in source
    assert "from freecad_cloth.simulation.DrapeVisualSanity import points_inside_closed_mesh" in source
    assert 'fit_counts["inside-correction"] += 1' in source
    assert 'inside_flags = _inside_target_states(tuple(mapped), avatar, target_surface)' in source
    assert '"tunic-initial-inside-classifiers authoritative=%d parity=%d mismatches=%d points=%d"' in source
    assert "correction_vector = tuple(" in source
    assert "correction_length = sum(" in source
    assert "required_offset * correction_vector[axis] / correction_length" in source
    assert "panel_collision_buffer_mm = float(" in source
    assert "required_vertex_offsets[index]" in source
    assert "_pbd_collision_effective_tolerance_mm(target_surface)" in source
    assert "extra_offset_mm=panel_collision_buffer_mm" in source
    assert "outward_offset = float(clearance) + 3.0" in source
    assert '"tunic-initial-inside-residual sample=%s"' in source
    assert "canonical tunic surface mapping leaves %d cloth vertices inside the mannequin target" in source
    assert "if float(distance) >= required_offset - 1e-6:" in source
    assert "canonical tunic step-0 target clearance is below configured separation" in source
    assert "scene_proxy = scene.Proxy" in source
    assert "scene_signature = scene_proxy._signature(scene)" in source
    assert "signature=scene_signature" in source
    assert "scene_proxy._build(" in source
    assert "piece_mesh=tunic_initial_surface_mesh" in source
    assert "sync_seam_provenance(base_proxy_getter())" in source
    signature_position = source.index("scene_signature = scene_proxy._signature(scene)")
    build_position = source.index("scene_proxy._build(", signature_position)
    sync_position = source.index("sync_seam_provenance(base_proxy_getter())", build_position)
    recompute_position = source.index("doc.recompute()", sync_position)
    assert signature_position < build_position < sync_position < recompute_position
    assert "canonical tunic fixture cannot synchronize authoritative seam provenance" in source
    assert "tunic-anchor-projection descriptor=%s particle=%d source=%s particle-before=%s " in source
    assert '"%s|%s|neck_center" % (front.PieceId, front_edge_ids[5])' in source
    assert '"%s|%s|neck_center" % (back.PieceId, back_edge_ids[5])' in source
    assert '"%s|%s|neck_center" % (front.PieceId, front_edge_ids[4])' not in source
    assert '"%s|%s|neck_center" % (back.PieceId, back_edge_ids[4])' not in source
    assert "surface-mapped mesh builder was not used" in source
    assert "refresh_drape_target(target)" not in source[source.index("def tunic_initial_surface_mesh("):source.index("tunic-initial-surface-map=")]
    assert "tunic-sewn-vertex-selection piece=%s ids=%s chain-sizes=%s vertices=%d" in source
    assert "for seam_obj, piece_a, piece_b in seam_records:" in source
    assert "tunic-seam-initial-report id=%s pairs=%d first=%.2f last=%.2f max=%.2f" in source
    assert "tunic-seam-initial-max-gap-mm=" in source
    assert "canonical tunic initial seam span exceeds the 35 mm convergence gate" in source
    assert source.index('"tunic-seam-initial-pair id=%s') < source.index("if initial_max_seam_gap > 35.0")


def test_tunic_upper_profile_uses_avatar_landmarks_and_distributed_support():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert 'neck_point = arrangement_world("neck")' in source
    assert "authored_neckline_height = neck_point.z - 25.0 - hem_z" in source
    assert "avatar landmarks do not fit the tunic's hem/armhole/shoulder/neckline profile" in source
    assert "tunic-neckline-support landmark=%s" in source
    assert "len(neckline_support) != 6" in source
    assert "tunic neckline fell below the neck/shoulder band" in source
    assert source.count('|%s|neck_center" % (') == 2
    assert source.count('|%s|neck_left" % (') == 2
    assert source.count('|%s|neck_right" % (') == 2
    simulation_objects = (ROOT / "freecad_cloth" / "simulation" / "SimulationObjects.py").read_text(encoding="utf-8")
    assert 'landmarks["neck_left"]' in simulation_objects
    assert 'landmarks["neck_right"]' in simulation_objects
    assert 'landmarks["neck_center"]' in simulation_objects


def test_tunic_attachment_selection_uses_authored_mesh_vertices():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    simulation = (ROOT / "freecad_cloth" / "simulation" / "SimulationObjects.py").read_text(
        encoding="utf-8"
    )
    attachments = (ROOT / "freecad_cloth" / "simulation" / "ClothAttachments.py").read_text(
        encoding="utf-8"
    )
    assert "normal_offset_y = -float(start_height)" in source
    assert "tunic-anchor-selection-depth piece=%s selection-y=[%.2f, %.2f] torso-mid-relative-y=[%.2f, %.2f] normal-offset-y=%.2f" in source
    assert "selection_vertices = tuple(" in source
    assert "float(vertex[1]) + normal_offset_y" in source
    assert "return tuple(mapped), triangles, boundary_edges, selection_vertices" in source
    assert "selection_positions.extend(mesh_selection_vertices)" in simulation
    assert "selection_positions=selection_positions" in simulation
    assert "selection_positions: Any = None" in attachments
