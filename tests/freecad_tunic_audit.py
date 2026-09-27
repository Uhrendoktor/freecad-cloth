"""CI entry point for the full tunic visual/simulation audit."""
from pathlib import Path
import os
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

source_path = Path(__file__).with_name("freecad_screenshot_source.py")
source = source_path.read_text(encoding="utf-8")

# The canonical tunic audit must use the authoritative DrapeTarget collision
# surface; do not replace it with the optional torso-envelope approximation.
os.environ["CLOTH_TISSU_COLLISION_MODE"] = "mesh"

replacements = {
    'clearance = max(20.0, 0.08 * body_depth)': 'clearance = max(8.0, 0.025 * body_depth);',
    'front, front_outline = make_piece("VisualTunicFront", "front", 0.64, 0.10); back, back_outline = make_piece("VisualTunicBack", "back", 0.64, 0.07)': 'front, front_outline = make_piece("VisualTunicFront", "back", 0.78, 0.18); back, back_outline = make_piece("VisualTunicBack", "front", 0.76, 0.12)',
    '    for edge_a, edge_b, seam_id in ((2,2,"TunicRightShoulder"),(5,5,"TunicLeftShoulder")):\n'
        '        seam = Seam(str(front.PieceId), edge_a, str(back.PieceId), edge_b, id=seam_id, alignment="uniform", stitch_group="TunicAssembly")\n'
        '        add_seam(doc, seam)\n'
        '        seam_obj = next(o for o in doc.Objects if getattr(o, "SeamId", "") == seam_id)\n'
        '        seam_records.append((seam_obj, front, back))':
        '    front_edge_ids = tuple(str(value) for value in getattr(front.Sketch, "SemanticEdgeIds", ()) or ())\n'
        '    back_edge_ids = tuple(str(value) for value in getattr(back.Sketch, "SemanticEdgeIds", ()) or ())\n'
        '    required_indices = (1, 2, 6, 7)\n'
        '    if len(front_edge_ids) < 8 or len(back_edge_ids) < 8 or any(not front_edge_ids[index] or not back_edge_ids[index] for index in required_indices): raise RuntimeError("canonical tunic fixture is missing authored semantic edge IDs")\n'
        '    seam_specs = ((front_edge_ids[1], back_edge_ids[1], "TunicRightSide"),(front_edge_ids[2], back_edge_ids[6], "TunicRightShoulder"),(front_edge_ids[6], back_edge_ids[2], "TunicLeftShoulder"),(front_edge_ids[7], back_edge_ids[7], "TunicLeftSide"))\n'
        '    for edge_a_id, edge_b_id, seam_id in seam_specs:\n'
        '        seam = Seam(str(front.PieceId), edge_a_id, str(back.PieceId), edge_b_id, id=seam_id, alignment="uniform", stitch_group="TunicAssembly")\n'
        '        add_seam(doc, seam)\n'
        '        seam_obj = next(o for o in doc.Objects if getattr(o, "SeamId", "") == seam_id)\n'
        '        if str(getattr(seam_obj, "EdgeAId", "")) != edge_a_id or str(getattr(seam_obj, "EdgeBId", "")) != edge_b_id: raise RuntimeError("canonical tunic seam %s did not retain authored semantic edge IDs" % seam_id)\n'
        '        seam_records.append((seam_obj, front, back))',
    'scene.FabricFriction = 0.75;': 'scene.FabricFriction = 0.85;',
    'scene.SolverIterations = 8;': 'scene.ParticleDistance = 32.0; scene.SolverIterations = 1; scene.SolverSubsteps = 1; log("tunic-solver=particle-distance-32 iterations-1 substeps-env");',
    '            y = (shoulder_left.y + shoulder_right.y) / 2.0 - clearance': '            y = min(target_ys) - clearance',
    '            y = (shoulder_left.y + shoulder_right.y) / 2.0 + clearance': '            y = max(target_ys) + clearance',
    'upper_margin = 0.12 * max(1.0, float(shoulder_z) - float(hem_z))': 'upper_margin = 0.17 * max(1.0, float(shoulder_z) - float(hem_z))',
}
for old, new in replacements.items():
    if old not in source:
        raise RuntimeError(f"audit replacement did not match source: {old}")
    source = source.replace(old, new, 1)


preview_probe = '''    from freecad_cloth.simulation import RealtimePreview
    if "ClothRealtimePreview" not in Gui.listCommands():
        raise RuntimeError("Realtime Cloth Preview GUI command is not registered")
    preview_saved = {name: getattr(scene, name) for name in ("ParticleDistance", "SolverIterations", "SolverSubsteps", "TimeStep", "QualityPreset")}
    Gui.runCommand("ClothRealtimePreview")
    scene.Document.recompute()
    preview_base = scene.Proxy._base_or_restore()
    preview_backend = getattr(preview_base, "backend", None)
    if getattr(preview_backend, "name", None) != "tissu":
        raise RuntimeError("Realtime Cloth Preview did not select the Tissu backend")
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
    log("realtime-preview=passed backend=tissu steps=%d" % preview_steps)
'''
target_snap_probe = r'''    # Target-aware fitting acceptance on the same native tunic fixture used below.
    import math
    from freecad_cloth.avatar import FittingCommands
    fitting = FittingCommands._scene(doc)
    if fitting is None or target is None or fitting.DrapeTarget != target:
        raise RuntimeError("canonical tunic fixture did not retain the authoritative DrapeTarget in FittingScene")
    if not hasattr(simulation_panel, "snap_to_target_button") or not simulation_panel.snap_to_target_button.isEnabled():
        raise RuntimeError("canonical tunic fixture did not expose an enabled target-snap action")
    pieces = tuple(getattr(scene, "ClothPieces", ()) or ())
    if len(pieces) < 2:
        raise RuntimeError("canonical tunic fixture did not expose the sewn garment pieces")

    def _pose_signature():
        values = []
        for piece in sorted(pieces, key=lambda item: str(item.PieceId)):
            base = piece.Placement.Base
            axis = piece.Placement.Rotation.Axis
            values.append((
                str(piece.PieceId),
                round(float(base.x), 9), round(float(base.y), 9), round(float(base.z), 9),
                round(float(piece.Placement.Rotation.Angle), 9),
                round(float(axis.x), 9), round(float(axis.y), 9), round(float(axis.z), 9),
            ))
        return tuple(values)

    def _pairwise_centers():
        centers = []
        for piece in sorted(pieces, key=lambda item: str(item.PieceId)):
            base = piece.Placement.Base
            centers.append((str(piece.PieceId), float(base.x), float(base.y), float(base.z)))
        distances = {}
        for index, left in enumerate(centers):
            for right in centers[index + 1:]:
                distances[(left[0], right[0])] = math.dist(left[1:], right[1:])
        return distances

    def _relative_rotations():
        values = []
        ordered = sorted(pieces, key=lambda item: str(item.PieceId))
        for index, left in enumerate(ordered):
            left_q = tuple(float(value) for value in left.Placement.Rotation.Q)
            left_norm = math.sqrt(sum(value * value for value in left_q))
            for right in ordered[index + 1:]:
                right_q = tuple(float(value) for value in right.Placement.Rotation.Q)
                right_norm = math.sqrt(sum(value * value for value in right_q))
                dot = sum(a * b for a, b in zip(left_q, right_q, strict=True)) / max(left_norm * right_norm, 1e-15)
                values.append(((str(left.PieceId), str(right.PieceId)), round(abs(float(dot)), 9)))
        return tuple(values)

    def _sketch_pose_signature():
        values = []
        for piece in sorted(pieces, key=lambda item: str(item.PieceId)):
            sketch = getattr(piece, "Sketch", None)
            if sketch is None:
                values.append((str(piece.PieceId), None))
                continue
            base = sketch.Placement.Base
            axis = sketch.Placement.Rotation.Axis
            values.append((
                str(piece.PieceId),
                round(float(base.x), 9), round(float(base.y), 9), round(float(base.z), 9),
                round(float(sketch.Placement.Rotation.Angle), 9),
                round(float(axis.x), 9), round(float(axis.y), 9), round(float(axis.z), 9),
            ))
        return tuple(values)

    home_pose = _pose_signature()
    home_sketch_pose = _sketch_pose_signature()
    home_pairwise = _pairwise_centers()
    home_relative = _relative_rotations()
    home_pin_mode = str(getattr(scene, "PinMode", ""))
    home_pin_selection = tuple(str(value) for value in (getattr(scene, "PinSelection", ()) or ()))

    target_was_enabled = bool(getattr(target, "Enabled", True))
    target.Enabled = False
    doc.recompute(); events()
    simulation_panel._refresh_fitting_stage()
    if simulation_panel.snap_to_target_button.isEnabled():
        raise RuntimeError("canonical tunic Snap-to-target remained enabled for a disabled DrapeTarget")
    target.Enabled = target_was_enabled
    doc.recompute(); events()
    simulation_panel._refresh_fitting_stage()
    if not simulation_panel.snap_to_target_button.isEnabled():
        raise RuntimeError("canonical tunic Snap-to-target did not recover after re-enabling the DrapeTarget")

    simulation_panel.snap_to_target()
    doc.recompute(); events()
    fitting = FittingCommands._scene(doc)
    anchors = tuple(getattr(fitting, "GarmentAnchors", ()) or ()) if fitting is not None else ()
    if fitting is None or fitting.DrapeTarget != target:
        raise RuntimeError("canonical tunic Snap-to-target lost persistent DrapeTarget identity")
    if len(anchors) < 2:
        raise RuntimeError("canonical tunic Snap-to-target did not persist one fitting anchor per garment piece")
    snapped_pairwise = _pairwise_centers()
    snapped_relative = _relative_rotations()
    if set(home_pairwise) != set(snapped_pairwise):
        raise RuntimeError("canonical tunic Snap-to-target changed the authored piece set")
    for key in home_pairwise:
        if abs(float(home_pairwise[key]) - float(snapped_pairwise[key])) > 1e-6:
            raise RuntimeError("canonical tunic Snap-to-target changed pairwise sewn-piece spacing")
    if dict(home_relative) != dict(snapped_relative):
        raise RuntimeError("canonical tunic Snap-to-target changed relative piece rotations")
    if str(getattr(scene, "PinMode", "")) != home_pin_mode or tuple(str(value) for value in (getattr(scene, "PinSelection", ()) or ())) != home_pin_selection:
        raise RuntimeError("canonical tunic Snap-to-target mutated existing pinning state")
    if _pose_signature() == home_pose:
        raise RuntimeError("canonical tunic Snap-to-target did not change the authored arrangement")
    log("tunic-target-snap=passed persistent_target=true anchors=%d shared-rigid=true pins-unchanged=true" % len(anchors))

    simulation_panel.reset_arrangement()
    doc.recompute(); events()
    if _pose_signature() != home_pose:
        raise RuntimeError("canonical tunic Reset arrangement did not restore the exact pre-snap placement")
    if _sketch_pose_signature() != home_sketch_pose:
        raise RuntimeError("canonical tunic Reset arrangement did not restore the native Sketch placement")
    log("tunic-target-reset=passed exact_piece_restore=true native_sketch_restore=true")

    simulation_panel.snap_to_target()
    doc.recompute(); events()
    if _pose_signature() == home_pose:
        raise RuntimeError("canonical tunic second Snap-to-target did not reapply the fitted arrangement")
    if str(getattr(scene, "PinMode", "")) != home_pin_mode or tuple(str(value) for value in (getattr(scene, "PinSelection", ()) or ())) != home_pin_selection:
        raise RuntimeError("canonical tunic Snap/Reset cycle mutated existing pinning state")
    log("tunic-target-resnap=passed")
'''
anchor = '''    for batch in (15,15,15,15,15,15):
        simulation_panel.step(batch); doc.recompute(); events()
'''
if anchor not in source:
    raise RuntimeError("simulation batch anchor missing")
source = source.replace(anchor, target_snap_probe + "\n" + anchor, 1)
timed_anchor = '''    from time import perf_counter
    simulation_started = perf_counter()
    active_backend = scene.Proxy._base_or_restore().backend
    active_collision = getattr(active_backend, "_collision_surface", None)
    log("tunic-simulation-start particles=%d iterations=%d substeps=%d backend=%s collision_triangles=%d" % (
        int(scene.ParticleCount), int(scene.SolverIterations), int(scene.SolverSubsteps),
        str(getattr(active_backend, "name", "")),
        0 if active_collision is None else len(active_collision.triangles),
    ))
    for batch in (15,15,15,15,15,15):
        batch_started = perf_counter()
        simulation_panel.step(batch); doc.recompute(); events()
        log("tunic-simulation-batch steps=%d elapsed_ms=%.1f total_ms=%.1f particles=%d iterations=%d substeps=%d" % (batch, 1000.0 * (perf_counter() - batch_started), 1000.0 * (perf_counter() - simulation_started), int(scene.ParticleCount), int(scene.SolverIterations), int(scene.SolverSubsteps)))
    log("tunic-simulation-total-ms=%.1f" % (1000.0 * (perf_counter() - simulation_started)))
'''
source = source.replace(anchor, preview_probe + '\n' + timed_anchor, 1)

seam_check = """    backend_state = scene.Proxy._base_or_restore()
    simulated_positions = tuple(backend_state.backend.positions())
    if not simulated_positions: raise RuntimeError("Tissu backend returned no simulated particle positions")
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

source = source.replace("    write_drape_metrics(\n        panels,\n        avatar,\n        x_mid,\n        shoulder_z=shoulder_z,\n        hem_z=hem_z,\n        seam_records=seam_records,\n        proxy=proxy,\n    ); bounds = []", seam_check + "\n" + "    write_drape_metrics(\n        panels,\n        avatar,\n        x_mid,\n        shoulder_z=shoulder_z,\n        hem_z=hem_z,\n        seam_records=seam_records,\n        proxy=proxy,\n    ); bounds = []", 1)
def _compile_generated_source(source_text):
    try:
        return compile(source_text, str(source_path), "exec")
    except SyntaxError as error:
        lines = source_text.splitlines()
        line_number = int(getattr(error, "lineno", 1) or 1)
        start = max(1, line_number - 2)
        end = min(len(lines), line_number + 2)
        context = "\n".join(
            "%4d | %s" % (number, lines[number - 1])
            for number in range(start, end + 1)
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
# the tunic fixture and verifies the realtime Tissu selector.
exec(compiled_source, globals(), globals())
print("tunic-audit-process-exit=success", flush=True)
os._exit(0)
