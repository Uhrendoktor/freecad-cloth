"""Import-safe shared FreeCAD/PBD diagnostic and ladder helpers.

The module provides callable infrastructure only. It does not launch tests,
create documents, start timers, or open output files during import.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from pathlib import Path


def make_progress_logger(path: str | Path) -> Callable[[str], None]:
    """Create a progress logger that appends to one file and mirrors stdout."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)

    def progress(message: str) -> None:
        line = str(message)
        with output.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        print(line, flush=True)

    return progress


def events() -> None:
    """Process pending FreeCAD GUI events without owning the application loop."""
    import FreeCADGui as Gui

    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    Gui.updateGui()
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.processEvents()
    Gui.updateGui()


def ensure_gui_ready() -> None:
    """Fail when the FreeCAD window is not visible and process one GUI event pass."""
    import FreeCADGui as Gui

    window = Gui.getMainWindow()
    if window is None or not window.isVisible():
        raise RuntimeError("FreeCAD GUI did not launch")
    window.show()
    events()


def add_rectangle_sketch(doc, name, width, height):
    """Create a native rectangular Sketcher profile for diagnostic cloth panels."""
    import FreeCAD as App
    import Part

    sketch = doc.addObject("Sketcher::SketchObject", name)
    points = (
        (0.0, 0.0),
        (float(width), 0.0),
        (float(width), float(height)),
        (0.0, float(height)),
    )
    for index, start in enumerate(points):
        end = points[(index + 1) % 4]
        sketch.addGeometry(
            Part.LineSegment(App.Vector(start[0], start[1], 0.0), App.Vector(end[0], end[1], 0.0)),
            False,
        )
    doc.recompute()
    return sketch


def adopt_sketch(sketch, name):
    """Adopt a diagnostic Sketcher profile through the production pattern command."""
    import FreeCADGui as Gui
    from freecad_cloth.pattern.PatternCommands import create_pattern_piece_from_selected_sketch

    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(sketch)
    piece = create_pattern_piece_from_selected_sketch(name=name, allowance=0.0, grainline=0.0)
    Gui.Selection.clearSelection()
    doc = sketch.Document
    doc.recompute()
    return piece


def mesh_geometry(obj):
    """Return stable point/triangle tuples from mesh topology or tessellated shape geometry."""
    mesh = getattr(obj, "Mesh", None)
    if mesh is not None:
        topology = getattr(mesh, "Topology", None)
        if topology is not None:
            vertices, triangles = topology
            return (
                tuple((float(v.x), float(v.y), float(v.z)) for v in vertices),
                tuple(tuple(int(i) for i in tri) for tri in triangles),
            )
    shape = getattr(obj, "Shape", None)
    if shape is None or shape.isNull():
        raise RuntimeError(
            "missing mesh or shape geometry on {}".format(getattr(obj, "Name", "object"))
        )
    vertices, triangles = shape.tessellate(1.0)
    return (
        tuple((float(v.x), float(v.y), float(v.z)) for v in vertices),
        tuple(tuple(int(i) for i in tri) for tri in triangles),
    )


def mesh_points(obj):
    """Return the point array from mesh_geometry."""
    return mesh_geometry(obj)[0]


def connected_components(vertices, triangles):
    """Count connected vertex components in a diagnostic triangle mesh."""
    if not vertices:
        return 0
    parent = list(range(len(vertices)))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left, right):
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for triangle in triangles:
        if len(triangle) != 3:
            continue
        a, b, c = (int(i) for i in triangle)
        if all(0 <= i < len(vertices) for i in (a, b, c)):
            union(a, b)
            union(b, c)
    return len({find(i) for i in range(len(vertices))})


def nearest_surface_observation(garment_points, surface):
    """Return the exact nearest target vertex distance and corresponding world point."""
    if not garment_points or surface is None:
        return None, None
    vertices = tuple(getattr(surface, "vertices", ()) or ())
    if not vertices:
        return None, None
    from freecad_cloth.common.MeshValidation import nearest_target_observation

    return nearest_target_observation(garment_points, vertices)


def inside_outside(points, source):
    """Classify sampled points against a native shape or its closed triangle mesh."""
    import FreeCAD as App

    shape = getattr(source, "Shape", None)
    if shape is not None and not getattr(shape, "isNull", lambda: True)():
        states = []
        for point in points[:64]:
            try:
                states.append(bool(shape.isInside(App.Vector(*point), 1e-6, True)))
            except (AttributeError, TypeError, ValueError):
                states = []
                break
        if states:
            if all(states):
                return "inside"
            if not any(states):
                return "outside"
            return "mixed"
    mesh = getattr(source, "Mesh", None)
    mesh_is_inside = getattr(mesh, "isInside", None) if mesh is not None else None
    if callable(mesh_is_inside):
        states = []
        for point in points[:64]:
            try:
                states.append(bool(mesh_is_inside(App.Vector(*point), 1e-6, True)))
            except (AttributeError, TypeError, ValueError):
                states = []
                break
        if states:
            if all(states):
                return "inside"
            if not any(states):
                return "outside"
            return "mixed"
    topology = getattr(mesh, "Topology", None) if mesh is not None else None
    if topology is None:
        return "unknown"
    raw_vertices, raw_faces = topology
    vertices = tuple((float(v.x), float(v.y), float(v.z)) for v in raw_vertices)
    triangles = tuple(tuple(int(i) for i in face) for face in raw_faces)
    if not vertices or not triangles:
        return "unknown"
    try:
        import numpy as np
        import trimesh

        target_mesh = trimesh.Trimesh(
            vertices=np.asarray(vertices, dtype=float),
            faces=np.asarray(triangles, dtype=int),
            process=False,
        )
        if not target_mesh.is_watertight:
            raise RuntimeError("target mesh is not watertight")
        states = [
            bool(value) for value in target_mesh.contains(np.asarray(points[:64], dtype=float))
        ]
    except (ImportError, RuntimeError, TypeError, ValueError):
        from freecad_cloth.simulation.DrapeVisualSanity import point_inside_closed_mesh

        states = [point_inside_closed_mesh(point, vertices, triangles) for point in points[:64]]
    if not states:
        return "unknown"
    if all(states):
        return "inside"
    if not any(states):
        return "outside"
    return "mixed"


def bounds(points):
    """Return axis-aligned bounds for a non-empty point set."""
    if not points:
        raise RuntimeError("cannot measure empty point set")
    return (
        min(p[0] for p in points), max(p[0] for p in points),
        min(p[1] for p in points), max(p[1] for p in points),
        min(p[2] for p in points), max(p[2] for p in points),
    )


def centroid(points):
    """Return the arithmetic centroid of a non-empty point set."""
    n = float(len(points))
    return tuple(sum(p[i] for p in points) / n for i in range(3))


def nearest_surface_distance(garment_points, surface):
    """Return exact point-to-surface distance, with bounded vertex fallback."""
    if not garment_points or surface is None:
        return None
    vertices = tuple(getattr(surface, "vertices", ()) or ())
    triangles = tuple(getattr(surface, "triangles", ()) or ())
    if not vertices:
        return None
    if triangles:
        try:
            from freecad_cloth.common.MeshValidation import nearest_surface_clearance
            return float(nearest_surface_clearance(garment_points, vertices, triangles))
        except (ImportError, RuntimeError, ValueError):
            pass
    sample = vertices[:: max(1, len(vertices) // 4096)]
    best = float("inf")
    for source in garment_points:
        for target in sample:
            d2 = sum((float(a) - float(b)) ** 2 for a, b in zip(source, target, strict=False))
            best = min(best, d2)
    return math.sqrt(best) if math.isfinite(best) else None


def target_signature(target):
    """Return stable target/source identity and topology metrics for diagnostic evidence."""
    source = getattr(target, "SourceObject", None)
    if source is None:
        raise RuntimeError("diagnostic target has no source")
    mesh = getattr(source, "Mesh", None)
    return {
        "target_type": str(getattr(target, "TargetType", "")),
        "source_name": str(getattr(source, "Name", "")),
        "source_label": str(getattr(source, "Label", "")),
        "source_revision": int(getattr(source, "AvatarRevision", 0)),
        "source_vertices": int(getattr(source, "MeshVertexCount",
            getattr(mesh, "CountPoints", 0) if mesh is not None else 0)),
        "source_triangles": int(getattr(source, "MeshTriangleCount",
            getattr(mesh, "CountFacets", 0) if mesh is not None else 0)),
        "collision_triangles_authored": int(getattr(target, "CollisionTriangleCount", 0)),
        "collision_vertices_authored": int(getattr(target, "CollisionVertexCount", 0)),
    }


def screenshot(view, path):
    """Capture a fixed-size diagnostic PNG and reject missing or empty artifacts."""
    view.setCameraType("Orthographic")
    view.fitAll()
    events()
    view.saveImage(str(path), 640, 360, "White")
    if not path.is_file() or path.stat().st_size <= 0:
        raise RuntimeError(f"screenshot missing: {path}")


def build_scene(doc, particle_distance=24.0):
    """Create the canonical production avatar/target scene for PBD diagnostic cases."""
    from freecad_cloth.avatar.AvatarCommands import create_avatar
    from freecad_cloth.simulation.DrapeCommands import set_drape_target_source
    from freecad_cloth.simulation.SimulationObjects import create_simulation_scene
    from freecad_cloth.simulation.SimulationQualityRuntime import (
        QualitySimulationProxy, ensure_quality_properties,
    )
    scene = create_simulation_scene(doc, build=False)
    legacy = doc.getObject("HumanoidAvatar")
    if legacy is not None and hasattr(legacy, "ViewObject"):
        legacy.ViewObject.Visibility = False
    avatar = create_avatar(attach_collision=False, doc=doc)
    avatar.Label = "Cloth Human Avatar (MakeHuman)"
    avatar.ViewObject.Visibility = True
    set_drape_target_source(scene, avatar, float(getattr(avatar, "SkinOffset", 3.0)), 1.0)
    scene.AvatarProxy.SourceObject = avatar
    scene.DrapeTarget = doc.getObject("DrapeTarget")
    ensure_quality_properties(scene)
    scene.Proxy = QualitySimulationProxy()
    scene.QualityPreset = "Fast"
    scene.ParticleDistance = particle_distance
    scene.SolverIterations = 1
    scene.SolverSubsteps = 1
    scene.TimeStep = 1.0 / 120.0
    scene.GravityX = scene.GravityY = scene.GravityZ = 0.0
    scene.FabricFriction = 0.5
    scene.PinMode = "None"
    scene.PinSelection = []
    scene.FabricTransparency = 0
    return scene


def build_piece(doc, name, placement, width=120.0, height=120.0):
    """Create a production pattern piece from a temporary rectangle sketch."""
    sketch = add_rectangle_sketch(doc, name + "Source", width, height)
    piece = adopt_sketch(sketch, name)
    piece.Placement = placement
    piece.Sketch.Placement = placement
    sketch.ViewObject.Visibility = False
    piece.ViewObject.Visibility = False
    doc.recompute()
    return piece


def positions_tuple(backend):
    """Return a stable tuple copy of backend particle positions."""
    return tuple(tuple(float(c) for c in point) for point in backend.positions())


def seam_geometry(backend, seam_stitch_pairs):
    """Return deterministic per-seam stitch gap measurements in millimetres."""
    positions = positions_tuple(backend)
    result = []
    for seam_id, pairs in sorted(seam_stitch_pairs.items()):
        measurements = []
        for left, right in pairs:
            a, b = positions[int(left)], positions[int(right)]
            measurements.append({
                "particle_a": int(left), "particle_b": int(right),
                "a_world_mm": [round(value, 6) for value in a],
                "b_world_mm": [round(value, 6) for value in b],
                "distance_mm": round(math.dist(a, b), 6),
            })
        distances = [item["distance_mm"] for item in measurements]
        result.append({
            "seam_id": str(seam_id),
            "pair_count": len(measurements),
            "min_span_mm": round(min(distances), 6) if distances else 0.0,
            "max_span_mm": round(max(distances), 6) if distances else 0.0,
            "mean_span_mm": round(sum(distances) / len(distances), 6) if distances else 0.0,
            "pairs": measurements,
        })
    return result


def checkpoint_record(
    step, image, positions, panel_triangles, signed_clearance, unsigned_clearance,
    base, connected_components, contact_state,
):
    """Build common checkpoint evidence for either cube or avatar ladder."""
    geometry = seam_geometry(base.backend, base.seam_stitch_pairs)
    return {
        "step": int(step),
        "image": image,
        "finite": all(math.isfinite(float(c)) for point in positions for c in point),
        "components": connected_components(positions, panel_triangles),
        "max_seam_gap_mm": round(max((entry["max_span_mm"] for entry in geometry), default=0.0), 6),
        "target_clearance_mm": signed_clearance,
        "target_unsigned_clearance_mm": unsigned_clearance,
        "penetration_mm": round(max(0.0, -float(signed_clearance)), 6) if signed_clearance is not None else None,
        "contact_state": contact_state,
        "seam_world_spans_mm": geometry,
    }


def make_shutdown_gui(progress: Callable[[str], None]) -> Callable[[], None]:
    """Create a GUI shutdown callback with diagnostics routed to the given logger."""
    def shutdown_gui() -> None:
        try:
            try:
                from PySide import QtWidgets
            except ImportError:
                from PySide2 import QtWidgets
            app = QtWidgets.QApplication.instance()
            if app is not None:
                app.quit()
        except Exception as exc:
            progress(f"qt-quit-failed={exc!r}")
        progress("gui-shutdown-requested")
    return shutdown_gui


def schedule_freecad_main(callback: Callable[[], None]) -> None:
    """Schedule a callback after FreeCAD finishes importing a delayed-startup script."""
    try:
        from PySide import QtCore
    except ImportError:
        from PySide2 import QtCore
    QtCore.QTimer.singleShot(0, callback)
