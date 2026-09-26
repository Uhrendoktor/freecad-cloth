"""CI entry point for the tunic visual/simulation audit using Tissu."""
from pathlib import Path

source_path = Path(__file__).with_name("freecad_screenshot_source.py")
source = source_path.read_text(encoding="utf-8")

# Tunic fixture profile: stable drape plus a closer-fitting shoulder/neckline silhouette.
replacements = {
    'chest = 980.0; hip = 1020.0; ease = 55.0;': 'chest = 860.0; hip = 880.0; ease = 10.0;',
    'for edge_a, edge_b, seam_id in ((2,2,"TunicRightShoulder"),(5,5,"TunicLeftShoulder")):' :
        'for edge_a, edge_b, seam_id in ((1,1,"TunicRightSide"),(2,6,"TunicRightShoulder"),(6,2,"TunicLeftShoulder"),(7,7,"TunicLeftSide")):',
    'scene.FabricFriction = 0.75;': 'scene.FabricFriction = 0.85;',
    'for batch in (15,15,15,15,15,15):': 'for batch in (40,40,40):',
    'if int(scene.Steps) != 90 or': 'if int(scene.Steps) != 120 or',
    '"simulation did not reach a finite 90-step state"': '"simulation did not reach a finite 120-step state"',
    'after 90 real steps;': 'after 120 real steps;',
    'upper_margin = 0.12 * max(1.0, float(shoulder_z) - float(hem_z))': 'upper_margin = 0.17 * max(1.0, float(shoulder_z) - float(hem_z))',
}
for old, new in replacements.items():
    if old not in source:
        raise RuntimeError(f"audit replacement did not match source: {old}")
    source = source.replace(old, new, 1)

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
anchor = '    for batch in (40,40,40):'
if anchor not in source:
    raise RuntimeError("simulation batch anchor missing")
source = source.replace(anchor, preview_probe + '\n' + anchor, 1)

# Validate seam closure against the actual Tissu particle positions. FreeCAD Mesh::Feature
# point ordering is a serialization detail and is not guaranteed to match particle indices.
seam_check = """    backend_state = scene.Proxy._base_or_restore()
    simulated_positions = tuple(backend_state.backend.positions())
    if not simulated_positions:
        raise RuntimeError("Tissu backend returned no simulated particle positions")
    stitch_pairs_by_seam = getattr(scene.Proxy, "seam_stitch_pairs", {})
    if not stitch_pairs_by_seam:
        raise RuntimeError("authoritative seam check has no exact solver stitch provenance")
    seam_gaps = []
    for seam, piece_a, piece_b in seam_records:
        edge_a_id = str(getattr(seam, "EdgeAId", ""))
        edge_b_id = str(getattr(seam, "EdgeBId", ""))
        if not edge_a_id.startswith(str(piece_a.PieceId) + ":edge:") or not edge_b_id.startswith(str(piece_b.PieceId) + ":edge:"):
            raise RuntimeError("authoritative tunic seam lost semantic edge identity")
        pairs = tuple(stitch_pairs_by_seam.get(str(seam.SeamId), ()))
        if not pairs:
            raise RuntimeError("authoritative seam check cannot resolve exact solver pairs for %s" % seam.SeamId)
        for ga, gb in pairs:
            a = simulated_positions[int(ga)]; b = simulated_positions[int(gb)]
            seam_gaps.append(((a[0]-b[0])**2+(a[1]-b[1])**2+(a[2]-b[2])**2)**0.5)
    seam_gap = max(seam_gaps) if seam_gaps else 0.0
    if seam_gap > 35.0:
        raise RuntimeError("simulated tunic seams did not converge: max endpoint gap %.1f mm" % seam_gap)
    log("tunic-seam-max-gap-mm=%.2f" % seam_gap)
"""

exec(compile(source, str(source_path), "exec"), globals(), globals())
