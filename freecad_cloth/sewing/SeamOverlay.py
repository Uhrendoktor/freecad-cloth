"""Transient viewport overlays for semantic sewing relationships.

Unlike view-property color assignment, this module draws an explicit, disposable
Coin3D overlay: both sides share a stable identity color, each side carries the
same short seam label plus an A/B suffix, and direction/notch marks expose
correspondence. No overlay node is persisted in the FreeCAD document.
"""

from __future__ import annotations

from collections.abc import Iterable
from hashlib import sha1
from types import ModuleType

from freecad_cloth.gui import register_workbench_deactivation_callback
from freecad_cloth.shared.seam_colors import (
    register_seam_refresh_callback,
    seam_color_map,
    set_seam_color_highlighting_enabled,
)

_ACTIVE_CONTROLLER = None
_REFRESH_PENDING = False
_PENDING_DOCUMENT = None
_OVERLAY_ENABLED = False


def _read_preference(name: str, default: bool) -> bool:
    try:
        import FreeCAD as App

        params = App.ParamGet("User parameter:BaseApp/Preferences/Mod/Cloth")
        return bool(params.GetBool(name, bool(default)))
    except (ImportError, AttributeError, RuntimeError, TypeError):
        return bool(default)


def _write_preference(name: str, value: bool) -> None:
    try:
        import FreeCAD as App

        params = App.ParamGet("User parameter:BaseApp/Preferences/Mod/Cloth")
        params.SetBool(name, bool(value))
    except (ImportError, AttributeError, RuntimeError, TypeError):
        pass


_HIGHLIGHTS_ENABLED = _read_preference("ShowSeamColorHighlights", True)
_RESPECT_DEPTH_OCCLUSION = _read_preference("SeamOverlayRespectDepth", True)
set_seam_color_highlighting_enabled(_HIGHLIGHTS_ENABLED)


def seam_display_labels(seam_ids: Iterable[object]) -> dict[str, str]:
    """Return stable, short, unique viewport labels for semantic seam IDs."""
    identities = sorted({str(value).strip() for value in seam_ids})
    if any(not identity for identity in identities):
        raise ValueError("seam identity must not be empty")

    labels = {
        identity: "S" + identity[5:]
        for identity in identities
        if identity.startswith("seam-") and identity[5:].isdigit()
    }
    hashed = {
        identity: sha1(identity.encode("utf-8")).hexdigest().upper()
        for identity in identities
        if identity not in labels
    }
    widths = {identity: 6 for identity in hashed}
    while True:
        candidates = {
            identity: "S" + hashed[identity][:widths[identity]]
            for identity in hashed
        }
        by_label: dict[str, list[str]] = {}
        for identity, label in candidates.items():
            by_label.setdefault(label, []).append(identity)
        collisions = [members for members in by_label.values() if len(members) > 1]
        if not collisions:
            labels.update(candidates)
            break
        for members in collisions:
            for identity in members:
                widths[identity] = min(widths[identity] + 2, len(hashed[identity]))
        # SHA-1 is long enough that the terminal collision path is only a defensive
        # guard; retain unique labels even if all digest characters collide.
        if any(widths[identity] >= len(hashed[identity]) for group in collisions for identity in group):
            labels.update(candidates)
            for identity in identities:
                if labels[identity] in {labels[other] for other in labels if other != identity}:
                    labels[identity] += "-" + str(identities.index(identity) + 1)
            break
    return labels


def should_show_seam_label(seam_id: object, hovered_seam_id: object) -> bool:
    """Show labels only for the one semantic seam currently under the pointer."""
    identity = str(seam_id).strip()
    hovered = str(hovered_seam_id).strip()
    return bool(hovered) and identity == hovered


def _coin_modules() -> ModuleType | None:
    try:
        from pivy import coin
    except ImportError:
        return None
    return coin


def _xyz(point: object) -> tuple[float, float, float]:
    if hasattr(point, "x"):
        return float(point.x), float(point.y), float(point.z)
    value = tuple(point)  # type: ignore[arg-type]
    if len(value) != 3:
        raise ValueError("seam overlay points must contain three coordinates")
    return float(value[0]), float(value[1]), float(value[2])


def _label_anchor(
    points: Iterable[object],
    index: int,
    offset: float = 14.0,
    lane: int = 0,
    lane_spacing: float = 36.0,
) -> tuple[float, float, float]:
    """Offset a label from its edge and into a deterministic seam-specific lane."""
    coordinates = [_xyz(point) for point in points]
    if not coordinates:
        raise ValueError("label anchor requires at least one point")
    center_index = max(0, min(int(index), len(coordinates) - 1))
    point = coordinates[center_index]
    before = coordinates[max(0, center_index - 1)]
    after = coordinates[min(len(coordinates) - 1, center_index + 1)]
    dx = after[0] - before[0]
    dy = after[1] - before[1]
    length = (dx * dx + dy * dy) ** 0.5
    lane_shift = int(lane) * float(lane_spacing)
    if length <= 1e-9:
        return (point[0], point[1] + lane_shift, point[2])
    return (
        point[0] - dy / length * float(offset),
        point[1] + dx / length * float(offset) + lane_shift,
        point[2],
    )


def _subtract(
    a: tuple[float, float, float], b: tuple[float, float, float]
) -> tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(
    a: tuple[float, float, float], b: tuple[float, float, float]
) -> tuple[float, float, float]:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(
    vector: tuple[float, float, float], factor: float
) -> tuple[float, float, float]:
    return (vector[0] * factor, vector[1] * factor, vector[2] * factor)


def _unit(
    vector: tuple[float, float, float]
) -> tuple[float, float, float] | None:
    length = sum(float(value) * float(value) for value in vector) ** 0.5
    if length <= 1e-9:
        return None
    return _scale(vector, 1.0 / length)


def _cross(
    a: tuple[float, float, float], b: tuple[float, float, float]
) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _side_segments(
    points: Iterable[object],
) -> list[list[tuple[float, float, float]]]:
    """Produce an edge polyline plus directional arrow and notch strokes."""
    coords = [_xyz(point) for point in points]
    if len(coords) < 2:
        return []
    segments = [coords]
    middle = len(coords) // 2
    tangent = _unit(_subtract(coords[min(middle + 1, len(coords) - 1)], coords[max(0, middle - 1)]))
    if tangent is None:
        return segments
    perpendicular = _unit(_cross(tangent, (0.0, 0.0, 1.0)))
    if perpendicular is None:
        perpendicular = _unit(_cross(tangent, (0.0, 1.0, 0.0)))
    if perpendicular is None:
        return segments

    span = sum(
        sum(value * value for value in _subtract(right, left)) ** 0.5
        for left, right in zip(coords, coords[1:])
    )
    notch_half = min(4.0, max(1.5, span * 0.045))
    notch_center = coords[middle]
    segments.append([
        _add(notch_center, _scale(perpendicular, -notch_half)),
        _add(notch_center, _scale(perpendicular, notch_half)),
    ])

    if len(coords) >= 3:
        arrow_index = max(1, min(len(coords) - 2, round((len(coords) - 1) * 0.68)))
        tip = coords[arrow_index]
        arrow_tangent = _unit(_subtract(coords[arrow_index + 1], coords[arrow_index - 1]))
    else:
        tip = coords[-1]
        arrow_tangent = _unit(_subtract(coords[-1], coords[0]))
    if arrow_tangent is not None:
        arrow_perpendicular = _unit(_cross(arrow_tangent, (0.0, 0.0, 1.0)))
        if arrow_perpendicular is None:
            arrow_perpendicular = perpendicular
        arrow_length = min(5.0, max(2.0, span * 0.10))
        wing = arrow_length * 0.56
        base = _add(tip, _scale(arrow_tangent, -arrow_length))
        segments.append([tip, _add(base, _scale(arrow_perpendicular, wing))])
        segments.append([tip, _add(base, _scale(arrow_perpendicular, -wing))])
    return segments


def _add_line_groups(
    parent: object,
    coin: ModuleType,
    groups: list[list[tuple[float, float, float]]],
    rgb: tuple[float, float, float],
    width: float,
) -> None:
    line_groups = [group for group in groups if len(group) >= 2]
    if not line_groups:
        return
    separator = coin.SoSeparator()
    draw_style = coin.SoDrawStyle()
    draw_style.lineWidth = float(width)
    color = coin.SoBaseColor()
    color.rgb = tuple(float(channel) for channel in rgb)
    coordinates = [point for group in line_groups for point in group]
    coord = coin.SoCoordinate3()
    coord.point.setValues(
        0,
        len(coordinates),
        [coin.SbVec3f(*_xyz(point)) for point in coordinates],
    )
    line_set = coin.SoLineSet()
    line_set.numVertices.setValues(0, len(line_groups), [len(group) for group in line_groups])
    separator.addChild(draw_style)
    separator.addChild(color)
    separator.addChild(coord)
    separator.addChild(line_set)
    parent.addChild(separator)


def _depth_buffer(coin: ModuleType, respect_depth: bool) -> object:
    """Configure depth testing without losing coplanar seam lines to z-fighting."""
    depth = coin.SoDepthBuffer()
    depth.test = bool(respect_depth)
    depth.write = False
    if respect_depth:
        # Solver seam points can lie exactly on cloth triangles. LEQUAL preserves
        # those lines while still hiding fragments behind nearer geometry.
        less_equal = getattr(coin.SoDepthBuffer, "LEQUAL", None)
        if less_equal is not None:
            depth.function = less_equal
    return depth


def _add_label(
    parent: object,
    coin: ModuleType,
    point: object,
    label: str,
    rgb: tuple[float, float, float],
    respect_depth: bool = True,
) -> None:
    """Add a label that either obeys scene occlusion or is explicitly foregrounded."""
    annotation_type = (
        coin.SoSeparator
        if respect_depth
        else getattr(coin, "SoAnnotation", coin.SoSeparator)
    )
    annotation = annotation_type()
    depth = _depth_buffer(coin, respect_depth)
    color = coin.SoBaseColor()
    color.rgb = tuple(float(channel) for channel in rgb)
    transform = coin.SoTransform()
    x, y, z = _xyz(point)
    transform.translation.setValue(coin.SbVec3f(x, y, z))
    font = coin.SoFont()
    font.size.setValue(16.0)
    text = coin.SoText2()
    text.string.setValue(str(label))
    annotation.addChild(depth)
    annotation.addChild(color)
    annotation.addChild(transform)
    annotation.addChild(font)
    annotation.addChild(text)
    parent.addChild(annotation)


def _canonical_seams(document: object) -> list[object]:
    seams = []
    for obj in getattr(document, "Objects", ()):
        identity = str(getattr(obj, "SeamId", "")).strip()
        if not identity:
            continue
        if getattr(obj, "PatternA", None) is None or getattr(obj, "PatternB", None) is None:
            continue
        if str(getattr(obj, "Status", "Valid")) != "Valid":
            continue
        view = getattr(obj, "ViewObject", None)
        if view is not None and not bool(getattr(view, "Visibility", True)):
            continue
        seams.append(obj)
    return seams


def _simulation_seam_geometry(
    document: object,
) -> dict[
    str,
    tuple[
        list[tuple[float, float, float]],
        list[tuple[float, float, float]],
        list[list[tuple[float, float, float]]],
    ],
]:
    """Resolve current draped seam sides from exact solver particle provenance."""
    for scene in getattr(document, "Objects", ()):
        proxy = getattr(scene, "Proxy", None)
        panels = tuple(getattr(scene, "DrapePanels", ()) or ())
        if not panels or not any(
            bool(getattr(getattr(panel, "ViewObject", None), "Visibility", True))
            for panel in panels
        ):
            continue
        try:
            seam_pairs = getattr(proxy, "seam_stitch_pairs", {})
            backend = getattr(proxy, "backend", None)
            position_reader = getattr(backend, "positions", None)
            if not seam_pairs or not callable(position_reader):
                continue
            positions = tuple(position_reader())
        except (AttributeError, RuntimeError, TypeError, ValueError):
            continue
        if not positions:
            continue

        resolved: dict[
            str,
            tuple[
                list[tuple[float, float, float]],
                list[tuple[float, float, float]],
                list[list[tuple[float, float, float]]],
            ],
        ] = {}
        for raw_seam_id, raw_pairs in seam_pairs.items():
            seam_id = str(raw_seam_id).strip()
            if not seam_id:
                continue
            side_a: list[tuple[float, float, float]] = []
            side_b: list[tuple[float, float, float]] = []
            connectors: list[list[tuple[float, float, float]]] = []
            for raw_pair in raw_pairs:
                try:
                    if len(raw_pair) != 2:
                        continue
                    index_a, index_b = int(raw_pair[0]), int(raw_pair[1])
                    if not (
                        0 <= index_a < len(positions)
                        and 0 <= index_b < len(positions)
                    ):
                        continue
                    point_a, point_b = _xyz(positions[index_a]), _xyz(positions[index_b])
                except (IndexError, TypeError, ValueError):
                    continue
                side_a.append(point_a)
                side_b.append(point_b)
                connectors.append([point_a, point_b])
            if len(side_a) >= 2 and len(side_b) >= 2:
                resolved[seam_id] = (side_a, side_b, connectors)
        if resolved:
            return resolved
    return {}


def _seam_id_at_position(document: object, view: object, position: object) -> str:
    """Map a viewport hover to the seam using the underlying pattern edge hit."""
    try:
        x, y = int(position[0]), int(position[1])  # type: ignore[index]
    except (IndexError, TypeError, ValueError):
        return ""

    hits: list[dict[str, object]] = []
    for getter_name in ("getObjectsInfo", "getObjectInfo"):
        getter = getattr(view, getter_name, None)
        if not callable(getter):
            continue
        try:
            result = getter((x, y))
        except TypeError:
            try:
                result = getter(x, y)
            except (AttributeError, RuntimeError, TypeError, ValueError):
                continue
        except (AttributeError, RuntimeError, ValueError):
            continue
        if isinstance(result, dict):
            hits.extend([result])
        elif isinstance(result, (list, tuple)):
            hits.extend(item for item in result if isinstance(item, dict))
        if any(str(hit.get("Component", "")).startswith("Edge") for hit in hits):
            break

    get_object = getattr(document, "getObject", None)
    seams = _canonical_seams(document)
    for hit in hits:
        component = str(hit.get("Component", hit.get("component", ""))).strip()
        if not component.startswith("Edge") or not component[4:].isdigit():
            continue
        edge_index = int(component[4:]) - 1
        if edge_index < 0:
            continue
        object_name = str(hit.get("Object", hit.get("object", ""))).strip()
        piece = get_object(object_name) if callable(get_object) and object_name else None
        if piece is None or str(getattr(piece, "PatternType", "")) != "PatternPiece":
            continue
        piece_name = str(getattr(piece, "Name", object_name))
        for seam in seams:
            for side in ("A", "B"):
                seam_piece = getattr(seam, "Pattern" + side, None)
                if seam_piece is None or str(getattr(seam_piece, "Name", "")) != piece_name:
                    continue
                try:
                    from freecad_cloth.sewing.SewingObjects import _resolved_edge

                    if int(_resolved_edge(seam_piece, seam, side)) == edge_index:
                        return str(getattr(seam, "SeamId", "")).strip()
                except (AttributeError, IndexError, KeyError, RuntimeError, TypeError, ValueError):
                    continue
    return ""


class SeamOverlayController:
    """Own one transient overlay tree for the active FreeCAD 3D view."""

    def __init__(self, view: object, document: object) -> None:
        self.view = view
        self.document = document
        self.scene_graph = None
        self.root = None
        self.rendered_seam_ids: tuple[str, ...] = ()
        self.rendered_label_seam_ids: tuple[str, ...] = ()
        self.hovered_seam_id = ""
        self._location_callback = None
        self.last_error = ""
        self._attach()

    def _attach(self) -> None:
        coin = _coin_modules()
        if coin is None:
            self.last_error = "Pivy Coin is unavailable"
            return
        try:
            self.scene_graph = self.view.getSceneGraph()
            self.root = coin.SoSeparator()
            self.root.setName("ClothSemanticSeamOverlay")
            self.scene_graph.addChild(self.root)
            try:
                self._location_callback = self.view.addEventCallback(
                    "SoLocation2Event", self._location_event
                )
            except (AttributeError, RuntimeError, TypeError):
                self._location_callback = None
        except (AttributeError, RuntimeError, TypeError) as exc:
            self.scene_graph = None
            self.root = None
            self.last_error = str(exc)

    def _location_event(self, event_info: object) -> None:
        """Refresh the transient label when the hovered semantic seam changes."""
        if not _OVERLAY_ENABLED or not _HIGHLIGHTS_ENABLED:
            return
        position = event_info.get("Position") if isinstance(event_info, dict) else None
        if position is None:
            return
        seam_id = _seam_id_at_position(self.document, self.view, position)
        if seam_id == self.hovered_seam_id:
            return
        self.hovered_seam_id = seam_id
        schedule_seam_overlay_refresh(self.document)

    def deactivate(self) -> None:
        """Remove only this controller's transient Coin node and hover callback."""
        if self._location_callback is not None:
            try:
                self.view.removeEventCallback("SoLocation2Event", self._location_callback)
            except (AttributeError, RuntimeError, TypeError):
                pass
        self._location_callback = None
        if self.scene_graph is not None and self.root is not None:
            try:
                self.scene_graph.removeChild(self.root)
            except (AttributeError, RuntimeError, TypeError):
                pass
        self.scene_graph = None
        self.root = None
        self.rendered_seam_ids = ()

    def refresh(
        self,
        document: object | None = None,
        active_seam_id: str = "",
        prefer_simulation: bool = False,
        hovered_seam_id: str = "",
    ) -> None:
        """Rebuild overlay geometry and show a label only for the hovered seam."""
        if document is not None:
            self.document = document
        self.hovered_seam_id = str(hovered_seam_id or "").strip()
        if self.root is None or self.scene_graph is None:
            return
        coin = _coin_modules()
        if coin is None:
            self.last_error = "Pivy Coin is unavailable"
            return

        while self.root.getNumChildren():
            self.root.removeChild(0)
        self.root.addChild(_depth_buffer(coin, _RESPECT_DEPTH_OCCLUSION))

        seams = _canonical_seams(self.document)
        ids = [str(seam.SeamId).strip() for seam in seams]
        colors = seam_color_map(ids)
        labels = seam_display_labels(ids)
        rendered_ids: list[str] = []
        rendered_label_ids: list[str] = []
        self.rendered_seam_ids = ()
        self.rendered_label_seam_ids = ()
        self.last_error = ""

        simulated = _simulation_seam_geometry(self.document) if prefer_simulation else {}
        if simulated:
            colors = seam_color_map(simulated.keys())
            labels = seam_display_labels(simulated.keys())
            simulation_rendered_ids: list[str] = []
            for label_lane, (identity, (points_a, points_b, connectors)) in enumerate(sorted(simulated.items())):
                focused = identity == str(active_seam_id)
                width = 5.5 if focused else 3.5
                side_group = coin.SoSeparator()
                # Respect occlusion by default; the UI can explicitly opt into
                # always-on-top rendering for crowded editing/simulation views.
                side_group.addChild(_depth_buffer(coin, _RESPECT_DEPTH_OCCLUSION))
                color = colors[identity]
                _add_line_groups(side_group, coin, _side_segments(points_a), color, width)
                _add_line_groups(side_group, coin, _side_segments(points_b), color, width)
                _add_line_groups(side_group, coin, connectors, color, 1.25)
                label_a = _label_anchor(points_a, len(points_a) // 3, lane=label_lane)
                label_b = _label_anchor(points_b, (len(points_b) * 2) // 3, lane=label_lane)
                if should_show_seam_label(identity, hovered_seam_id):
                    _add_label(
                        side_group, coin, label_a, labels[identity] + "-A", color,
                        respect_depth=_RESPECT_DEPTH_OCCLUSION,
                    )
                    _add_label(
                        side_group, coin, label_b, labels[identity] + "-B", color,
                        respect_depth=_RESPECT_DEPTH_OCCLUSION,
                    )
                    rendered_label_ids.append(identity)
                self.root.addChild(side_group)
                simulation_rendered_ids.append(identity)
            self.rendered_seam_ids = tuple(sorted(simulation_rendered_ids))
            self.rendered_label_seam_ids = tuple(sorted(set(rendered_label_ids)))
            return

        if not seams:
            return

        from freecad_cloth.sewing.SewingObjects import _edge_samples, _resolved_edge

        label_lanes = {identity: lane for lane, identity in enumerate(sorted(ids))}
        for seam in seams:
            identity = str(seam.SeamId).strip()
            label_lane = label_lanes[identity]
            piece_a = seam.PatternA
            piece_b = seam.PatternB
            try:
                edge_a = _resolved_edge(piece_a, seam, "A")
                edge_b = _resolved_edge(piece_b, seam, "B")
                points_a = _edge_samples(
                    piece_a, edge_a, float(seam.StartA), float(seam.EndA), 17,
                    z=0.75, transform_to_world=True,
                )
                points_b = _edge_samples(
                    piece_b, edge_b, float(seam.StartB), float(seam.EndB), 17,
                    z=0.75, transform_to_world=True,
                )
                if bool(getattr(seam, "ReversedB", False)):
                    points_b.reverse()
            except (AttributeError, IndexError, KeyError, RuntimeError, TypeError, ValueError):
                continue
            color = colors[identity]
            focused = identity == str(active_seam_id)
            width = 5.5 if focused else 3.5
            side_group = coin.SoSeparator()
            _add_line_groups(side_group, coin, _side_segments(points_a), color, width)
            _add_line_groups(side_group, coin, _side_segments(points_b), color, width)
            label_a = _label_anchor(points_a, len(points_a) // 3, lane=label_lane)
            label_b = _label_anchor(points_b, (len(points_b) * 2) // 3, lane=label_lane)
            if should_show_seam_label(identity, hovered_seam_id):
                _add_label(
                    side_group, coin, label_a, labels[identity] + "-A", color,
                    respect_depth=_RESPECT_DEPTH_OCCLUSION,
                )
                _add_label(
                    side_group, coin, label_b, labels[identity] + "-B", color,
                    respect_depth=_RESPECT_DEPTH_OCCLUSION,
                )
                rendered_label_ids.append(identity)
            self.root.addChild(side_group)
            rendered_ids.append(identity)
        self.rendered_seam_ids = tuple(sorted(set(rendered_ids)))
        self.rendered_label_seam_ids = tuple(sorted(set(rendered_label_ids)))


def _selected_seam_id(gui: object, document: object) -> str:
    try:
        for selected in gui.Selection.getSelection():
            identity = str(getattr(selected, "SeamId", "")).strip()
            if identity and selected in getattr(document, "Objects", ()):
                return identity
    except (AttributeError, RuntimeError, TypeError):
        pass
    return ""


def _release_controller() -> None:
    """Remove the current view node without disabling future refreshes."""
    global _ACTIVE_CONTROLLER
    if _ACTIVE_CONTROLLER is not None:
        _ACTIVE_CONTROLLER.deactivate()
    _ACTIVE_CONTROLLER = None


def seam_highlights_enabled() -> bool:
    """Return whether transient seam color highlights are enabled."""
    return bool(_HIGHLIGHTS_ENABLED)


def set_seam_highlights_enabled(enabled: bool) -> bool:
    """Persist the highlight visibility setting and apply it to the active view."""
    global _HIGHLIGHTS_ENABLED
    _HIGHLIGHTS_ENABLED = bool(enabled)
    _write_preference("ShowSeamColorHighlights", _HIGHLIGHTS_ENABLED)
    set_seam_color_highlighting_enabled(_HIGHLIGHTS_ENABLED)
    try:
        import FreeCAD as App

        if App.ActiveDocument is not None:
            from freecad_cloth.sewing.SewingView import apply_seam_colors

            apply_seam_colors(App.ActiveDocument.Objects)
    except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):
        pass
    if not _HIGHLIGHTS_ENABLED:
        _release_controller()
    elif _OVERLAY_ENABLED:
        refresh_seam_overlay()
    return _HIGHLIGHTS_ENABLED


def seam_overlay_respects_depth() -> bool:
    """Return whether seam lines and labels are hidden by foreground geometry."""
    return bool(_RESPECT_DEPTH_OCCLUSION)


def set_seam_overlay_respect_depth(enabled: bool) -> bool:
    """Persist the overlay's depth/occlusion mode and refresh visible geometry."""
    global _RESPECT_DEPTH_OCCLUSION
    _RESPECT_DEPTH_OCCLUSION = bool(enabled)
    _write_preference("SeamOverlayRespectDepth", _RESPECT_DEPTH_OCCLUSION)
    if _OVERLAY_ENABLED and _HIGHLIGHTS_ENABLED:
        refresh_seam_overlay()
    return _RESPECT_DEPTH_OCCLUSION


def refresh_seam_overlay(document: object | None = None) -> SeamOverlayController | None:
    """Attach or refresh the current view's overlay; safe outside a GUI process."""
    global _ACTIVE_CONTROLLER
    if not _OVERLAY_ENABLED:
        return None
    if not _HIGHLIGHTS_ENABLED:
        _release_controller()
        return None
    try:
        import FreeCADGui as Gui

        active = Gui.activeDocument()
        if active is None:
            _release_controller()
            return None
        view = active.activeView()
        active_document = getattr(active, "Document", None)
        target_document = document or active_document
        if view is None or target_document is None:
            _release_controller()
            return None
        if active_document is not None and getattr(active_document, "Name", None) != getattr(
            target_document, "Name", None
        ):
            return None
        if (
            _ACTIVE_CONTROLLER is None
            or _ACTIVE_CONTROLLER.view is not view
            or getattr(_ACTIVE_CONTROLLER.document, "Name", None)
            != getattr(target_document, "Name", None)
        ):
            # Replacing a controller because the active view/document changed
            # must not disable the workbench-level refresh lifecycle.
            _release_controller()
            _ACTIVE_CONTROLLER = SeamOverlayController(view, target_document)
        if _ACTIVE_CONTROLLER.root is None:
            _ACTIVE_CONTROLLER.deactivate()
            _ACTIVE_CONTROLLER = None
            return None
        try:
            workbench_name = str(Gui.activeWorkbench().name()).lower()
        except (AttributeError, RuntimeError, TypeError):
            workbench_name = ""
        hovered_seam_id = _ACTIVE_CONTROLLER.hovered_seam_id
        _ACTIVE_CONTROLLER.refresh(
            target_document,
            active_seam_id=hovered_seam_id or _selected_seam_id(Gui, target_document),
            prefer_simulation="simulation" in workbench_name,
            hovered_seam_id=hovered_seam_id,
        )
        return _ACTIVE_CONTROLLER
    except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):
        return None


def activate_seam_overlay(document: object | None = None) -> SeamOverlayController | None:
    """Enable view overlays and register shared presentation refresh dispatch."""
    global _OVERLAY_ENABLED
    _OVERLAY_ENABLED = True
    register_seam_refresh_callback(schedule_seam_overlay_refresh)
    register_workbench_deactivation_callback(deactivate_seam_overlay)
    return refresh_seam_overlay(document)


def get_active_seam_overlay() -> SeamOverlayController | None:
    """Return the active controller for focused GUI acceptance tests."""
    return _ACTIVE_CONTROLLER


def deactivate_seam_overlay() -> None:
    """Discard the transient overlay when the user leaves a Cloth workbench."""
    global _OVERLAY_ENABLED, _REFRESH_PENDING, _PENDING_DOCUMENT
    _OVERLAY_ENABLED = False
    _REFRESH_PENDING = False
    _PENDING_DOCUMENT = None
    register_seam_refresh_callback(None)
    register_workbench_deactivation_callback(None)
    _release_controller()


def _run_scheduled_refresh() -> None:
    global _REFRESH_PENDING, _PENDING_DOCUMENT
    document = _PENDING_DOCUMENT
    _PENDING_DOCUMENT = None
    _REFRESH_PENDING = False
    refresh_seam_overlay(document)


def schedule_seam_overlay_refresh(document: object | None = None) -> None:
    """Coalesce recompute/restore refreshes until FreeCAD has completed the event."""
    global _REFRESH_PENDING, _PENDING_DOCUMENT
    if not _OVERLAY_ENABLED:
        return
    _PENDING_DOCUMENT = document or _PENDING_DOCUMENT
    if _REFRESH_PENDING:
        return
    _REFRESH_PENDING = True
    try:
        try:
            from PySide import QtCore
        except ImportError:
            from PySide2 import QtCore
        QtCore.QTimer.singleShot(0, _run_scheduled_refresh)
    except ImportError:
        _run_scheduled_refresh()
