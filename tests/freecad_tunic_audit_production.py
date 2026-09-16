"""Production-oriented tunic visual audit built on the canonical FreeCAD GUI scenario."""
from pathlib import Path
import re

wrapper_path = Path(__file__).with_name("freecad_tunic_audit_tissu.py")
wrapper = wrapper_path.read_text(encoding="utf-8")

# Keep the canonical acceptance flow, but correct the authored garment assembly so the
# two panels actually form a worn tunic: correct front/rear placement, true side and
# shoulder seam correspondence, and placement-aware shoulder pins on both panels.
replacements = {
    "'front_y = box.YMin - clearance; back_y = box.YMax + clearance;': 'front_y = box.YMax + clearance; back_y = box.YMin - clearance;',":
    "'front_y = box.YMin - clearance; back_y = box.YMax + clearance;': 'front_y = box.YMin - clearance; back_y = box.YMax + clearance;',",
    "'front, front_outline = make_piece(\"VisualTunicFront\", front_y, 0.64, 0.10); back, back_outline = make_piece(\"VisualTunicBack\", back_y, 0.64, 0.07)':\n        'front, front_outline = make_piece(\"VisualTunicFront\", front_y, 0.78, 0.18); back, back_outline = make_piece(\"VisualTunicBack\", back_y, 0.76, 0.12)',":
    "'front, front_outline = make_piece(\"VisualTunicFront\", front_y, 0.64, 0.10); back, back_outline = make_piece(\"VisualTunicBack\", back_y, 0.64, 0.07)':\n        'front, front_outline = make_piece(\"VisualTunicFront\", front_y, 0.67, 0.10); back, back_outline = make_piece(\"VisualTunicBack\", back_y, 0.67, 0.10)',",
    "'for edge_a, edge_b, seam_id in ((2,2,\"TunicRightShoulder\"),(5,5,\"TunicLeftShoulder\")):' :\n        'for edge_a, edge_b, seam_id in ((1,1,\"TunicRightSide\"),(3,3,\"TunicRightShoulder\"),(5,5,\"TunicLeftShoulder\"),(7,7,\"TunicLeftSide\")):',":
    "'for edge_a, edge_b, seam_id in ((2,2,\"TunicRightShoulder\"),(5,5,\"TunicLeftShoulder\")):' :\n        'for edge_a, edge_b, seam_id in ((1,1,\"TunicRightSide\"),(2,2,\"TunicRightShoulder\"),(5,5,\"TunicLeftShoulder\"),(6,6,\"TunicLeftSide\")):',",
    "'scene.FabricFriction = 0.75;': 'scene.FabricFriction = 0.85;',":
    "'scene.FabricFriction = 0.85;': 'scene.FabricFriction = 0.88;',",
    "'for batch in (15,15,15,15,15,15):': 'for batch in (30,30,30,30):',":
    "'for batch in (40,40,40):': 'for batch in (30,30,30,30):',",
    "'if int(scene.Steps) != 90 or': 'if int(scene.Steps) != 120 or',":
    "'if int(scene.Steps) != 120 or': 'if int(scene.Steps) != 120 or',",
    "'\"simulation did not reach a finite 90-step state\"': '\"simulation did not reach a finite 120-step state\"',":
    "'\"simulation did not reach a finite 120-step state\"': '\"simulation did not reach a finite 120-step state\"',",
    "'after 90 real steps;': 'after 120 real steps;',":
    "'after 120 real steps;': 'after 120 real steps;',",
}
for old, new in replacements.items():
    if old in wrapper:
        wrapper = wrapper.replace(old, new, 1)

# Fix the wrapper's pin selector: authored sketch targets are local coordinates, while
# quality_piece_mesh returns placed/global coordinates. Pin both panels at the shoulder
# boundary so the sewn neckline and shoulders stay on the mannequin.
old_pin_function = '''    def authored_shoulder_pins(piece, outline, positions):
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
'''
new_pin_function = '''    def authored_shoulder_pins(piece, outline, positions):
        points = [(float(x), float(y)) for x, y in outline]
        shoulder_targets = (points[3], points[6])
        available = list(dict.fromkeys(int(i) for i in quality_piece_mesh(piece, 0.0, scene.ParticleDistance)[2]))
        if len(available) < len(shoulder_targets):
            raise RuntimeError("insufficient boundary vertices for authored shoulder pins")
        pins = []
        for local_x, local_y in shoulder_targets:
            target_point = piece.Placement.multVec(App.Vector(float(local_x), float(local_y), 0.0))
            index = min(
                available,
                key=lambda i: (positions[i][0] - target_point.x) ** 2
                + (positions[i][1] - target_point.y) ** 2
                + (positions[i][2] - target_point.z) ** 2,
            )
            pins.append(index)
            available.remove(index)
        return tuple(pins)
'''
if old_pin_function in wrapper:
    wrapper = wrapper.replace(old_pin_function, new_pin_function, 1)
else:
    raise RuntimeError("production audit could not locate authored shoulder pin function")

wrapper = wrapper.replace(
    'scene.PinSelection = [str(i) for i in front_pins]\n    log("pin-map front-shoulders=%s" % (front_pins,)); doc.recompute()',
    'back_pins_local = authored_shoulder_pins(back, back_outline, back_positions)\n'
    '    back_offset = len(front_positions)\n'
    '    back_pins = tuple(back_offset + i for i in back_pins_local)\n'
    '    scene.PinSelection = [str(i) for i in front_pins + back_pins]\n'
    '    log("pin-map front=%s back=%s" % (front_pins, back_pins_local)); doc.recompute()',
    1,
)

# Correct seam validation to inspect the actual side/shoulder boundary edges.
wrapper = wrapper.replace(
    'for edge_a, edge_b in ((1, 1), (3, 3), (5, 5), (7, 7)):',
    'for edge_a, edge_b in ((1, 1), (2, 2), (5, 5), (6, 6)):',
    1,
)

# Tighten only the production-readiness proximity gate. The canonical baseline was visibly
# floating despite passing the broader sanity bound; this gate rejects that state.
metric_anchor = '    write_drape_metrics(panels, avatar, x_mid, shoulder_z=shoulder_z, hem_z=hem_z); bounds = []'
metric_check = '''    write_drape_metrics(panels, avatar, x_mid, shoulder_z=shoulder_z, hem_z=hem_z)
    with open(METRICS, encoding="utf-8") as handle:
        metric_payload = json.load(handle)
    max_clearance = max(float(item["target_vertex_clearance"]) for item in metric_payload["panels"])
    if max_clearance > float(target_width) * 0.10:
        raise RuntimeError("production tunic remains visibly detached from avatar: max clearance %.1f mm" % max_clearance)
    bounds = []'''
if metric_anchor in wrapper:
    wrapper = wrapper.replace(metric_anchor, metric_check, 1)
else:
    raise RuntimeError("production audit could not locate drape metric anchor")

# Run the transformed canonical audit.
exec(compile(wrapper, str(wrapper_path), "exec"), globals(), globals())
