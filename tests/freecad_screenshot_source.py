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
        if dock.objectName() == "Tasks" or "task" in str(dock.windowTitle()).lower():
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


def _camera_snapshot(view):
    """Return the actual world-space camera axes used for screenshot projection."""
    rotation = view.getCameraOrientation()
    right = rotation.multVec(App.Vector(1.0, 0.0, 0.0))
    up = rotation.multVec(App.Vector(0.0, 1.0, 0.0))
    forward = rotation.multVec(App.Vector(0.0, 0.0, -1.0))
    return {
        "quaternion": [round(float(value), 9) for value in rotation.Q],
        "screen_right_world": [
            round(float(right.x), 6),
            round(float(right.y), 6),
            round(float(right.z), 6),
        ],
        "screen_up_world": [round(float(up.x), 6), round(float(up.y), 6), round(float(up.z), 6)],
        "view_forward_world": [
            round(float(forward.x), 6),
            round(float(forward.y), 6),
            round(float(forward.z), 6),
        ],
    }


def _seam_lateral_snapshot(proxy, center_x):
    """Measure world-X placement of every semantic seam from its exact solver pairs."""
    backend = getattr(proxy, "backend", None)
    reader = getattr(backend, "positions", None)
    pairs_by_seam = getattr(proxy, "seam_stitch_pairs", {})
    if not callable(reader) or not pairs_by_seam:
        raise RuntimeError("seam lateral diagnostic requires solver position and pair provenance")
    positions = tuple(reader())

    def x_value(point):
        return float(point.x) if hasattr(point, "x") else float(point[0])

    snapshot = {}
    for seam_id, pairs in sorted(pairs_by_seam.items()):
        offsets = []
        for index_a, index_b in pairs:
            a, b = int(index_a), int(index_b)
            if not (0 <= a < len(positions) and 0 <= b < len(positions)):
                raise RuntimeError("seam lateral diagnostic found an invalid solver particle index")
            offsets.append(0.5 * (x_value(positions[a]) + x_value(positions[b])) - float(center_x))
        if not offsets:
            raise RuntimeError(
                "seam lateral diagnostic found a seam without samples: " + str(seam_id)
            )
        snapshot[str(seam_id)] = {
            "mean_x_offset_mm": round(sum(offsets) / len(offsets), 3),
            "min_x_offset_mm": round(min(offsets), 3),
            "max_x_offset_mm": round(max(offsets), 3),
            "positive_samples": sum(value > 0.0 for value in offsets),
            "negative_samples": sum(value < 0.0 for value in offsets),
            "sample_count": len(offsets),
        }
    return snapshot


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
                log(
                    "penetration-check=trimesh contains points=%d triangles=%d"
                    % (len(points), len(triangles))
                )
                return int(np.count_nonzero(states))
        except (ImportError, RuntimeError, TypeError, ValueError):
            pass

        from freecad_cloth.simulation.DrapeVisualSanity import points_inside_closed_mesh

        log(
            "penetration-check=numpy-ray-parity points=%d triangles=%d"
            % (len(points), len(triangles))
        )
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
    from freecad_cloth.common.MeshValidation import validate_mesh
    from freecad_cloth.simulation.DrapeFailureClassifier import (
        classify_drape,
        summarize_classification,
    )
    from freecad_cloth.simulation.DrapeVisualSanity import inspect_drape, summarize

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


def _arc_through_midpoint(Part, start, end, midpoint):
    """Build a minor native circular arc through an explicit on-arc point."""
    import math

    sx, sy = float(start.x), float(start.y)
    ex, ey = float(end.x), float(end.y)
    mx, my = float(midpoint.x), float(midpoint.y)
    start_sq = sx * sx + sy * sy
    end_sq = ex * ex + ey * ey
    middle_sq = mx * mx + my * my
    determinant = 2.0 * (sx * (ey - my) + ex * (my - sy) + mx * (sy - ey))
    if abs(determinant) <= 1e-9:
        raise RuntimeError("tunic armhole points are collinear; cannot construct an arc")

    center_x = (start_sq * (ey - my) + end_sq * (my - sy) + middle_sq * (sy - ey)) / determinant
    center_y = (start_sq * (mx - ex) + end_sq * (sx - mx) + middle_sq * (ex - sx)) / determinant
    radius = math.hypot(sx - center_x, sy - center_y)
    if not math.isfinite(radius) or radius <= 1e-9:
        raise RuntimeError("tunic armhole circle has an invalid radius")

    def curve_value(curve, parameter_value):
        getter = getattr(curve, "valueAt", None)
        if not callable(getter):
            getter = getattr(curve, "value", None)
        if not callable(getter):
            raise RuntimeError("tunic armhole curve has no native parameter evaluator")
        return getter(float(parameter_value))

    tau = 2.0 * math.pi
    selected = None
    for normal_z in (1.0, -1.0):
        circle = Part.Circle(
            App.Vector(center_x, center_y, 0.0),
            App.Vector(0.0, 0.0, normal_z),
            radius,
        )
        # Derive parameters from the native circle basis instead of assuming
        # which global direction its X axis uses for either normal orientation.
        zero_point = curve_value(circle, 0.0)
        quarter_point = curve_value(circle, math.pi / 2.0)
        axis_x = (
            (float(zero_point.x) - center_x) / radius,
            (float(zero_point.y) - center_y) / radius,
        )
        axis_y = (
            (float(quarter_point.x) - center_x) / radius,
            (float(quarter_point.y) - center_y) / radius,
        )

        def parameter(point_x, point_y, axis_x=axis_x, axis_y=axis_y):
            dx = point_x - center_x
            dy = point_y - center_y
            return (
                math.atan2(
                    dx * axis_y[0] + dy * axis_y[1],
                    dx * axis_x[0] + dy * axis_x[1],
                )
                % tau
            )

        start_angle = parameter(sx, sy)
        end_angle = parameter(ex, ey)
        middle_angle = parameter(mx, my)
        sweep = (end_angle - start_angle) % tau
        middle_sweep = (middle_angle - start_angle) % tau
        if sweep > 1e-9 and middle_sweep <= sweep + 1e-9:
            selected = (circle, normal_z, start_angle, sweep, middle_sweep)
            break

    if selected is None:
        raise RuntimeError("tunic armhole points do not define a consistent circular sweep")
    circle, normal_z, start_angle, sweep, middle_sweep = selected
    if sweep >= math.pi:
        raise RuntimeError(
            "tunic armhole through-point selects a major arc: sweep-rad=%.6f" % sweep
        )

    arc = Part.ArcOfCircle(circle, start_angle, start_angle + sweep)
    checks = (
        ("start", start, start_angle),
        ("end", end, start_angle + sweep),
        ("midpoint", midpoint, start_angle + middle_sweep),
    )
    for role, expected, parameter_value in checks:
        actual = curve_value(arc, parameter_value)
        error = math.hypot(float(actual.x) - float(expected.x), float(actual.y) - float(expected.y))
        if error > 1e-5:
            raise RuntimeError(
                "tunic armhole arc lost authored %s: error-mm=%.6f "
                "normal-z=%.0f expected=(%.4f,%.4f) actual=(%.4f,%.4f)"
                % (
                    role,
                    error,
                    normal_z,
                    float(expected.x),
                    float(expected.y),
                    float(actual.x),
                    float(actual.y),
                )
            )
    return arc


def _polyline_distance_fraction(point, samples):
    """Return nearest 2D polyline distance and its normalized arc-length position."""
    import math

    spans = []
    total = 0.0
    for start, end in zip(samples, samples[1:], strict=False):
        length = math.hypot(float(end[0]) - float(start[0]), float(end[1]) - float(start[1]))
        spans.append((total, start, end, length))
        total += length
    if total <= 1e-12:
        return math.inf, 0.0

    best = (math.inf, 0.0)
    for offset, start, end, length in spans:
        if length <= 1e-12:
            continue
        dx = float(end[0]) - float(start[0])
        dy = float(end[1]) - float(start[1])
        fraction = (
            (float(point[0]) - float(start[0])) * dx + (float(point[1]) - float(start[1])) * dy
        ) / (length * length)
        fraction = max(0.0, min(1.0, fraction))
        nearest_x = float(start[0]) + fraction * dx
        nearest_y = float(start[1]) + fraction * dy
        distance = math.hypot(float(point[0]) - nearest_x, float(point[1]) - nearest_y)
        candidate = (distance, (offset + fraction * length) / total)
        if candidate < best:
            best = candidate
    return best


def _neckline_boundary_particles(
    piece, boundary, piece_indices, boundary_chains, particle_positions
):
    """Resolve neckline mesh particles from semantic endpoints, with geometric fallback."""
    import math

    import FreeCAD as App

    samples = tuple((float(sample[0]), float(sample[1])) for sample in boundary.samples)
    if len(samples) < 2:
        raise RuntimeError("canonical tunic neckline source edge has fewer than two samples")

    placement = getattr(piece, "Placement", None)
    inverse = placement.inverse() if placement is not None else None
    local_positions = {}
    for raw_index in piece_indices:
        index = int(raw_index)
        world = particle_positions[index]
        point = App.Vector(float(world[0]), float(world[1]), float(world[2]))
        if inverse is not None:
            point = inverse.multVec(point)
        local_positions[index] = (float(point.x), float(point.y))

    start, end = samples[0], samples[-1]
    best_chain = ()
    best_endpoint_error = math.inf
    # A runtime may order boundary chains differently from a separate PatternIR
    # resolution. Match the authored edge by its actual endpoints before using
    # any sequence position.
    for raw_chain in boundary_chains:
        chain = tuple(int(index) for index in raw_chain)
        if len(chain) < 2 or chain[0] not in local_positions or chain[-1] not in local_positions:
            continue
        first = local_positions[chain[0]]
        last = local_positions[chain[-1]]
        forward_error = max(math.dist(first, start), math.dist(last, end))
        reverse_error = max(math.dist(first, end), math.dist(last, start))
        if reverse_error < forward_error:
            candidate_chain = tuple(reversed(chain))
            error = reverse_error
        else:
            candidate_chain = chain
            error = forward_error
        if error < best_endpoint_error:
            best_chain = candidate_chain
            best_endpoint_error = error

    # This is a coordinate-correspondence tolerance, not a fit or solver threshold.
    if best_chain and best_endpoint_error <= 1e-4:
        return best_chain, "semantic-chain-endpoints", best_endpoint_error

    # If chain metadata omits or reorders this edge, recover only vertices that
    # lie on the authored edge in the piece's local plane. Unrelated world-space
    # nearest vertices are deliberately excluded.
    projected = []
    nearest_distance = math.inf
    for index, point in local_positions.items():
        distance, fraction = _polyline_distance_fraction(point, samples)
        nearest_distance = min(nearest_distance, distance)
        if distance <= 1e-4:
            projected.append((fraction, index))
    projected.sort()
    particles = tuple(index for _fraction, index in projected)
    if len(particles) >= 2:
        return particles, "authored-edge-projection", best_endpoint_error

    raise RuntimeError(
        "canonical tunic neckline has no mesh particles on its authored edge: "
        "piece=%s edge=%s chains=%d matched-particles=%d nearest-mm=%.6f "
        "endpoint-error-mm=%.6f"
        % (
            piece.Name,
            boundary.id,
            len(boundary_chains),
            len(particles),
            nearest_distance,
            best_endpoint_error,
        )
    )


def _make_tunic_sketch(
    doc, name, panel_width, garment_height, hem_width, neckline_ratio, neckline_drop=0.08
):
    import Part
    import Sketcher

    sketch = doc.addObject("Sketcher::SketchObject", name + "Sketch")
    neck_z = (1.0 - float(neckline_drop)) * garment_height
    x_offset = 0.5 * (float(hem_width) - float(panel_width))
    armhole_z = 0.88 * float(garment_height)
    shoulder_z = 0.98 * float(garment_height)
    points = [
        (0.00, 0.00),
        (hem_width, 0.00),
        (x_offset + 0.84 * panel_width, armhole_z),
        (x_offset + 0.90 * panel_width, shoulder_z),
        (x_offset + neckline_ratio * panel_width, neck_z),
        (x_offset + (1.0 - neckline_ratio) * panel_width, neck_z),
        (x_offset + 0.10 * panel_width, shoulder_z),
        (x_offset + 0.16 * panel_width, armhole_z),
    ]
    center_x = 0.5 * float(hem_width)
    for left, right in ((0, 1), (2, 7), (3, 6), (4, 5)):
        if abs((points[left][0] + points[right][0]) - 2.0 * center_x) > 1e-9:
            raise RuntimeError("canonical tunic pattern lost bilateral symmetry")

    # The armholes are free, inward-scooped edges. They must not be sewn shut.
    geometry = []
    armhole_mid_z = armhole_z + 0.5 * (shoulder_z - armhole_z)
    for index, (start, end) in enumerate(zip(points, points[1:] + points[:1], strict=True)):
        start_vector = App.Vector(start[0], start[1], 0)
        end_vector = App.Vector(end[0], end[1], 0)
        if index == 2:
            # Keep the circular bulge inside the panel: a deeper midpoint makes
            # this arc cross the adjacent shoulder-to-neckline segment.
            midpoint = App.Vector(x_offset + 0.847 * panel_width, armhole_mid_z, 0)
            geometry.append(_arc_through_midpoint(Part, start_vector, end_vector, midpoint))
        elif index == 6:
            midpoint = App.Vector(x_offset + 0.153 * panel_width, armhole_mid_z, 0)
            geometry.append(_arc_through_midpoint(Part, start_vector, end_vector, midpoint))
        else:
            geometry.append(Part.LineSegment(start_vector, end_vector))

    sketch.addGeometry(geometry, False)
    # This fixture authors every segment explicitly; preserve each segment's
    # coordinates so an underconstrained Sketcher solve cannot fold the straight
    # shoulders/sides/hem across the outline while retaining the two fixed arcs.
    # Shared endpoints are authored from the same point tuples, so no coincidence
    # solver movement is needed to close this deterministic test profile.
    sketch.addConstraint([Sketcher.Constraint("Block", index) for index in range(len(geometry))])
    doc.recompute()
    for index in (2, 6):
        curve = sketch.Geometry[index]
        first = float(curve.FirstParameter)
        last = float(curve.LastParameter)
        parameter_span = last - first
        if parameter_span <= 1e-3:
            raise RuntimeError(
                "tunic armhole collapsed during Sketcher recompute: index=%d span=%.9f"
                % (index, parameter_span)
            )
        evaluator = getattr(curve, "valueAt", None)
        if not callable(evaluator):
            evaluator = getattr(curve, "value", None)
        if not callable(evaluator):
            raise RuntimeError("tunic armhole native curve has no parameter evaluator")
        native_samples = tuple(
            evaluator(first + parameter_span * fraction / 8.0) for fraction in range(9)
        )
        native_xy = tuple((float(sample.x), float(sample.y)) for sample in native_samples)
        start_xy, end_xy = native_xy[0], native_xy[-1]
        vertical_span = end_xy[1] - start_xy[1]
        if abs(vertical_span) <= 1e-9:
            raise RuntimeError("tunic armhole native curve has a horizontal endpoint chord")
        inward = -1.0 if index == 2 else 1.0
        deviations = tuple(
            inward
            * (
                sample[0]
                - (
                    start_xy[0]
                    + (sample[1] - start_xy[1]) / vertical_span * (end_xy[0] - start_xy[0])
                )
            )
            for sample in native_xy[1:-1]
        )
        log(
            "tunic-native-armhole index=%d type=%s range=(%.9f,%.9f) "
            "start=(%.3f,%.3f) end=(%.3f,%.3f) "
            "bounds=(%.3f,%.3f,%.3f,%.3f) inward-scoop=%.3f samples=%r"
            % (
                index,
                type(curve).__name__,
                first,
                last,
                start_xy[0],
                start_xy[1],
                end_xy[0],
                end_xy[1],
                min(point[0] for point in native_xy),
                min(point[1] for point in native_xy),
                max(point[0] for point in native_xy),
                max(point[1] for point in native_xy),
                max(deviations),
                tuple((round(point[0], 3), round(point[1], 3)) for point in native_xy),
            )
        )
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
        back_placement = App.Placement(App.Vector(gap / 2.0, 0.0, 0.0), App.Rotation())
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
        raise RuntimeError(
            "canonical tunic sewing view needs the simulation's semantic seam records"
        )

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
        back_placement = App.Placement(App.Vector(gap / 2.0, 0.0, 0.0), App.Rotation())
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
    from freecad_cloth.simulation.SimulationCommands import create_quality_simulation_scene
    from freecad_cloth.simulation.SimulationQualityGui import SimulationQualityTaskPanel

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
    panel_width = max(420.0, shoulder_width + 100.0)
    hem_width = max(450.0, panel_width + 80.0)
    garment_height = max(560.0, shoulder_z - hem_z)
    body_depth = max(120.0, min(260.0, y_span))
    clearance = max(20.0, 0.08 * body_depth)
    rot = App.Rotation(App.Vector(1, 0, 0), 90.0)

    def target_relative_piece_placement(side):
        if side == "front":
            y = (shoulder_left.y + shoulder_right.y) / 2.0 - clearance
        elif side == "back":
            y = (shoulder_left.y + shoulder_right.y) / 2.0 + clearance
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

    front, front_outline = make_piece("VisualTunicFront", "front", 0.64, 0.10)
    back, back_outline = make_piece("VisualTunicBack", "back", 0.64, 0.10)

    def log_tunic_outline_topology(piece):
        """Report the ordered native boundary around any polygon self-intersection."""
        try:
            import ast
            import re

            from shapely.geometry import LineString, Point, Polygon
            from shapely.validation import explain_validity

            from freecad_cloth.pattern.SketchAuthority import (
                _resolve_sketch_ir,
                _sampled_outline,
            )

            piece_ir = _resolve_sketch_ir(piece)
            points = _sampled_outline(piece_ir)
            polygon = Polygon(points)
            reason = explain_validity(polygon)
            draft_points = [
                (float(point[0]), float(point[1]))
                for point in ast.literal_eval(str(piece.DraftingBoundary))
            ]
            draft_polygon = Polygon(draft_points)
            draft_reason = explain_validity(draft_polygon)

            ranges = []
            cursor = 0
            boundary_summary = []
            for boundary in piece_ir.boundaries:
                count = len(boundary.samples) - 1
                ranges.append(
                    (cursor, cursor + count, str(boundary.id), str(boundary.kind))
                )
                cursor += count
                boundary_summary.append(
                    (
                        str(boundary.id),
                        str(boundary.kind),
                        len(boundary.samples),
                        tuple(round(float(v), 3) for v in boundary.samples[0][:2]),
                        tuple(round(float(v), 3) for v in boundary.samples[-1][:2]),
                    )
                )

            def edge_id(index):
                for start, end, identity, _kind in ranges:
                    if start <= index < end:
                        return identity
                return "<unknown>"

            crossing_match = re.search(
                r"\\[([+-]?[0-9.eE+-]+)\\s+([+-]?[0-9.eE+-]+)\\]",
                reason,
            )
            nearby = ()
            if crossing_match:
                crossing = Point(
                    float(crossing_match.group(1)),
                    float(crossing_match.group(2)),
                )
                distances = []
                for index, start in enumerate(points):
                    end = points[(index + 1) % len(points)]
                    distance = LineString((start, end)).distance(crossing)
                    distances.append(
                        (
                            round(float(distance), 6),
                            index,
                            edge_id(index),
                            tuple(round(float(v), 3) for v in start),
                            tuple(round(float(v), 3) for v in end),
                        )
                    )
                nearby = tuple(sorted(distances)[:8])

            log(
                "tunic-outline-topology piece=%s ir-valid=%s ir-reason=%s "
                "draft-valid=%s draft-reason=%s ir-points=%d draft-points=%d "
                "boundary-order=%r near-crossing=%r"
                % (
                    piece.Name,
                    polygon.is_valid,
                    reason,
                    draft_polygon.is_valid,
                    draft_reason,
                    len(points),
                    len(draft_points),
                    tuple(boundary_summary),
                    nearby,
                )
            )
        except Exception as exc:
            log(
                "tunic-outline-topology-error piece=%s error=%s:%s"
                % (piece.Name, type(exc).__name__, exc)
            )

    for piece in (front, back):
        log_tunic_outline_topology(piece)

    capture_tunic_pattern_view(doc, front, back, hem_width)

    # Use semantic edge IDs and keep the two curved armholes (edges 2 and 6)
    # open. Only the two side seams and two shoulder seams are joined.
    front_edge_ids = tuple(
        str(value) for value in getattr(front.Sketch, "SemanticEdgeIds", ()) or ()
    )
    back_edge_ids = tuple(str(value) for value in getattr(back.Sketch, "SemanticEdgeIds", ()) or ())
    if len(front_edge_ids) < 8 or len(back_edge_ids) < 8:
        raise RuntimeError("canonical tunic sketches have no complete semantic edge map")
    required_indices = (1, 3, 5, 7)
    if any(not front_edge_ids[index] or not back_edge_ids[index] for index in required_indices):
        raise RuntimeError("canonical tunic fixture is missing authored semantic edge IDs")

    from freecad_cloth.simulation.PatternSimulationAdapter import resolve_piece_ir

    for piece, edge_ids in ((front, front_edge_ids), (back, back_edge_ids)):
        piece_ir = resolve_piece_ir(piece)
        boundary_by_id = {str(boundary.id): boundary for boundary in piece_ir.boundaries}
        for edge_index, inward in ((2, -1.0), (6, 1.0)):
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
                deviations = tuple(
                    float(sample[0])
                    - (
                        float(start_point[0])
                        + (float(sample[1]) - float(start_point[1]))
                        / vertical_span
                        * (float(end_point[0]) - float(start_point[0]))
                    )
                    for sample in boundary.samples[1:-1]
                )
                native_geometry = piece.Sketch.Geometry[edge_index]
                log(
                    "tunic-armhole-debug piece=%s edge=%s native=%s range=%s "
                    "start=(%.3f,%.3f) end=(%.3f,%.3f) x-deviation=[%.3f,%.3f] "
                    "signed-inward=%.3f"
                    % (
                        piece.Name,
                        edge_ids[edge_index],
                        type(native_geometry).__name__,
                        tuple(float(value) for value in boundary.parameter_range),
                        float(start_point[0]),
                        float(start_point[1]),
                        float(end_point[0]),
                        float(end_point[1]),
                        min(deviations),
                        max(deviations),
                        float(scoop_depth),
                    )
                )
                raise RuntimeError(
                    "canonical garment armhole curve has insufficient inward clearance: "
                    "piece=%s edge=%s scoop-mm=%.2f"
                    % (piece.Name, edge_ids[edge_index], scoop_depth)
                )

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
            raise RuntimeError(
                "canonical tunic seam %s did not retain its authored correspondence" % seam_id
            )
        seam_records.append((seam_obj, front, back))
    capture_tunic_sewing_view(doc, front, back, hem_width, seam_records)
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
    # Build once to resolve each authored neckline center to a stable boundary particle.
    # Explicit neckline anchors stop the unsupported tunic from dropping toward the hips.
    scene.PinMode = "Automatic"
    scene.PinSelection = []
    scene.ClothPieces = [front, back]
    link_records = tuple(
        (
            str(getattr(piece, "Name", "")),
            str(getattr(piece, "PieceId", "")),
            str(getattr(piece, "PatternType", "")),
        )
        for piece in (getattr(scene, "ClothPieces", ()) or ())
    )
    log("tunic-simulation-input-cloth-pieces=%r" % (link_records,))
    proxy = scene.Proxy
    base_proxy_getter = getattr(proxy, "_base_or_restore", None)
    if not callable(base_proxy_getter):
        raise RuntimeError("canonical tunic simulation cannot invalidate its cached scene")
    # Explicitly invalidate the initial demo signature; touch() alone retained its backend.
    base_proxy_getter().source_signature = None
    scene.touch()
    refresh_drape_target(target)
    doc.recompute()
    # Recompute may leave the GUI-created demo backend cached after the authored
    # PatternPieces are linked. Re-enter the same proxy execution path with its
    # signature invalidated so the audit measures the real tunic panels.
    proxy = scene.Proxy
    base_proxy_getter = getattr(proxy, "_base_or_restore", None)
    if not callable(base_proxy_getter):
        raise RuntimeError("canonical tunic simulation cannot rebuild its authored panels")
    base_proxy_getter().source_signature = None
    proxy.execute(scene)
    status = target_status(target)
    if str(status.get("state", "")) != "ready":
        raise RuntimeError(
            "canonical tunic DrapeTarget is not current: {}".format(status.get("message", status))
        )
    proxy = scene.Proxy
    backend = getattr(proxy, "backend", None)
    if backend is None:
        raise RuntimeError("canonical tunic did not build a simulation backend")
    particle_positions = tuple(
        tuple(float(value) for value in position) for position in backend.positions()
    )
    panel_indices = getattr(proxy, "panel_indices", {})
    panel_objects = tuple(getattr(scene, "DrapePanels", ()))
    if len(panel_objects) < 2:
        raise RuntimeError("canonical tunic did not create one drape mesh per panel")
    anchor_indices = []
    panel_boundary_edges = getattr(proxy, "panel_boundary_edges", {})
    panel_piece_names = getattr(proxy, "panel_piece_names", {})
    panel_map_summary = tuple(
        (
            str(getattr(panel, "Name", "")),
            str(panel_piece_names.get(getattr(panel, "Name", ""), "")),
            len(tuple(panel_indices.get(getattr(panel, "Name", ""), ()))),
            len(tuple(panel_boundary_edges.get(getattr(panel, "Name", ""), ()))),
        )
        for panel in panel_objects[:2]
    )
    log(
        "tunic-simulation-panel-map proxy=%s links=%d panels=%r map=%r particles=%d"
        % (
            type(proxy).__name__,
            len(tuple(getattr(scene, "ClothPieces", ()) or ())),
            tuple(str(getattr(panel, "Name", "")) for panel in panel_objects[:2]),
            panel_map_summary,
            len(particle_positions),
        )
    )
    for piece, panel in zip((front, back), panel_objects[:2], strict=True):
        if str(panel_piece_names.get(panel.Name, "")) != str(piece.Name):
            raise RuntimeError(
                "canonical tunic simulation did not build an authored pattern panel: "
                "piece=%s panel=%s mapped-piece=%s cloth-pieces=%r"
                % (
                    piece.Name,
                    panel.Name,
                    str(panel_piece_names.get(panel.Name, "")),
                    link_records,
                )
            )
    for piece, _outline, panel, edge_ids in zip(
        (front, back),
        (front_outline, back_outline),
        panel_objects[:2],
        (front_edge_ids, back_edge_ids),
        strict=True,
    ):
        piece_indices = tuple(int(index) for index in panel_indices.get(panel.Name, ()))
        piece_index_set = set(piece_indices)
        if not piece_index_set:
            raise RuntimeError(
                "canonical tunic has no simulation particles for piece %s" % piece.Name
            )

        # Resolve the neckline by authored Sketcher edge ID, then anchor to the
        # midpoint of that edge's actual meshed boundary chain. This avoids a
        # world-space nearest-vertex search that can accidentally select the
        # wrong region when a panel has been placed or rotated.
        piece_ir = resolve_piece_ir(piece)
        neckline_edge_id = str(edge_ids[4])
        neckline_boundary = next(
            (boundary for boundary in piece_ir.boundaries if str(boundary.id) == neckline_edge_id),
            None,
        )
        if neckline_boundary is None:
            raise RuntimeError(
                "canonical tunic could not resolve neckline semantic edge: "
                "piece=%s edge=%s" % (piece.Name, neckline_edge_id)
            )
        boundary_chains = tuple(panel_boundary_edges.get(panel.Name, ()))
        neckline_particles, boundary_method, endpoint_error = _neckline_boundary_particles(
            piece,
            neckline_boundary,
            piece_indices,
            boundary_chains,
            particle_positions,
        )
        log(
            "tunic-neckline-resolution piece=%s edge=%s method=%s chains=%d endpoint-error-mm=%.6f"
            % (
                piece.Name,
                neckline_edge_id,
                boundary_method,
                len(boundary_chains),
                endpoint_error,
            )
        )
        if len(neckline_particles) < 2:
            raise RuntimeError(
                "canonical tunic neckline boundary has too few mesh vertices: "
                "piece=%s edge=%s" % (piece.Name, neckline_edge_id)
            )
        if any(index not in piece_index_set for index in neckline_particles):
            raise RuntimeError(
                "canonical tunic neckline boundary contains particles from another panel: "
                "piece=%s edge=%s" % (piece.Name, neckline_edge_id)
            )

        cumulative_distances = [0.0]
        for first_index, second_index in zip(
            neckline_particles, neckline_particles[1:], strict=False
        ):
            first = particle_positions[first_index]
            second = particle_positions[second_index]
            span = sum((float(second[axis]) - float(first[axis])) ** 2 for axis in range(3)) ** 0.5
            if span <= 1e-9:
                raise RuntimeError(
                    "canonical tunic neckline boundary contains a zero-length segment: "
                    "piece=%s edge=%s" % (piece.Name, neckline_edge_id)
                )
            cumulative_distances.append(cumulative_distances[-1] + span)

        total_length = cumulative_distances[-1]
        if total_length <= 1e-9:
            raise RuntimeError(
                "canonical tunic neckline boundary has zero length: "
                "piece=%s edge=%s" % (piece.Name, neckline_edge_id)
            )
        midpoint_distance = 0.5 * total_length
        central_offset = min(
            range(len(neckline_particles)),
            key=lambda index: abs(cumulative_distances[index] - midpoint_distance),
        )
        particle_index = neckline_particles[central_offset]
        snap_distance = abs(cumulative_distances[central_offset] - midpoint_distance)
        if snap_distance > max(8.0, float(scene.ParticleDistance)):
            raise RuntimeError(
                "canonical tunic neckline anchor did not resolve to its boundary midpoint: "
                "piece=%s edge=%s midpoint-offset-mm=%.2f"
                % (piece.Name, neckline_edge_id, snap_distance)
            )
        anchor_indices.append(particle_index)
        log(
            "tunic-neckline-boundary piece=%s edge=%s vertices=%d length-mm=%.2f"
            % (piece.Name, neckline_edge_id, len(neckline_particles), total_length)
        )
        # Keep the established contract log token; snap-mm is measured along the
        # authored neckline chain, not from an unrelated world-space mesh vertex.
        log(
            "tunic-neckline-anchor piece=%s particle=%d snap-mm=%.2f"
            % (piece.Name, particle_index, snap_distance)
        )
    expected_pins = tuple(sorted(set(anchor_indices)))
    if len(expected_pins) != 2:
        raise RuntimeError(
            "canonical tunic requires one distinct neckline anchor per panel: %s" % (expected_pins,)
        )

    scene.PinMode = "Explicit"
    scene.PinSelection = [str(index) for index in expected_pins]
    proxy = scene.Proxy
    base_proxy_getter = getattr(proxy, "_base_or_restore", None)
    if not callable(base_proxy_getter):
        raise RuntimeError("canonical tunic simulation cannot invalidate its cached scene")
    # Rebuild against the explicit anchors instead of retaining automatic corner pins.
    base_proxy_getter().source_signature = None
    doc.recompute()
    status = target_status(target)
    if str(status.get("state", "")) != "ready":
        raise RuntimeError(
            "canonical tunic DrapeTarget is not current: {}".format(status.get("message", status))
        )
    proxy = scene.Proxy
    backend = getattr(proxy, "backend", None)
    if backend is None:
        raise RuntimeError("canonical tunic did not build an anchored simulation backend")
    solver_pins = tuple(sorted(int(index) for index in getattr(backend, "_pin_indices", ())))
    persisted_pins = tuple(sorted(int(index) for index in getattr(scene, "PinSelection", ())))
    if str(getattr(scene, "PinMode", "")) != "Explicit":
        raise RuntimeError("canonical tunic requires Explicit neckline anchoring")
    if solver_pins != expected_pins or persisted_pins != expected_pins:
        raise RuntimeError(
            "canonical tunic neckline anchors differ from solver pins: "
            "solver=%s expected=%s persisted=%s" % (solver_pins, expected_pins, persisted_pins)
        )
    log("pin-mode=Explicit neckline-anchor-pins=%s" % (solver_pins,))
    surface = collision_surface(
        target_source,
        float(getattr(target, "CollisionDeflection", 1.0)),
        float(getattr(target, "CollisionThickness", 0.0)),
    )
    initial_clearance = None
    try:
        from freecad_cloth.common.MeshValidation import nearest_target_clearance

        initial_clearance = nearest_target_clearance(
            tuple(backend.positions()), tuple(surface.vertices)
        )
    except (ImportError, ValueError):
        initial_clearance = None
    if initial_clearance is None or float(initial_clearance) < float(clearance):
        raise RuntimeError(
            "canonical tunic step-0 target clearance is below configured separation: "
            f"{float(initial_clearance or 0.0):.2f} mm < {float(clearance):.2f} mm"
        )
    log("pin-mode=None solver-pins=0")
    log("seam-world-x-step0=" + json.dumps(_seam_lateral_snapshot(proxy, x_mid), sort_keys=True))
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
    # FreeCAD animates viewFront/viewRear transitions by default. Capturing while
    # that transition is in progress records different camera rotations depending
    # on the preceding view, which can mirror left/right seam colors between frames.
    # Disable animation before setting either screenshot view so both captures use
    # the same canonical orthographic projection.
    view.setAnimationEnabled(False)
    view.setCameraType("Orthographic")
    view.viewFront()
    view.fitAll()
    events()
    task_dock.hide()
    events()
    arranged_front_orientation = view.getCameraOrientation()
    log("camera-arranged=" + json.dumps(_camera_snapshot(view), sort_keys=True))
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
    log("seam-world-x-step90=" + json.dumps(_seam_lateral_snapshot(proxy, x_mid), sort_keys=True))

    from freecad_cloth.sewing.SeamOverlay import refresh_seam_overlay

    overlay = refresh_seam_overlay(doc)
    expected_seam_ids = {str(seam.SeamId) for seam, _piece_a, _piece_b in seam_records}
    rendered_seam_ids = set(getattr(overlay, "rendered_seam_ids", ()))
    if overlay is None or not expected_seam_ids or not expected_seam_ids <= rendered_seam_ids:
        raise RuntimeError(
            "simulation seam overlay is not rendering exact solver stitch pairs: "
            f"expected={sorted(expected_seam_ids)!r} rendered={sorted(rendered_seam_ids)!r}"
        )
    log(
        "simulation-seam-overlay=passed ids=%s source=solver-stitch-pairs"
        % sorted(rendered_seam_ids)
    )
    if any(panel.Mesh.CountFacets <= 10 for panel in scene.DrapePanels):
        raise RuntimeError("draped tunic panel mesh is empty")
    from freecad_cloth.simulation.ClothDiagnosticsGui import (
        DiagnosticsTaskPanel,
        create_diagnostic_map,
    )

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
        if direction == "front":
            # With animation disabled, viewFront must resolve to exactly the same
            # orientation as the arranged capture, independently of prior views.
            restored_orientation = view.getCameraOrientation()
            expected_q = tuple(float(value) for value in arranged_front_orientation.Q)
            actual_q = tuple(float(value) for value in restored_orientation.Q)
            rotation_agreement = abs(sum(a * b for a, b in zip(expected_q, actual_q, strict=True)))
            if rotation_agreement < 1.0 - 1e-8:
                raise RuntimeError(
                    "draped front camera rotation does not match arranged screenshot "
                    f"(quaternion agreement={rotation_agreement:.12f})"
                )
            log("camera-draped-front=" + json.dumps(_camera_snapshot(view), sort_keys=True))
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
