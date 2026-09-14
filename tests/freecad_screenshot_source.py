"""Deterministic FreeCAD GUI acceptance and six-side cloth visual audit."""
import importlib.util
import json
import os
import sys
import traceback

import FreeCAD as App
import FreeCADGui as Gui
try:
    from PySide import QtWidgets
except ImportError:
    from PySide2 import QtWidgets

ROOT = "/workspace"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
OUT = os.environ.get("CLOTH_SCREENSHOT_DIR", "docs/images/generated")
os.makedirs(OUT, exist_ok=True)
LOG = os.path.join(OUT, "gui-progress.log")
MANIFEST = os.path.join(OUT, "gui-screenshot-manifest.txt")
METRICS = os.path.join(OUT, "drape-visual-metrics.json")


def log(message):
    with open(LOG, "a", encoding="utf-8") as handle:
        handle.write(message + "\n")


def events():
    Gui.updateGui()
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.processEvents()


def ensure_task_view_visible():
    window = Gui.getMainWindow()
    if window is None:
        raise RuntimeError("FreeCAD main window is unavailable")
    dock = window.findChild(QtWidgets.QDockWidget, "Tasks")
    if dock is not None:
        dock.show(); dock.raise_(); events()
        if dock.isVisible():
            return dock
    raise RuntimeError("FreeCAD Tasks dock is unavailable")


def validate_task(panel, name, required):
    events(); dock = ensure_task_view_visible(); events()
    if not panel.form.isVisible():
        panel.form.show(); panel.form.raise_(); events()
    texts = []
    for widget in [panel.form] + panel.form.findChildren(QtWidgets.QWidget):
        value = getattr(widget, "text", "")
        try:
            value = value() if callable(value) else value
        except TypeError:
            value = ""
        if value:
            texts.append(str(value))
    combined = " | ".join(texts)
    missing = [item for item in required if item not in combined]
    log("task-panel=%s visible=true missing=%s" % (name, ",".join(missing)))
    if missing:
        raise RuntimeError("task panel %s is missing visible text: %s" % (name, ",".join(missing)))
    return dock


def show_task(panel, name, required=()):
    if Gui.Control.activeDialog():
        Gui.Control.closeDialog(); events()
    Gui.Control.showDialog(panel)
    return validate_task(panel, name, required)


def close_task():
    if Gui.Control.activeDialog():
        Gui.Control.closeDialog(); events()


def activate(name, toolbar, commands):
    if name not in Gui.listWorkbenches():
        raise RuntimeError("workbench is not registered: %s" % name)
    Gui.activateWorkbench(name); events()
    window = Gui.getMainWindow()
    if window is None or not window.isVisible():
        raise RuntimeError("FreeCAD main window is not visible")
    for bar in window.findChildren(QtWidgets.QToolBar):
        if bar.windowTitle() == toolbar:
            bar.show()
    missing = [command for command in commands if command not in Gui.listCommands()]
    if missing:
        raise RuntimeError("commands are not registered: " + ",".join(missing))
    log("workbench=%s toolbar=%s" % (name, toolbar))


def save(name, state, proof):
    window = Gui.getMainWindow()
    if window is None or not window.isVisible():
        raise RuntimeError("FreeCAD main window unavailable for screenshot")
    window.show(); window.raise_(); window.activateWindow(); window.resize(1280, 720); events()
    image = window.grab(); path = os.path.join(OUT, name)
    if image.isNull() or (image.width(), image.height()) != (1280, 720):
        raise RuntimeError("invalid GUI capture for %s" % state)
    if not image.save(path) or os.path.getsize(path) < 20000:
        raise RuntimeError("failed or suspiciously small screenshot: %s" % path)
    log("screenshot=%s state=%s bytes=%d" % (path, state, os.path.getsize(path)))
    with open(MANIFEST, "a", encoding="utf-8") as handle:
        handle.write("%s\t%s\t%s\n" % (name, state, proof))


def load_and_run(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load acceptance module: %s" % path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); module.run_acceptance()


def run_canonical_acceptance():
    for path, name, marker in ((
        "tests/freecad_avatar_acceptance.py", "freecad_avatar_acceptance", "avatar-provider-acceptance"),
        ("tests/freecad_garment_e2e_smoke.py", "freecad_garment_e2e_smoke", "canonical-garment-e2e"),
        ("tests/freecad_simulation_quality_acceptance.py", "freecad_simulation_quality_acceptance", "simulation-quality-acceptance")):
        load_and_run(os.path.join(ROOT, path), name); log(marker + "=passed")


def _mesh_points(mesh):
    topology = getattr(mesh, "Topology", None)
    if topology is None:
        return ()
    vertices, _triangles = topology
    return tuple((float(p.x), float(p.y), float(p.z)) for p in vertices)


def write_drape_metrics(panels, avatar, center_x=None, shoulder_z=None, hem_z=None):
    from freecad_cloth.common.DrapeVisualSanity import inspect_drape, summarize
    avatar_vertices = _mesh_points(getattr(avatar, "Mesh", None)); box = avatar.Mesh.BoundBox
    target_height = float(box.ZMax - box.ZMin)
    target_width = float(max(box.XMax - box.XMin, box.YMax - box.YMin))
    if shoulder_z is None:
        shoulder_z = float(box.ZMin) + 0.76 * target_height
    if hem_z is None:
        hem_z = float(box.ZMin) + 0.40 * target_height
    upper_margin = 0.12 * max(1.0, float(shoulder_z) - float(hem_z))
    lower_margin = 0.20 * max(1.0, float(shoulder_z) - float(hem_z))
    records = []
    for panel in panels:
        vertices = _mesh_points(getattr(panel, "Mesh", None))
        metrics = inspect_drape(vertices, avatar_vertices, target_height=target_height, target_width=target_width)
        record = {"panel": str(getattr(panel, "Label", getattr(panel, "Name", ""))), **summarize(metrics)}
        diagnostics = []
        if not metrics.finite:
            raise RuntimeError("draped panel %s contains non-finite geometry" % record["panel"])
        if not vertices:
            raise RuntimeError("draped panel %s has no mesh vertices" % record["panel"])
        if center_x is not None:
            record["centroid_lateral_offset"] = abs(float(metrics.centroid[0]) - float(center_x))
            if record["centroid_lateral_offset"] > target_width * 0.18:
                diagnostics.append("lateral-detached-candidate")
        if metrics.target_vertex_clearance is None or metrics.target_vertex_clearance > target_width * 0.15:
            diagnostics.append("target-clearance-candidate")
        if metrics.vertical_span_ratio < 0.25 or metrics.lateral_span_ratio < 0.25:
            diagnostics.append("collapsed-candidate")
        if float(metrics.bounds[5]) > float(shoulder_z) + upper_margin:
            diagnostics.append("above-shoulder-candidate")
        if float(metrics.bounds[4]) < float(hem_z) - lower_margin:
            diagnostics.append("below-hem-candidate")
        if float(metrics.centroid[2]) > float(shoulder_z) + upper_margin:
            diagnostics.append("centroid-above-shoulder-candidate")
        record["diagnostics"] = diagnostics
        records.append(record)
        log("drape-metrics=%s" % json.dumps(record, sort_keys=True))
    with open(METRICS, "w", encoding="utf-8") as handle:
        json.dump({"target_height": target_height, "target_width": target_width, "shoulder_z": shoulder_z, "hem_z": hem_z, "panels": records}, handle, indent=2, sort_keys=True)


def _make_tunic_sketch(doc, name, panel_width, garment_height, hem_width, neckline_ratio, neckline_drop=0.08):
    import Part, Sketcher
    sketch = doc.addObject("Sketcher::SketchObject", name + "Sketch")
    neck_z = (1.0 - float(neckline_drop)) * garment_height
    points = [
        (0.00, 0.00), (hem_width, 0.00),
        (panel_width, 0.82 * garment_height), (0.86 * panel_width, 0.97 * garment_height),
        (neckline_ratio * panel_width, neck_z), ((1.0 - neckline_ratio) * panel_width, neck_z),
        (0.14 * panel_width, 0.97 * garment_height), (0.00, 0.82 * garment_height),
    ]
    geometry = [Part.LineSegment(App.Vector(points[i][0], points[i][1], 0), Part.Vector(points[(i + 1) % len(points)][0], points[(i + 1) % len(points)][1], 0)) for i in range(len(points))]
    sketch.addGeometry(geometry, False)
    sketch.addConstraint([
        Sketcher.Constraint("Coincident",0,2,1,1), Sketcher.Constraint("Coincident",1,2,2,1),
        Sketcher.Constraint("Coincident",2,2,3,1), Sketcher.Constraint("Coincident",3,2,4,1),
        Sketcher.Constraint("Coincident",4,2,5,1), Sketcher.Constraint("Coincident",5,2,6,1),
        Sketcher.Constraint("Coincident",6,2,7,1), Sketcher.Constraint("Coincident",7,2,0,1)])
    doc.recompute(); return sketch, points
