"""CI entry point for the tunic visual/simulation audit using Tissu."""
from pathlib import Path
import re

source_path = Path(__file__).with_name("freecad_screenshot_source.py")
source = source_path.read_text(encoding="utf-8")

# Tunic fixture profile: stable drape plus a closer-fitting shoulder/neckline silhouette.
replacements = {
    'clearance = max(20.0, 0.08 * body_depth);': 'clearance = max(8.0, 0.025 * body_depth);',
    'chest = 980.0; hip = 1020.0; ease = 55.0;': 'chest = 860.0; hip = 880.0; ease = 10.0;',
    'front_y = box.YMin - clearance; back_y = box.YMax + clearance;': 'front_y = box.YMax + clearance; back_y = box.YMin - clearance;',
    'front, front_outline = make_piece("VisualTunicFront", front_y, 0.64, 0.10); back, back_outline = make_piece("VisualTunicBack", back_y, 0.64, 0.07)':
        'front, front_outline = make_piece("VisualTunicFront", front_y, 0.78, 0.18); back, back_outline = make_piece("VisualTunicBack", back_y, 0.76, 0.12)',
    'for edge_a, edge_b, seam_id in ((2,2,"TunicRightShoulder"),(5,5,"TunicLeftShoulder")):' :
        'for edge_a, edge_b, seam_id in ((1,1,"TunicRightSide"),(3,3,"TunicRightShoulder"),(5,5,"TunicLeftShoulder"),(7,7,"TunicLeftSide")):',
    'scene.FabricFriction = 0.75;': 'scene.FabricFriction = 0.85;',
    'for batch in (15,15,15,15,15,15):': 'for batch in (5,5,5):',
    'if int(scene.Steps) != 90 or': 'if int(scene.Steps) != 15 or',
    '"simulation did not reach a finite 90-step state"': '"simulation did not reach a finite 15-step state"',
    'after 90 real steps;': 'after 15 real steps;',
    'upper_margin = 0.12 * max(1.0, float(shoulder_z) - float(hem_z))': 'upper_margin = 0.17 * max(1.0, float(shoulder_z) - float(hem_z))',
}
for old, new in replacements.items():
    if old not in source:
        raise RuntimeError(f"audit replacement did not match source: {old}")
    source = source.replace(old, new, 1)

# Use the same authored shoulder pinning as the canonical tunic turntable:
# two boundary vertices on the front panel only; the rear panel is sewn and free.
pin_pattern = re.compile(r'    def authored_shoulder_pins\(piece, positions\):.*?    for source in \(doc\.getObject', re.S)
pin_replacement = '''    def authored_shoulder_pins(piece, outline, positions):
        points = [(float(x), float(y)) for x, y in outline]
        shoulder_targets = (points[3], points[6])
        available = list(dict.fromkeys(int(i) for i in quality_piece_mesh(piece, 0.0, scene.ParticleDistance)[2]))
        if len(available) < len(shoulder_targets):
            raise RuntimeError("insufficient boundary vertices for authored shoulder pins")
        pins = []
        for target_x, target_y in shoulder_targets:
            index = min(
                available,
                key=lambda i: (positions[i][0] - target_x) ** 2 + (positions[i][1] - target_y) ** 2,
            )
            pins.append(index)
            available.remove(index)
        return tuple(pins)

    front_positions, _front_triangles, _front_boundary = quality_piece_mesh(front, 0.0, scene.ParticleDistance)
    front_pins = authored_shoulder_pins(front, front_outline, front_positions)
    scene.PinSelection = [str(i) for i in front_pins]
    log("pin-map front-shoulders=%s" % (front_pins,)); doc.recompute()

    for source in (doc.getObject'''
source, pin_count = pin_pattern.subn(pin_replacement, source, count=1)
if pin_count != 1:
    raise RuntimeError("boundary pin patch did not match source")

# Backend selection is owned by the production runtime. The audit must not rewrite
# an obsolete backend assignment or duplicate solver construction.
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
anchor = '    for batch in (5,5,5):'
if anchor not in source:
    raise RuntimeError("simulation batch anchor missing")
source = source.replace(anchor, preview_probe + '\n' + anchor, 1)

exec(compile(source, str(source_path), "exec"), globals(), globals())
