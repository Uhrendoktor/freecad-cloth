"""Transient viewport overlays for semantic sewing relationships.

Unlike view-property color assignment, this module draws an explicit, disposable
Coin3D overlay: both sides share a stable identity color, each side carries the
same short seam label plus an A/B suffix, and direction/notch marks expose
correspondence. No overlay node is persisted in the FreeCAD document.
"""

from __future__ import annotations

from collections.abc import Iterable
from hashlib import sha1
from typing import Any

from freecad_cloth.gui import register_workbench_deactivation_callback
from freecad_cloth.shared.seam_colors import register_seam_refresh_callback, seam_color_map

_ACTIVE_CONTROLLER = None
_REFRESH_PENDING = False
_PENDING_DOCUMENT = None
_OVERLAY_ENABLED = False


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


def _coin_modules() -> Any | None:
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
    parent: Any,
    coin: Any,
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


def _add_label(
    parent: Any,
    coin: Any,
    point: object,
    label: str,
    rgb: tuple[float, float, float],
) -> None:
    # Pattern solids can cover labels when their sampled edge lies below the
    # face surface. SoAnnotation renders its children in Coin's foreground pass,
    # keeping semantic A/B identifiers legible in both flat and 3D workbench views.
    annotation_type = getattr(coin, "SoAnnotation", coin.SoSeparator)
    annotation = annotation_type()
    depth = coin.SoDepthBuffer()
    depth.test = False
    depth.write = False
    color = coin.SoBaseColor()
    color.rgb = tuple(float(channel) for channel in rgb)
    transform = coin.SoTransform()
    x, y, z = _xyz(point)
    transform.translation.setValue(coin.SbVec3f(x, y, z + 1.2))
    font = coin.SoFont()
    font.size.setValue(12.0)
    text = coin.SoText2()
    text.string.setValue(str(label))
    annotation.addChild(depth)
    annotation.addChild(color)
    annotation.addChild(transform)
    annotation.addChild(font)
    annotation.addChild(text)
    parent.addChild(annotation)


def _canonical_seams(document: Any) -> list[Any]:
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
    document: Any,
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


class SeamOverlayController:
    """Own one transient overlay tree for the active FreeCAD 3D view."""

    def __init__(self, view: Any, document: Any) -> None:
        self.view = view
        self.document = document
        self.scene_graph = None
        self.root = None
        self.rendered_seam_ids: tuple[str, ...] = ()
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
        except (AttributeError, RuntimeError, TypeError) as exc:
            self.scene_graph = None
            self.root = None
            self.last_error = str(exc)

    def deactivate(self) -> None:
        """Remove only this controller's transient Coin node."""
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
        document: Any | None = None,
        active_seam_id: str = "",
        prefer_simulation: bool = False,
    ) -> None:
        """Rebuild the overlay from the active semantic or simulated seam geometry."""
        if document is not None:
            self.document = document
        if self.root is None or self.scene_graph is None:
            return
        coin = _coin_modules()
        if coin is None:
            self.last_error = "Pivy Coin is unavailable"
            return

        while self.root.getNumChildren():
            self.root.removeChild(0)
        depth = coin.SoDepthBuffer()
        depth.test = True
        depth.write = False
        self.root.addChild(depth)

        seams = _canonical_seams(self.document)
        ids = [str(seam.SeamId).strip() for seam in seams]
        colors = seam_color_map(ids)
        labels = seam_display_labels(ids)
        rendered_ids: list[str] = []
        self.rendered_seam_ids = ()
        self.last_error = ""

        simulated = _simulation_seam_geometry(self.document) if prefer_simulation else {}
        if simulated:
            colors = seam_color_map(simulated.keys())
            labels = seam_display_labels(simulated.keys())
            simulation_rendered_ids: list[str] = []
            for identity, (points_a, points_b, connectors) in sorted(simulated.items()):
                focused = identity == str(active_seam_id)
                width = 5.5 if focused else 3.5
                side_group = coin.SoSeparator()
                # Solver positions lie exactly on the live cloth surface; disable
                # depth testing only for this path to avoid z-fighting with its mesh.
                depth = coin.SoDepthBuffer()
                depth.test = False
                depth.write = False
                side_group.addChild(depth)
                color = colors[identity]
                _add_line_groups(side_group, coin, _side_segments(points_a), color, width)
                _add_line_groups(side_group, coin, _side_segments(points_b), color, width)
                _add_line_groups(side_group, coin, connectors, color, 1.25)
                label_a = points_a[len(points_a) // 3]
                label_b = points_b[(len(points_b) * 2) // 3]
                _add_label(side_group, coin, label_a, labels[identity] + "-A", color)
                _add_label(side_group, coin, label_b, labels[identity] + "-B", color)
                self.root.addChild(side_group)
                simulation_rendered_ids.append(identity)
            self.rendered_seam_ids = tuple(sorted(simulation_rendered_ids))
            return

        if not seams:
            return

        from freecad_cloth.sewing.SewingObjects import _edge_samples, _resolved_edge

        for seam in seams:
            identity = str(seam.SeamId).strip()
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
            label_a = _xyz(points_a[len(points_a) // 3])
            label_b = _xyz(points_b[(len(points_b) * 2) // 3])
            _add_label(side_group, coin, label_a, labels[identity] + "-A", color)
            _add_label(side_group, coin, label_b, labels[identity] + "-B", color)
            self.root.addChild(side_group)
            rendered_ids.append(identity)
        self.rendered_seam_ids = tuple(sorted(set(rendered_ids)))


def _selected_seam_id(gui: Any, document: Any) -> str:
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


def refresh_seam_overlay(document: Any | None = None) -> SeamOverlayController | None:
    """Attach or refresh the current view's overlay; safe outside a GUI process."""
    global _ACTIVE_CONTROLLER
    if not _OVERLAY_ENABLED:
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
        _ACTIVE_CONTROLLER.refresh(
            target_document,
            active_seam_id=_selected_seam_id(Gui, target_document),
            prefer_simulation="simulation" in workbench_name,
        )
        return _ACTIVE_CONTROLLER
    except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):
        return None


def activate_seam_overlay(document: Any | None = None) -> SeamOverlayController | None:
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


def schedule_seam_overlay_refresh(document: Any | None = None) -> None:
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
