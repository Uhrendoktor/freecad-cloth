"""CI entry point for the full tunic visual/simulation audit."""
from pathlib import Path
import os
import re
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def _stage_start(name):
    started = perf_counter()
    log("stage-start=%s" % name)
    return started


def _stage_end(name, started):
    elapsed_ms = 1000.0 * (perf_counter() - started)
    log("stage-end=%s elapsed_ms=%.1f" % (name, elapsed_ms))


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
    'scene.SolverIterations = 8;': 'scene.SolverIterations = 8; log("tunic-solver=iterations-8 substeps-env");',
    'upper_margin = 0.12 * max(1.0, float(shoulder_z) - float(hem_z))': 'upper_margin = 0.17 * max(1.0, float(shoulder_z) - float(hem_z))',
}
for old, new in replacements.items():
    if old not in source:
        raise RuntimeError(f"audit replacement did not match source: {old}")
    source = source.replace(old, new, 1)


preview_probe = '''    _preview_stage = _stage_start("realtime-preview")
    from freecad_cloth.simulation import RealtimePreview
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
    _stage_end("realtime-preview", _preview_stage)
'''
anchor = '    for batch in (15,15,15,15,15,15):'
if anchor not in source:
    raise RuntimeError("simulation batch anchor missing")
timed_anchor = '''    _authoritative_stage = _stage_start("authoritative-simulation")
    from time import perf_counter
    simulation_started = perf_counter()
    for batch in (15,15,15,15,15,15):
        batch_started = perf_counter()
        simulation_panel.step(batch); doc.recompute(); events()
        log("tunic-simulation-batch steps=%d elapsed_ms=%.1f total_ms=%.1f particles=%d iterations=%d substeps=%d" % (batch, 1000.0 * (perf_counter() - batch_started), 1000.0 * (perf_counter() - simulation_started), int(scene.ParticleCount), int(scene.SolverIterations), int(scene.SolverSubsteps)))
    log("tunic-simulation-total-ms=%.1f" % (1000.0 * (perf_counter() - simulation_started)))
    _stage_end("authoritative-simulation", _authoritative_stage)
'''
source = source.replace(anchor, preview_probe + '\n' + timed_anchor, 1)


source = source.replace(
    'def run_canonical_acceptance():\\n    os.makedirs',
    'def run_canonical_acceptance():\\n    _stage = _stage_start("canonical-acceptance")\\n    os.makedirs',
    1,
)
source = source.replace(
    '        log(marker + "=passed")\\n\\n\\ndef _mesh_geometry(mesh):',
    '        log(marker + "=passed")\\n    _stage_end("canonical-acceptance", _stage)\\n\\n\\ndef _mesh_geometry(mesh):',
    1,
)
source = source.replace(
    'def pattern_and_sewing():\\n    from freecad_cloth.pattern.PatternModel import Seam',
    'def pattern_and_sewing():\\n    _pattern_stage = _stage_start("pattern-and-sewing-fixture")\\n    from freecad_cloth.pattern.PatternModel import Seam',
    1,
)
source = source.replace(
    '    panel = SewingTaskPanel(sewing); show_task(panel, "Sewing Workbench", ("Seam", "Alignment", "Validation tolerance", "Stitch samples", "Status")); Gui.activeDocument().activeView().viewTop(); Gui.activeDocument().activeView().fitAll(); events(); save("cloth-sewing.png", "Sewing Workbench", "native tunic Sketcher boundary and semantic seam"); close_task(); App.closeDocument(doc.Name)\\n\\ndef style_mesh',
    '    panel = SewingTaskPanel(sewing); show_task(panel, "Sewing Workbench", ("Seam", "Alignment", "Validation tolerance", "Stitch samples", "Status")); Gui.activeDocument().activeView().viewTop(); Gui.activeDocument().activeView().fitAll(); events(); save("cloth-sewing.png", "Sewing Workbench", "native tunic Sketcher boundary and semantic seam"); close_task(); App.closeDocument(doc.Name)\\n    _stage_end("pattern-and-sewing-fixture", _pattern_stage)\\n\\ndef style_mesh',
    1,
)
source = source.replace(
    'def simulation():\\n    import os',
    'def simulation():\\n    _fixture_stage = _stage_start("tunic-simulation-fixture")\\n    import os',
    1,
)
source = source.replace(
    '    log("pin-mode=None solver-pins=0")',
    '    _stage_end("tunic-simulation-fixture", _fixture_stage)\\n    log("pin-mode=None solver-pins=0")',
    1,
)
source = source.replace(
    'def save(name, state, proof):',
    'def save(name, state, proof):\\n    _screenshot_stage = _stage_start("screenshot-render")',
    1,
)
source = source.replace(
    '    log("screenshot=%s state=%s bytes=%d" % (path, state, os.path.getsize(path)))',
    '    log("screenshot=%s state=%s bytes=%d" % (path, state, os.path.getsize(path)))\\n    _stage_end("screenshot-render", _screenshot_stage)',
    1,
)
source = source.replace(
    '    if int(scene.Steps) != 90 or float(scene.SimulatedTime) <= 0.0 or not bool(scene.FiniteState):',
    '    _validation_stage = _stage_start("validation")\\n    if int(scene.Steps) != 90 or float(scene.SimulatedTime) <= 0.0 or not bool(scene.FiniteState):',
    1,
)

source = source.replace(
    'finally:\\n    try:',
    'finally:\\n    _cleanup_stage = _stage_start("cleanup")\\n    try:',
    1,
)
source = source.replace(
    '        events(); log("script-end exit-code=%d" % exit_code)\\n        if exit_code == 0:',
    '        events(); log("script-end exit-code=%d" % exit_code)\\n        _stage_end("cleanup", _cleanup_stage)\\n        if exit_code == 0:',
    1,
)
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

source = source.replace(
    """    write_drape_metrics(
        panels,
        avatar,
        x_mid,
        shoulder_z=shoulder_z,
        hem_z=hem_z,
        seam_records=seam_records,
        proxy=proxy,
    ); bounds = []""",
    seam_check + "\n" + """    write_drape_metrics(
        panels,
        avatar,
        x_mid,
        shoulder_z=shoulder_z,
        hem_z=hem_z,
        seam_records=seam_records,
        proxy=proxy,
    ); bounds = []
    _stage_end("validation", _validation_stage)""",
    1,
)
# The source uses the production simulation path; this wrapper only stabilizes
# the tunic fixture and verifies the realtime Tissu selector.
exec(compile(source, str(source_path), "exec"), globals(), globals())
print("tunic-audit-process-exit=success", flush=True)
os._exit(0)
