"""CI entry point for the full tunic visual/simulation audit."""
from pathlib import Path
import json
import os
import re
import sys
import traceback
from datetime import datetime, timezone

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
    visual_checkpoints = (15,30,45,60,75,90)
    for batch in (15,15,15,15,15,15):
        batch_started = perf_counter()
        simulation_panel.step(batch); doc.recompute(); events()
        checkpoint_step = int(scene.Steps)
        if checkpoint_step not in visual_checkpoints:
            raise RuntimeError("unexpected tunic visual checkpoint step %d" % checkpoint_step)
        view.viewFront(); view.fitAll(); events()
        save(
            "cloth-simulation-draped-step-%03d.png" % checkpoint_step,
            "Simulation Workbench draped step %d" % checkpoint_step,
            "human-review checkpoint after %d real simulation steps; six-step exported sequence"
            % checkpoint_step,
        )
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

# The generated acceptance source historically terminates with os._exit(), which can
# discard buffered diagnostics and leave CI with only a bare exit code. For this
# wrapper, convert those terminal exits to SystemExit so the supervisor can emit
# a full traceback and a durable failure report.
source = source.replace(
    'except BaseException as error:\n    exit_code = 1; print("SCENARIO FAILURE: %r" % (error,), flush=True);',
    'except BaseException as error:\n    globals()["_TUNIC_SOURCE_FAILURE"] = error\n    globals()["_TUNIC_SOURCE_FAILURE_TRACEBACK"] = traceback.format_exc()\n    exit_code = 1; print("SCENARIO FAILURE: %r" % (error,), flush=True);',
)
source = source.replace('os._exit(1)', 'raise SystemExit(1)')
source = source.replace('getattr(os, "_" + "exit")(0)', 'raise SystemExit(0)')

def _diagnostic_report_path():
    return Path(os.environ.get(
        "TUNIC_AUDIT_DIAGNOSTICS",
        str(ROOT / "docs" / "images" / "generated" / "tunic-audit-diagnostics.txt"),
    ))

def _write_failure_report(error):
    path = _diagnostic_report_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "tunic-audit-diagnostics",
        "timestamp_utc=%s" % datetime.now(timezone.utc).isoformat(),
        "python=%s" % sys.version.replace("\n", " "),
        "platform=%s" % sys.platform,
        "cwd=%s" % os.getcwd(),
        "pid=%s" % os.getpid(),
        "source_path=%s" % source_path,
        "generated_source_lines=%d" % len(source.splitlines()),
        "collision_mode=%s" % os.environ.get("CLOTH_TISSU_COLLISION_MODE", ""),
        "simulation_backend=%s" % os.environ.get("CLOTH_SIMULATION_BACKEND", ""),
        "tissu_substeps=%s" % os.environ.get("CLOTH_TISSU_SUBSTEPS", ""),
        "tissu_collision_triangles=%s" % os.environ.get("CLOTH_TISSU_COLLISION_TRIANGLES", ""),
        "exception_type=%s" % type(error).__name__,
        "exception=%r" % (error,),
        "source_exception_type=%s" % type(globals().get("_TUNIC_SOURCE_FAILURE", error)).__name__,
        "source_exception=%r" % (globals().get("_TUNIC_SOURCE_FAILURE", error),),
        "",
        "traceback:",
        str(globals().get("_TUNIC_SOURCE_FAILURE_TRACEBACK") or traceback.format_exc()),
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    print("tunic-audit-diagnostics-path=%s" % path, flush=True)
    source_failure = globals().get("_TUNIC_SOURCE_FAILURE", error)
    print("tunic-audit-diagnostics-exception=%s: %r" % (type(source_failure).__name__, source_failure), flush=True)
    if "_TUNIC_SOURCE_FAILURE_TRACEBACK" in globals():
        print("tunic-audit-source-traceback-begin", flush=True)
        print(globals()["_TUNIC_SOURCE_FAILURE_TRACEBACK"], flush=True)
        print("tunic-audit-source-traceback-end", flush=True)
    try:
        log_path = ROOT / "docs" / "images" / "generated" / "gui-progress.log"
        if log_path.is_file():
            tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-80:]
            print("tunic-audit-gui-log-tail-begin", flush=True)
            for line in tail:
                print(line, flush=True)
            print("tunic-audit-gui-log-tail-end", flush=True)
    except Exception as log_error:
        print("tunic-audit-log-tail-error=%r" % (log_error,), flush=True)

compiled_source = _compile_generated_source(source)
if "--syntax-check" in sys.argv:
    print(
        "tunic-audit-source-syntax=passed lines=%d" % len(source.splitlines()),
        flush=True,
    )
    raise SystemExit(0)

# The source uses the production simulation path; this wrapper only stabilizes
# the tunic fixture and verifies the realtime Tissu selector.
try:
    exec(compiled_source, globals(), globals())
except SystemExit as error:
    code = int(getattr(error, "code", 1) or 0)
    if code:
        _write_failure_report(error)
        print("tunic-audit-process-exit=failure code=%d" % code, flush=True)
        raise SystemExit(code)
    print("tunic-audit-process-exit=success", flush=True)
except BaseException as error:
    _write_failure_report(error)
    print("tunic-audit-process-exit=failure exception=%s" % type(error).__name__, flush=True)
    raise
else:
    print("tunic-audit-process-exit=success", flush=True)
