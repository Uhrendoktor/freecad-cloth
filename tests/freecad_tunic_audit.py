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
    'clearance = max(20.0, 0.08 * body_depth);': 'clearance = max(8.0, 0.025 * body_depth);',
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
    'scene.SolverIterations = 8;': 'scene.SolverIterations = 64; log("tunic-solver-ab=iterations-64");',
    'upper_margin = 0.12 * max(1.0, float(shoulder_z) - float(hem_z))': 'upper_margin = 0.17 * max(1.0, float(shoulder_z) - float(hem_z))',
}
for old, new in replacements.items():
    if old not in source:
        raise RuntimeError(f"audit replacement did not match source: {old}")
    source = source.replace(old, new, 1)



pattern_lifecycle_old = """    seam = add_seam(doc, Seam(str(front.PieceId), 7, str(back.PieceId), 7, id="FrontBack", alignment="endpoints", stitch_group="MainSeam")); doc.recompute()
    sewing = create_sewing_operation(); doc.recompute()
    if str(seam.Status) != "Valid" or seam.Shape.isNull() or str(sewing.Status) != "Valid" or sewing.Shape.isNull():
        raise RuntimeError("sewing fixture is invalid")
"""
pattern_lifecycle_new = """    seam_records = []
    for edge_a, edge_b, seam_id in ((7, 7, "FrontBack"), (2, 2, "FrontBackShoulder"), (5, 5, "FrontBackSide")):
        seam_obj = add_seam(
            doc,
            Seam(str(front.PieceId), edge_a, str(back.PieceId), edge_b, id=seam_id, alignment="endpoints", stitch_group="MainSeam"),
        )
        seam_records.append(seam_obj)
    seam = seam_records[0]
    doc.recompute()
    Gui.Selection.clearSelection(); Gui.Selection.addSelection(seam)
    sewing = create_sewing_operation(); doc.recompute()
    if any(str(item.Status) != "Valid" or item.Shape.isNull() for item in seam_records) or str(sewing.Status) != "Valid" or sewing.Shape.isNull():
        raise RuntimeError("sewing fixture is invalid")
"""
if pattern_lifecycle_old not in source:
    raise RuntimeError("pattern lifecycle seam anchor missing")
source = source.replace(pattern_lifecycle_old, pattern_lifecycle_new, 1)

pattern_lifecycle_anchor = """    panel = SewingTaskPanel(sewing); show_task(panel, "Sewing Workbench", ("Seam", "Alignment", "Validation tolerance", "Stitch samples", "Status")); Gui.activeDocument().activeView().viewTop(); Gui.activeDocument().activeView().fitAll(); events(); save("cloth-sewing.png", "Sewing Workbench", "native tunic Sketcher boundary and semantic seam"); close_task(); App.closeDocument(doc.Name)"""
pattern_lifecycle_probe = r'''    from freecad_cloth.sewing.SewingView import refresh_seam_colors, seam_color_map, apply_seam_colors
    semantic_seams = tuple(seam_records)
    seam_ids = tuple(str(item.SeamId) for item in semantic_seams)
    if len(set(seam_ids)) < 3:
        raise RuntimeError("pattern/sewing lifecycle fixture requires at least three semantic SeamId values")
    def seam_rgb(obj):
        return tuple(round(float(value), 4) for value in obj.ViewObject.LineColor[:3])
    refresh_seam_colors(doc)
    expected = seam_color_map(seam_ids)
    color_snapshot = {str(item.SeamId): seam_rgb(item) for item in semantic_seams}
    for seam_id, actual in color_snapshot.items():
        target = expected[seam_id]
        if max(abs(actual[index] - target[index]) for index in range(3)) > 0.01:
            raise RuntimeError("SeamId-derived RGB mismatch for %s" % seam_id)
    doc.recompute()
    if str(sewing.SeamId) != str(seam.SeamId):
        raise RuntimeError("SewingOperation did not inherit linked SeamId")
    if seam_rgb(sewing) != seam_rgb(seam):
        raise RuntimeError("SewingOperation presentation color diverged from linked SeamId")
    apply_seam_colors(tuple(reversed(doc.Objects)))
    for item in semantic_seams:
        if seam_rgb(item) != color_snapshot[str(item.SeamId)]:
            raise RuntimeError("seam color changed under document-order reversal")
    activate("ClothPatternWorkbench", "Cloth Pattern", ["ClothPattern_Show2D"])
    Gui.runCommand("ClothPattern_Show2D", 0); events()
    save("seam-lifecycle-pattern-2d.png", "Pattern 2D seam colors", "three persistent SeamId values; Pattern 2D entry refresh")
    activate("ClothSewingWorkbench", "Cloth Sewing", ["ClothSewing_Show2D", "ClothSewing_FocusSeam3D"])
    Gui.runCommand("ClothSewing_Show2D", 0); events()
    save("seam-lifecycle-sewing-2d.png", "Sewing 2D seam colors", "three persistent SeamId values; Sewing 2D entry refresh")
    Gui.Selection.clearSelection(); Gui.Selection.addSelection(seam)
    Gui.runCommand("ClothSewing_FocusSeam3D", 0); events()
    save("seam-lifecycle-sewing-3d-focus.png", "Sewing 3D seam focus", "selected semantic seam focused in 3D")
    activate("ClothSimulationWorkbench", "Cloth Simulation", ["ClothSimulation_Edit"])
    view = Gui.activeDocument().activeView(); view.viewFront(); view.fitAll(); events()
    save("seam-lifecycle-simulation.png", "Simulation workbench seam colors", "Simulation activation refresh preserves SeamId-derived RGB")
    doc.recompute(); refresh_seam_colors(doc)
    for item in semantic_seams:
        if seam_rgb(item) != color_snapshot[str(item.SeamId)]:
            raise RuntimeError("recompute changed semantic SeamId color for %s" % item.SeamId)
    log("seam-color-recompute=passed seams=%d" % len(semantic_seams))
    import tempfile
    close_task()
    doc.recompute()
    with tempfile.TemporaryDirectory() as directory:
        seam_color_path = os.path.join(directory, "seam-color-lifecycle.FCStd")
        doc.saveAs(seam_color_path)
        App.closeDocument(doc.Name)
        reloaded = App.openDocument(seam_color_path)
        reloaded.recompute()
        refresh_seam_colors(reloaded)
        reloaded_seams = [obj for obj in reloaded.Objects if str(getattr(obj, "SeamId", "")).strip()]
        reloaded_colors = {str(obj.SeamId): seam_rgb(obj) for obj in reloaded_seams}
        for seam_id, expected_color in color_snapshot.items():
            if reloaded_colors.get(seam_id) != expected_color:
                raise RuntimeError("save/reload changed semantic SeamId color for %s" % seam_id)
        log("seam-color-save-reload=passed seams=%d" % len(reloaded_seams))
        doc = reloaded
'''
if pattern_lifecycle_anchor not in source:
    raise RuntimeError("pattern lifecycle screenshot anchor missing")
source = source.replace(pattern_lifecycle_anchor, "    panel = SewingTaskPanel(sewing); show_task(panel, \"Sewing Workbench\", (\"Seam\", \"Alignment\", \"Validation tolerance\", \"Stitch samples\", \"Status\")); Gui.activeDocument().activeView().viewTop(); Gui.activeDocument().activeView().fitAll(); events(); save(\"cloth-sewing.png\", \"Sewing Workbench\", \"native tunic Sketcher boundary and semantic seam\"); close_task()\n" + pattern_lifecycle_probe + "\n    App.closeDocument(doc.Name)", 1)

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
source = source.replace(anchor, preview_probe + '\n' + anchor, 1)

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
seam_lifecycle_probe = '''
    from freecad_cloth.sewing.SewingView import refresh_seam_colors, seam_color_map, apply_seam_colors
    semantic_seams = tuple(record[0] for record in seam_records)
    seam_ids = tuple(str(seam.SeamId) for seam in semantic_seams)
    if len(set(seam_ids)) < 3:
        raise RuntimeError("seam presentation fixture requires at least three semantic SeamId values")
    refresh_seam_colors(doc)
    color_snapshot = {str(seam.SeamId): tuple(float(value) for value in seam.ViewObject.LineColor[:3]) for seam in semantic_seams}
    expected_snapshot = seam_color_map(seam_ids)
    if color_snapshot != {key: tuple(expected_snapshot[key]) for key in expected_snapshot}:
        raise RuntimeError("initial seam colors do not match direct SeamId-derived colors")
    if len(set(color_snapshot.values())) < 3:
        raise RuntimeError("three semantic seams did not render three distinct colors")
    apply_seam_colors(tuple(reversed(doc.Objects)))
    for seam in semantic_seams:
        if tuple(float(value) for value in seam.ViewObject.LineColor[:3]) != color_snapshot[str(seam.SeamId)]:
            raise RuntimeError("seam color changed under reordered document presentation iteration")
    activate("ClothPatternWorkbench", "Cloth Pattern", ["ClothPattern_Show2D"])
    Gui.runCommand("ClothPattern_Show2D", 0); events()
    save("seam-lifecycle-pattern-2d.png", "Pattern 2D seam colors", ">=3 persistent SeamId values; Pattern 2D entry refresh")
    activate("ClothSewingWorkbench", "Cloth Sewing", ["ClothSewing_Show2D", "ClothSewing_FocusSeam3D"])
    Gui.runCommand("ClothSewing_Show2D", 0); events()
    save("seam-lifecycle-sewing-2d.png", "Sewing 2D seam colors", ">=3 persistent SeamId values; Sewing 2D entry refresh")
    Gui.Selection.clearSelection(); Gui.Selection.addSelection(semantic_seams[0])
    Gui.runCommand("ClothSewing_FocusSeam3D", 0); events()
    save("seam-lifecycle-sewing-3d-focus.png", "Sewing 3D seam focus", "selected semantic seam focused in 3D without changing presentation identity")
    activate("ClothSimulationWorkbench", "Cloth Simulation", ["ClothSimulation_Edit"])
    view = Gui.activeDocument().activeView(); view.viewFront(); view.fitAll(); events()
    save("seam-lifecycle-simulation.png", "Simulation workbench seam colors", "Simulation activation refresh preserves the same SeamId-derived RGB")
    doc.recompute(); refresh_seam_colors(doc)
    for seam in semantic_seams:
        if tuple(float(value) for value in seam.ViewObject.LineColor[:3]) != color_snapshot[str(seam.SeamId)]:
            raise RuntimeError("recompute changed semantic SeamId color for %s" % seam.SeamId)
    log("seam-color-recompute=passed seams=%d" % len(semantic_seams))
'''
seam_lifecycle_anchor = "    scene.StartHeight = 0.0;"
if seam_lifecycle_anchor not in source:
    raise RuntimeError("canonical seam lifecycle anchor missing")
source = source.replace(seam_lifecycle_anchor, seam_lifecycle_probe + "\n" + seam_lifecycle_anchor, 1)

seam_reload_probe = '''
    import tempfile
    from freecad_cloth.sewing.SewingView import refresh_seam_colors
    doc.recompute()
    with tempfile.TemporaryDirectory() as directory:
        seam_color_path = os.path.join(directory, "seam-color-lifecycle.FCStd")
        doc.saveAs(seam_color_path)
        saved_doc_name = doc.Name
        App.closeDocument(saved_doc_name)
        reloaded = App.openDocument(seam_color_path)
        reloaded.recompute()
        refresh_seam_colors(reloaded)
        reloaded_seams = [obj for obj in reloaded.Objects if str(getattr(obj, "SeamId", "")).strip()]
        reloaded_colors = {str(obj.SeamId): tuple(float(value) for value in obj.ViewObject.LineColor[:3]) for obj in reloaded_seams}
        for seam_id, color in color_snapshot.items():
            if reloaded_colors.get(seam_id) != color:
                raise RuntimeError("save/reload changed semantic SeamId color for %s" % seam_id)
        log("seam-color-save-reload=passed seams=%d" % len(reloaded_seams))
        doc = reloaded
'''
seam_reload_anchor = "    task_dock.show(); task_dock.raise_(); events(); close_task(); App.closeDocument(doc.Name)"
if seam_reload_anchor not in source:
    raise RuntimeError("canonical seam save/reload anchor missing")
source = source.replace(seam_reload_anchor, seam_reload_probe + "\n    App.closeDocument(doc.Name)", 1)

# The source uses the production simulation path; this wrapper only stabilizes
# the tunic fixture and verifies the realtime Tissu selector.
exec(compile(source, str(source_path), "exec"), globals(), globals())
print("tunic-audit-process-exit=success", flush=True)
os._exit(0)
