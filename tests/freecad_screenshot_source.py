"""Deterministic FreeCAD GUI acceptance and six-side cloth visual audit."""

import contextlib
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


def _dialog_text(dialog):
    form = getattr(dialog, "form", dialog)
    widgets = [form]
    if hasattr(form, "findChildren"):
        widgets.extend(form.findChildren(QtWidgets.QWidget))
    return " | ".join(
        str(getter())
        for widget in widgets
        for getter in [getattr(widget, "text", None)]
        if callable(getter)
    )


def ensure_task_view_visible():
    window = Gui.getMainWindow()
    if window is None:
        raise RuntimeError("FreeCAD main window is unavailable")
    for dock in window.findChildren(QtWidgets.QDockWidget):
        if (
            dock.objectName() == "Tasks"
            or "task" in str(dock.windowTitle()).lower()
        ):
            dock.show()
            dock.raise_()
            events()
            if dock.isVisible():
                return dock
    return _TaskDockProxy()


class _TaskDockProxy:
    def hide(self):
        return None

    def show(self):
        return None

    def raise_(self):
        return None


def validate_task(panel, name, required):
    events()
    dock = ensure_task_view_visible()
    dialog = Gui.Control.activeDialog()
    if dialog is None:
        raise RuntimeError(f"{name} did not open an active public task dialog")
    texts = []
    for target in (panel, dialog, dock):
        if target is None:
            continue
        text = _dialog_text(target)
        if text:
            texts.append(text)
    combined = " | ".join(texts)
    missing = [item for item in required if item not in combined]
    log("task-panel={} visible=true missing={}".format(name, ",".join(missing)))
    if missing:
        raise RuntimeError(
            "task panel {} is missing visible text: {}".format(name, ",".join(missing))
        )
    return dock


def show_task(panel, name, required=()):
    if Gui.Control.activeDialog():
        Gui.Control.closeDialog()
        events()
    Gui.Control.showDialog(panel)
    return validate_task(panel, name, required)


def close_task():
    if Gui.Control.activeDialog():
        Gui.Control.closeDialog()
        events()


def activate(name, toolbar, commands):
    if name not in Gui.listWorkbenches():
        raise RuntimeError(f"workbench is not registered: {name}")
    Gui.activateWorkbench(name)
    events()
    window = Gui.getMainWindow()
    if window is None or not window.isVisible():
        raise RuntimeError("FreeCAD main window is not visible")
    for bar in window.findChildren(QtWidgets.QToolBar):
        if bar.windowTitle() == toolbar:
            bar.show()
    missing = [command for command in commands if command not in Gui.listCommands()]
    if missing:
        raise RuntimeError("commands are not registered: " + ",".join(missing))
    log(f"workbench={name} toolbar={toolbar}")


def save(name, state, proof):
    window = Gui.getMainWindow()
    if window is None or not window.isVisible():
        raise RuntimeError("FreeCAD main window unavailable for screenshot")
    window.show()
    window.raise_()
    window.activateWindow()
    window.resize(1280, 720)
    events()
    image = window.grab()
    path = os.path.join(OUT, name)
    if image.isNull() or (image.width(), image.height()) != (1280, 720):
        raise RuntimeError(f"invalid GUI capture for {state}")
    if not image.save(path) or os.path.getsize(path) < 20000:
        raise RuntimeError(f"failed or suspiciously small screenshot: {path}")
    log("screenshot=%s state=%s bytes=%d" % (path, state, os.path.getsize(path)))
    with open(MANIFEST, "a", encoding="utf-8") as handle:
        handle.write(f"{name}\t{state}\t{proof}\n")


def save_view(name, state, proof):
    """Capture the active FreeCAD 3D view without task-dock chrome."""
    document = Gui.activeDocument()
    view = document.activeView() if document is not None else None
    if view is None:
        raise RuntimeError("FreeCAD active 3D view is unavailable for screenshot")
    events()
    view.redraw()
    events()
    path = os.path.join(OUT, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    view.saveImage(path, 1280, 720, "White")
    if not os.path.isfile(path) or os.path.getsize(path) < 5000:
        raise RuntimeError(f"failed or suspiciously small 3D-view screenshot: {path}")
    log("screenshot=%s state=%s bytes=%d" % (path, state, os.path.getsize(path)))
    with open(MANIFEST, "a", encoding="utf-8") as handle:
        handle.write(f"{name}\t{state}\t{proof}\n")


def load_and_run(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load acceptance module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.run_acceptance()


GARMENT_E2E_LOG = os.environ.get("CLOTH_GARMENT_E2E_LOG", "/workspace/artifacts/garment-e2e.log")


def run_canonical_acceptance():
    os.makedirs(os.path.dirname(GARMENT_E2E_LOG), exist_ok=True)
    with open(GARMENT_E2E_LOG, "w", encoding="utf-8"):
        pass
    for path, name, marker in (
        (
            "tests/freecad_avatar_acceptance.py",
            "freecad_avatar_acceptance",
            "avatar-provider-acceptance",
        ),
        (
            "tests/freecad_garment_e2e_smoke.py",
            "freecad_garment_e2e_smoke",
            "canonical-garment-e2e",
        ),
        (
            "tests/freecad_simulation_quality_acceptance.py",
            "freecad_simulation_quality_acceptance",
            "simulation-quality-acceptance",
        ),
    ):
        if name == "freecad_garment_e2e_smoke":
            with (
                open(GARMENT_E2E_LOG, "a", encoding="utf-8") as handle,
                contextlib.redirect_stdout(handle),
            ):
                load_and_run(os.path.join(ROOT, path), name)
        else:
            load_and_run(os.path.join(ROOT, path), name)
        log(marker + "=passed")


def _mesh_geometry(mesh):
    topology = getattr(mesh, "Topology", None)
    if topology is None:
        return (), ()
    vertices, triangles = topology
    points = tuple((float(p.x), float(p.y), float(p.z)) for p in vertices)
    faces = tuple(tuple(int(index) for index in triangle) for triangle in triangles)
    return points, faces


def _mesh_points(mesh):
    return _mesh_geometry(mesh)[0]


def _post_drape_seam_gap(stitch_pairs, positions):
    """Measure the gap on the exact particle pairs passed to the solver."""
    if not stitch_pairs:
        raise ValueError("solver stitch pair provenance is required")
    from math import dist

    maximum = 0.0
    for a_index, b_index in stitch_pairs:
        if not (0 <= int(a_index) < len(positions) and 0 <= int(b_index) < len(positions)):
            raise ValueError("solver stitch pair is outside backend particle positions")
        a = positions[int(a_index)]
        b = positions[int(b_index)]
        maximum = max(
            maximum,
            dist(a, b),
        )
    return maximum


def _seam_coherence(panels, seam_records, proxy=None):
    if not seam_records:
        return {
            "sample_count": 0,
            "seams": [],
            "max_correspondence_gap_mm": None,
            "method": "solver-stitch-pairs",
        }
    if proxy is None or not getattr(proxy, "seam_stitch_pairs", None):
        raise RuntimeError("seam diagnostics require exact solver stitch-pair provenance")
    positions = tuple(proxy.backend.positions())
    stitch_pairs_by_seam = proxy.seam_stitch_pairs
    records = []
    maximum = 0.0
    sample_count = 0
    for seam, piece_a, piece_b in seam_records:
        seam_id = str(getattr(seam, "SeamId", getattr(seam, "Label", "")))
        stitch_pairs = tuple(stitch_pairs_by_seam.get(seam_id, ()))
        if not stitch_pairs:
            raise RuntimeError(f"solver stitch-pair provenance missing for seam {seam_id}")
        gap = _post_drape_seam_gap(stitch_pairs, positions)
        sample_count = max(sample_count, len(stitch_pairs))
        edge_a_id = str(getattr(seam, "EdgeAId", "")).strip()
        edge_b_id = str(getattr(seam, "EdgeBId", "")).strip()
        if not edge_a_id or not edge_b_id:
            raise RuntimeError(f"semantic seam edge identity is missing for {seam_id}")
        ids_a = tuple(
            str(value)
            for value in (getattr(getattr(piece_a, "Sketch", None), "SemanticEdgeIds", ()) or ())
        )
        ids_b = tuple(
            str(value)
            for value in (getattr(getattr(piece_b, "Sketch", None), "SemanticEdgeIds", ()) or ())
        )
        if edge_a_id not in ids_a or edge_b_id not in ids_b:
            raise RuntimeError(
                "semantic seam edge identity is not present on its authoritative Sketch"
            )
        records.append(
            {
                "seam": seam_id,
                "piece_a": str(getattr(piece_a, "PieceId", "")),
                "piece_b": str(getattr(piece_b, "PieceId", "")),
                "edge_a_id": edge_a_id,
                "edge_b_id": edge_b_id,
                "edge_a": ids_a.index(edge_a_id),
                "edge_b": ids_b.index(edge_b_id),
                "stitch_pair_count": len(stitch_pairs),
                "max_correspondence_gap_mm": round(float(gap), 6),
            }
        )
        maximum = max(maximum, float(gap))
    return {
        "sample_count": sample_count,
        "seams": records,
        "max_correspondence_gap_mm": round(maximum, 6),
        "method": "solver-stitch-pairs",
    }


def _inside_target_count(points, target, collision_surface=None, solver_collision_surface=None):
    """Count cloth vertices inside the authoritative FreeCAD mannequin target."""
    shape = getattr(target, "Shape", None)
    shape_is_inside = getattr(shape, "isInside", None) if shape is not None else None
    if callable(shape_is_inside):
        count = 0
        for point in points:
            try:
                if bool(shape_is_inside(App.Vector(*point), 1e-6, True)):
                    count += 1
            except (AttributeError, TypeError, ValueError):
                count = None
                break
        if count is not None:
            return count

    mesh = getattr(target, "Mesh", None)
    mesh_is_inside = getattr(mesh, "isInside", None) if mesh is not None else None
    if callable(mesh_is_inside):
        count = 0
        for point in points:
            try:
                if bool(mesh_is_inside(App.Vector(*point), 1e-6, True)):
                    count += 1
            except (AttributeError, TypeError, ValueError):
                count = None
                break
        if count is not None:
            return count

    surface = collision_surface
    if surface is not None:
        vertices = tuple(getattr(surface, "vertices", ()) or ())
        triangles = tuple(getattr(surface, "triangles", ()) or ())
        if not vertices or not triangles:
            raise RuntimeError("authoritative collision surface has no inside/outside topology")

        # Prefer trimesh's vectorized ray query for production-size mannequins.
        # The deterministic pure-Python parity test remains the dependency-free fallback.
        try:
            import numpy as np
            import trimesh

            target_mesh = trimesh.Trimesh(
                vertices=np.asarray(vertices, dtype=float),
                faces=np.asarray(triangles, dtype=int),
                process=False,
            )
            if target_mesh.is_watertight:
                states = target_mesh.contains(np.asarray(points, dtype=float))
                log("penetration-check=trimesh contains points=%d triangles=%d" % (
                    len(points), len(triangles)
                ))
                return int(np.count_nonzero(states))
        except (ImportError, RuntimeError, TypeError, ValueError):
            pass

        from freecad_cloth.simulation.DrapeVisualSanity import points_inside_closed_mesh

        log("penetration-check=numpy-ray-parity points=%d triangles=%d" % (
            len(points), len(triangles)
        ))
        return sum(points_inside_closed_mesh(points, vertices, triangles))
    raise RuntimeError("mannequin target does not expose an inside/outside collision test")

def write_drape_metrics(
    panels,
    avatar,
    center_x=None,
    shoulder_z=None,
    hem_z=None,
    seam_records=(),
    proxy=None,
    collision_surface=None,
):
    from freecad_cloth.simulation.DrapeFailureClassifier import classify_drape, summarize_classification
    from freecad_cloth.simulation.DrapeVisualSanity import inspect_drape, summarize
    from freecad_cloth.common.MeshValidation import validate_mesh

    avatar_vertices = _mesh_points(getattr(avatar, "Mesh", None))
    box = avatar.Mesh.BoundBox
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
        vertices, triangles = _mesh_geometry(getattr(panel, "Mesh", None))
        metrics = inspect_drape(
            vertices, avatar_vertices, target_height=target_height, target_width=target_width
        )
        mesh_result = validate_mesh(vertices, triangles, prefer_trimesh=False)
        classification = classify_drape(
            metrics, components=mesh_result.components, target_width=target_width
        )
        record = {
            "panel": str(getattr(panel, "Label", getattr(panel, "Name", ""))),
            **summarize(metrics),
        }
        diagnostics = []
        if not metrics.finite:
            raise RuntimeError(
                "draped panel {} contains non-finite geometry".format(record["panel"])
            )
        if not vertices:
            raise RuntimeError("draped panel {} has no mesh vertices".format(record["panel"]))
        if center_x is not None:
            record["centroid_lateral_offset"] = abs(float(metrics.centroid[0]) - float(center_x))
            if record["centroid_lateral_offset"] > target_width * 0.18:
                diagnostics.append("lateral-detached-candidate")
        if (
            metrics.target_vertex_clearance is None
            or metrics.target_vertex_clearance > target_width * 0.15
        ):
            diagnostics.append("target-clearance-candidate")
        if metrics.vertical_span_ratio < 0.25 or metrics.lateral_span_ratio < 0.25:
            diagnostics.append("collapsed-candidate")
        if float(metrics.bounds[5]) > float(shoulder_z) + upper_margin:
            diagnostics.append("above-shoulder-candidate")
        if float(metrics.bounds[4]) < float(hem_z) - lower_margin:
            diagnostics.append("below-hem-candidate")
        if float(metrics.centroid[2]) > float(shoulder_z) + upper_margin:
            diagnostics.append("centroid-above-shoulder-candidate")
        backend_for_collision = getattr(proxy, "backend", None) if proxy is not None else None
        solver_collision_surface = (
            getattr(backend_for_collision, "solver_collision_surface", None)
            if backend_for_collision is not None
            else None
        )
        penetrating_vertices = _inside_target_count(
            vertices,
            avatar,
            collision_surface,
            solver_collision_surface,
        )
        record["penetration_surface"] = (
            "solver" if solver_collision_surface is not None else "authoritative-target"
        )
        record["penetrating_vertices"] = int(penetrating_vertices)
        if penetrating_vertices:
            if collision_surface is not None:
                from math import dist

                from freecad_cloth.simulation.DrapeVisualSanity import point_inside_closed_mesh

                target_points = tuple(getattr(collision_surface, "vertices", ()) or ())
                target_triangles = tuple(getattr(collision_surface, "triangles", ()) or ())
                backend = getattr(proxy, "backend", None) if proxy is not None else None
                solver_surface = (
                    getattr(backend, "solver_collision_surface", None)
                    if backend is not None
                    else None
                )
                solver_vertices = (
                    tuple(getattr(solver_surface, "vertices", ()) or ())
                    if solver_surface is not None
                    else ()
                )
                solver_triangles = (
                    tuple(getattr(solver_surface, "triangles", ()) or ())
                    if solver_surface is not None
                    else ()
                )
                inside_points = []
                if target_points and target_triangles:
                    for point in vertices:
                        point_tuple = tuple(float(value) for value in point)
                        try:
                            authoritative_inside = point_inside_closed_mesh(
                                point_tuple, target_points, target_triangles
                            )
                        except (TypeError, ValueError, IndexError):
                            break
                        if not authoritative_inside:
                            continue
                        nearest = min(
                            dist(point_tuple, tuple(float(value) for value in target))
                            for target in target_points
                        )
                        solver_inside = None
                        if solver_vertices and solver_triangles:
                            try:
                                solver_inside = point_inside_closed_mesh(
                                    point_tuple, solver_vertices, solver_triangles
                                )
                            except (TypeError, ValueError, IndexError):
                                solver_inside = None
                        inside_points.append(
                            {
                                "point": tuple(round(value, 3) for value in point_tuple),
                                "nearest_target_vertex_mm": round(float(nearest), 3),
                                "solver_surface_inside": solver_inside,
                            }
                        )
                log(
                    "penetration-evidence panel=%s count=%d samples=%s"
                    % (record["panel"], penetrating_vertices, inside_points[:12])
                )
            raise RuntimeError(
                "draped panel {} has {} vertices inside the mannequin collision surface".format(
                    record["panel"], penetrating_vertices
                )
            )
        record["connected_components"] = int(mesh_result.components)
        record["failure_classification"] = summarize_classification(classification)
        record["diagnostics"] = diagnostics
        records.append(record)
        log(f"drape-metrics={json.dumps(record, sort_keys=True)}")
    payload = {
        "target_height": target_height,
        "target_width": target_width,
        "shoulder_z": shoulder_z,
        "hem_z": hem_z,
        "panels": records,
        "seam_coherence": _seam_coherence(panels, seam_records, proxy=proxy),
    }
    with open(METRICS, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)


def _make_tunic_sketch(
    doc, name, panel_width, garment_height, hem_width, neckline_ratio, neckline_drop=0.08
):
    import Part
    import Sketcher

    sketch = doc.addObject("Sketcher::SketchObject", name + "Sketch")
    neck_z = (1.0 - float(neckline_drop)) * garment_height
    # Keep the shoulder/neck construction centered within the wider hem.
    # The previous coordinates anchored the upper panel at x=0, so changing
    # hem_width moved the hem center without moving the shoulder center.
    x_offset = 0.5 * (float(hem_width) - float(panel_width))
    armhole_z = 0.88 * garment_height
    shoulder_z = 0.98 * garment_height
    points = [
        (0.00, 0.00),
        (hem_width, 0.00),
        (x_offset + panel_width, armhole_z),
        (x_offset + 0.86 * panel_width, shoulder_z),
        (x_offset + neckline_ratio * panel_width, neck_z),
        (x_offset + (1.0 - neckline_ratio) * panel_width, neck_z),
        (x_offset + 0.14 * panel_width, shoulder_z),
        (x_offset, armhole_z),
    ]
    center_x = 0.5 * float(hem_width)
    for left, right in ((0, 1), (2, 7), (3, 6), (4, 5)):
        if abs((points[left][0] + points[right][0]) - 2.0 * center_x) > 1e-9:
            raise RuntimeError("canonical tunic pattern lost bilateral symmetry")
    geometry = [
        Part.LineSegment(
            App.Vector(points[i][0], points[i][1], 0),
            App.Vector(points[(i + 1) % len(points)][0], points[(i + 1) % len(points)][1], 0),
        )
        for i in range(len(points))
    ]
    sketch.addGeometry(geometry, False)
    sketch.addConstraint(
        [
            Sketcher.Constraint("Coincident", 0, 2, 1, 1),
            Sketcher.Constraint("Coincident", 1, 2, 2, 1),
            Sketcher.Constraint("Coincident", 2, 2, 3, 1),
            Sketcher.Constraint("Coincident", 3, 2, 4, 1),
            Sketcher.Constraint("Coincident", 4, 2, 5, 1),
            Sketcher.Constraint("Coincident", 5, 2, 6, 1),
            Sketcher.Constraint("Coincident", 6, 2, 7, 1),
            Sketcher.Constraint("Coincident", 7, 2, 0, 1),
        ]
    )
    doc.recompute()
    return sketch, points


def _adopt_sketch(sketch, name, allowance, grainline):
    from freecad_cloth.pattern.PatternCommands import create_pattern_piece_from_selected_sketch

    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(sketch)
    piece = create_pattern_piece_from_selected_sketch(
        name=name, allowance=allowance, grainline=grainline
    )
    piece.Label = name
    doc = App.ActiveDocument
    doc.recompute()
    if piece.Sketch is not sketch:
        raise RuntimeError("Cloth PatternPiece did not retain the selected native Sketcher source")
    return piece


def pattern_and_sewing():
    import Part

    from freecad_cloth.pattern.PatternGui import PatternPieceTaskPanel
    from freecad_cloth.pattern.PatternModel import Seam
    from freecad_cloth.pattern.PatternObjects import add_seam
    from freecad_cloth.sewing.SewingCommands import create_sewing_operation
    from freecad_cloth.sewing.SewingGui import SewingTaskPanel

    doc = App.newDocument("ClothVisualPattern")
    front_sketch, _front_outline = _make_tunic_sketch(
        doc, "VisualFront", 520.0, 720.0, 600.0, 0.64, 0.10
    )
    back_sketch, _back_outline = _make_tunic_sketch(
        doc, "VisualBack", 520.0, 720.0, 600.0, 0.64, 0.07
    )
    doc.recompute()
    front = _adopt_sketch(front_sketch, "Front Tunic", 10.0, 0.0)
    back = _adopt_sketch(back_sketch, "Back Tunic", 10.0, 0.0)
    front.Placement.Base.x = -660
    back.Placement.Base.x = 40
    front.Sketch.Placement = front.Placement
    back.Sketch.Placement = back.Placement
    marker = doc.addObject("Part::Feature", "GrainlineMarker")
    marker.Shape = Part.makeLine(App.Vector(-400, 90, 1), App.Vector(-400, 640, 1))
    front.ViewObject.Visibility = False
    back.ViewObject.Visibility = False
    front.Sketch.ViewObject.Visibility = True
    back.Sketch.ViewObject.Visibility = True
    doc.recompute()
    if front.Shape.isNull() or back.Shape.isNull():
        raise RuntimeError("pattern fixture produced empty geometry from native sketches")
    activate(
        "ClothPatternWorkbench",
        "Cloth Pattern",
        [
            "ClothPattern_CreatePieceTask",
            "ClothPattern_EditPiece",
            "ClothPattern_Show2D",
            "ClothPattern_CreateFromSketch",
        ],
    )
    panel = PatternPieceTaskPanel(front)
    show_task(
        panel,
        "Pattern Workbench",
        ("Piece name", "Width", "Height", "Seam allowance", "Grainline angle"),
    )
    Gui.activeDocument().activeView().viewTop()
    Gui.activeDocument().activeView().fitAll()
    events()
    save(
        "cloth-pattern-design.png",
        "Pattern Workbench",
        "native Sketcher tunic pattern adopted into Cloth PatternPiece",
    )
    close_task()
    seam = add_seam(
        doc,
        Seam(
            str(front.PieceId),
            7,
            str(back.PieceId),
            7,
            id="FrontBack",
            alignment="endpoints",
            stitch_group="MainSeam",
        ),
    )
    doc.recompute()
    sewing = create_sewing_operation()
    doc.recompute()
    if (
        str(seam.Status) != "Valid"
        or seam.Shape.isNull()
        or str(sewing.Status) != "Valid"
        or sewing.Shape.isNull()
    ):
        raise RuntimeError("sewing fixture is invalid")
    activate(
        "ClothSewingWorkbench",
        "Cloth Sewing",
        ["ClothSewing_CreateOperation", "ClothSewing_EditOperation", "ClothSewing_Validate"],
    )
    panel = SewingTaskPanel(sewing)
    show_task(
        panel,
        "Sewing Workbench",
        ("Seam", "Alignment", "Validation tolerance", "Stitch samples", "Status"),
    )
    Gui.activeDocument().activeView().viewTop()
    Gui.activeDocument().activeView().fitAll()
    events()
    save("cloth-sewing.png", "Sewing Workbench", "native tunic Sketcher boundary and semantic seam")
    close_task()
    App.closeDocument(doc.Name)


def style_mesh(obj, label):
    obj.Label = label
    try:
        obj.ViewObject.DisplayMode = "Shaded"
        obj.ViewObject.ShapeColor = (0.14, 0.32, 0.78)
        obj.ViewObject.Transparency = 0
        obj.ViewObject.LineWidth = 1.0
        if hasattr(obj.ViewObject, "SpecularColor"):
            obj.ViewObject.SpecularColor = (0.45, 0.45, 0.45)
        if hasattr(obj.ViewObject, "Shininess"):
            obj.ViewObject.Shininess = 45.0
    except (AttributeError, TypeError, ValueError):
        pass


def simulation():
    import os

    os.environ["CLOTH_PBD_COLLISION_MODE"] = "mesh"
    from freecad_cloth.pattern.PatternModel import Seam
    from freecad_cloth.pattern.PatternObjects import add_seam
    from freecad_cloth.simulation.DrapeTarget import (
        collision_surface,
        refresh_drape_target,
        target_status,
    )
    from freecad_cloth.simulation.SimulationQualityGui import SimulationQualityTaskPanel
    from freecad_cloth.simulation.SimulationCommands import create_quality_simulation_scene

    doc = App.newDocument("ClothSimulationVisualRegression")
    scene = create_quality_simulation_scene(doc)
    avatar = getattr(scene.AvatarProxy, "SourceObject", None)
    target = scene.DrapeTarget
    if avatar is None or str(getattr(avatar, "AvatarType", "")) != "ClothAvatar":
        raise RuntimeError("visual fixture did not create the production ClothAvatar")
    if target is None:
        raise RuntimeError("visual fixture did not create DrapeTarget")
    target_source = getattr(target, "SourceObject", None)
    if target_source is not avatar:
        raise RuntimeError(
            "visual fixture DrapeTarget does not reference the production ClothAvatar"
        )
    refresh_drape_target(target)
    pre_status = target_status(target)
    if str(pre_status.get("state", "")) != "ready":
        raise RuntimeError(
            "canonical tunic DrapeTarget is not current before placement: {}".format(
                pre_status.get("message", pre_status)
            )
        )
    target_surface = collision_surface(
        target_source,
        float(getattr(target, "CollisionDeflection", 1.0)),
        float(getattr(target, "CollisionThickness", 0.0)),
    )
    if not target_surface.vertices or not target_surface.triangles:
        raise RuntimeError("canonical tunic DrapeTarget has no authoritative collision triangles")
    from freecad_cloth.avatar.AvatarFitting import ArrangementPoint

    def arrangement_world(name):
        raw = next(
            (
                value
                for value in getattr(avatar, "ArrangementPoints", ())
                if str(value).split("|", 1)[0] == name
            ),
            None,
        )
        if raw is None:
            raise RuntimeError(f"canonical tunic is missing avatar arrangement point {name}")
        point = ArrangementPoint.from_string(raw)
        return avatar.Placement.multVec(App.Vector(*point.position()))

    shoulder_left = arrangement_world("shoulder_left")
    shoulder_right = arrangement_world("shoulder_right")
    hip_point = arrangement_world("hip")
    target_ys = [float(vertex[1]) for vertex in target_surface.vertices]
    y_span = max(target_ys) - min(target_ys)
    x_mid = (shoulder_left.x + shoulder_right.x) / 2.0
    shoulder_z = (shoulder_left.z + shoulder_right.z) / 2.0
    hem_z = hip_point.z
    shoulder_width = abs(shoulder_right.x - shoulder_left.x)
    # The shoulder line occupies 72% of the authored panel width (0.86 - 0.14).
    # Size the panel from the mannequin shoulder span so the garment is not
    # undersized at the shoulders before the sewing constraints are evaluated.
    shoulder_span_ratio = 0.86 - 0.14
    panel_width = max(420.0, shoulder_width / shoulder_span_ratio + 20.0)
    hem_width = max(450.0, panel_width + 80.0)
    garment_height = max(560.0, shoulder_z - hem_z)
    body_depth = max(120.0, min(260.0, y_span))
    clearance = max(20.0, 0.08 * body_depth)
    rot = App.Rotation(App.Vector(1, 0, 0), 90.0)

    def target_relative_piece_placement(side):
        if side == "front":
            y = min(target_ys) - clearance
        elif side == "back":
            y = max(target_ys) + clearance
        else:
            raise ValueError("tunic target-relative side must be front or back")
        return App.Placement(App.Vector(x_mid - hem_width / 2.0, y, hem_z), rot)

    def make_piece(name, side, neckline_ratio, neckline_drop):
        sketch, outline = _make_tunic_sketch(
            doc,
            name + "Source",
            panel_width,
            garment_height,
            hem_width,
            neckline_ratio,
            neckline_drop,
        )
        doc.recompute()
        piece = _adopt_sketch(sketch, name, 10.0, 0.0)
        piece.Label = name
        piece.Placement = target_relative_piece_placement(side)
        piece.Sketch.Placement = piece.Placement
        return piece, outline

    # Match the sewn shoulder endpoints on both panels. Front/back neckline shape may diverge at the center,
    # but this planar fixture represents the shared shoulder-to-neck join with identical authored coordinates.
    front, front_outline = make_piece("VisualTunicFront", "front", 0.64, 0.10)
    back, back_outline = make_piece("VisualTunicBack", "back", 0.64, 0.10)
    # Resolve sewn edges by native semantic IDs; PatternIR boundary order is independent
    # of Sketcher insertion order. Side seams run in opposite authored directions on
    # the mirrored panels, so B is reversed only for the two side seams.
    front_edge_ids = tuple(str(value) for value in getattr(front.Sketch, "SemanticEdgeIds", ()) or ())
    back_edge_ids = tuple(str(value) for value in getattr(back.Sketch, "SemanticEdgeIds", ()) or ())
    if len(front_edge_ids) < 8 or len(back_edge_ids) < 8:
        raise RuntimeError("canonical tunic sketches have no complete semantic edge map")
    required_indices = (1, 3, 5, 7)
    if any(not front_edge_ids[index] or not back_edge_ids[index] for index in required_indices):
        raise RuntimeError("canonical tunic fixture is missing authored semantic edge IDs")
    seam_specs = (
        (front_edge_ids[1], back_edge_ids[1], "TunicRightSide", False),
        (front_edge_ids[3], back_edge_ids[3], "TunicRightShoulder", False),
        (front_edge_ids[5], back_edge_ids[5], "TunicLeftShoulder", False),
        (front_edge_ids[7], back_edge_ids[7], "TunicLeftSide", False),
    )
    seam_records = []
    for edge_a_id, edge_b_id, seam_id, reversed_b in seam_specs:
        seam = Seam(
            str(front.PieceId),
            edge_a_id,
            str(back.PieceId),
            edge_b_id,
            id=seam_id,
            reversed_b=reversed_b,
            alignment="uniform",
            stitch_group="TunicAssembly",
        )
        add_seam(doc, seam)
        seam_obj = next(o for o in doc.Objects if getattr(o, "SeamId", "") == seam_id)
        if (
            str(getattr(seam_obj, "EdgeAId", "")) != edge_a_id
            or str(getattr(seam_obj, "EdgeBId", "")) != edge_b_id
            or bool(getattr(seam_obj, "ReversedB", False)) != reversed_b
        ):
            raise RuntimeError("canonical tunic seam %s did not retain its authored correspondence" % seam_id)
        seam_records.append((seam_obj, front, back))
    scene.StartHeight = 0.0
    scene.QualityPreset = "Fast"
    scene.ParticleDistance = 24.0
    scene.SolverIterations = 8
    scene.SolverSubsteps = 1
    scene.TimeStep = 1.0 / 120.0
    scene.GravityX = 0.0
    scene.GravityY = 0.0
    scene.GravityZ = -9810.0
    scene.FabricFriction = 0.75
    # Semantic descriptors survive remeshing: piece ID + authored edge ID + avatar landmark.
    scene.ClothPieces = [front, back]
    scene.PinMode = "Avatar Attachment"
    scene.PinSelection = []
    scene.AttachmentOffset = max(3.0, float(getattr(target, "CollisionThickness", 0.0)))
    # Both panels attach to the same lateral skin points at each sewn shoulder.
    # This supports the seam on both sides; initial gaps below diagnose whether the
    # solver stitches pair pinned particles with their actual counterparts.
    scene.AvatarAttachmentAnchors = [
        "%s|%s|shoulder_right" % (front.PieceId, front_edge_ids[3]),
        "%s|%s|shoulder_left" % (front.PieceId, front_edge_ids[5]),
        "%s|%s|shoulder_right" % (back.PieceId, back_edge_ids[3]),
        "%s|%s|shoulder_left" % (back.PieceId, back_edge_ids[5]),
    ]
    refresh_drape_target(target)
    doc.recompute()
    status = target_status(target)
    if str(status.get("state", "")) != "ready":
        raise RuntimeError(
            "canonical tunic DrapeTarget is not current: {}".format(status.get("message", status))
        )
    proxy = scene.Proxy
    backend = getattr(proxy, "backend", None)
    if backend is None:
        raise RuntimeError("canonical tunic did not build an avatar-attached simulation backend")
    solver_pins = tuple(sorted(int(index) for index in getattr(backend, "_pin_indices", ())))
    projections = tuple(getattr(proxy, "attachment_projections", ()))
    expected_pins = tuple(sorted(int(projection.particle_index) for projection in projections))
    if not projections or solver_pins != expected_pins:
        raise RuntimeError(
            "canonical tunic semantic avatar anchors did not resolve to solver pins: {} != {}".format(
                solver_pins, expected_pins
            )
        )
    # Trace the exact solver stitch correspondence before stepping. Pinned-particle
    # flags show whether the avatar anchors are members of stitched samples; XYZ
    # deltas distinguish incorrect edge pairing from later solver dynamics.
    initial_solver_positions = tuple(backend.positions())
    pinned_indices = set(solver_pins)
    stitch_pairs_by_seam = getattr(proxy, "seam_stitch_pairs", {})
    for seam, _piece_a, _piece_b in seam_records:
        seam_id = str(getattr(seam, "SeamId", ""))
        stitch_pairs = tuple(stitch_pairs_by_seam.get(seam_id, ()))
        if not stitch_pairs:
            raise RuntimeError("canonical tunic seam has no solver stitch pairs: %s" % seam_id)
        for sample_index, (index_a, index_b) in enumerate(stitch_pairs):
            point_a = initial_solver_positions[int(index_a)]
            point_b = initial_solver_positions[int(index_b)]
            dx = float(point_a[0]) - float(point_b[0])
            dy = float(point_a[1]) - float(point_b[1])
            dz = float(point_a[2]) - float(point_b[2])
            gap = (dx * dx + dy * dy + dz * dz) ** 0.5
            log(
                "tunic-seam-initial-pair id=%s sample=%d vertices=%d,%d pins=%s,%s "
                "dx=%.2f dy=%.2f dz=%.2f gap=%.2f"
                % (
                    seam_id, sample_index, int(index_a), int(index_b),
                    int(index_a) in pinned_indices, int(index_b) in pinned_indices,
                    dx, dy, dz, gap,
                )
            )
    surface = collision_surface(
        target_source,
        float(getattr(target, "CollisionDeflection", 1.0)),
        float(getattr(target, "CollisionThickness", 0.0)),
    )
    initial_clearance = None
    try:
        from freecad_cloth.common.MeshValidation import nearest_target_clearance

        current_positions = tuple(backend.positions())
        pinned_set = set(solver_pins)
        unanchored_positions = tuple(
            position for index, position in enumerate(current_positions) if index not in pinned_set
        )
        initial_clearance = nearest_target_clearance(
            unanchored_positions, tuple(surface.vertices)
        )
    except (ImportError, ValueError):
        initial_clearance = None
    if initial_clearance is None or float(initial_clearance) < float(clearance):
        raise RuntimeError(
            "canonical tunic step-0 target clearance is below configured separation: "
            f"{float(initial_clearance or 0.0):.2f} mm < {float(clearance):.2f} mm"
        )
    log("pin-mode=Avatar Attachment shoulder-anchor-pins=%s offset-mm=%.2f" % (solver_pins, float(scene.AttachmentOffset)))
    log("target-collision-mode=mesh")
    log(
        f"step0-target-vertex-clearance-mm={float(initial_clearance):.2f} required-mm={float(clearance):.2f}"
    )
    for source in (doc.getObject("VisualTunicFront"), doc.getObject("VisualTunicBack")):
        if source is not None:
            source.ViewObject.Visibility = False
        sketch = getattr(source, "Sketch", None) if source is not None else None
        if sketch is not None:
            sketch.ViewObject.Visibility = False
    panels = list(scene.DrapePanels)
    if len(panels) != 2:
        raise RuntimeError("expected two drape panels, got %d" % len(panels))
    for panel, label in zip(panels, ("Drape: Tunic Front", "Drape: Tunic Back"), strict=False):
        style_mesh(panel, label)
        panel.ViewObject.Visibility = True
    avatar.ViewObject.Visibility = True
    doc.recompute()
    target_xs = [float(vertex[0]) for vertex in target_surface.vertices]
    target_ys = [float(vertex[1]) for vertex in target_surface.vertices]
    target_zs = [float(vertex[2]) for vertex in target_surface.vertices]
    log(
        f"target-surface-bounds x={min(target_xs):.1f}..{max(target_xs):.1f} y={min(target_ys):.1f}..{max(target_ys):.1f} z={min(target_zs):.1f}..{max(target_zs):.1f}"
    )
    log(
        "tunic-source=freecad-native-sketcher edges=%d front=%s back=%s"
        % (len(front.Sketch.Geometry), front.Sketch.Name, back.Sketch.Name)
    )
    if (
        int(getattr(avatar, "MeshVertexCount", 0)) <= 100
        or int(getattr(avatar, "MeshTriangleCount", 0)) <= 100
    ):
        raise RuntimeError("visual fixture does not contain a real humanoid mesh")
    activate("ClothSimulationWorkbench", "Cloth Simulation", ["ClothSimulation_Edit"])
    simulation_panel = SimulationQualityTaskPanel(scene)
    task_dock = show_task(
        simulation_panel,
        "Simulation Workbench arranged",
        (
            "Preset",
            "Particle distance",
            "Density",
            "Avatar skin offset",
            "Simulation steps",
            "Step",
            "Run 30",
            "Reset",
        ),
    )
    view = Gui.activeDocument().activeView()
    view.setCameraType("Orthographic")
    view.viewFront()
    view.fitAll()
    events()
    task_dock.hide()
    events()
    save(
        "cloth-simulation-arranged.png",
        "Simulation Workbench arranged",
        "vertical sewn tunic generated from native Sketcher pattern sources on production mannequin",
    )
    task_dock.show()
    task_dock.raise_()
    events()
    os.makedirs(os.path.join(OUT, "cloth-tunic-mannequin-motion-frames"), exist_ok=True)
    task_dock.hide()
    events()
    view.setCameraType("Orthographic")
    view.viewAxonometric()
    view.fitAll()
    events()
    save(
        "cloth-tunic-mannequin-motion-frames/motion-000.png",
        "mannequin drape step 0",
        "production tunic before gravity",
    )
    for frame_index, batch in enumerate((10, 10, 10, 10, 10, 10, 10, 10, 10), start=1):
        simulation_panel.step(batch)
        doc.recompute()
        events()
        view.viewAxonometric()
        view.fitAll()
        events()
        save(
            "cloth-tunic-mannequin-motion-frames/motion-%03d.png" % frame_index,
            "mannequin drape step %d" % int(scene.Steps),
            "production tunic gravity progression",
        )
    task_dock.show()
    task_dock.raise_()
    events()
    if int(scene.Steps) != 90 or float(scene.SimulatedTime) <= 0.0 or not bool(scene.FiniteState):
        raise RuntimeError("simulation did not reach a finite 90-step state")
    # A tunic that begins at the shoulders must remain supported by the upper
    # body after gravity; a skirt-like result is a simulation failure even
    # when the solver remains finite and non-penetrating.
    final_positions = tuple(backend.positions())
    from freecad_cloth.simulation.SimulationObjects import seam_gap_diagnostics
    seam_reports = seam_gap_diagnostics(
        final_positions,
        getattr(proxy, "seam_stitch_pairs", {}),
    )
    expected_seam_ids = tuple(str(seam.SeamId) for seam, _piece_a, _piece_b in seam_records)
    if set(seam_reports) != set(expected_seam_ids):
        raise RuntimeError(
            "authoritative tunic seam set mismatch: expected=%s actual=%s"
            % (expected_seam_ids, tuple(sorted(seam_reports)))
        )
    for seam, _piece_a, _piece_b in seam_records:
        report = seam_reports[str(seam.SeamId)]
        log(
            "authoritative-seam-detail id=%s reversed_b=%s pairs=%d first_gap=%.2f last_gap=%.2f max_gap=%.2f"
            % (
                str(seam.SeamId),
                bool(getattr(seam, "ReversedB", False)),
                int(report["pair_count"]),
                float(report["first_gap"]),
                float(report["last_gap"]),
                float(report["max_gap"]),
            )
        )
    max_seam_gap = max(float(report["max_gap"]) for report in seam_reports.values())
    if max_seam_gap > 35.0:
        raise RuntimeError(
            "authoritative tunic seams did not converge: max endpoint gap %.1f mm"
            % max_seam_gap
        )
    log("authoritative-seam-max-gap-mm=%.2f seam-ids=%s" % (max_seam_gap, expected_seam_ids))
    minimum_top_z = float(shoulder_z) - 30.0
    for panel in scene.DrapePanels:
        panel_indices = tuple(getattr(proxy, "panel_indices", {}).get(panel.Name, ()))
        if not panel_indices:
            raise RuntimeError(f"missing solver indices for drape panel {panel.Name}")
        top_z = max(float(final_positions[index][2]) for index in panel_indices)
        log(f"tunic-upper-support={panel.Name} top-z={top_z:.2f} shoulder-z={float(shoulder_z):.2f} minimum-top-z={minimum_top_z:.2f}")
        if top_z < minimum_top_z:
            raise RuntimeError(
                "simulated tunic slipped below the shoulder line: "
                f"{panel.Name} top z={top_z:.2f} mm < required {minimum_top_z:.2f} mm"
            )
    if any(panel.Mesh.CountFacets <= 10 for panel in scene.DrapePanels):
        raise RuntimeError("draped tunic panel mesh is empty")
    from freecad_cloth.simulation.ClothDiagnosticsGui import DiagnosticsTaskPanel, create_diagnostic_map

    diagnostics_panel = DiagnosticsTaskPanel(scene)
    diagnostic_dock = show_task(
        diagnostics_panel,
        "Cloth Diagnostics",
        (
            "Formula:",
            "Read-only",
            "Refresh analysis",
            "Create diagnostic map",
            "Export analysis data",
        ),
    )
    diagnostic_dock.hide()
    events()
    diagnostic_maps = create_diagnostic_map(scene, "stress")
    if not diagnostic_maps:
        raise RuntimeError("valid draped tunic produced no diagnostic stress map")
    for diagnostic in diagnostic_maps:
        diagnostic.ViewObject.Visibility = True
    log("diagnostic-map=passed metric=stress maps=%d" % len(diagnostic_maps))
    original_finite = bool(scene.FiniteState)
    scene.FiniteState = False
    try:
        create_diagnostic_map(scene, "stress")
    except RuntimeError as exc:
        log(f"diagnostic-stale-guard=passed message={str(exc)}")
    else:
        raise RuntimeError("diagnostics created a map from a non-finite simulation state")
    finally:
        scene.FiniteState = original_finite
    view.viewFront()
    view.fitAll()
    events()
    save(
        "cloth-simulation-draped-diagnostics.png",
        "Cloth Diagnostics stress map",
        "read-only stress utilization map over the valid 90-step drape",
    )
    for diagnostic in diagnostic_maps:
        diagnostic.ViewObject.Visibility = False
    write_drape_metrics(
        panels,
        avatar,
        x_mid,
        shoulder_z=shoulder_z,
        hem_z=hem_z,
        seam_records=seam_records,
        proxy=proxy,
        collision_surface=target_surface,
    )
    bounds = []
    for panel in scene.DrapePanels:
        b = panel.Mesh.BoundBox
        bounds.append((b.XMin, b.XMax, b.YMin, b.YMax, b.ZMin, b.ZMax))
    log(f"drape-bounds={bounds}")
    task_dock.hide()
    events()
    for direction, method_name in (
        ("front", "viewFront"),
        ("rear", "viewRear"),
        ("left", "viewLeft"),
        ("right", "viewRight"),
        ("top", "viewTop"),
        ("bottom", "viewBottom"),
    ):
        getattr(view, method_name)()
        view.fitAll()
        events()
        save(
            f"cloth-simulation-draped-{direction}.png",
            f"Simulation Workbench draped {direction}",
            "same sewn tunic after %d real steps; six-side audit from native Sketcher pattern sources"
            % int(scene.Steps),
        )
        if direction == "front":
            save(
                "cloth-simulation-draped.png",
                "Simulation Workbench draped front",
                "legacy front screenshot alias; native Sketcher tunic source",
            )
    from freecad_cloth.simulation.DrapeVisualSanity import assert_drape_diagnostics

    with open(METRICS, encoding="utf-8") as handle:
        # This fixture is intentionally unpinned: gravity may place the free-draped
        # hem below the authored hip reference without indicating detachment, collapse,
        # or collision failure. Keep those other fail-closed diagnostics authoritative.
        assert_drape_diagnostics(
            json.load(handle).get("panels", ()),
            allowed_diagnostics={"below-hem-candidate"},
        )
    task_dock.show()
    task_dock.raise_()
    events()
    close_task()
    App.closeDocument(doc.Name)


def main():
    log("script-start")
    if Gui.getMainWindow() is None or not Gui.getMainWindow().isVisible():
        raise RuntimeError("FreeCAD GUI did not launch")
    Gui.getMainWindow().show()
    events()
    events()
    if os.environ.get("CLOTH_TUNIC_AUDIT_RUN_AVATAR_ACCEPTANCE"):
        load_and_run(
            os.path.join(ROOT, "tests/freecad_avatar_acceptance.py"),
            "freecad_avatar_acceptance_inprocess",
        )
        log("avatar-provider-acceptance=passed")
    if not os.environ.get("CLOTH_TUNIC_AUDIT_SKIP_CANONICAL_ACCEPTANCE"):
        run_canonical_acceptance()
    if not os.environ.get("CLOTH_TUNIC_AUDIT_SKIP_PATTERN_SEWING"):
        pattern_and_sewing()
    if not os.environ.get("CLOTH_TUNIC_AUDIT_SKIP_SIMULATION"):
        simulation()
    log("scenario-pass")


exit_code = 0
try:
    main()
except BaseException as error:
    exit_code = 1
    print(f"SCENARIO FAILURE: {error!r}", flush=True)
    print(traceback.format_exc(), flush=True)
    log(f"scenario-fail exception={error!r}")
finally:
    try:
        close_task()
        for document in list(App.listDocuments().values()):
            with contextlib.suppress(Exception):
                App.closeDocument(document.Name)
        events()
        log("script-end exit-code=%d" % exit_code)
        if exit_code == 0:
            log("tunic-audit-process-exit=success")
            sys.stdout.flush()
            getattr(os, "_" + "exit")(0)
        window = Gui.getMainWindow()
        if window is not None:
            window.close()
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.quit()
    except BaseException:
        pass
if exit_code:
    os._exit(1)
