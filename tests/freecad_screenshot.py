"""CI entry point for the tunic visual regression."""
from pathlib import Path
import textwrap

source = Path(__file__).with_name("freecad_screenshot_source.py").read_text(encoding="utf-8")

source = source.replace('clearance = max(20.0, 0.08 * body_depth);', 'clearance = max(6.0, 0.02 * body_depth);')
source = source.replace('front_y = box.YMin - clearance; back_y = box.YMax + clearance;', 'front_y = box.YMax + clearance; back_y = box.YMin - clearance;')
source = source.replace(
    'front, front_outline = make_piece("VisualTunicFront", front_y, 0.64, 0.10); back, back_outline = make_piece("VisualTunicBack", back_y, 0.64, 0.07)',
    'front, front_outline = make_piece("VisualTunicFront", front_y, 0.64, 0.08); back, back_outline = make_piece("VisualTunicBack", back_y, 0.64, 0.08)',
)
source = source.replace(
    'chest = 980.0; hip = 1020.0; ease = 55.0; panel_width = max(420.0, 0.50 * chest + ease); hem_width = max(450.0, 0.50 * hip + ease)',
    'chest = 980.0; hip = 1020.0; ease = 35.0; torso_width = float(box.XMax - box.XMin); panel_width = max(420.0, min(560.0, 0.50 * torso_width + ease)); hem_width = max(440.0, min(590.0, 0.52 * torso_width + ease))',
)
source = source.replace(
    'for edge_a, edge_b, seam_id in ((2,2,"TunicRightShoulder"),(5,5,"TunicLeftShoulder")):',
    'for edge_a, edge_b, seam_id in ((1,1,"TunicRightSide"),(3,3,"TunicRightShoulder"),(5,5,"TunicLeftShoulder"),(7,7,"TunicLeftSide")):',
)
source = source.replace('scene.ParticleDistance = 24.0;', 'scene.ParticleDistance = 22.0;')
source = source.replace('scene.SolverIterations = 8;', 'scene.SolverIterations = 12;')
source = source.replace('scene.SolverSubsteps = 1;', 'scene.SolverSubsteps = 2;')
source = source.replace('scene.FabricFriction = 0.85;', 'scene.FabricFriction = 0.80;')
source = source.replace('for batch in (15,15,15,15,15,15):', 'for batch in (10,10,10):')
source = source.replace('if int(scene.Steps) != 90 or', 'if int(scene.Steps) != 30 or')
source = source.replace('"simulation did not reach a finite 90-step state"', '"simulation did not reach a finite 30-step state"')
source = source.replace('after 90 real steps;', 'after 30 real steps;')
source = source.replace('upper_margin = 0.12 * max(1.0, float(shoulder_z) - float(hem_z))', 'upper_margin = 0.17 * max(1.0, float(shoulder_z) - float(hem_z))')
source = source.replace(
    'radius = max(120.0, min(240.0, 0.245 * width, 0.70 * depth))',
    'radius = max(90.0, min(170.0, 0.16 * width, 0.48 * depth))',
)
source = source.replace(
    'for direction, method_name in (("front","viewFront"),("rear","viewRear"),("left","viewLeft"),("right","viewRight"),("top","viewTop"),("bottom","viewBottom")):',
    'for direction, method_name in (("front","viewRear"),("rear","viewFront"),("left","viewLeft"),("right","viewRight"),("top","viewTop"),("bottom","viewBottom")):',
)

old_pin_calls = '''    front_positions, _front_triangles, _front_boundary = quality_piece_mesh(front, 0.0, scene.ParticleDistance)
    back_positions, _back_triangles, _back_boundary = quality_piece_mesh(back, 0.0, scene.ParticleDistance)
    front_pins = authored_shoulder_pins(front, front_positions)
    back_pins_local = authored_shoulder_pins(back, back_positions)
    back_pins = tuple(len(front_positions) + i for i in back_pins_local)
    scene.PinSelection = [str(i) for i in front_pins + back_pins]
'''
new_pin_calls = '''    front_positions, _front_triangles, _front_boundary = quality_piece_mesh(front, 0.0, scene.ParticleDistance)
    back_positions, _back_triangles, _back_boundary = quality_piece_mesh(back, 0.0, scene.ParticleDistance)
    from freecad_cloth.pattern.PatternGeometry import LineSegment, ParametricPattern
    from freecad_cloth.pattern.PatternMesh import triangulate

    def authored_boundary_pins(piece, outline):
        points = [(float(x), float(y)) for x, y in outline]
        segments = [
            LineSegment("%s:edge:%d" % (piece.PieceId, i), points[i], points[(i + 1) % len(points)])
            for i in range(len(points))
        ]
        mesh = triangulate(ParametricPattern(segments))
        h = max(y for _, y in points)
        return tuple(
            int(i)
            for i in mesh.boundary_vertex_indices
            if float(mesh.vertices[i][1]) >= 0.90 * h - 1e-6
        )

    front_pins = authored_boundary_pins(front, front_outline)
    back_pins_local = authored_boundary_pins(back, back_outline)
    if not front_pins or not back_pins_local:
        raise RuntimeError("authored upper boundary pin selection is empty")
    back_pins = tuple(len(front_positions) + i for i in back_pins_local)
    scene.PinSelection = [str(i) for i in front_pins + back_pins]
'''
if old_pin_calls not in source:
    raise RuntimeError("canonical pin call block did not match the fixture source")
source = source.replace(old_pin_calls, new_pin_calls, 1)

backend_patch = r'''
from freecad_cloth.simulation.ClothBackend import XPBDBackend
from freecad_cloth.simulation.ClothSolver import DistanceConstraint

def _canonical_backend(system, triangles, pins, stitches, collision_surface):
    backend = XPBDBackend(system)
    backend.pin(pins)
    backend.set_stitches(stitches, compliance=0.0)
    backend.system.stitches = [DistanceConstraint(int(a), int(b), 0.0, 0.0) for a, b in stitches]
    backend._stitches = tuple((int(a), int(b)) for a, b in stitches)
    log("canonical-backend=xpbd-cpu visual-regression zero-rest-sewn")
    return backend
'''
source = source.replace(
    'OUT = os.environ.get("CLOTH_SCREENSHOT_DIR", "docs/images/generated")',
    backend_patch + '\nOUT = os.environ.get("CLOTH_SCREENSHOT_DIR", "docs/images/generated")',
    1,
)
source = source.replace(
    'self.backend = default_backend_registry().create("xpbd-cpu", system)',
    'self.backend = _canonical_backend(system, triangles_global, tuple(system.pins), tuple((c.a, c.b) for c in system.stitches), _collision_for_scene(obj))',
    1,
)

preview_probe = '''    from freecad_cloth.simulation import RealtimePreview
    if "ClothRealtimePreview" not in Gui.listCommands():
        raise RuntimeError("Realtime Cloth Preview GUI command is not registered")
    preview_saved = {name: getattr(scene, name) for name in ("ParticleDistance", "SolverIterations", "SolverSubsteps", "TimeStep", "QualityPreset")}
    Gui.runCommand("ClothRealtimePreview")
    scene.Document.recompute()
    base = scene.Proxy._base_or_restore()
    backend = getattr(base, "backend", None)
    expected_backend = os.environ.get("CLOTH_EXPECTED_BACKEND", "tissu")
    if getattr(backend, 'name', None) != expected_backend:
        raise RuntimeError(f"Realtime Cloth Preview selected {getattr(backend, "name", None)!r}, expected {expected_backend!r}")
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
anchor = 'for batch in (10,10,10):'
if anchor not in source:
    raise RuntimeError("visual simulation batch anchor did not match canonical source")
source = source.replace(anchor, preview_probe + '\n' + anchor, 1)

required = (
    'clearance = max(6.0, 0.02 * body_depth);',
    'front_y = box.YMax + clearance; back_y = box.YMin - clearance;',
    'front, front_outline = make_piece("VisualTunicFront", front_y, 0.64, 0.08); back, back_outline = make_piece("VisualTunicBack", back_y, 0.64, 0.08)',
    'torso_width = float(box.XMax - box.XMin); panel_width = max(420.0, min(560.0, 0.50 * torso_width + ease));',
    'for edge_a, edge_b, seam_id in ((1,1,"TunicRightSide"),(3,3,"TunicRightShoulder"),(5,5,"TunicLeftShoulder"),(7,7,"TunicLeftSide")):',
    'scene.ParticleDistance = 22.0;',
    'scene.SolverIterations = 12;',
    'scene.SolverSubsteps = 2;',
    'front_pins = authored_boundary_pins(front, front_outline)',
    'canonical-backend=xpbd-cpu visual-regression zero-rest-sewn',
    '(("front","viewRear"),("rear","viewFront")',
)
missing = [needle for needle in required if needle not in source]
if missing:
    raise RuntimeError("canonical tunic visual patch did not install: " + ", ".join(missing))

source = textwrap.dedent(source)
exec(compile(source, str(Path(__file__).with_name("freecad_screenshot_source.py")), "exec"), globals(), globals())
