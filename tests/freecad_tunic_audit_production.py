"""Production-oriented tunic visual audit using the canonical FreeCAD GUI scenario."""
from pathlib import Path
import re
import json

source_path = Path(__file__).with_name("freecad_screenshot_source.py")
source = source_path.read_text(encoding="utf-8")

replacements = {
    "clearance = max(20.0, 0.08 * body_depth);": "clearance = max(6.0, 0.02 * body_depth);",
    "chest = 980.0; hip = 1020.0; ease = 55.0;": "chest = 860.0; hip = 880.0; ease = 10.0;",
    "front_y = box.YMin - clearance; back_y = box.YMax + clearance;": "front_y = box.YMax + clearance; back_y = box.YMin - clearance;",
    'front, front_outline = make_piece("VisualTunicFront", front_y, 0.64, 0.10); back, back_outline = make_piece("VisualTunicBack", back_y, 0.64, 0.07)':
        'front, front_outline = make_piece("VisualTunicFront", front_y, 0.64, 0.08); back, back_outline = make_piece("VisualTunicBack", back_y, 0.64, 0.08)',
    'for edge_a, edge_b, seam_id in ((2,2,"TunicRightShoulder"),(5,5,"TunicLeftShoulder")):':
        'for edge_a, edge_b, seam_id in ((2,2,"TunicRightShoulder"),(5,5,"TunicLeftShoulder")):',
    "scene.ParticleDistance = 24.0;": "scene.ParticleDistance = 22.0;",
    "scene.SolverIterations = 8;": "scene.SolverIterations = 12;",
    "scene.SolverSubsteps = 1;": "scene.SolverSubsteps = 2;",
    "scene.FabricFriction = 0.75;": "scene.FabricFriction = 0.80;",
    "for batch in (15,15,15,15,15,15):": "for batch in (30,30,30,30):",
    "if int(scene.Steps) != 90 or": "if int(scene.Steps) != 120 or",
    '"simulation did not reach a finite 90-step state"': '"simulation did not reach a finite 120-step state"',
    "after 90 real steps;": "after 120 real steps;",
    "upper_margin = 0.12 * max(1.0, float(shoulder_z) - float(hem_z))": "upper_margin = 0.17 * max(1.0, float(shoulder_z) - float(hem_z))",
    "front_positions, _front_triangles, _front_boundary = quality_piece_mesh(front, 0.0, scene.ParticleDistance)": "front_positions, _front_triangles, front_boundary = quality_piece_mesh(front, 0.0, scene.ParticleDistance)",
    "back_positions, _back_triangles, _back_boundary = quality_piece_mesh(back, 0.0, scene.ParticleDistance)": "back_positions, _back_triangles, back_boundary = quality_piece_mesh(back, 0.0, scene.ParticleDistance)",
    "front_pins = authored_shoulder_pins(front, front_positions)": "front_pins = authored_shoulder_pins(front, front_outline, front_positions)",
    "back_pins_local = authored_shoulder_pins(back, back_positions)": "back_pins_local = authored_shoulder_pins(back, back_outline, back_positions)",
}
for old, new in replacements.items():
    if old not in source:
        raise RuntimeError(f"production replacement did not match source: {old}")
    source = source.replace(old, new, 1)

pin_pattern = re.compile(r'    def authored_shoulder_pins\(piece, positions\):.*?        return tuple\(result\)\n', re.S)
pin_replacement = '''    def authored_shoulder_pins(piece, outline, positions):
        points = [(float(x), float(y)) for x, y in outline]
        shoulder_targets = (points[3], points[6])
        boundary_indices = quality_piece_mesh(piece, 0.0, scene.ParticleDistance)[2]
        available = list(dict.fromkeys(int(i) for i in boundary_indices))
        if len(available) < len(shoulder_targets):
            raise RuntimeError("insufficient boundary vertices for authored shoulder pins")
        pins = []
        for local_x, local_y in shoulder_targets:
            target_point = piece.Placement.multVec(App.Vector(float(local_x), float(local_y), 0.0))
            index = min(available, key=lambda i: (positions[i][0] - target_point.x) ** 2 + (positions[i][1] - target_point.y) ** 2 + (positions[i][2] - target_point.z) ** 2)
            pins.append(index)
            available.remove(index)
        return tuple(pins)
'''
source, pin_count = pin_pattern.subn(pin_replacement, source, count=1)
if pin_count != 1:
    raise RuntimeError("production shoulder pin function did not match source")

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
    for _ in range(12):
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
solve_anchor = "    for batch in (30,30,30,30):"
if solve_anchor not in source:
    raise RuntimeError("production solve anchor not found")
source = source.replace(solve_anchor, preview_probe + "\n" + solve_anchor, 1)

seam_check = '''    backend_state = scene.Proxy._base_or_restore()
    simulated_positions = tuple(backend_state.backend.positions())
    if not simulated_positions:
        raise RuntimeError("Tissu backend returned no simulated particle positions")
    back_offset = len(front_positions)
    seam_gaps = []
    for edge_a, edge_b in ((2, 2), (5, 5)):
        front_a0 = front_boundary[edge_a]; front_a1 = front_boundary[(edge_a + 1) % len(front_boundary)]
        back_a0 = back_boundary[edge_b] + back_offset; back_a1 = back_boundary[(edge_b + 1) % len(back_boundary)] + back_offset
        for ia, ib in ((front_a0, back_a0), (front_a1, back_a1)):
            a = simulated_positions[ia]; b = simulated_positions[ib]
            seam_gaps.append(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5)
    seam_gap = max(seam_gaps) if seam_gaps else 0.0
    if seam_gap > 35.0:
        raise RuntimeError("simulated authored shoulder seams did not converge: max endpoint gap %.1f mm" % seam_gap)
    log("tunic-authored-shoulder-max-gap-mm=%.2f" % seam_gap)
'''
metric_anchor = '    write_drape_metrics(panels, avatar, x_mid, shoulder_z=shoulder_z, hem_z=hem_z); bounds = []'
if metric_anchor not in source:
    raise RuntimeError("production metrics anchor not found")
metric_check = '''    write_drape_metrics(panels, avatar, x_mid, shoulder_z=shoulder_z, hem_z=hem_z)
    with open(METRICS, encoding="utf-8") as handle:
        metric_payload = json.load(handle)
    production_target_width = float(max(avatar.Mesh.BoundBox.XMax - avatar.Mesh.BoundBox.XMin, avatar.Mesh.BoundBox.YMax - avatar.Mesh.BoundBox.YMin))
    max_clearance = max(float(item["target_vertex_clearance"]) for item in metric_payload["panels"])
    if max_clearance > production_target_width * 0.10:
        raise RuntimeError("production tunic remains visibly detached from avatar: max clearance %.1f mm" % max_clearance)
    bounds = []'''
source = source.replace(metric_anchor, seam_check + metric_check, 1)

exec(compile(source, str(source_path), "exec"), globals(), globals())
