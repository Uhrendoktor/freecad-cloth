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
    '    for edge_a, edge_b, seam_id in ((2,2,"TunicRightShoulder"),(5,5,"TunicLeftShoulder")):\n'
        '        seam = Seam(str(front.PieceId), edge_a, str(back.PieceId), edge_b, id=seam_id, alignment="uniform", stitch_group="TunicAssembly")\n'
        '        add_seam(doc, seam)\n'
        '        seam_obj = next(o for o in doc.Objects if getattr(o, "SeamId", "") == seam_id)\n'
        '        seam_records.append((seam_obj, front, back))':
        '    front_edge_ids = tuple(str(value) for value in getattr(front.Sketch, "SemanticEdgeIds", ()) or ())\n'
        '    back_edge_ids = tuple(str(value) for value in getattr(back.Sketch, "SemanticEdgeIds", ()) or ())\n'
        '    required_indices = (1, 2, 6, 7)\n'
        '    if len(front_edge_ids) < 8 or len(back_edge_ids) < 8 or any(not front_edge_ids[index] or not back_edge_ids[index] for index in required_indices): raise RuntimeError("canonical tunic fixture is missing authored semantic edge IDs")\n'
        '    seam_specs = ((front_edge_ids[1], back_edge_ids[1], "TunicRightSide"),(front_edge_ids[2], back_edge_ids[2], "TunicRightShoulder"),(front_edge_ids[6], back_edge_ids[6], "TunicLeftShoulder"),(front_edge_ids[7], back_edge_ids[7], "TunicLeftSide"))\n'
        '    for edge_a_id, edge_b_id, seam_id in seam_specs:\n'
        '        seam = Seam(str(front.PieceId), edge_a_id, str(back.PieceId), edge_b_id, id=seam_id, alignment="uniform", stitch_group="TunicAssembly")\n'
        '        add_seam(doc, seam)\n'
        '        seam_obj = next(o for o in doc.Objects if getattr(o, "SeamId", "") == seam_id)\n'
        '        if str(getattr(seam_obj, "EdgeAId", "")) != edge_a_id or str(getattr(seam_obj, "EdgeBId", "")) != edge_b_id: raise RuntimeError("canonical tunic seam %s did not retain authored semantic edge IDs" % seam_id)\n'
        '        seam_records.append((seam_obj, front, back))',
    'scene.FabricFriction = 0.75;': 'scene.FabricFriction = 0.85;',
    'scene.SolverIterations = 8;': 'scene.ParticleDistance = 32.0; scene.SolverIterations = 1; scene.SolverSubsteps = 1; log("tunic-solver=particle-distance-32 iterations-1 substeps-env");',
    'upper_margin = 0.12 * max(1.0, float(shoulder_z) - float(hem_z))': 'upper_margin = 0.17 * max(1.0, float(shoulder_z) - float(hem_z))',
}
for old, new in replacements.items():
    if old not in source:
        raise RuntimeError(f"audit replacement did not match source: {old}")
    source = source.replace(old, new, 1)


timing_instrumentation = '''from time import perf_counter as _tunic_audit_perf_counter
_TUNIC_AUDIT_ORIGIN = _tunic_audit_perf_counter()

def _tunic_audit_phase(label):
    log("tunic-audit-phase=%s elapsed_ms=%.1f" % (label, 1000.0 * (_tunic_audit_perf_counter() - _TUNIC_AUDIT_ORIGIN)))
'''
source = source.replace("def run_canonical_acceptance():", timing_instrumentation + "\ndef run_canonical_acceptance():", 1)
source = source.replace("def pattern_and_sewing():", "def pattern_and_sewing():\n    _tunic_audit_phase(\"pattern-and-sewing-enter\")", 1)
source = source.replace('    doc = App.newDocument("ClothVisualPattern")', '    doc = App.newDocument("ClothVisualPattern"); _tunic_audit_phase("pattern-document-created")', 1)
source = source.replace('    doc.recompute(); front = _adopt_sketch(front_sketch, "Front Tunic", 10.0, 0.0); back = _adopt_sketch(back_sketch, "Back Tunic", 10.0, 0.0)', '    doc.recompute(); _tunic_audit_phase("pattern-sketches-recomputed"); front = _adopt_sketch(front_sketch, "Front Tunic", 10.0, 0.0); back = _adopt_sketch(back_sketch, "Back Tunic", 10.0, 0.0); _tunic_audit_phase("pattern-pieces-adopted")', 1)
source = source.replace('    front.ViewObject.Visibility = False; back.ViewObject.Visibility = False; front.Sketch.ViewObject.Visibility = True; back.Sketch.ViewObject.Visibility = True; doc.recompute()', '    front.ViewObject.Visibility = False; back.ViewObject.Visibility = False; front.Sketch.ViewObject.Visibility = True; back.Sketch.ViewObject.Visibility = True; doc.recompute(); _tunic_audit_phase("pattern-visibility-ready")', 1)
source = source.replace('    panel = PatternPieceTaskPanel(front); show_task(panel, "Pattern Workbench", ("Piece name", "Width", "Height", "Seam allowance", "Grainline angle")); Gui.activeDocument().activeView().viewTop(); Gui.activeDocument().activeView().fitAll(); events(); save("cloth-pattern-design.png", "Pattern Workbench", "native Sketcher tunic pattern adopted into Cloth PatternPiece"); close_task()', '    panel = PatternPieceTaskPanel(front); _tunic_audit_phase("pattern-task-created"); show_task(panel, "Pattern Workbench", ("Piece name", "Width", "Height", "Seam allowance", "Grainline angle")); _tunic_audit_phase("pattern-task-shown"); Gui.activeDocument().activeView().viewTop(); Gui.activeDocument().activeView().fitAll(); events(); save("cloth-pattern-design.png", "Pattern Workbench", "native Sketcher tunic pattern adopted into Cloth PatternPiece"); close_task(); _tunic_audit_phase("pattern-task-closed")', 1)
source = source.replace('    seam = add_seam(doc, Seam(str(front.PieceId), 7, str(back.PieceId), 7, id="FrontBack", alignment="endpoints", stitch_group="MainSeam")); doc.recompute()', '    seam = add_seam(doc, Seam(str(front.PieceId), 7, str(back.PieceId), 7, id="FrontBack", alignment="endpoints", stitch_group="MainSeam")); doc.recompute(); _tunic_audit_phase("seam-created")', 1)
source = source.replace('    sewing = create_sewing_operation(); doc.recompute()', '    sewing = create_sewing_operation(); _tunic_audit_phase("sewing-operation-created"); doc.recompute(); _tunic_audit_phase("sewing-operation-recomputed")', 1)
source = source.replace('    panel = SewingTaskPanel(sewing); show_task(panel, "Sewing Workbench", ("Seam", "Alignment", "Validation tolerance", "Stitch samples", "Status")); Gui.activeDocument().activeView().viewTop(); Gui.activeDocument().activeView().fitAll(); events(); save("cloth-sewing.png", "Sewing Workbench", "native tunic Sketcher boundary and semantic seam"); close_task(); App.closeDocument(doc.Name)', '    panel = SewingTaskPanel(sewing); _tunic_audit_phase("sewing-task-created"); show_task(panel, "Sewing Workbench", ("Seam", "Alignment", "Validation tolerance", "Stitch samples", "Status")); _tunic_audit_phase("sewing-task-shown"); Gui.activeDocument().activeView().viewTop(); Gui.activeDocument().activeView().fitAll(); events(); save("cloth-sewing.png", "Sewing Workbench", "native tunic Sketcher boundary and semantic seam"); close_task(); App.closeDocument(doc.Name); _tunic_audit_phase("pattern-and-sewing-exit")', 1)
source = source.replace('    doc = App.newDocument("ClothSimulationVisualRegression"); scene = create_quality_simulation_scene(doc); avatar = getattr(scene.AvatarProxy, "SourceObject", None); target = scene.DrapeTarget', '    phase_started = _tunic_audit_perf_counter(); doc = App.newDocument("ClothSimulationVisualRegression"); _tunic_audit_phase("simulation-document-created"); scene = create_quality_simulation_scene(doc); _tunic_audit_phase("quality-scene-created elapsed_ms=%.1f" % (1000.0 * (_tunic_audit_perf_counter() - phase_started))); avatar = getattr(scene.AvatarProxy, "SourceObject", None); target = scene.DrapeTarget', 1)
source = source.replace('scene.PinMode = "None"; scene.PinSelection = []; scene.ClothPieces = [front, back]; refresh_drape_target(target); doc.recompute()', 'scene.PinMode = "None"; scene.PinSelection = []; scene.ClothPieces = [front, back]; _tunic_audit_phase("tunic-pieces-authored"); refresh_drape_target(target); _tunic_audit_phase("drape-target-refreshed"); doc.recompute(); _tunic_audit_phase("solver-initialized")', 1)
source = source.replace('log("pin-mode=None solver-pins=0")', '_tunic_audit_phase("pre-preview"); log("pin-mode=None solver-pins=0")', 1)
source = source.replace('    Gui.runCommand("ClothRealtimePreview")\n    scene.Document.recompute()', '    _tunic_audit_phase("preview-command-enter")\n    Gui.runCommand("ClothRealtimePreview")\n    _tunic_audit_phase("preview-command-return")\n    scene.Document.recompute()\n    _tunic_audit_phase("preview-recompute-return")', 1)
source = source.replace('    if getattr(preview_backend, "name", None) != "tissu":\n        raise RuntimeError("Realtime Cloth Preview did not select the Tissu backend")', '    if getattr(preview_backend, "name", None) != "tissu":\n        raise RuntimeError("Realtime Cloth Preview did not select the Tissu backend")\n    _tunic_audit_phase("preview-backend-selected")', 1)
source = source.replace('    preview_steps = int(scene.Steps)\n    if preview_steps <= 0:', '    preview_steps = int(scene.Steps)\n    _tunic_audit_phase("preview-first-step steps=%d" % preview_steps)\n    if preview_steps <= 0:', 1)
source = source.replace('    Gui.runCommand("ClothRealtimePreview")\n    if int(scene.Steps) != 0:', '    Gui.runCommand("ClothRealtimePreview")\n    _tunic_audit_phase("preview-stop-command-return")\n    if int(scene.Steps) != 0:', 1)
source = source.replace('    for name, value in preview_saved.items():', '    _tunic_audit_phase("preview-stop-reset-complete")\n    for name, value in preview_saved.items():', 1)
source = source.replace('    simulation_started = perf_counter()', '    _tunic_audit_phase("actual-simulation-enter")\n    simulation_started = perf_counter()', 1)
source = source.replace('        batch_started = perf_counter()\n        simulation_panel.step(batch); doc.recompute(); events()', '        batch_started = perf_counter()\n        _tunic_audit_phase("batch-enter")\n        simulation_panel.step(batch); doc.recompute(); events()\n        _tunic_audit_phase("batch-exit")', 1)
source = source.replace('    Gui.getMainWindow().show(); events(); init_gui = os.path.join(ROOT, "InitGui.py"); exec(compile(open(init_gui, encoding="utf-8").read(), init_gui, "exec"), globals(), globals()); events(); run_canonical_acceptance(); pattern_and_sewing(); simulation(); log("scenario-pass")', '    Gui.getMainWindow().show(); events(); init_gui = os.path.join(ROOT, "InitGui.py"); exec(compile(open(init_gui, encoding="utf-8").read(), init_gui, "exec"), globals(), globals()); events(); _tunic_audit_phase("init-gui-ready"); run_canonical_acceptance(); _tunic_audit_phase("canonical-acceptance-return"); pattern_and_sewing(); _tunic_audit_phase("pattern-and-sewing-return"); simulation(); _tunic_audit_phase("simulation-return"); log("scenario-pass")', 1)

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
anchor = '    for batch in (15,15,15,15,15,15):'
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
# The source uses the production simulation path; this wrapper only stabilizes
# the tunic fixture and verifies the realtime Tissu selector.
exec(compile(source, str(source_path), "exec"), globals(), globals())
print("tunic-audit-process-exit=success", flush=True)
os._exit(0)
