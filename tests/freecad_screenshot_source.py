"""Deterministic FreeCAD GUI acceptance and six-side cloth visual audit."""

import contextlib
import importlib.util
import json
import math
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


def _as_coordinates3(value, label):
    """Normalize either a FreeCAD vector or a tuple-like 3D value."""
    if all(hasattr(value, axis) for axis in ("x", "y", "z")):
        raw = (value.x, value.y, value.z)
    else:
        try:
            raw = tuple(value)
        except TypeError as exc:
            raise ValueError("%s must be a three-component coordinate" % label) from exc
    try:
        coordinates = tuple(float(component) for component in raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("%s must be a three-component coordinate" % label) from exc
    if len(coordinates) != 3:
        raise ValueError("%s must be a three-component coordinate" % label)
    return coordinates


def _mesh_geometry(mesh):
    topology = getattr(mesh, "Topology", None)
    if topology is None:
        return (), ()
    vertices, triangles = topology
    points = tuple(_as_coordinates3(point, "mesh vertex") for point in vertices)
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


def _inside_target_states(points, target, collision_surface=None):
    """Return inside/outside states and report the topology used by the audit."""
    shape = getattr(target, "Shape", None)
    shape_is_inside = getattr(shape, "isInside", None) if shape is not None else None
    if callable(shape_is_inside):
        states = []
        try:
            for point in points:
                states.append(bool(shape_is_inside(App.Vector(*point), 1e-6, True)))
        except (AttributeError, TypeError, ValueError, RuntimeError):
            states = None
        if states is not None:
            log("penetration-check=FreeCAD-Shape.isInside points=%d" % len(points))
            return tuple(states)

    native_mesh = getattr(target, "Mesh", None)
    mesh_is_inside = getattr(native_mesh, "isInside", None) if native_mesh is not None else None
    if callable(mesh_is_inside):
        states = []
        try:
            for point in points:
                states.append(bool(mesh_is_inside(App.Vector(*point), 1e-6, True)))
        except (AttributeError, TypeError, ValueError, RuntimeError):
            states = None
        if states is not None:
            log("penetration-check=FreeCAD-Mesh.isInside points=%d" % len(points))
            return tuple(states)

    if collision_surface is None:
        raise RuntimeError("mannequin target does not expose an inside/outside collision test")
    vertices = tuple(getattr(collision_surface, "vertices", ()) or ())
    triangles = tuple(getattr(collision_surface, "triangles", ()) or ())
    if not vertices or not triangles:
        raise RuntimeError("authoritative collision surface has no inside/outside topology")

    native_mesh_solid = None
    native_is_solid = getattr(native_mesh, "isSolid", None) if native_mesh is not None else None
    if callable(native_is_solid):
        try:
            native_mesh_solid = bool(native_is_solid())
        except (AttributeError, TypeError, ValueError, RuntimeError):
            native_mesh_solid = None

    log("penetration-target-native-solid=%s" % native_mesh_solid)

    # trimesh provides a robust vectorized point-containment query only for a
    # watertight target. Log both topology and query fallback reasons so open
    # target meshes cannot silently masquerade as a valid solid classification.
    try:
        import numpy as np
        import trimesh
    except ImportError as error:
        log("penetration-trimesh-unavailable reason=%s:%s" % (
            type(error).__name__, str(error)[:180]
        ))
    else:
        try:
            target_mesh = trimesh.Trimesh(
                vertices=np.asarray(vertices, dtype=float),
                faces=np.asarray(triangles, dtype=int),
                process=False,
            )
            watertight = bool(target_mesh.is_watertight)
            winding_consistent = bool(target_mesh.is_winding_consistent)
            log(
                "penetration-target-topology watertight=%s winding_consistent=%s native_mesh_solid=%s"
                % (watertight, winding_consistent, native_mesh_solid)
            )
            if watertight:
                try:
                    states = target_mesh.contains(np.asarray(points, dtype=float))
                except Exception as error:
                    log("penetration-trimesh-contains-fallback reason=%s:%s" % (
                        type(error).__name__, str(error)[:180]
                    ))
                else:
                    log("penetration-check=trimesh-contains points=%d triangles=%d" % (
                        len(points), len(triangles)
                    ))
                    return tuple(bool(state) for state in states)
            else:
                log("penetration-trimesh-contains-fallback reason=target-not-watertight")
        except (RuntimeError, TypeError, ValueError, IndexError) as error:
            log("penetration-trimesh-topology-fallback reason=%s:%s" % (
                type(error).__name__, str(error)[:180]
            ))

    from freecad_cloth.simulation.DrapeVisualSanity import points_inside_closed_mesh

    log("penetration-check=numpy-ray-parity points=%d triangles=%d" % (
        len(points), len(triangles)
    ))
    return points_inside_closed_mesh(points, vertices, triangles)


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
        inside_flags = _inside_target_states(vertices, avatar, collision_surface)
        penetrating_vertices = sum(inside_flags)
        record["penetration_surface"] = (
            "solver" if solver_collision_surface is not None else "authoritative-target"
        )
        record["penetrating_vertices"] = int(penetrating_vertices)
        if penetrating_vertices:
            if collision_surface is not None:
                from math import dist

                from freecad_cloth.simulation.DrapeVisualSanity import points_inside_closed_mesh

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
                inside_positions = []
                if target_points and target_triangles:
                    for point, authoritative_inside in zip(vertices, inside_flags, strict=False):
                        if not authoritative_inside:
                            continue
                        point_tuple = tuple(float(value) for value in point)
                        nearest = min(
                            dist(point_tuple, tuple(float(value) for value in target))
                            for target in target_points
                        )
                        inside_positions.append(point_tuple)
                        inside_points.append(
                            {
                                "point": tuple(round(value, 3) for value in point_tuple),
                                "nearest_target_vertex_mm": round(float(nearest), 3),
                                "solver_surface_inside": None,
                            }
                        )
                        if len(inside_points) >= 12:
                            break
                if inside_positions and solver_vertices and solver_triangles:
                    solver_inside_states = points_inside_closed_mesh(
                        inside_positions, solver_vertices, solver_triangles
                    )
                    for sample, solver_inside in zip(inside_points, solver_inside_states, strict=False):
                        sample["solver_surface_inside"] = bool(solver_inside)
                log(
                    "penetration-evidence panel=%s count=%d samples=%s"
                    % (record["panel"], penetrating_vertices, inside_points)
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
    doc,
    name,
    panel_width,
    garment_height,
    hem_width,
    neckline_ratio,
    neckline_drop=0.08,
    shoulder_height=None,
    neckline_height=None,
    armhole_height=None,
):
    import Part
    import Sketcher

    sketch = doc.addObject("Sketcher::SketchObject", name + "Sketch")
    # Normal pattern previews retain the authored ratios. The mannequin audit
    # supplies heights from its named shoulder and neck landmarks so the source
    # pattern, not only the solver's pinned vertices, matches the avatar.
    shoulder_z = (
        0.78 * garment_height
        if shoulder_height is None
        else float(shoulder_height)
    )
    neck_z = (
        shoulder_z - float(neckline_drop) * garment_height
        if neckline_height is None
        else float(neckline_height)
    )
    x_offset = 0.5 * (float(hem_width) - float(panel_width))
    armhole_z = (
        0.68 * garment_height
        if armhole_height is None
        else float(armhole_height)
    )
    if armhole_height is not None and not (0.0 < armhole_z < shoulder_z < neck_z < garment_height):
        raise RuntimeError(
            "canonical tunic heights must satisfy hem < armhole < shoulder < neckline < top"
        )
    points = [
        (0.00, 0.00),
        (hem_width, 0.00),
        (x_offset + 0.95 * panel_width, armhole_z),
        (x_offset + 0.86 * panel_width, shoulder_z),
        (x_offset + neckline_ratio * panel_width, neck_z),
        (x_offset + 0.5 * panel_width, neck_z),
        (x_offset + (1.0 - neckline_ratio) * panel_width, neck_z),
        (x_offset + 0.14 * panel_width, shoulder_z),
        (x_offset + 0.05 * panel_width, armhole_z),
    ]
    center_x = 0.5 * float(hem_width)
    for left, right in ((0, 1), (2, 8), (3, 7), (4, 6)):
        if abs((points[left][0] + points[right][0]) - 2.0 * center_x) > 1e-9:
            raise RuntimeError("canonical tunic pattern lost bilateral symmetry")
    if abs(points[5][0] - center_x) > 1e-9:
        raise RuntimeError("canonical tunic neckline center is not on the panel centerline")
    geometry = []
    armhole_mid_z = armhole_z + 0.5 * (shoulder_z - armhole_z)
    for index, (start, end) in enumerate(
        zip(points, points[1:] + points[:1], strict=True)
    ):
        start_vector = App.Vector(start[0], start[1], 0)
        end_vector = App.Vector(end[0], end[1], 0)
        if index in (2, 7):
            # Give each free side opening a genuine inward scoop instead of the
            # straight shoulder-to-underarm chord that drapes over the arms.
            scoop_ratio = 0.83 if index == 2 else 0.17
            midpoint = App.Vector(
                x_offset + scoop_ratio * panel_width,
                armhole_mid_z,
                0,
            )
            # Keep the native arc parameter sweep counterclockwise by reversing its endpoints;
            # boundary connectivity restores garment traversal order when resolving PatternIR.
            geometry.append(Part.Arc(end_vector, midpoint, start_vector))
        else:
            geometry.append(Part.LineSegment(start_vector, end_vector))
    sketch.addGeometry(geometry, False)
    sketch.addConstraint(
        [
            Sketcher.Constraint("Coincident", 0, 2, 1, 1),
            Sketcher.Constraint("Coincident", 1, 2, 2, 2),
            Sketcher.Constraint("Coincident", 2, 1, 3, 1),
            Sketcher.Constraint("Coincident", 3, 2, 4, 1),
            Sketcher.Constraint("Coincident", 4, 2, 5, 1),
            Sketcher.Constraint("Coincident", 5, 2, 6, 1),
            Sketcher.Constraint("Coincident", 6, 2, 7, 2),
            Sketcher.Constraint("Coincident", 7, 1, 8, 1),
            Sketcher.Constraint("Coincident", 8, 2, 0, 1),
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


def _projected_point_within_outline_margin(x, z, points, margin):
    """Check whether a projected mesh vertex overlaps a pattern outline or its clearance band."""
    px = float(x)
    pz = float(z)
    margin_sq = float(margin) * float(margin)
    inside = False
    near = False
    for index, (ax_raw, az_raw) in enumerate(points):
        bx_raw, bz_raw = points[(index + 1) % len(points)]
        ax, az = float(ax_raw), float(az_raw)
        bx, bz = float(bx_raw), float(bz_raw)
        if (az > pz) != (bz > pz):
            crossing_x = ax + (pz - az) * (bx - ax) / (bz - az)
            if px < crossing_x:
                inside = not inside
        dx, dz = bx - ax, bz - az
        length_sq = dx * dx + dz * dz
        if length_sq > 0.0:
            factor = max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / length_sq))
            closest_x = ax + factor * dx
            closest_z = az + factor * dz
        else:
            closest_x, closest_z = ax, az
        if (px - closest_x) ** 2 + (pz - closest_z) ** 2 <= margin_sq:
            near = True
    return inside or near


def capture_tunic_pattern_view(doc, front, back, hem_width):
    """Capture the exact Sketcher profiles that are subsequently used by the 3D audit."""
    from freecad_cloth.pattern.PatternGui import PatternPieceTaskPanel

    pieces = (front, back)
    original_piece_placements = {
        piece.Name: App.Placement(piece.Placement.Base, piece.Placement.Rotation)
        for piece in pieces
    }
    original_sketch_placements = {
        piece.Sketch.Name: App.Placement(
            piece.Sketch.Placement.Base, piece.Sketch.Placement.Rotation
        )
        for piece in pieces
    }
    original_visibility = {}
    for obj in doc.Objects:
        view_object = getattr(obj, "ViewObject", None)
        if view_object is not None and hasattr(view_object, "Visibility"):
            original_visibility[obj.Name] = bool(view_object.Visibility)

    # Show the same authoritative Sketcher objects in a flat, side-by-side layout.
    # Only their placements change for this screenshot; the local profile geometry
    # remains exactly what the canonical 3D simulation consumes.
    gap = max(80.0, 0.15 * float(hem_width))
    try:
        for obj in doc.Objects:
            view_object = getattr(obj, "ViewObject", None)
            if view_object is not None and hasattr(view_object, "Visibility"):
                view_object.Visibility = False

        front_placement = App.Placement(
            App.Vector(-float(hem_width) - gap / 2.0, 0.0, 0.0), App.Rotation()
        )
        back_placement = App.Placement(
            App.Vector(gap / 2.0, 0.0, 0.0), App.Rotation()
        )
        front.Placement = front_placement
        front.Sketch.Placement = front_placement
        back.Placement = back_placement
        back.Sketch.Placement = back_placement
        front.ViewObject.Visibility = False
        back.ViewObject.Visibility = False
        front.Sketch.ViewObject.Visibility = True
        back.Sketch.ViewObject.Visibility = True
        doc.recompute()

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
        # The floating task panel obscures the second profile in the captured view.
        # Keep the workbench active, but close the panel so both canonical pieces are visible.
        close_task()
        view = Gui.activeDocument().activeView()
        view.viewTop()
        view.fitAll()
        events()
        save(
            "cloth-pattern-design.png",
            "Pattern Workbench canonical tunic profile",
            "same native Sketcher profiles used by the canonical 3D tunic audit",
        )
        log(
            "pattern-profile-alignment=passed front=%s front_edges=%d back=%s back_edges=%d"
            % (
                front.Sketch.Name,
                len(front.Sketch.Geometry),
                back.Sketch.Name,
                len(back.Sketch.Geometry),
            )
        )
    finally:
        close_task()
        for piece in pieces:
            piece.Placement = original_piece_placements[piece.Name]
            piece.Sketch.Placement = original_sketch_placements[piece.Sketch.Name]
        for obj in doc.Objects:
            if obj.Name in original_visibility:
                obj.ViewObject.Visibility = original_visibility[obj.Name]
        doc.recompute()
        Gui.activateWorkbench("ClothSimulationWorkbench")
        events()


def capture_tunic_sewing_view(doc, front, back, hem_width, seam_records):
    """Capture the Sewing workbench using the canonical simulation's tunic pieces and seams."""
    from freecad_cloth.sewing.SewingCommands import create_sewing_operation
    from freecad_cloth.sewing.SewingGui import SewingTaskPanel

    if not seam_records:
        raise RuntimeError("canonical tunic sewing view needs the simulation's semantic seam records")

    pieces = (front, back)
    original_piece_placements = {
        piece.Name: App.Placement(piece.Placement.Base, piece.Placement.Rotation)
        for piece in pieces
    }
    original_sketch_placements = {
        piece.Sketch.Name: App.Placement(
            piece.Sketch.Placement.Base, piece.Sketch.Placement.Rotation
        )
        for piece in pieces
    }
    original_visibility = {}
    for obj in doc.Objects:
        view_object = getattr(obj, "ViewObject", None)
        if view_object is not None and hasattr(view_object, "Visibility"):
            original_visibility[obj.Name] = bool(view_object.Visibility)

    sewing = None
    gap = max(80.0, 0.15 * float(hem_width))
    try:
        # Reuse the exact native Sketcher sources used by the drape. Only their
        # placements and visibility change for the flat Sewing-workbench capture.
        for obj in doc.Objects:
            view_object = getattr(obj, "ViewObject", None)
            if view_object is not None and hasattr(view_object, "Visibility"):
                view_object.Visibility = False

        front_placement = App.Placement(
            App.Vector(-float(hem_width) - gap / 2.0, 0.0, 0.0), App.Rotation()
        )
        back_placement = App.Placement(
            App.Vector(gap / 2.0, 0.0, 0.0), App.Rotation()
        )
        front.Placement = front_placement
        front.Sketch.Placement = front_placement
        back.Placement = back_placement
        back.Sketch.Placement = back_placement
        front.ViewObject.Visibility = False
        back.ViewObject.Visibility = False
        front.Sketch.ViewObject.Visibility = True
        back.Sketch.ViewObject.Visibility = True
        for seam, _piece_a, _piece_b in seam_records:
            seam.ViewObject.Visibility = True
        doc.recompute()

        invalid_seams = [
            str(getattr(seam, "SeamId", getattr(seam, "Label", seam.Name)))
            for seam, _piece_a, _piece_b in seam_records
            if str(getattr(seam, "Status", "")) != "Valid"
            or getattr(getattr(seam, "Shape", None), "isNull", lambda: True)()
        ]
        if invalid_seams:
            raise RuntimeError(
                "canonical tunic has invalid semantic seams before Sewing capture: "
                + ", ".join(invalid_seams)
            )

        activate(
            "ClothSewingWorkbench",
            "Cloth Sewing",
            ["ClothSewing_CreateOperation", "ClothSewing_EditOperation", "ClothSewing_Validate"],
        )
        sewing = create_sewing_operation()
        doc.recompute()
        if (
            str(getattr(sewing, "Status", "")) != "Valid"
            or getattr(getattr(sewing, "Shape", None), "isNull", lambda: True)()
        ):
            raise RuntimeError("canonical tunic Sewing operation is invalid")

        panel = SewingTaskPanel(sewing)
        show_task(
            panel,
            "Sewing Workbench",
            ("Seam", "Alignment", "Validation tolerance", "Stitch samples", "Status"),
        )
        # As with the pattern view, close the task panel so neither canonical
        # profile is obscured in the generated evidence.
        close_task()
        view = Gui.activeDocument().activeView()
        view.viewTop()
        view.fitAll()
        events()
        save(
            "cloth-sewing.png",
            "Sewing Workbench canonical tunic",
            "same native Sketcher profiles and semantic seams used by the canonical 3D tunic audit",
        )
        log(
            "canonical-tunic-sewing=passed front=%s back=%s seam-ids=%s"
            % (
                front.Sketch.Name,
                back.Sketch.Name,
                tuple(str(getattr(seam, "SeamId", "")) for seam, _a, _b in seam_records),
            )
        )
    finally:
        close_task()
        if sewing is not None:
            sewing.ViewObject.Visibility = False
        for piece in pieces:
            piece.Placement = original_piece_placements[piece.Name]
            piece.Sketch.Placement = original_sketch_placements[piece.Sketch.Name]
        for obj in doc.Objects:
            if obj.Name in original_visibility:
                obj.ViewObject.Visibility = original_visibility[obj.Name]
        doc.recompute()
        Gui.activateWorkbench("ClothSimulationWorkbench")
        events()


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
    # Set the fixture's local normal offset before computing panel placements.
    scene.StartHeight = 0.0
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
    neck_point = arrangement_world("neck")
    target_ys = [float(vertex[1]) for vertex in target_surface.vertices]
    y_span = max(target_ys) - min(target_ys)
    x_mid = (shoulder_left.x + shoulder_right.x) / 2.0
    shoulder_z = (shoulder_left.z + shoulder_right.z) / 2.0
    hem_z = hip_point.z
    shoulder_width = abs(shoulder_right.x - shoulder_left.x)
    # Match the panel's named landmarks to the body before solving. The outer
    # shoulder endpoints sit at shoulder height; the neckline endpoints sit just
    # below the named neck landmark. This avoids a low fixed-ratio neckline that
    # lets the entire upper panel collapse toward the hips.
    shoulder_span_ratio = 0.86 - 0.14
    panel_width = max(420.0, shoulder_width / shoulder_span_ratio)
    hem_width = max(450.0, panel_width + 80.0)
    garment_height = max(560.0, shoulder_z - hem_z, neck_point.z - hem_z)
    authored_shoulder_height = shoulder_z - hem_z
    authored_neckline_height = neck_point.z - 25.0 - hem_z
    armhole_height = authored_shoulder_height - 0.12 * garment_height
    if not (0.0 < armhole_height < authored_shoulder_height < authored_neckline_height < garment_height):
        raise RuntimeError(
            "avatar landmarks do not fit the tunic's hem/armhole/shoulder/neckline profile"
        )
    log(
        "tunic-pattern-vertical hip-z=%.2f shoulder-z=%.2f neckline-z=%.2f "
        "authored-shoulder-height=%.2f authored-neckline-height=%.2f"
        % (
            hem_z, shoulder_z, neck_point.z - 25.0,
            authored_shoulder_height, authored_neckline_height,
        )
    )
    body_depth = max(120.0, min(260.0, y_span))
    clearance = max(20.0, 0.08 * body_depth)
    # Select depth from the central torso column as well as the pattern
    # silhouette. Arms/hands can sit inside a broad 2-D garment projection and
    # otherwise inflate the front/back span despite being outside the torso.
    panel_origin_x = x_mid - hem_width / 2.0
    torso_half_width = max(80.0, 0.30 * shoulder_width)
    rot = App.Rotation(App.Vector(1, 0, 0), 90.0)

    tunic_torso_y_mid = None

    def target_relative_piece_placement(side, outline):
        projected_target_ys = [
            float(vertex[1])
            for vertex in target_surface.vertices
            if abs(float(vertex[0]) - x_mid) <= torso_half_width
            and _projected_point_within_outline_margin(
                float(vertex[0]) - panel_origin_x,
                float(vertex[2]) - hem_z,
                outline,
                clearance,
            )
        ]
        if not projected_target_ys:
            raise RuntimeError("canonical tunic torso silhouette does not overlap DrapeTarget projections")
        target_front_y = min(projected_target_ys)
        target_back_y = max(projected_target_ys)
        nonlocal tunic_torso_y_mid
        tunic_torso_y_mid = 0.5 * (target_front_y + target_back_y)
        # The placement Y origin is already the solver mesh world-space panel plane
        # because this fixture fixes StartHeight to zero before computing placement.
        mesh_normal_offset = float(getattr(scene, "StartHeight", 0.0))
        if side == "front":
            y = target_front_y - clearance + mesh_normal_offset
        elif side == "back":
            y = target_back_y + clearance + mesh_normal_offset
        else:
            raise ValueError("tunic target-relative side must be front or back")
        log(
            "tunic-placement-depth side=%s projected-target-y=[%.2f, %.2f] "
            "panel-y=%.2f transformed-panel-y=%.2f mesh-normal-offset-mm=%.2f "
            "clearance-mm=%.2f torso-x=[%.2f, %.2f] projected-vertices=%d"
            % (
                side, target_front_y, target_back_y, y, y - mesh_normal_offset,
                mesh_normal_offset, clearance,
                x_mid - torso_half_width, x_mid + torso_half_width, len(projected_target_ys),
            )
        )
        return App.Placement(App.Vector(panel_origin_x, y, hem_z), rot)

    def make_piece(name, side, neckline_ratio, neckline_drop):
        sketch, outline = _make_tunic_sketch(
            doc,
            name + "Source",
            panel_width,
            garment_height,
            hem_width,
            neckline_ratio,
            neckline_drop,
            shoulder_height=authored_shoulder_height,
            neckline_height=authored_neckline_height,
            armhole_height=armhole_height,
        )
        doc.recompute()
        piece = _adopt_sketch(sketch, name, 10.0, 0.0)
        piece.Label = name
        piece.Placement = target_relative_piece_placement(side, outline)
        piece.Sketch.Placement = piece.Placement
        return piece, outline

    # Match the sewn shoulder endpoints on both panels. Front/back neckline shape may diverge at the center,
    # but this planar fixture represents the shared shoulder-to-neck join with identical authored coordinates.
    front, front_outline = make_piece("VisualTunicFront", "front", 0.61, 0.10)
    back, back_outline = make_piece("VisualTunicBack", "back", 0.61, 0.10)
    capture_tunic_pattern_view(doc, front, back, hem_width)
    # Resolve sewn edges by native semantic IDs; PatternIR boundary order is independent
    # of Sketcher insertion order. The mesher normalizes the front/back boundary traversal,
    # so preserve B's order for side and shoulder correspondences alike.
    front_edge_ids = tuple(str(value) for value in getattr(front.Sketch, "SemanticEdgeIds", ()) or ())
    back_edge_ids = tuple(str(value) for value in getattr(back.Sketch, "SemanticEdgeIds", ()) or ())
    if len(front_edge_ids) < 9 or len(back_edge_ids) < 9:
        raise RuntimeError("canonical tunic sketches have no complete semantic edge map")
    required_indices = (1, 3, 6, 8)
    if any(not front_edge_ids[index] or not back_edge_ids[index] for index in required_indices):
        raise RuntimeError("canonical tunic fixture is missing authored semantic edge IDs")

    # Exercise the generic Sketcher -> PatternIR -> sampled-boundary adapter too:
    # an armhole must remain a curved, concave open edge when the solver mesh is built.
    from freecad_cloth.simulation.PatternSimulationAdapter import resolve_piece_ir

    for piece, edge_ids in ((front, front_edge_ids), (back, back_edge_ids)):
        piece_ir = resolve_piece_ir(piece)
        boundary_by_id = {str(boundary.id): boundary for boundary in piece_ir.boundaries}
        for edge_index, inward in ((2, -1.0), (7, 1.0)):
            boundary = boundary_by_id.get(edge_ids[edge_index])
            if boundary is None or boundary.kind != "arc" or len(boundary.samples) < 8:
                raise RuntimeError(
                    "canonical garment armhole was not preserved as a sampled native curve: "
                    "piece=%s edge=%s" % (piece.Name, edge_ids[edge_index])
                )
            start_point = boundary.samples[0]
            end_point = boundary.samples[-1]
            vertical_span = float(end_point[1]) - float(start_point[1])
            if abs(vertical_span) <= 1e-9:
                raise RuntimeError(
                    "canonical garment armhole endpoints do not define a vertical chord: "
                    "piece=%s edge=%s" % (piece.Name, edge_ids[edge_index])
                )
            scoop_depth = max(
                inward
                * (
                    float(sample[0])
                    - (
                        float(start_point[0])
                        + (float(sample[1]) - float(start_point[1]))
                        / vertical_span
                        * (float(end_point[0]) - float(start_point[0]))
                    )
                )
                for sample in boundary.samples[1:-1]
            )
            if scoop_depth <= 0.02 * float(panel_width):
                raise RuntimeError(
                    "canonical garment armhole curve has insufficient inward clearance: "
                    "piece=%s edge=%s scoop-mm=%.2f"
                    % (piece.Name, edge_ids[edge_index], scoop_depth)
                )
    seam_specs = (
        (front_edge_ids[1], back_edge_ids[1], "TunicRightSide", False),
        (front_edge_ids[3], back_edge_ids[3], "TunicRightShoulder", False),
        (front_edge_ids[6], back_edge_ids[6], "TunicLeftShoulder", False),
        (front_edge_ids[8], back_edge_ids[8], "TunicLeftSide", False),
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
    capture_tunic_sewing_view(doc, front, back, hem_width, seam_records)
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
    # Initial seam gaps diagnose whether the solver stitches pair the pinned particles
    # with their actual counterparts. Shoulder corners, neckline corners, and
    # each neckline center are independently anchored so the top contour cannot
    # collapse while still allowing the lower panels to drape.
    scene.AvatarAttachmentAnchors = [
        "%s|%s|shoulder_right" % (front.PieceId, front_edge_ids[3]),
        "%s|%s|neck_right" % (front.PieceId, front_edge_ids[3]),
        "%s|%s|shoulder_left" % (front.PieceId, front_edge_ids[6]),
        "%s|%s|neck_left" % (front.PieceId, front_edge_ids[6]),
        # The center landmark is the endpoint of the left neckline half-edge.
        # Using the right half-edge can resolve to its outer endpoint after surface fitting.
        "%s|%s|neck_center" % (front.PieceId, front_edge_ids[5]),
        "%s|%s|shoulder_right" % (back.PieceId, back_edge_ids[3]),
        "%s|%s|neck_right" % (back.PieceId, back_edge_ids[3]),
        "%s|%s|shoulder_left" % (back.PieceId, back_edge_ids[6]),
        "%s|%s|neck_left" % (back.PieceId, back_edge_ids[6]),
        "%s|%s|neck_center" % (back.PieceId, back_edge_ids[5]),
    ]
    # Start the diagnostic cloth on an offset target surface instead of two
    # parallel planes whose matching side seams are about 238 mm apart.
    # Source Sketcher geometry and PatternIR topology are not modified.
    import Mesh
    from freecad_cloth.simulation import SimulationObjects as simulation_objects
    from freecad_cloth.simulation.ClothAttachments import _nearest_surface_point
    from freecad_cloth.simulation.DrapeVisualSanity import points_inside_closed_mesh
    from scipy.spatial import cKDTree

    from freecad_cloth.simulation.SimulationMeshQuality import quality_piece_mesh

    # Keep the fixture mesh topology identical to the production quality mesh.
    # The custom builder maps its sewn vertices onto the target, but it must not
    # silently fall back to the coarse two-vertex boundary chains from _piece_mesh.
    def original_piece_mesh(piece, start_height, piece_ir=None):
        return quality_piece_mesh(
            piece,
            start_height,
            float(scene.ParticleDistance),
            piece_ir=piece_ir,
        )

    native_avatar_mesh = Mesh.Mesh()
    native_avatar_mesh.addFacets(
        [
            (target_surface.vertices[a], target_surface.vertices[b], target_surface.vertices[c])
            for a, b, c in target_surface.triangles
        ]
    )
    native_avatar_facets = tuple(native_avatar_mesh.Facets)
    target_vertex_tree = cKDTree(target_surface.vertices)
    if len(native_avatar_facets) != len(target_surface.triangles):
        raise RuntimeError("tunic initialization lost DrapeTarget facet correspondence")
    fit_radius = 3.0 * float(scene.ParticleDistance)
    outward_offset = float(clearance) + 3.0
    fit_zs = tuple(float(vertex[2]) for vertex in target_surface.vertices)
    target_fit_center = (
        float(x_mid),
        float(tunic_torso_y_mid),
        0.5 * (min(fit_zs) + max(fit_zs)),
    )
    seam_fit_cache = {}
    ray_hit_cache = {}
    fit_counts = {
        "seam-surface": 0,
        "seam-outside": 0,
        "panel-surface": 0,
        "panel-fallback": 0,
        "clearance-correction": 0,
        "inside-correction": 0,
    }

    from freecad_cloth.simulation.PositionBasedDynamicsBackend import (
        _pbd_collision_effective_tolerance_mm,
    )
    # Use the solver's existing SDF tolerance as a small initialization-only
    # clearance buffer on free panel vertices. Sewn vertices keep their shared
    # base offset so seam correspondence and the configured 23.80 mm gate do not
    # change; the collision solver, voxel size, and all acceptance limits remain
    # exactly as configured.
    panel_collision_buffer_mm = float(
        _pbd_collision_effective_tolerance_mm(target_surface)
    )
    if not math.isfinite(panel_collision_buffer_mm) or panel_collision_buffer_mm < 0.0:
        raise RuntimeError("tunic collision clearance buffer must be finite and non-negative")
    log(
        "tunic-panel-collision-buffer-mm=%.2f base-offset-mm=%.2f"
        % (panel_collision_buffer_mm, outward_offset)
    )

    def _fit_surface_point(point, triangle_index, extra_offset_mm=0.0):
        facet_normal = native_avatar_facets[int(triangle_index)].Normal
        try:
            normal = _as_coordinates3(facet_normal, "DrapeTarget facet normal")
        except ValueError as exc:
            raise RuntimeError(
                "tunic initialization received an invalid DrapeTarget facet normal"
            ) from exc
        length = sum(value * value for value in normal) ** 0.5
        if length <= 1e-12:
            raise RuntimeError("tunic initialization found a degenerate DrapeTarget facet")
        normal = tuple(value / length for value in normal)
        radial = tuple(float(point[i]) - target_fit_center[i] for i in range(3))
        if sum(normal[i] * radial[i] for i in range(3)) < 0.0:
            normal = tuple(-value for value in normal)
        offset = float(outward_offset) + float(extra_offset_mm)
        if not math.isfinite(offset) or offset < float(outward_offset):
            raise RuntimeError("tunic surface-fit offset must be finite and no smaller than the base offset")
        return tuple(float(point[i]) + offset * normal[i] for i in range(3))

    def _seam_surface_vertex(x, z):
        key = (round(float(x), 4), round(float(z), 4))
        if key not in seam_fit_cache:
            distance, triangle_index, closest = _nearest_surface_point(
                (float(x), float(tunic_torso_y_mid), float(z)),
                target_surface.vertices,
                target_surface.triangles,
            )
            if float(distance) <= fit_radius:
                seam_fit_cache[key] = _fit_surface_point(closest, triangle_index)
                fit_counts["seam-surface"] += 1
            else:
                # Keep garment ease where the silhouette is well outside the avatar,
                # while putting corresponding front/back seam vertices at one point.
                seam_fit_cache[key] = (float(x), float(tunic_torso_y_mid), float(z))
                fit_counts["seam-outside"] += 1
        return seam_fit_cache[key]

    def _ray_surface_hit(x, z, direction):
        key = (round(float(x), 4), round(float(z), 4), int(direction))
        if key not in ray_hit_cache:
            origin = App.Vector(float(x), float(tunic_torso_y_mid), float(z))
            vector = App.Vector(0.0, float(direction), 0.0)
            raw_hits = native_avatar_mesh.nearestFacetOnRay(origin, vector)
            candidates = []
            for raw_index, hit in raw_hits.items():
                triangle_index = int(raw_index)
                point = _as_coordinates3(hit, "Mesh ray intersection")
                delta_y = point[1] - float(tunic_torso_y_mid)
                if direction < 0 and delta_y > 1e-6:
                    continue
                if direction > 0 and delta_y < -1e-6:
                    continue
                candidates.append((abs(delta_y), triangle_index, point))
            ray_hit_cache[key] = (
                min(candidates, key=lambda item: (item[0], item[1]))[1:]
                if candidates else None
            )
        return ray_hit_cache[key]

    def tunic_initial_surface_mesh(piece, start_height, piece_ir=None):
        vertices, triangles, boundary_edges = original_piece_mesh(
            piece, start_height, piece_ir=piece_ir
        )
        if piece_ir is None or str(getattr(piece, "PieceId", "")) not in {
            str(front.PieceId), str(back.PieceId)
        }:
            return vertices, triangles, boundary_edges
        piece_id = str(piece.PieceId)
        if abs(float(start_height)) > 1e-9:
            raise RuntimeError(
                "canonical tunic fixture requires StartHeight=0 before target-relative placement"
            )
        is_front = piece_id == str(front.PieceId)
        if tunic_torso_y_mid is None:
            raise RuntimeError("canonical tunic placement did not establish a torso depth reference")
        # StartHeight is zero, so the authored placement Y is already the solver
        # world-space side. Fail closed if anchor-selection coordinates cross the
        # mannequin's torso midplane.
        normal_offset_y = -float(start_height)
        selection_y_values = tuple(
            float(vertex[1]) + normal_offset_y for vertex in vertices
        )
        selection_depths = tuple(
            value - float(tunic_torso_y_mid) for value in selection_y_values
        )
        if (
            (is_front and max(selection_depths) >= -1e-6)
            or (not is_front and min(selection_depths) <= 1e-6)
        ):
            raise RuntimeError(
                "canonical tunic panel selection depth is on the wrong side of the mannequin center plane: "
                "piece=%s relative-y=[%.2f, %.2f]"
                % (piece_id, min(selection_depths), max(selection_depths))
            )
        log(
            "tunic-anchor-selection-depth piece=%s selection-y=[%.2f, %.2f] torso-mid-relative-y=[%.2f, %.2f] normal-offset-y=%.2f"
            % (
                piece_id,
                min(selection_y_values),
                max(selection_y_values),
                min(selection_depths),
                max(selection_depths),
                normal_offset_y,
            )
        )
        selection_vertices = tuple(
            (
                float(vertex[0]),
                float(vertex[1]) + normal_offset_y,
                float(vertex[2]),
            )
            for vertex in vertices
        )
        # Use the actual seam objects that feed SimulationProxy rather than a
        # second, index-based reconstruction of which semantic boundaries are sewn.
        sewn_ids = set()
        for seam_obj, piece_a, piece_b in seam_records:
            if str(piece_a.PieceId) == piece_id:
                sewn_ids.add(str(getattr(seam_obj, "EdgeAId", "")).strip())
            if str(piece_b.PieceId) == piece_id:
                sewn_ids.add(str(getattr(seam_obj, "EdgeBId", "")).strip())
        chain_by_id = {
            str(boundary.id): tuple(int(index) for index in chain)
            for boundary, chain in zip(piece_ir.boundaries, boundary_edges, strict=False)
        }
        missing_sewn_ids = sorted(sewn_ids - set(chain_by_id))
        if missing_sewn_ids:
            raise RuntimeError(
                "canonical tunic sewn semantic edges are missing from the simulation mesh "
                "for %s: %s (mesh edges=%s)"
                % (piece_id, missing_sewn_ids, sorted(chain_by_id))
            )
        chain_sizes = {edge_id: len(chain_by_id[edge_id]) for edge_id in sorted(sewn_ids)}
        if piece_id in {str(front.PieceId), str(back.PieceId)}:
            for boundary_ir in piece_ir.boundaries:
                edge_id = str(boundary_ir.id)
                if edge_id in {
                    str(front_edge_ids[3]), str(front_edge_ids[4]), str(front_edge_ids[5]),
                    str(front_edge_ids[6]), str(back_edge_ids[3]), str(back_edge_ids[4]),
                    str(back_edge_ids[5]), str(back_edge_ids[6]),
                }:
                    chain = chain_by_id[edge_id]
                    log(
                        "tunic-debug-boundary piece=%s edge=%s count=%d vertices=%s"
                        % (
                            piece_id,
                            edge_id,
                            len(chain),
                            tuple(
                                (
                                    int(vertex_index),
                                    tuple(round(float(component), 2) for component in vertices[int(vertex_index)]),
                                )
                                for vertex_index in chain
                            ),
                        )
                    )
        sewn_vertices = {
            vertex_index
            for edge_id in sewn_ids
            for vertex_index in chain_by_id[edge_id]
        }
        # Sewn vertices keep the base offset to preserve shared seam positions.
        # Unsewn vertices retain the extra collision-tolerance margin throughout
        # every local clearance/containment repair below.
        required_vertex_offsets = tuple(
            float(outward_offset)
            if index in sewn_vertices
            else float(outward_offset) + panel_collision_buffer_mm
            for index in range(len(vertices))
        )
        log(
            "tunic-sewn-vertex-selection piece=%s ids=%s chain-sizes=%s vertices=%d"
            % (piece_id, sorted(sewn_ids), chain_sizes, len(sewn_vertices))
        )
        direction = -1 if is_front else 1
        mapped = []
        for index, raw in enumerate(vertices):
            x, y, z = (float(value) for value in raw)
            if index in sewn_vertices:
                point = _seam_surface_vertex(x, z)
            else:
                hit = _ray_surface_hit(x, z, direction)
                if hit is None:
                    fit_counts["panel-fallback"] += 1
                    point = (x, y, z)
                else:
                    triangle_index, surface_point = hit
                    point = _fit_surface_point(
                        surface_point,
                        triangle_index,
                        extra_offset_mm=panel_collision_buffer_mm,
                    )
                    fit_counts["panel-surface"] += 1
            mapped.append(tuple(float(value) for value in point))
        # Enforce the configured vertex clearance with a local closest-point
        # direction. A global-center test can orient a facet normal inward near
        # concavities even when ray parity classifies the point as outside.
        clearance_inside_flags = _inside_target_states(
            tuple(mapped), avatar, target_surface
        )
        log(
            "tunic-initial-clearance-direction inside=%d points=%d"
            % (sum(1 for inside in clearance_inside_flags if inside), len(mapped))
        )
        for index, raw_point in enumerate(mapped):
            point = tuple(float(value) for value in raw_point)
            required_offset = required_vertex_offsets[index]
            distance, _target_vertex_index = target_vertex_tree.query(
                point, k=1, eps=0.0, workers=1
            )
            if float(distance) >= required_offset - 1e-6:
                continue
            fit_counts["clearance-correction"] += 1
            corrected = point
            inside = bool(clearance_inside_flags[index])
            for _attempt in range(3):
                distance, _target_vertex_index = target_vertex_tree.query(
                    corrected, k=1, eps=0.0, workers=1
                )
                if float(distance) >= required_offset - 1e-3:
                    break
                _surface_distance, triangle_index, closest = _nearest_surface_point(
                    corrected,
                    target_surface.vertices,
                    target_surface.triangles,
                )
                correction_vector = tuple(
                    (
                        float(closest[axis]) - float(corrected[axis])
                        if inside
                        else float(corrected[axis]) - float(closest[axis])
                    )
                    for axis in range(3)
                )
                correction_length = sum(
                    value * value for value in correction_vector
                ) ** 0.5
                if correction_length <= 1e-9:
                    corrected = _fit_surface_point(
                        closest,
                        triangle_index,
                        extra_offset_mm=required_offset - outward_offset,
                    )
                else:
                    corrected = tuple(
                        float(closest[axis])
                        + required_offset * correction_vector[axis] / correction_length
                        for axis in range(3)
                    )
                # Reclassify only the rare point that needed another pass, since
                # its first local offset may already have moved it to the outside.
                if _attempt < 2:
                    inside = _inside_target_states(
                        (corrected,), avatar, target_surface
                    )[0]
            mapped[index] = tuple(float(value) for value in corrected)
        # Compare the fast ray-parity predicate with the exact containment path
        # used by the final penetration audit. A triangulated concave avatar must
        # not be classified by a fixture-only approximation if native/watertight
        # containment is available.
        parity_flags = points_inside_closed_mesh(
            tuple(mapped),
            target_surface.vertices,
            target_surface.triangles,
        )
        inside_flags = _inside_target_states(tuple(mapped), avatar, target_surface)
        classifier_mismatches = sum(
            1 for parity, authoritative in zip(parity_flags, inside_flags, strict=True)
            if parity != authoritative
        )
        log(
            "tunic-initial-inside-classifiers authoritative=%d parity=%d mismatches=%d points=%d"
            % (
                sum(1 for inside in inside_flags if inside),
                sum(1 for inside in parity_flags if inside),
                classifier_mismatches,
                len(mapped),
            )
        )
        for _attempt in range(3):
            inside_indices = [index for index, inside in enumerate(inside_flags) if inside]
            log(
                "tunic-initial-inside-correction attempt=%d interior=%d"
                % (_attempt + 1, len(inside_indices))
            )
            if not inside_indices:
                break
            for index in inside_indices:
                required_offset = required_vertex_offsets[index]
                _surface_distance, triangle_index, closest = _nearest_surface_point(
                    mapped[index],
                    target_surface.vertices,
                    target_surface.triangles,
                )
                # For a genuinely interior point, the shortest vector to the
                # closed boundary points from the interior toward the exterior.
                # A global-center dot product can reverse the normal at concave
                # anatomy (e.g. underarms); use this local exit direction instead.
                correction_vector = tuple(
                    float(closest[axis]) - float(mapped[index][axis])
                    for axis in range(3)
                )
                correction_length = sum(
                    value * value for value in correction_vector
                ) ** 0.5
                if correction_length <= 1e-9:
                    # Degenerate on-surface classification: use the same fitted
                    # outward facet as a last resort and let containment verify it.
                    corrected = _fit_surface_point(
                        closest,
                        triangle_index,
                        extra_offset_mm=required_offset - outward_offset,
                    )
                else:
                    corrected = tuple(
                        float(closest[axis])
                        + required_offset * correction_vector[axis] / correction_length
                        for axis in range(3)
                    )
                mapped[index] = tuple(float(value) for value in corrected)
                fit_counts["inside-correction"] += 1
            inside_flags = _inside_target_states(tuple(mapped), avatar, target_surface)
        # The final inside correction follows the nearest triangle exit vector,
        # but a neighboring shoulder/arm surface can still leave the point closer
        # than the authoritative nearest-target-vertex margin. Repair that metric
        # directly, and re-check containment after each bounded pass.
        for _clearance_attempt in range(5):
            repair_inside_flags = _inside_target_states(
                tuple(mapped), avatar, target_surface
            )
            repair_distances, repair_target_indices = target_vertex_tree.query(
                tuple(mapped), k=1, eps=0.0, workers=1
            )
            repair_indices = [
                index
                for index, (inside, distance) in enumerate(
                    zip(repair_inside_flags, repair_distances, strict=True)
                )
                if inside or float(distance) < required_vertex_offsets[index] - 1e-3
            ]
            log(
                "tunic-initial-clearance-repair attempt=%d inside=%d below-offset=%d"
                % (
                    _clearance_attempt + 1,
                    sum(1 for inside in repair_inside_flags if inside),
                    sum(
                        1 for index, distance in enumerate(repair_distances)
                        if float(distance) < required_vertex_offsets[index] - 1e-3
                    ),
                )
            )
            if not repair_indices:
                break
            for index in repair_indices:
                point = tuple(float(value) for value in mapped[index])
                required_offset = required_vertex_offsets[index]
                target_vertex_index = int(repair_target_indices[index])
                target_vertex = tuple(
                    float(value)
                    for value in target_surface.vertices[target_vertex_index]
                )
                if repair_inside_flags[index]:
                    correction_vector = tuple(
                        target_vertex[axis] - point[axis] for axis in range(3)
                    )
                else:
                    correction_vector = tuple(
                        point[axis] - target_vertex[axis] for axis in range(3)
                    )
                correction_length = sum(
                    value * value for value in correction_vector
                ) ** 0.5
                if correction_length <= 1e-9:
                    _surface_distance, triangle_index, closest = _nearest_surface_point(
                        point,
                        target_surface.vertices,
                        target_surface.triangles,
                    )
                    correction_vector = tuple(
                        (
                            float(closest[axis]) - point[axis]
                            if repair_inside_flags[index]
                            else point[axis] - float(closest[axis])
                        )
                        for axis in range(3)
                    )
                    correction_length = sum(
                        value * value for value in correction_vector
                    ) ** 0.5
                    if correction_length <= 1e-9:
                        corrected = _fit_surface_point(
                            closest,
                            triangle_index,
                            extra_offset_mm=required_offset - outward_offset,
                        )
                    else:
                        corrected = tuple(
                            float(closest[axis])
                            + required_offset * correction_vector[axis] / correction_length
                            for axis in range(3)
                        )
                else:
                    corrected = tuple(
                        target_vertex[axis]
                        + required_offset * correction_vector[axis] / correction_length
                        for axis in range(3)
                    )
                mapped[index] = tuple(float(value) for value in corrected)
                fit_counts["clearance-correction"] += 1
        remaining_inside = _inside_target_states(tuple(mapped), avatar, target_surface)
        remaining_indices = [
            index for index, inside in enumerate(remaining_inside) if inside
        ]
        if remaining_indices:
            residual_sample = tuple(
                (
                    int(index),
                    tuple(round(float(value), 2) for value in mapped[index]),
                )
                for index in remaining_indices[:12]
            )
            log("tunic-initial-inside-residual sample=%s" % (residual_sample,))
            raise RuntimeError(
                "canonical tunic surface mapping leaves %d cloth vertices inside the mannequin target"
                % len(remaining_indices)
            )
        final_distances, final_target_indices = target_vertex_tree.query(
            tuple(mapped), k=1, eps=0.0, workers=1
        )
        minimum_vertex_clearance = min(float(value) for value in final_distances)
        log(
            "tunic-initial-min-vertex-clearance-mm=%.2f required-offset-mm=%.2f points=%d"
            % (minimum_vertex_clearance, outward_offset, len(mapped))
        )
        clearance_residuals = [
            index for index, distance in enumerate(final_distances)
            if float(distance) < required_vertex_offsets[index] - 1e-3
        ]
        if clearance_residuals:
            residual_sample = tuple(
                (
                    int(index),
                    round(float(final_distances[index]), 2),
                    int(final_target_indices[index]),
                    tuple(round(float(value), 2) for value in mapped[index]),
                )
                for index in clearance_residuals[:12]
            )
            log("tunic-initial-clearance-residual sample=%s" % (residual_sample,))
            raise RuntimeError(
                "canonical tunic surface mapping leaves %d cloth vertices below configured outward offset: "
                "%.2f mm < %.2f mm"
                % (len(clearance_residuals), minimum_vertex_clearance, outward_offset)
            )
        return tuple(mapped), triangles, boundary_edges, selection_vertices

    # Refreshing DrapeTarget only rebuilds collision metadata; it does not
    # rebuild cloth particles. Build the simulation scene explicitly with this
    # fixture-specific surface mesh so the seam/skin mapping is actually applied.
    scene_proxy = scene.Proxy
    # Inject the fixture-only mapped mesh through the underlying builder while
    # preserving the wrapper's authoritative source signature. Otherwise the
    # next document recompute sees a signature mismatch and rebuilds an unmapped
    # production scene over the just-mapped particles.
    scene_signature = scene_proxy._signature(scene)
    scene_proxy._build(
        scene,
        signature=scene_signature,
        piece_mesh=tunic_initial_surface_mesh,
    )
    base_proxy_getter = getattr(scene_proxy, "_base_or_restore", None)
    sync_seam_provenance = getattr(scene_proxy, "_sync_seam_stitch_provenance", None)
    if not callable(base_proxy_getter) or not callable(sync_seam_provenance):
        raise RuntimeError("canonical tunic fixture cannot synchronize authoritative seam provenance")
    sync_seam_provenance(base_proxy_getter())
    doc.recompute()
    if not any(fit_counts.values()):
        raise RuntimeError(
            "canonical tunic surface-mapped mesh builder was not used: %s" % fit_counts
        )
    log("tunic-initial-surface-map=%s fit-radius-mm=%.1f offset-mm=%.2f" % (
        fit_counts, fit_radius, outward_offset
    ))
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
    for descriptor, projection in zip(
        tuple(str(value) for value in (getattr(scene, "AvatarAttachmentAnchors", ()) or ())),
        projections,
        strict=False,
    ):
        log(
            "tunic-anchor-projection descriptor=%s particle=%d source=%s particle-before=%s "
            "surface=%s anchor=%s triangle=%d source-distance=%.2f"
            % (
                descriptor,
                int(projection.particle_index),
                tuple(round(float(value), 2) for value in projection.source_position),
                tuple(round(float(value), 2) for value in projection.particle_position),
                tuple(round(float(value), 2) for value in projection.surface_point),
                tuple(round(float(value), 2) for value in projection.anchor_position),
                int(projection.triangle_index),
                float(projection.source_distance_mm),
            )
        )
    # Trace the exact solver stitch correspondence before stepping. Pinned-particle
    # flags show whether the avatar anchors are members of stitched samples; XYZ
    # deltas distinguish incorrect edge pairing from later solver dynamics.
    initial_solver_positions = tuple(backend.positions())
    pinned_indices = set(solver_pins)
    from freecad_cloth.simulation.SimulationObjects import seam_gap_diagnostics
    initial_seam_reports = seam_gap_diagnostics(
        initial_solver_positions,
        getattr(proxy, "seam_stitch_pairs", {}),
    )
    initial_max_seam_gap = max(
        float(report["max_gap"]) for report in initial_seam_reports.values()
    )
    for seam_id, report in sorted(initial_seam_reports.items()):
        log(
            "tunic-seam-initial-report id=%s pairs=%d first=%.2f last=%.2f max=%.2f"
            % (
                seam_id,
                int(report["pair_count"]),
                float(report["first_gap"]),
                float(report["last_gap"]),
                float(report["max_gap"]),
            )
        )
    log("tunic-seam-initial-max-gap-mm=%.2f" % initial_max_seam_gap)
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
    if initial_max_seam_gap > 35.0:
        raise RuntimeError(
            "canonical tunic initial seam span exceeds the 35 mm convergence gate: "
            "%.2f mm" % initial_max_seam_gap
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
    log("pin-mode=Avatar Attachment semantic-anchor-pins=%s offset-mm=%.2f" % (solver_pins, float(scene.AttachmentOffset)))
    for projection in projections:
        log(
            "tunic-anchor-projection particle=%d distance-mm=%.2f surface=%s anchor=%s"
            % (
                int(projection.particle_index),
                float(projection.source_distance_mm),
                tuple(round(float(value), 3) for value in projection.surface_point),
                tuple(round(float(value), 3) for value in projection.anchor_position),
            )
        )
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

    # Check the whole authored neckline support, not just the single highest
    # pinned vertex (which previously allowed a skirt-like drape to pass).
    neckline_support = []
    neckline_min_z = float(neck_point.z) - 80.0
    for descriptor, projection in zip(
        tuple(str(value) for value in scene.AvatarAttachmentAnchors),
        tuple(projections),
        strict=True,
    ):
        landmark_name = descriptor.rsplit("|", 1)[-1]
        if landmark_name not in {"neck_left", "neck_right", "neck_center"}:
            continue
        particle_index = int(projection.particle_index)
        point = tuple(float(value) for value in final_positions[particle_index])
        anchor = tuple(float(value) for value in projection.anchor_position)
        drift = sum((point[axis] - anchor[axis]) ** 2 for axis in range(3)) ** 0.5
        log(
            "tunic-neckline-support landmark=%s particle=%d z=%.2f minimum-z=%.2f drift-mm=%.4f"
            % (landmark_name, particle_index, point[2], neckline_min_z, drift)
        )
        if drift > 1e-3:
            raise RuntimeError(
                "tunic neckline support drifted away from its named avatar surface anchor: "
                "%s (%.3f mm)" % (landmark_name, drift)
            )
        if point[2] < neckline_min_z:
            raise RuntimeError(
                "tunic neckline fell below the neck/shoulder band: "
                "%s z=%.2f mm < required %.2f mm" % (landmark_name, point[2], neckline_min_z)
            )
        neckline_support.append((descriptor, particle_index, point[2]))
    if len(neckline_support) != 6:
        raise RuntimeError(
            "tunic needs six independently supported neckline endpoints/centers, got %d"
            % len(neckline_support)
        )
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
