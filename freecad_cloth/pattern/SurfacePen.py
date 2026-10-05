"""3D surface authoring bridge for Cloth Pattern.

The surface pen is intentionally an authoring frontend, not a second pattern
editor. It records a temporary surface stroke on a visible FreeCAD target and
can extract a sufficiently planar patch into a normal native Sketcher-backed
PatternPiece.

The MVP fail-closes when the sampled patch cannot be represented by a single
2D plane without exceeding the configured deviation tolerance. A future
surface-parameterization backend can replace the flattening helper without
changing the viewport or PatternPiece authority boundaries.
"""

from __future__ import annotations

import contextlib
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass

from freecad_cloth.shared.SourceSignature import source_signature


Point3 = tuple[float, float, float]
Vector3 = Point3
Point2 = tuple[float, float]
DEFAULT_CLOSE_DISTANCE_MM = 6.0


def _as_point3(value) -> Point3:
    try:
        values = tuple(value)
        if len(values) >= 3:
            return tuple(float(v) for v in values[:3])
    except (TypeError, ValueError):
        pass
    return (float(value.x), float(value.y), float(value.z))


def _dot(a: Vector3, b: Vector3) -> float:
    return sum(float(x) * float(y) for x, y in zip(a, b, strict=False))


def _cross(a: Vector3, b: Vector3) -> Vector3:
    return (
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    )


def _sub(a: Point3, b: Point3) -> Vector3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a: Point3, b: Vector3) -> Point3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(a: Vector3, value: float) -> Vector3:
    return (a[0] * value, a[1] * value, a[2] * value)


def _length(a: Vector3) -> float:
    return math.sqrt(_dot(a, a))


def _normalize(a: Vector3) -> Vector3:
    length = _length(a)
    if length <= 1e-12:
        raise ValueError("surface points do not define a usable direction")
    return _scale(a, 1.0 / length)


def _centroid(points: Sequence[Point3]) -> Point3:
    if not points:
        raise ValueError("at least one point is required")
    count = float(len(points))
    return (
        sum(point[0] for point in points) / count,
        sum(point[1] for point in points) / count,
        sum(point[2] for point in points) / count,
    )


def polygon_area_2d(points: Sequence[Point2]) -> float:
    """Return the signed polygon area in square millimetres."""
    if len(points) < 3:
        return 0.0
    return 0.5 * sum(
        float(a[0]) * float(b[1]) - float(b[0]) * float(a[1])
        for a, b in zip(points, (*points[1:], points[0]), strict=False)
    )


def _orientation(a: Point2, b: Point2, c: Point2) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: Point2, b: Point2, p: Point2, tolerance: float = 1e-9) -> bool:
    return (
        min(a[0], b[0]) - tolerance <= p[0] <= max(a[0], b[0]) + tolerance
        and min(a[1], b[1]) - tolerance <= p[1] <= max(a[1], b[1]) + tolerance
    )


def _segments_intersect(a: Point2, b: Point2, c: Point2, d: Point2) -> bool:
    values = (_orientation(a, b, c), _orientation(a, b, d), _orientation(c, d, a), _orientation(c, d, b))
    eps = 1e-9
    if (
        ((values[0] > eps and values[1] < -eps) or (values[0] < -eps and values[1] > eps))
        and ((values[2] > eps and values[3] < -eps) or (values[2] < -eps and values[3] > eps))
    ):
        return True
    return any(
        abs(value) <= eps and _on_segment(pair[0], pair[1], pair[2])
        for value, pair in (
            (values[0], (a, b, c)),
            (values[1], (a, b, d)),
            (values[2], (c, d, a)),
            (values[3], (c, d, b)),
        )
    )


def polygon_self_intersects(points: Sequence[Point2]) -> bool:
    """Return True when a non-adjacent polygon edge pair intersects."""
    count = len(points)
    if count < 4:
        return False
    for first in range(count):
        first_end = (first + 1) % count
        for second in range(first + 1, count):
            second_end = (second + 1) % count
            if first == second or first_end == second or second_end == first:
                continue
            if _segments_intersect(
                points[first],
                points[first_end],
                points[second],
                points[second_end],
            ):
                return True
    return False


def simplify_polyline(points: Sequence[Point3], tolerance_mm: float = 1.0) -> tuple[Point3, ...]:
    """Simplify a spatial polyline with a deterministic RDP pass."""
    values = tuple(_as_point3(point) for point in points)
    if len(values) <= 2:
        return values
    tolerance = max(0.0, float(tolerance_mm))
    if tolerance <= 1e-12:
        return values

    def perpendicular_distance(point: Point3, start: Point3, end: Point3) -> float:
        axis = _sub(end, start)
        span = _length(axis)
        if span <= 1e-12:
            return _length(_sub(point, start))
        projection = _add(start, _scale(axis, _dot(_sub(point, start), axis) / (span * span)))
        return _length(_sub(point, projection))

    def rdp(items: Sequence[Point3]) -> tuple[Point3, ...]:
        if len(items) <= 2:
            return tuple(items)
        start, end = items[0], items[-1]
        farthest_index = -1
        farthest_distance = tolerance
        for index in range(1, len(items) - 1):
            distance = perpendicular_distance(items[index], start, end)
            if distance > farthest_distance:
                farthest_distance = distance
                farthest_index = index
        if farthest_index < 0:
            return (start, end)
        left = rdp(items[: farthest_index + 1])
        right = rdp(items[farthest_index:])
        return left[:-1] + right

    return rdp(values)


@dataclass(frozen=True)
class SurfaceAnchor:
    """A sampled target-space point and its surface normal.

    The first MVP stores the target's authoritative source signature plus the
    world-space pick. Triangle/barycentric storage can be added later without
    changing the public stroke representation.
    """

    point: Point3
    normal: Vector3

    def to_json(self) -> dict:
        """Serialize this surface anchor for persistent document storage."""
        return {
            "point": [round(float(value), 6) for value in self.point],
            "normal": [round(float(value), 6) for value in self.normal],
        }

    @classmethod
    def from_json(cls, value: dict) -> "SurfaceAnchor":
        """Restore a surface anchor from its serialized mapping."""
        return cls(_as_point3(value["point"]), _as_point3(value["normal"]))


@dataclass(frozen=True)
class FlattenedSurfacePatch:
    """2D result of the bounded MVP surface-to-plane projection."""

    points: tuple[Point2, ...]
    centroid: Point3
    normal: Vector3
    max_deviation_mm: float

    def validate(self, tolerance_mm: float) -> "FlattenedSurfacePatch":
        """Validate topology, area, and allowed planar deviation."""
        if len(self.points) < 3:
            raise ValueError("surface patch needs at least three distinct points")
        if polygon_self_intersects(self.points):
            raise ValueError("surface patch self-intersects after flattening")
        if abs(polygon_area_2d(self.points)) <= 1e-6:
            raise ValueError("surface patch has negligible 2D area")
        limit = max(0.0, float(tolerance_mm))
        if self.max_deviation_mm > limit + 1e-9:
            raise ValueError(
                "surface patch is too curved for the bounded planar MVP: "
                f"{self.max_deviation_mm:.2f} mm deviation exceeds {limit:.2f} mm tolerance"
            )
        return self


def flatten_surface_patch(
    points: Sequence[Point3],
    tolerance_mm: float = 8.0,
) -> FlattenedSurfacePatch:
    """Project a sampled closed surface boundary onto a deterministic best local plane.

    The plane is oriented from a deterministic local boundary normal. This is not a
    general mesh parameterization; the explicit deviation test prevents silently
    turning a strongly curved region into a misleading flat pattern.
    """
    values = tuple(_as_point3(point) for point in points)
    if len(values) < 3:
        raise ValueError("surface patch needs at least three points")
    center = _centroid(values)

    # Use the strongest non-collinear local triangle instead of a polygon Newell
    # sum. A self-intersecting boundary may have a zero Newell normal even though
    # its individual segments still define a usable projection plane; validation
    # should then report the actual self-intersection rather than a misleading
    # "no direction" error.
    origin = values[0]
    best_normal = (0.0, 0.0, 0.0)
    best_length = 0.0
    for index in range(1, len(values) - 1):
        candidate = _cross(
            _sub(values[index], origin),
            _sub(values[index + 1], origin),
        )
        candidate_length = _length(candidate)
        if candidate_length > best_length:
            best_normal = candidate
            best_length = candidate_length
    normal = _normalize(best_normal)

    # Prefer the longest centered edge as the local U axis to make the result
    # deterministic while preserving the user's dominant drawing direction.
    candidates = []
    for first, second in zip(values, (*values[1:], values[0]), strict=False):
        edge = _sub(second, first)
        projected = _sub(edge, _scale(normal, _dot(edge, normal)))
        candidates.append(projected)
    u = _normalize(max(candidates, key=_length))
    v = _normalize(_cross(normal, u))

    points_2d = []
    max_deviation = 0.0
    for point in values:
        relative = _sub(point, center)
        coordinates = (_dot(relative, u), _dot(relative, v))
        points_2d.append((round(coordinates[0], 6), round(coordinates[1], 6)))
        max_deviation = max(max_deviation, abs(_dot(relative, normal)))

    patch = FlattenedSurfacePatch(tuple(points_2d), center, normal, float(max_deviation))
    return patch.validate(tolerance_mm)


def _target_source(target):
    source = getattr(target, "SourceObject", None)
    return source if source is not None else target


def _target_signature(target) -> str:
    source = _target_source(target)
    try:
        return repr(
            source_signature(
                source,
                float(getattr(target, "CollisionDeflection", 1.0)),
                float(getattr(target, "CollisionThickness", 0.0)),
            )
        )
    except (AttributeError, TypeError, ValueError, RuntimeError):
        return str(getattr(target, "Name", ""))


def _surface_target_from_document(doc, Gui):
    selection = tuple(Gui.Selection.getSelection()) if Gui is not None else ()
    for obj in selection:
        if str(getattr(obj, "TargetType", "")) in {"Mannequin", "FreeCAD Geometry"}:
            source = getattr(obj, "SourceObject", None)
            if source is not None:
                return obj, source
        if str(getattr(obj, "AvatarType", "")) == "ClothAvatar":
            return obj, obj
    for obj in getattr(doc, "Objects", ()):
        if str(getattr(obj, "TargetType", "")) in {"Mannequin", "FreeCAD Geometry"}:
            source = getattr(obj, "SourceObject", None)
            if source is not None:
                return obj, source
    for obj in getattr(doc, "Objects", ()):
        if str(getattr(obj, "AvatarType", "")) == "ClothAvatar":
            return obj, obj
    return None, None


def _hit_matches_target(view, x: int, y: int, target_source) -> bool:
    """Guard surface picking against unrelated visible geometry."""
    try:
        info = view.getObjectInfo(int(x), int(y))
    except (AttributeError, TypeError, ValueError, RuntimeError):
        info = None
    if not info:
        return True
    target_name = str(getattr(target_source, "Name", ""))
    target_label = str(getattr(target_source, "Label", ""))
    encoded = repr(info)
    return bool(target_name and target_name in encoded) or bool(target_label and target_label in encoded)


def pick_surface_point(view, x: int, y: int, target_source) -> SurfaceAnchor | None:
    """Pick a world-space point and normal from the selected surface target."""
    if not _hit_matches_target(view, x, y, target_source):
        return None
    viewer_factory = getattr(view, "getViewer", None)
    if not callable(viewer_factory):
        return None
    viewer = viewer_factory()
    picker = getattr(viewer, "pickPoint", None)
    if not callable(picker):
        return None
    try:
        picked = picker((int(x), int(y)))
    except (TypeError, ValueError, RuntimeError):
        try:
            picked = picker((int(x), int(y),))
        except (TypeError, ValueError, RuntimeError):
            return None
    if picked is None:
        return None
    point_getter = getattr(picked, "getPoint", None)
    normal_getter = getattr(picked, "getNormal", None)
    if not callable(point_getter) or not callable(normal_getter):
        return None
    try:
        point = _as_point3(point_getter())
        normal = _normalize(_as_point3(normal_getter()))
    except (TypeError, ValueError, RuntimeError):
        return None
    return SurfaceAnchor(point, normal)


def _append_anchor(
    anchors: list[SurfaceAnchor],
    anchor: SurfaceAnchor,
    minimum_spacing_mm: float,
) -> bool:
    if anchors and _length(_sub(anchor.point, anchors[-1].point)) < float(minimum_spacing_mm):
        return False
    anchors.append(anchor)
    return True


def close_surface_stroke(
    anchors: Sequence[SurfaceAnchor],
    tolerance_mm: float = DEFAULT_CLOSE_DISTANCE_MM,
) -> tuple[SurfaceAnchor, ...]:
    """Validate and normalize a closed surface boundary."""
    values = tuple(anchors)
    if len(values) < 4:
        raise ValueError("close the surface boundary with at least three distinct points")
    limit = max(0.0, float(tolerance_mm))
    distance = _length(_sub(values[-1].point, values[0].point))
    if distance > limit + 1e-9:
        raise ValueError(
            "surface boundary is open; return to the first surface point "
            f"within {limit:.1f} mm before finishing"
        )
    boundary = values[:-1]
    unique = {
        tuple(round(float(value), 6) for value in anchor.point)
        for anchor in boundary
    }
    if len(unique) < 3:
        raise ValueError("surface boundary needs at least three distinct points")
    return boundary


def create_surface_pen_object(doc, target, anchors: Sequence[SurfaceAnchor], label="3D Surface Draft"):
    """Persist a finished surface draft as a rebuildable authoring object."""
    import FreeCAD as App
    import Part

    values = close_surface_stroke(anchors)
    obj = doc.addObject("Part::FeaturePython", doc.getUniqueObjectName("SurfacePatternDraft"))
    obj.Label = label
    obj.addProperty("App::PropertyString", "AuthoringType", "3D Pattern").AuthoringType = (
        "ClothPattern.SurfacePen"
    )
    obj.addProperty("App::PropertyLinkGlobal", "Target", "3D Pattern").Target = target
    obj.addProperty("App::PropertyString", "TargetSignature", "3D Pattern").TargetSignature = (
        _target_signature(target)
    )
    obj.addProperty("App::PropertyString", "AnchorsJSON", "3D Pattern").AnchorsJSON = json.dumps(
        [anchor.to_json() for anchor in values],
        sort_keys=True,
        separators=(",", ":"),
    )
    obj.addProperty("App::PropertyString", "Status", "State").Status = "Surface draft"
    obj.addProperty("App::PropertyString", "FlatteningMode", "State").FlatteningMode = (
        "PlanarProjectionMVP"
    )
    obj.addProperty("App::PropertyLength", "PlanarTolerance", "State").PlanarTolerance = 8.0
    obj.addProperty("App::PropertyLength", "MaxDeviation", "State").MaxDeviation = 0.0
    obj.addProperty("App::PropertyLength", "ClosureTolerance", "State").ClosureTolerance = (
        DEFAULT_CLOSE_DISTANCE_MM
    )
    points = [App.Vector(*anchor.point) for anchor in values]
    points.append(points[0])
    obj.Shape = Part.makePolygon(points)
    return obj


def _add_surface_provenance(piece, surface_draft):
    if "SurfaceDraft" not in piece.PropertiesList:
        piece.addProperty("App::PropertyLinkGlobal", "SurfaceDraft", "3D Authoring")
    piece.SurfaceDraft = surface_draft
    if "SurfaceAuthoring" not in piece.PropertiesList:
        piece.addProperty("App::PropertyString", "SurfaceAuthoring", "3D Authoring")
    piece.SurfaceAuthoring = "ClothPattern.SurfacePen"


def extract_surface_draft_to_pattern(surface_draft, tolerance_mm=8.0, name=None):
    """Create a native Sketcher-backed PatternPiece from a persisted surface draft."""
    import FreeCAD as App

    target = getattr(surface_draft, "Target", None)
    if target is None:
        raise ValueError("surface draft has no target")
    expected = str(getattr(surface_draft, "TargetSignature", ""))
    if expected and expected != _target_signature(target):
        surface_draft.Status = "Stale surface target"
        raise ValueError("surface draft target changed; redraw the surface before extraction")
    try:
        anchors = tuple(
            SurfaceAnchor.from_json(value)
            for value in json.loads(str(getattr(surface_draft, "AnchorsJSON", "[]")))
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("surface draft contains invalid anchor data") from exc
    closure_tolerance = float(
        getattr(surface_draft, "ClosureTolerance", DEFAULT_CLOSE_DISTANCE_MM)
    )
    anchors = close_surface_stroke(anchors, closure_tolerance)
    patch = flatten_surface_patch([anchor.point for anchor in anchors], tolerance_mm)
    surface_draft.PlanarTolerance = float(tolerance_mm)
    surface_draft.MaxDeviation = float(patch.max_deviation_mm)
    from freecad_cloth.pattern.PatternModel import PatternPiece
    from freecad_cloth.pattern.PatternObjects import add_pattern_piece
    from freecad_cloth.pattern.PatternSketch import create_sketch_for_piece

    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a FreeCAD document before extracting a pattern")
    existing_count = len(
        [obj for obj in doc.Objects if getattr(obj, "PatternType", "") == "PatternPiece"]
    )
    piece_name = str(name or f"Surface Piece {existing_count + 1}")
    piece_id = f"pattern-piece-surface-{existing_count + 1}"
    points = list(patch.points)
    # Translate the flattened polygon to positive document coordinates without
    # changing its geometry. This keeps the default Sketcher view convenient.
    min_x = min(point[0] for point in points)
    min_y = min(point[1] for point in points)
    offset = (min_x, min_y)
    shifted = [(round(x - offset[0], 6), round(y - offset[1], 6)) for x, y in points]
    pattern = PatternPiece(piece_name, shifted, id=piece_id)
    obj = add_pattern_piece(doc, pattern)
    sketch = create_sketch_for_piece(pattern, doc)
    obj.GeometryMode = "Sketch"
    _add_surface_provenance(obj, surface_draft)
    surface_draft.Visibility = False
    sketch.Visibility = True
    surface_draft.Status = "Extracted"
    doc.recompute()
    return obj


def _surface_stroke_object(doc, target, anchors):
    return create_surface_pen_object(doc, target, anchors)


class SurfacePenController:
    """Interactive viewport controller for the Cloth 3D Pattern Pen."""

    SAMPLE_PIXEL_THRESHOLD = 4.0
    SAMPLE_DISTANCE_MM = 3.0
    CLOSE_DISTANCE_MM = DEFAULT_CLOSE_DISTANCE_MM

    def __init__(self, target, target_source, status_callback=None):
        self.App, self.Gui = self._modules()
        self.target = target
        self.target_source = target_source
        self.status_callback = status_callback or (lambda _message: None)
        self.view = None
        self.anchors: list[SurfaceAnchor] = []
        self._drawing = False
        self._last_screen = None
        self._mouse_callback = None
        self._location_callback = None
        self._overlay = None

    @staticmethod
    def _modules():
        import FreeCAD as App
        import FreeCADGui as Gui

        return App, Gui

    def _status(self, message):
        self.status_callback(str(message))

    def _pick(self, position):
        return pick_surface_point(self.view, int(position[0]), int(position[1]), self.target_source)

    def _update_overlay(self):
        if self.view is None:
            return
        try:
            from pivy import coin

            scene = self.view.getSceneGraph()
            if self._overlay is not None:
                scene.removeChild(self._overlay)
            self._overlay = coin.SoSeparator()
            coords = coin.SoCoordinate3()
            coords.point.setValues(
                0,
                len(self.anchors),
                [coin.SbVec3f(*anchor.point) for anchor in self.anchors],
            )
            line = coin.SoLineSet()
            line.numVertices.setValue(len(self.anchors))
            material = coin.SoBaseColor()
            material.rgb = (0.95, 0.55, 0.10)
            width = coin.SoDrawStyle()
            width.lineWidth = 4.0
            self._overlay.addChild(material)
            self._overlay.addChild(width)
            self._overlay.addChild(coords)
            self._overlay.addChild(line)
            scene.addChild(self._overlay)
        except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):
            self._overlay = None

    def _event_position(self, info):
        value = info.get("Position", (0, 0))
        try:
            return float(value[0]), float(value[1])
        except (TypeError, ValueError, IndexError):
            return None

    def activate(self):
        """Install viewport callbacks and begin interactive surface drawing."""
        if self.view is not None:
            return
        active = self.Gui.activeDocument()
        if active is None:
            raise RuntimeError("an active FreeCAD document is required")
        self.view = active.activeView()
        if self.view is None:
            raise RuntimeError("an active FreeCAD 3D view is required")
        self._mouse_callback = self.view.addEventCallback(
            "SoMouseButtonEvent", self._mouse_event
        )
        self._location_callback = self.view.addEventCallback(
            "SoLocation2Event", self._location_event
        )
        self._status(
            "3D Pattern Pen: drag on the mannequin surface. Release to lift the pen; "
            "use Finish Stroke to extract."
        )

    def deactivate(self):
        """Remove viewport callbacks and discard transient drawing state."""
        if self.view is None:
            return
        try:
            if self._mouse_callback is not None:
                self.view.removeEventCallback("SoMouseButtonEvent", self._mouse_callback)
            if self._location_callback is not None:
                self.view.removeEventCallback("SoLocation2Event", self._location_callback)
            if self._overlay is not None:
                self.view.getSceneGraph().removeChild(self._overlay)
        except (AttributeError, RuntimeError):
            pass
        self._mouse_callback = None
        self._location_callback = None
        self._overlay = None
        self.view = None
        self._drawing = False
        self._last_screen = None

    def clear(self):
        """Clear the current stroke and remove its viewport overlay."""
        self.anchors.clear()
        self._drawing = False
        self._last_screen = None
        self._update_overlay()
        self._status("Surface stroke cleared.")

    def _mouse_event(self, info):
        position = self._event_position(info)
        if position is None:
            return
        state = str(info.get("State", "")).upper()
        button = str(info.get("Button", "BUTTON1")).upper()
        if button not in {"BUTTON1", "LEFT"}:
            return
        if state == "DOWN":
            anchor = self._pick(position)
            if anchor is None:
                self._status("Pointer is not over the selected mannequin surface.")
                return
            self._drawing = True
            self._last_screen = position
            _append_anchor(self.anchors, anchor, self.SAMPLE_DISTANCE_MM)
            self._update_overlay()
        elif state == "UP":
            self._drawing = False
            self._last_screen = None
            self._status(
                f"Surface stroke: {len(self.anchors)} samples. Continue drawing or Finish Stroke."
            )

    def _location_event(self, info):
        if not self._drawing:
            return
        position = self._event_position(info)
        if position is None:
            return
        if self._last_screen is not None:
            dx = position[0] - self._last_screen[0]
            dy = position[1] - self._last_screen[1]
            if math.hypot(dx, dy) < self.SAMPLE_PIXEL_THRESHOLD:
                return
        anchor = self._pick(position)
        if anchor is None:
            return
        if _append_anchor(self.anchors, anchor, self.SAMPLE_DISTANCE_MM):
            self._last_screen = position
            self._update_overlay()

    def finish(self, tolerance_mm=8.0, name=None):
        """Validate the stroke and create a native Sketcher-backed pattern piece."""
        if self._drawing:
            self._drawing = False
            self._last_screen = None
        if len(self.anchors) < 3:
            raise ValueError("draw at least three surface points before finishing")
        closed = close_surface_stroke(self.anchors, self.CLOSE_DISTANCE_MM)
        document = self.App.ActiveDocument
        if document is None:
            raise RuntimeError("an active document is required")
        simplified = simplify_polyline([anchor.point for anchor in closed], 1.0)
        if len(simplified) < 3:
            raise ValueError("surface stroke simplified to fewer than three points")
        by_point = {tuple(round(value, 6) for value in anchor.point): anchor for anchor in closed}
        anchors = tuple(
            by_point.get(tuple(round(value, 6) for value in point))
            or SurfaceAnchor(point, closed[min(index, len(closed) - 1)].normal)
            for index, point in enumerate(simplified)
        )
        # Validate the same bounded planar contract before any persistent object
        # is created. Extraction itself repeats the target-signature check.
        patch = flatten_surface_patch([anchor.point for anchor in anchors], tolerance_mm)
        draft = _surface_stroke_object(document, self.target, anchors)
        draft.PlanarTolerance = float(tolerance_mm)
        draft.MaxDeviation = float(patch.max_deviation_mm)
        piece = extract_surface_draft_to_pattern(draft, tolerance_mm=tolerance_mm, name=name)
        self.clear()
        self._status(
            f"Created native Sketcher PatternPiece '{piece.Label}' "
            f"from a {len(anchors)}-point surface stroke."
        )
        return piece


class SurfacePenTaskPanel:
    """Small native FreeCAD task panel controlling the viewport pen."""

    def __init__(self, controller):
        _App, _Gui, QtWidgets = self._modules()
        self.controller = controller
        self.form = QtWidgets.QWidget()
        outer = QtWidgets.QVBoxLayout(self.form)

        outer.addWidget(
            QtWidgets.QLabel(
                "<b>3D Pattern Pen</b><br>"
                "Drag directly on the visible mannequin surface to trace a closed piece. "
                "Lift the mouse to continue later; the same stroke is accumulated."
            )
        )

        controls = QtWidgets.QFormLayout()
        self.tolerance = QtWidgets.QDoubleSpinBox()
        self.tolerance.setRange(0.5, 100.0)
        self.tolerance.setDecimals(1)
        self.tolerance.setSuffix(" mm")
        self.tolerance.setValue(8.0)
        controls.addRow("Planar deviation limit", self.tolerance)
        outer.addLayout(controls)

        self.status = QtWidgets.QLabel("Waiting for surface input.")
        self.status.setWordWrap(True)
        outer.addWidget(self.status)

        buttons = QtWidgets.QHBoxLayout()
        self.finish_button = QtWidgets.QPushButton("Finish Stroke → Pattern")
        self.finish_button.clicked.connect(self.finish)
        self.clear_button = QtWidgets.QPushButton("Clear")
        self.clear_button.clicked.connect(self.controller.clear)
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        buttons.addWidget(self.finish_button)
        buttons.addWidget(self.clear_button)
        buttons.addWidget(self.cancel_button)
        outer.addLayout(buttons)

    @staticmethod
    def _modules():
        try:
            from PySide import QtWidgets
        except ImportError:
            from PySide2 import QtWidgets
        return __import__("FreeCAD"), __import__("FreeCADGui"), QtWidgets

    def finish(self):
        """Finish extraction using the task-panel planar tolerance."""
        try:
            self.controller.finish(float(self.tolerance.value()))
        except (RuntimeError, ValueError) as exc:
            self.status.setText(str(exc))
            return False
        self.accept()
        return True

    def accept(self):
        """Close the task panel after committing the current surface draft."""
        self.controller.deactivate()
        with contextlib.suppress(AttributeError, RuntimeError):
            self.controller.Gui.Control.closeDialog()
        return True

    def reject(self):
        """Cancel surface drawing and close the task panel without extraction."""
        self.controller.clear()
        self.controller.deactivate()
        with contextlib.suppress(AttributeError, RuntimeError):
            self.controller.Gui.Control.closeDialog()
        return True

    def getStandardButtons(self):
        """Use no standard dialog buttons; actions are explicit in the panel."""
        try:
            from PySide import QtWidgets
        except ImportError:
            from PySide2 import QtWidgets
        return QtWidgets.QDialogButtonBox.NoButton


def start_surface_pen():
    """Start the public Cloth Pattern 3D Surface Pen command."""
    import FreeCAD as App
    import FreeCADGui as Gui

    doc = App.ActiveDocument
    if doc is None:
        raise RuntimeError("open a garment document before starting the 3D Pattern Pen")
    target, source = _surface_target_from_document(doc, Gui)
    if target is None or source is None:
        raise ValueError(
            "select a mannequin/drape target or create one before starting the 3D Pattern Pen"
        )
    controller = SurfacePenController(target, source)
    panel = SurfacePenTaskPanel(controller)
    panel.controller.status_callback = panel.status.setText
    controller.activate()
    Gui.Control.showDialog(panel)
    return panel


__all__ = [
    "FlattenedSurfacePatch",
    "SurfaceAnchor",
    "SurfacePenController",
    "SurfacePenTaskPanel",
    "extract_surface_draft_to_pattern",
    "flatten_surface_patch",
    "close_surface_stroke",
    "polygon_area_2d",
    "polygon_self_intersects",
    "simplify_polyline",
    "start_surface_pen",
]
