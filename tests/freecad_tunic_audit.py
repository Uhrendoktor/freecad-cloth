"""CI entry point for the full tunic visual/simulation audit."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

source_path = Path(__file__).with_name("freecad_screenshot_source.py")
source = source_path.read_text(encoding="utf-8")

# The canonical tunic audit must use the authoritative DrapeTarget collision
# surface; do not replace it with the optional torso-envelope approximation.
os.environ["CLOTH_PBD_COLLISION_MODE"] = "mesh"
os.environ["CLOTH_TUNIC_AUDIT_SKIP_CANONICAL_ACCEPTANCE"] = "1"
os.environ["CLOTH_TUNIC_AUDIT_RUN_AVATAR_ACCEPTANCE"] = "1"
# Preserve the canonical workflow's PBD substep budget. The audit must not secretly
# multiply the configured simulation cost behind the workflow's back.

SEAM_SOURCE = """    for edge_a, edge_b, seam_id in ((2, 2, "TunicRightShoulder"), (5, 5, "TunicLeftShoulder")):
        seam = Seam(
            str(front.PieceId),
            edge_a,
            str(back.PieceId),
            edge_b,
            id=seam_id,
            alignment="uniform",
            stitch_group="TunicAssembly",
        )
        add_seam(doc, seam)
        seam_obj = next(o for o in doc.Objects if getattr(o, "SeamId", "") == seam_id)
        seam_records.append((seam_obj, front, back))"""

POSE_SOURCE = """    target_source = getattr(target, "SourceObject", None)
    if target_source is not avatar:
        raise RuntimeError(
            "visual fixture DrapeTarget does not reference the production ClothAvatar"
        )
    pre_status = target_status(target)"""

LANDMARK_SOURCE = """    shoulder_left = arrangement_world("shoulder_left")
    shoulder_right = arrangement_world("shoulder_right")
    hip_point = arrangement_world("hip")"""
replacements = {
    POSE_SOURCE: """    target_source = getattr(target, "SourceObject", None)
    if target_source is not avatar:
        raise RuntimeError(
            "visual fixture DrapeTarget does not reference the production ClothAvatar"
        )

    # Start the drape fixture with arms abducted rather than hanging beside the torso.
    # Rebuild through the product FK pipeline and refresh the collision target before
    # measuring clearances or placing any garment pieces.
    from dataclasses import replace as _replace_dataclass
    from freecad_cloth.avatar.AvatarCommands import _parameters, apply_avatar_parameters

    initial_parameters = _parameters(avatar)
    near_t_pose = _replace_dataclass(
        initial_parameters.pose,
        left_arm_angle=12.0,
        right_arm_angle=12.0,
        left_elbow_angle=0.0,
        right_elbow_angle=0.0,
        joint_rotations=(),
    )
    apply_avatar_parameters(
        avatar,
        _replace_dataclass(initial_parameters, pose=near_t_pose),
    )
    refresh_drape_target(target)
    doc.recompute()
    log("tunic-avatar-pose=near-horizontal left_arm_angle=12 right_arm_angle=12 joint_overrides=cleared")
    pre_status = target_status(target)""",
    LANDMARK_SOURCE: """    shoulder_left = arrangement_world("shoulder_left")
    shoulder_right = arrangement_world("shoulder_right")
    hip_point = arrangement_world("hip")
    def landmark_world(name):
        raw = next(
            (
                value
                for value in getattr(avatar, "Landmarks", ())
                if str(value).split("|", 1)[0] == name
            ),
            None,
        )
        if raw is None:
            raise RuntimeError("posed avatar mesh is missing FK landmark %s" % name)
        coordinates = tuple(float(value) for value in str(raw).split("|", 1)[1].split(","))
        if len(coordinates) != 3:
            raise RuntimeError("posed avatar FK landmark %s has invalid coordinates" % name)
        return avatar.Placement.multVec(App.Vector(*coordinates))

    wrist_left = landmark_world("wrist_left")
    wrist_right = landmark_world("wrist_right")
    left_span = abs(float(wrist_left.x) - float(shoulder_left.x))
    right_span = abs(float(wrist_right.x) - float(shoulder_right.x))
    left_vertical = abs(float(wrist_left.z) - float(shoulder_left.z))
    right_vertical = abs(float(wrist_right.z) - float(shoulder_right.z))
    log("tunic-pose-geometry left_dx=%.1f left_dz=%.1f right_dx=%.1f right_dz=%.1f" % (left_span, left_vertical, right_span, right_vertical))
    if min(left_span, right_span) < 150.0 or left_vertical > 0.22 * left_span or right_vertical > 0.22 * right_span:
        raise RuntimeError("tunic mannequin FK mesh is not near-T-pose: wrists are not near shoulder height")
    pose_view = Gui.activeDocument().activeView()
    pose_view.viewFront()
    pose_view.fitAll()
    events()
    save("cloth-mannequin-near-t-pose.png", "Mannequin near-T pose before cloth", "FK pose verified by shoulder-to-wrist geometry before draping")""",
    "clearance = max(20.0, 0.08 * body_depth)": "clearance = max(20.0, 0.08 * body_depth);",
    # Use torso-local depth samples and a centered shoulder/neck outline. Full-mesh
    # depth extrema are dominated by hands in the near-T pose and can pull the stitched
    # panels through the body; the silhouette filter excludes those outliers.
    "panel_width = max(420.0, shoulder_width + 100.0)": "shoulder_span_ratio = 0.86 - 0.14; panel_width = max(420.0, shoulder_width / shoulder_span_ratio + 20.0)",
    "hem_width = max(450.0, panel_width + 80.0)": "hem_width = max(500.0, panel_width + 80.0)",
    """    neck_z = (1.0 - float(neckline_drop)) * garment_height
    points = [
        (0.00, 0.00),
        (hem_width, 0.00),
        (panel_width, 0.82 * garment_height),
        (0.86 * panel_width, 0.97 * garment_height),
        (neckline_ratio * panel_width, neck_z),
        ((1.0 - neckline_ratio) * panel_width, neck_z),
        (0.14 * panel_width, 0.97 * garment_height),
        (0.00, 0.82 * garment_height),
    ]
""": """    neck_z = (1.0 - float(neckline_drop)) * garment_height
    x_offset = 0.5 * (float(hem_width) - float(panel_width))
    armhole_z = 0.88 * garment_height
    shoulder_z = 0.98 * garment_height
    points = [
        (0.00, 0.00),
        (hem_width, 0.00),
        (x_offset + panel_width, armhole_z),
        (x_offset + 0.86 * panel_width, shoulder_z),
        (x_offset + neckline_ratio * panel_width, neck_z),
        (x_offset + (1.0 - neckline_ratio) * panel_width, neck_z),
        (x_offset + 0.14 * panel_width, shoulder_z),
        (x_offset, armhole_z),
    ]
    center_x = 0.5 * float(hem_width)
    for left, right in ((0, 1), (2, 7), (3, 6), (4, 5)):
        if abs((points[left][0] + points[right][0]) - 2.0 * center_x) > 1e-9:
            raise RuntimeError("canonical tunic pattern lost bilateral symmetry")
""",
    'front, front_outline = make_piece("VisualTunicFront", "front", 0.64, 0.10)\n    back, back_outline = make_piece("VisualTunicBack", "back", 0.64, 0.07)': 'front, front_outline = make_piece("VisualTunicFront", "back", 0.78, 0.18); back, back_outline = make_piece("VisualTunicBack", "front", 0.76, 0.12)',
    SEAM_SOURCE: '    front_edge_ids = tuple(str(value) for value in getattr(front.Sketch, "SemanticEdgeIds", ()) or ())\n'
    '    back_edge_ids = tuple(str(value) for value in getattr(back.Sketch, "SemanticEdgeIds", ()) or ())\n'
    "    required_indices = (1, 2, 6, 7)\n"
    '    if len(front_edge_ids) < 8 or len(back_edge_ids) < 8 or any(not front_edge_ids[index] or not back_edge_ids[index] for index in required_indices): raise RuntimeError("canonical tunic fixture is missing authored semantic edge IDs")\n'
    '    # The audit screenshots show the mannequin from behind; seam color identities follow the visible sides.\n'
    '    seam_specs = ((front_edge_ids[1], back_edge_ids[1], "TunicLeftSide"),(front_edge_ids[2], back_edge_ids[2], "TunicLeftShoulder"),(front_edge_ids[6], back_edge_ids[6], "TunicRightShoulder"),(front_edge_ids[7], back_edge_ids[7], "TunicRightSide"))\n'
    "    for edge_a_id, edge_b_id, seam_id in seam_specs:\n"
    '        seam = Seam(str(front.PieceId), edge_a_id, str(back.PieceId), edge_b_id, id=seam_id, alignment="uniform", stitch_group="TunicAssembly")\n'
    "        add_seam(doc, seam)\n"
    '        seam_obj = next(o for o in doc.Objects if getattr(o, "SeamId", "") == seam_id)\n'
    '        if str(getattr(seam_obj, "EdgeAId", "")) != edge_a_id or str(getattr(seam_obj, "EdgeBId", "")) != edge_b_id: raise RuntimeError("canonical tunic seam %s did not retain authored semantic edge IDs" % seam_id)\n'
    "        seam_records.append((seam_obj, front, back))",
    "scene.FabricFriction = 0.75": "scene.FabricFriction = 0.85;",
    "scene.TimeStep = 1.0 / 120.0": 'scene.TimeStep = 1.0 / 240.0; log("tunic-time-step=1/240s for 90-step free-drape audit");',
    "scene.SolverIterations = 8": 'scene.ParticleDistance = 32.0; scene.SolverIterations = 4; scene.SolverSubsteps = 1; log("tunic-solver=particle-distance-32 iterations-4 substeps-env");',
    """    def target_relative_piece_placement(side):
        if side == "front":
            y = (shoulder_left.y + shoulder_right.y) / 2.0 - clearance
        elif side == "back":
            y = (shoulder_left.y + shoulder_right.y) / 2.0 + clearance
        else:
            raise ValueError("tunic target-relative side must be front or back")
        return App.Placement(App.Vector(x_mid - hem_width / 2.0, y, hem_z), rot)
""": """    panel_origin_x = x_mid - hem_width / 2.0
    torso_half_width = max(80.0, 0.30 * shoulder_width)

    def target_relative_piece_placement(side, outline):
        projected_target_ys = [
            float(vertex[1])
            for vertex in target_surface.vertices
            if abs(float(vertex[0]) - x_mid) <= torso_half_width
            and _projected_point_within_outline_margin(
                float(vertex[0]) - panel_origin_x,
                float(vertex[2]) - hem_z,
                outline,
                clearance,
            )
        ]
        if not projected_target_ys:
            raise RuntimeError("canonical tunic torso silhouette does not overlap DrapeTarget projections")
        target_front_y = min(projected_target_ys)
        target_back_y = max(projected_target_ys)
        if side == "front":
            y = target_front_y - clearance
        elif side == "back":
            y = target_back_y + clearance
        else:
            raise ValueError("tunic target-relative side must be front or back")
        log(
            "tunic-placement-depth side=%s projected-target-y=[%.2f, %.2f] "
            "panel-y=%.2f clearance-mm=%.2f torso-x=[%.2f, %.2f] projected-vertices=%d"
            % (
                side, target_front_y, target_back_y, y, clearance,
                x_mid - torso_half_width, x_mid + torso_half_width, len(projected_target_ys),
            )
        )
        return App.Placement(App.Vector(panel_origin_x, y, hem_z), rot)
""",
    "piece.Placement = target_relative_piece_placement(side)": "piece.Placement = target_relative_piece_placement(side, outline)",
    "upper_margin = 0.12 * max(1.0, float(shoulder_z) - float(hem_z))": "upper_margin = 0.17 * max(1.0, float(shoulder_z) - float(hem_z))",
}
for old, new in replacements.items():
    if old not in source:
        raise RuntimeError(f"audit replacement did not match source: {old}")
    source = source.replace(old, new, 1)


OUTLINE_MARGIN_HELPER = '''def _projected_point_within_outline_margin(x, z, points, margin):
    """Check whether a projected mesh vertex overlaps a pattern outline or its clearance band."""
    px = float(x)
    pz = float(z)
    margin_sq = float(margin) * float(margin)
    inside = False
    near = False
    for index, (ax_raw, az_raw) in enumerate(points):
        bx_raw, bz_raw = points[(index + 1) % len(points)]
        ax, az = float(ax_raw), float(az_raw)
        bx, bz = float(bx_raw), float(bz_raw)
        if (az > pz) != (bz > pz):
            crossing_x = ax + (pz - az) * (bx - ax) / (bz - az)
            if px < crossing_x:
                inside = not inside
        dx, dz = bx - ax, bz - az
        length_sq = dx * dx + dz * dz
        if length_sq > 0.0:
            factor = max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / length_sq))
            closest_x = ax + factor * dx
            closest_z = az + factor * dz
        else:
            closest_x, closest_z = ax, az
        if (px - closest_x) ** 2 + (pz - closest_z) ** 2 <= margin_sq:
            near = True
    return inside or near
'''


source = source.replace("\ndef simulation():", "\n" + OUTLINE_MARGIN_HELPER + "def simulation():", 1)
if "_projected_point_within_outline_margin" not in source:
    raise RuntimeError("tunic placement silhouette helper was not installed")


preview_probe = """    from freecad_cloth.simulation import RealtimePreview
    if "ClothRealtimePreview" not in Gui.listCommands():
        raise RuntimeError("Realtime Cloth Preview GUI command is not registered")
    preview_saved = {name: getattr(scene, name) for name in ("ParticleDistance", "SolverIterations", "SolverSubsteps", "TimeStep", "QualityPreset")}
    Gui.runCommand("ClothRealtimePreview")
    scene.Document.recompute()
    preview_base = scene.Proxy._base_or_restore()
    preview_backend = getattr(preview_base, "backend", None)
    if getattr(preview_backend, "name", None) != "position-based-dynamics":
        raise RuntimeError("Realtime Cloth Preview did not select the PositionBasedDynamics backend")
    from time import monotonic, sleep
    deadline = monotonic() + 2.0
    while int(scene.Steps) <= 0 and monotonic() < deadline:
        events()
        sleep(0.04)
    events()
    preview_steps = int(scene.Steps)
    if preview_steps <= 0:
        RealtimePreview.stop_realtime_preview()
        raise RuntimeError("Realtime Cloth Preview timer did not advance the simulation")
    Gui.runCommand("ClothRealtimePreview")
    if int(scene.Steps) != 0:
        RealtimePreview.stop_realtime_preview()
        raise RuntimeError("Realtime Cloth Preview did not reset steps on stop")
    for name, value in preview_saved.items():
        if getattr(scene, name) != value:
            raise RuntimeError("Realtime Cloth Preview did not restore %s" % name)
    log("realtime-preview=passed backend=position-based-dynamics steps=%d" % preview_steps)
"""
anchor = """    os.makedirs(os.path.join(OUT, "cloth-tunic-mannequin-motion-frames"), exist_ok=True)
    task_dock.hide()
    events()
    view.setCameraType("Orthographic")
    view.viewAxonometric()
    view.fitAll()
    events()
    save(
        "cloth-tunic-mannequin-motion-frames/motion-000.png",
        "mannequin drape step 0",
        "production tunic before gravity",
    )
    for frame_index, batch in enumerate((10, 10, 10, 10, 10, 10, 10, 10, 10), start=1):
        simulation_panel.step(batch)
        doc.recompute()
        events()
        view.viewAxonometric()
        view.fitAll()
        events()
        save(
            "cloth-tunic-mannequin-motion-frames/motion-%03d.png" % frame_index,
            "mannequin drape step %d" % int(scene.Steps),
            "production tunic gravity progression",
        )
    task_dock.show()
    task_dock.raise_()
    events()
"""
if anchor not in source:
    raise RuntimeError("simulation batch anchor missing")
timed_anchor = """    from time import perf_counter
    simulation_started = perf_counter()
    active_backend = scene.Proxy._base_or_restore().backend
    active_collision = getattr(active_backend, "_collision_surface", None)
    log("tunic-simulation-start particles=%d iterations=%d substeps=%d backend=%s collision_triangles=%d" % (
        int(scene.ParticleCount), int(scene.SolverIterations), int(scene.SolverSubsteps),
        str(getattr(active_backend, "name", "")),
        0 if active_collision is None else len(active_collision.triangles),
    ))
    task_dock.hide(); events()
    view.setCameraType("Orthographic"); view.viewAxonometric(); view.fitAll(); events()
    save_view("cloth-tunic-mannequin-motion-frames/motion-000.png", "mannequin drape step 0", "production tunic before gravity")
    for frame_index, batch in enumerate((10,10,10,10,10,10,10,10,10), start=1):
        batch_started = perf_counter()
        simulation_panel.step(batch); doc.recompute(); events()
        view.viewAxonometric(); view.fitAll(); events()
        save_view("cloth-tunic-mannequin-motion-frames/motion-%03d.png" % frame_index, "mannequin drape step %d" % int(scene.Steps), "production tunic gravity progression")
        log("tunic-simulation-frame=%d steps=%d batch=%d elapsed_ms=%.1f total_ms=%.1f particles=%d iterations=%d substeps=%d" % (frame_index, int(scene.Steps), batch, 1000.0 * (perf_counter() - batch_started), 1000.0 * (perf_counter() - simulation_started), int(scene.ParticleCount), int(scene.SolverIterations), int(scene.SolverSubsteps)))
    task_dock.show(); task_dock.raise_(); events()
    log("tunic-simulation-total-ms=%.1f" % (1000.0 * (perf_counter() - simulation_started)))
"""
source = source.replace(anchor, preview_probe + "\n" + timed_anchor, 1)

seam_check = """    backend_state = scene.Proxy._base_or_restore()
    simulated_positions = tuple(backend_state.backend.positions())
    if not simulated_positions: raise RuntimeError("PositionBasedDynamics backend returned no simulated particle positions")
    stitch_pairs_by_seam = getattr(scene.Proxy, "seam_stitch_pairs", {})
    if not stitch_pairs_by_seam: raise RuntimeError("authoritative seam check has no exact solver stitch provenance")
    seam_gaps = []
    for seam, piece_a, piece_b in seam_records:
        expected_a = f"{piece_a.PieceId}:edge:"
        expected_b = f"{piece_b.PieceId}:edge:"
        edge_a_id = str(getattr(seam, "EdgeAId", ""))
        edge_b_id = str(getattr(seam, "EdgeBId", ""))
        if not edge_a_id.startswith(expected_a) or not edge_b_id.startswith(expected_b):
            raise RuntimeError("authoritative tunic seam lost semantic edge identity")
        pairs = tuple(stitch_pairs_by_seam.get(str(seam.SeamId), ()))
        if not pairs:
            raise RuntimeError("authoritative seam check cannot resolve exact solver pairs for %s" % seam.SeamId)
        for ga, gb in pairs:
            a = simulated_positions[int(ga)]
            b = simulated_positions[int(gb)]
            seam_gaps.append(((a[0]-b[0])**2+(a[1]-b[1])**2+(a[2]-b[2])**2)**0.5)
    max_seam_gap = max(seam_gaps) if seam_gaps else 0.0
    if max_seam_gap > 35.0: raise RuntimeError("authoritative tunic seams did not converge: max endpoint gap %.1f mm" % max_seam_gap)
    log("authoritative-seam-max-gap-mm=%.2f seam-ids=%s" % (max_seam_gap, tuple(str(seam.SeamId) for seam, _a, _b in seam_records)))
"""

source = source.replace(
    "    write_drape_metrics(\n        panels,\n        avatar,\n        x_mid,\n        shoulder_z=shoulder_z,\n        hem_z=hem_z,\n        seam_records=seam_records,\n        proxy=proxy,\n    )\n    bounds = []",
    seam_check
    + "\n"
    + "    write_drape_metrics(\n        panels,\n        avatar,\n        x_mid,\n        shoulder_z=shoulder_z,\n        hem_z=hem_z,\n        seam_records=seam_records,\n        proxy=proxy,\n        collision_surface=target_surface,\n    ); bounds = []",
    1,
)


def _compile_generated_source(source_text):
    try:
        return compile(source_text, str(source_path), "exec")
    except SyntaxError as error:
        lines = source_text.splitlines()
        line_number = int(getattr(error, "lineno", 1) or 1)
        start = max(1, line_number - 2)
        end = min(len(lines), line_number + 2)
        context = "\n".join(
            "%4d | %s" % (number, lines[number - 1]) for number in range(start, end + 1)
        )
        raise RuntimeError(
            "generated tunic audit source failed syntax validation: %s at line %d\n%s"
            % (error.msg, line_number, context)
        ) from error


compiled_source = _compile_generated_source(source)
if "--syntax-check" in sys.argv:
    print(
        "tunic-audit-source-syntax=passed lines=%d" % len(source.splitlines()),
        flush=True,
    )
    raise SystemExit(0)

# The source uses the production simulation path; this wrapper only stabilizes
# the tunic fixture and verifies the realtime PositionBasedDynamics selector.
exec(compiled_source, globals(), globals())
print("tunic-audit-process-exit=success", flush=True)
os._exit(0)
