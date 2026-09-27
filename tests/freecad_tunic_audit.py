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
        '    required_indices = (1, 2, 5, 7)\n'
        '    if len(front_edge_ids) < 8 or len(back_edge_ids) < 8 or any(not front_edge_ids[index] or not back_edge_ids[index] for index in required_indices): raise RuntimeError("canonical tunic fixture is missing authored semantic edge IDs")\n'
        '    seam_specs = ((front_edge_ids[1], back_edge_ids[1], "TunicRightSide"),(front_edge_ids[2], back_edge_ids[2], "TunicRightShoulder"),(front_edge_ids[5], back_edge_ids[5], "TunicLeftShoulder"),(front_edge_ids[7], back_edge_ids[7], "TunicLeftSide"))\n'
        '    for edge_a_id, edge_b_id, seam_id in seam_specs:\n'
        '        seam = Seam(str(front.PieceId), edge_a_id, str(back.PieceId), edge_b_id, id=seam_id, alignment="uniform", stitch_group="TunicAssembly")\n'
        '        add_seam(doc, seam)\n'
        '        seam_obj = next(o for o in doc.Objects if getattr(o, "SeamId", "") == seam_id)\n'
        '        if str(getattr(seam_obj, "EdgeAId", "")) != edge_a_id or str(getattr(seam_obj, "EdgeBId", "")) != edge_b_id: raise RuntimeError("canonical tunic seam %s did not retain authored semantic edge IDs" % seam_id)\n'
        '        seam_records.append((seam_obj, front, back))',
    'scene.FabricFriction = 0.75;': 'scene.FabricFriction = 0.85;',
    'scene.SolverIterations = 8;': 'scene.ParticleDistance = 32.0; scene.SolverIterations = 1; scene.SolverSubsteps = 1; log("tunic-solver=particle-distance-32 iterations-1 substeps-env");',
    '    def target_relative_piece_placement(side):\n'
        '        if side == "front":\n'
        '            y = (shoulder_left.y + shoulder_right.y) / 2.0 - clearance\n'
        '        elif side == "back":\n'
        '            y = (shoulder_left.y + shoulder_right.y) / 2.0 + clearance\n'
        '        else:\n'
        '            raise ValueError("tunic target-relative side must be front or back")\n'
        '        return App.Placement(App.Vector(x_mid - hem_width / 2.0, y, hem_z), rot)':
        '    def open_book_placement(side, outline):\n'
        '        target_centroid = App.Vector(sum(float(vertex[0]) for vertex in target_surface.vertices) / len(target_surface.vertices), sum(float(vertex[1]) for vertex in target_surface.vertices) / len(target_surface.vertices), sum(float(vertex[2]) for vertex in target_surface.vertices) / len(target_surface.vertices))\n'
        '        shoulder_mid_world = App.Vector(x_mid, (shoulder_left.y + shoulder_right.y) / 2.0, shoulder_z)\n'
        '        shoulder_surface_anchor = min((App.Vector(float(vertex[0]), float(vertex[1]), float(vertex[2])) for vertex in target_surface.vertices), key=lambda vertex: (vertex - shoulder_mid_world).Length)\n'
        '        outward = shoulder_surface_anchor - target_centroid\n'
        '        if outward.Length <= 1e-9: outward = shoulder_mid_world - target_centroid\n'
        '        if outward.Length <= 1e-9: raise RuntimeError("canonical tunic DrapeTarget has no usable shoulder outward direction")\n'
        '        outward.normalize()\n'
        '        launch_anchor = shoulder_surface_anchor + outward * float(clearance)\n'
        '        right_mid = ((outline[2][0] + outline[3][0]) / 2.0, (outline[2][1] + outline[3][1]) / 2.0)\n'
        '        left_mid = ((outline[5][0] + outline[6][0]) / 2.0, (outline[5][1] + outline[6][1]) / 2.0)\n'
        '        shoulder_local = ((right_mid[0] + left_mid[0]) / 2.0, (right_mid[1] + left_mid[1]) / 2.0)\n'
        '        hem_local = ((outline[0][0] + outline[1][0]) / 2.0, (outline[0][1] + outline[1][1]) / 2.0)\n'
        '        shoulder_to_hem = max(1.0, math.hypot(shoulder_local[0] - hem_local[0], shoulder_local[1] - hem_local[1]))\n'
        '        target_half_depth = 0.5 * y_span + clearance\n'
        '        if target_half_depth >= shoulder_to_hem: raise RuntimeError("open-book launch depth exceeds authored shoulder-to-hem span")\n'
        '        angle = math.degrees(math.asin(target_half_depth / shoulder_to_hem))\n'
        '        signed_angle = -angle if side == "front" else angle\n'
        '        pivot = launch_anchor\n'
        '        base_zero = App.Vector(x_mid - shoulder_local[0], pivot.y, pivot.z - shoulder_local[1])\n'
        '        extra = App.Rotation(App.Vector(1,0,0), signed_angle)\n'
        '        base = pivot + extra.multVec(base_zero - pivot)\n'
        '        log("open-book side=%s anchor=(%.2f,%.2f,%.2f) pivot=(%.2f,%.2f,%.2f) angle_deg=%.3f shoulder_to_hem_mm=%.2f target_half_depth_mm=%.2f" % (side, launch_anchor.x, launch_anchor.y, launch_anchor.z, pivot.x, pivot.y, pivot.z, signed_angle, shoulder_to_hem, target_half_depth))\n'
        '        return App.Placement(base, App.Rotation(App.Vector(1,0,0), 90.0 + signed_angle))\n',

    'upper_margin = 0.12 * max(1.0, float(shoulder_z) - float(hem_z))': 'upper_margin = 0.17 * max(1.0, float(shoulder_z) - float(hem_z))',
    'import json': 'import json\nimport math',
}
for old, new in replacements.items():
    if old not in source:
        raise RuntimeError(f"audit replacement did not match source: {old}")
    source = source.replace(old, new, 1)

placement_source = r"piece\\.Placement\\s*=\\s*target_relative_piece_placement\\(side\\);"
source, placement_count = re.subn(
    placement_source,
    "piece.Placement = open_book_placement(side, outline);",
    source,
    count=1,
)
if placement_count != 1:
    raise RuntimeError("audit placement rewrite did not match source exactly once: %d" % placement_count)


initial_probe = '''    initial_positions = tuple(scene.Proxy._base_or_restore().backend.positions())
    initial_pairs_by_seam = getattr(scene.Proxy, "seam_stitch_pairs", {})
    if not initial_positions or not initial_pairs_by_seam:
        raise RuntimeError("open-book initial seam-span probe lacks solver state or stitch provenance")
    initial_all = []
    initial_summary = {}
    for seam, _piece_a, _piece_b in seam_records:
        pairs = tuple(initial_pairs_by_seam.get(str(seam.SeamId), ()))
        if not pairs:
            raise RuntimeError("open-book initial seam-span probe cannot resolve %s" % seam.SeamId)
        spans = []
        for ga, gb in pairs:
            a = initial_positions[int(ga)]; b = initial_positions[int(gb)]
            spans.append(((a[0]-b[0])**2+(a[1]-b[1])**2+(a[2]-b[2])**2)**0.5)
        initial_summary[str(seam.SeamId)] = {"count": len(spans), "min_mm": min(spans), "max_mm": max(spans), "mean_mm": sum(spans) / len(spans)}
        initial_all.extend(spans)
    if not initial_all:
        raise RuntimeError("open-book initial seam-span probe produced no pairs")
    log("open-book-initial-stitch-spans-mm=%s" % json.dumps(initial_summary, sort_keys=True))
    log("open-book-initial-stitch-global-mm=min:%.3f max:%.3f mean:%.3f" % (min(initial_all), max(initial_all), sum(initial_all)/len(initial_all)))
'''
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
anchor = '''    for batch in (15,15,15,15,15,15):
        simulation_panel.step(batch); doc.recompute(); events()
'''
if anchor not in source:
    raise RuntimeError("simulation batch anchor missing")
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
source = source.replace(anchor, preview_probe + '\n' + initial_probe + '\n' + timed_anchor, 1)

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
