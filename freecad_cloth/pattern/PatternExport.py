"""Dependency-free, deterministic SVG/DXF interchange for sewing patterns."""

import json
from dataclasses import dataclass
from html import escape
from math import cos, hypot, radians, sin
from xml.etree import ElementTree

from shapely.geometry import Point as ShapelyPoint, Polygon

from freecad_cloth.pattern.PatternDerivedGeometry import (
    DerivedPattern,
    Notch,
    PatternMark,
    add_marks,
    add_notches,
    derive_cut_boundary,
    mark_point,
    notch_point,
)
from freecad_cloth.pattern.PatternGeometry import (
    LineSegment,
    ParametricPattern,
    Point,
    PolylineSegment,
    signed_area,
)


def _fmt(value):
    return f"{float(value):.6f}"


def _dim(value):
    return f"{float(value):g}"


def _validate_units(units: str) -> str:
    """Require millimetres, the canonical unit of Cloth pattern geometry."""
    normalized = str(units).strip().lower()
    if normalized != "mm":
        raise ValueError("units must be 'mm'; pattern coordinates are defined in millimetres")
    return "mm"



@dataclass(frozen=True)
class _ResolvedNotchCut:
    """Geometric cut-insertion plan for one semantic notch."""

    center: float
    left_measure: float
    right_measure: float
    left_point: Point
    right_point: Point
    apex: Point
    half_width: float


def _project_point_onto_polyline(point: Point, points: list[Point]) -> tuple[Point, float, float]:
    """Project a point to a polyline and return (projection, arclength, distance)."""
    if len(points) < 2:
        raise ValueError("cannot project onto a polyline with fewer than two points")
    travelled = 0.0
    best_distance = float("inf")
    best_point: Point | None = None
    best_measure = 0.0
    for start, end in zip(points, points[1:], strict=False):
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = hypot(dx, dy)
        if length <= 1e-12:
            continue
        fraction = min(
            1.0,
            max(
                0.0,
                ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / (length * length),
            ),
        )
        projected = (start[0] + fraction * dx, start[1] + fraction * dy)
        distance = hypot(point[0] - projected[0], point[1] - projected[1])
        if distance < best_distance:
            best_distance = distance
            best_point = projected
            best_measure = travelled + fraction * length
        travelled += length
    if best_point is None:
        raise ValueError("cannot project onto a degenerate polyline")
    return best_point, best_measure, best_distance


def _polyline_point_at(points: list[Point], distance: float) -> Point:
    """Interpolate a point at an arclength on a polyline."""
    if len(points) < 2:
        raise ValueError("cannot interpolate a polyline with fewer than two points")
    total = sum(hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:], strict=False))
    target = min(total, max(0.0, distance))
    travelled = 0.0
    for start, end in zip(points, points[1:], strict=False):
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = hypot(dx, dy)
        if length <= 1e-12:
            continue
        if travelled + length >= target:
            fraction = (target - travelled) / length
            return (start[0] + fraction * dx, start[1] + fraction * dy)
        travelled += length
    return points[-1]


def _interior_normal(pattern: ParametricPattern, notch: Notch) -> Point:
    """Find the sewing-side normal, including zero-allowance and curved edges."""
    segment = pattern.by_id()[notch.segment_id]
    before_t = max(0.0, notch.t - 1e-4)
    after_t = min(1.0, notch.t + 1e-4)
    before, after = segment.point(before_t), segment.point(after_t)
    dx, dy = after[0] - before[0], after[1] - before[1]
    length = hypot(dx, dy)
    if length <= 1e-12:
        raise ValueError(f"cannot determine notch orientation on edge {notch.segment_id}")
    orientation = signed_area(pattern.sampled_outline(32))
    return (-dy / length, dx / length) if orientation > 0 else (dy / length, -dx / length)


def _cut_contour_with_notches(
    pattern: ParametricPattern, derived: DerivedPattern
) -> tuple[Point, ...]:
    """Insert inward-facing V notches into the actual cut perimeter.

    Each notch is mapped through its semantic sewing edge to the matching offset
    edge and then to the joined outer perimeter. The perimeter is split around
    the notch and replaced with two cut legs meeting at the requested inward
    depth. This avoids emitting a misleading line or circle on the sewing line.
    """
    contour = tuple(
        derived.cut_contour
        or tuple(point for edge in derived.cut_boundary for point in edge.points)
    )
    if not derived.notches:
        return contour
    if len(contour) < 3:
        raise ValueError("cannot place notches on an invalid cut contour")

    ring = [*contour, contour[0]]
    measures = [0.0]
    for start, end in zip(ring, ring[1:], strict=False):
        measures.append(measures[-1] + hypot(end[0] - start[0], end[1] - start[1]))
    perimeter = measures[-1]
    base_polygon = Polygon(contour)
    if perimeter <= 1e-9 or not base_polygon.is_valid or base_polygon.area <= 0:
        raise ValueError("cannot place notches on an invalid cut contour")

    edge_by_id = {edge.id: edge for edge in derived.cut_boundary}
    resolved: list[_ResolvedNotchCut] = []
    for notch in derived.notches:
        sewing_point = notch_point(pattern, notch)
        edge = edge_by_id.get(notch.segment_id)
        if edge is None:
            raise ValueError(f"notch references missing cut edge: {notch.segment_id}")
        edge_anchor, _, _ = _project_point_onto_polyline(sewing_point, list(edge.points))
        cut_point, cut_measure, _ = _project_point_onto_polyline(edge_anchor, ring)
        inward_x = sewing_point[0] - cut_point[0]
        inward_y = sewing_point[1] - cut_point[1]
        inward_length = hypot(inward_x, inward_y)
        if inward_length <= 1e-6:
            inward_x, inward_y = _interior_normal(pattern, notch)
        else:
            inward_x, inward_y = inward_x / inward_length, inward_y / inward_length

        apex: Point = (
            cut_point[0] + inward_x * notch.depth,
            cut_point[1] + inward_y * notch.depth,
        )
        if not base_polygon.contains(ShapelyPoint(*apex)):
            raise ValueError(f"notch {notch.id} extends outside the cut piece")
        half_width = min(2.0, max(0.5, notch.depth / 2.0))
        left_measure = (cut_measure - half_width) % perimeter
        right_measure = (cut_measure + half_width) % perimeter
        resolved.append(
            _ResolvedNotchCut(
                cut_measure % perimeter,
                left_measure,
                right_measure,
                _polyline_point_at(ring, left_measure),
                _polyline_point_at(ring, right_measure),
                apex,
                half_width,
            )
        )

    for index, first in enumerate(resolved):
        for second in resolved[index + 1 :]:
            distance = abs(first.center - second.center)
            distance = min(distance, perimeter - distance)
            if distance <= first.half_width + second.half_width + 1e-6:
                raise ValueError("notch cut spans overlap on the cut contour")

    origin = resolved[0].left_measure
    intervals: list[tuple[float, float]] = []
    events: list[tuple[float, str, Point, Point | None]] = []
    for notch in resolved:
        left_q = (notch.left_measure - origin) % perimeter
        right_q = (notch.right_measure - origin) % perimeter
        if left_q >= right_q:
            raise ValueError("notch cut spans cannot be ordered on the cut contour")
        intervals.append((left_q, right_q))
        events.append((left_q, "left", notch.left_point, notch.apex))
        events.append((right_q, "right", notch.right_point, None))

    for measure, point in zip(measures[:-1], contour, strict=False):
        relative = (measure - origin) % perimeter
        if any(left - 1e-9 <= relative <= right + 1e-9 for left, right in intervals):
            continue
        events.append((relative, "vertex", point, None))
    events.sort(key=lambda event: event[0])

    result: list[Point] = []
    for _, kind, point, apex in events:
        candidates = (point, apex) if kind == "left" and apex is not None else (point,)
        for candidate in candidates:
            if (
                not result
                or hypot(candidate[0] - result[-1][0], candidate[1] - result[-1][1]) > 1e-9
            ):
                result.append(candidate)
    if (
        len(result) > 1
        and hypot(result[-1][0] - result[0][0], result[-1][1] - result[0][1]) <= 1e-9
    ):
        result.pop()
    notched_polygon = Polygon(result)
    if (
        len(result) < 3
        or not notched_polygon.is_valid
        or not notched_polygon.exterior.is_simple
        or notched_polygon.area > base_polygon.area
    ):
        raise ValueError("notches produce an invalid cut contour")
    return tuple(result)


def _sampled_sewing(pattern, curve_samples):
    points = pattern.sampled_outline(curve_samples)
    if not points:
        raise ValueError("pattern has no outline")
    return points


def _metadata(pattern, units, piece_id="", seam_ids=(), derived=None, seam_allowance=0.0):
    data = {"version": 1, "units": units, "edge_ids": [s.id for s in pattern.segments]}
    if piece_id:
        data["piece_id"] = str(piece_id)
    seam_ids = tuple(str(value) for value in seam_ids if str(value))
    if seam_ids:
        data["seam_ids"] = list(dict.fromkeys(seam_ids))
    # Keep the v1 legacy payload byte-for-byte compatible unless the caller
    # opts into the semantic export contract with a piece or seam identity.
    if derived is not None and (piece_id or seam_ids):
        data["scale"] = 1.0
        data["seam_allowance_mm"] = float(seam_allowance)
        data["notch_ids"] = [str(value.id) for value in derived.notches]
        data["mark_ids"] = [str(value.id) for value in derived.marks]
    return data


def to_svg(
    pattern: ParametricPattern,
    curve_samples: int = 32,
    units: str = "mm",
    derived: DerivedPattern | None = None,
    piece_id: str = "",
    seam_ids=(),
    seam_allowance: float = 0.0,
) -> str:
    """Provide the public to svg operation."""
    units = _validate_units(units)
    sewing = _sampled_sewing(pattern, curve_samples)
    if derived is not None and derived.sewing_boundary is not pattern:
        raise ValueError("derived pattern belongs to a different sewing boundary")
    cut_edges = derived.cut_boundary if derived is not None else ()
    cut_contour = _cut_contour_with_notches(pattern, derived) if derived is not None else ()
    xs = [p[0] for p in sewing]
    ys = [p[1] for p in sewing]
    if cut_contour:
        xs.extend(point[0] for point in cut_contour)
        ys.extend(point[1] for point in cut_contour)
    else:
        for edge in cut_edges:
            xs.extend(p[0] for p in edge.points)
            ys.extend(p[1] for p in edge.points)
    if derived is not None:
        for mark in derived.marks:
            x, y = mark_point(pattern, mark)
            half = mark.length / 2
            dx, dy = cos(radians(mark.angle)) * half, sin(radians(mark.angle)) * half
            xs.extend((x - dx, x + dx))
            ys.extend((y - dy, y + dy))
            if mark.text:
                xs.append(x + max(2.0, len(mark.text) * 1.8))
                ys.extend((y - 1.0, y + 2.0))
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    width, height = max_x - min_x, max_y - min_y
    if width <= 0 or height <= 0:
        raise ValueError("pattern must have non-zero extent")

    def xy(point):
        return (point[0] - min_x, height - (point[1] - min_y))

    def path(points, closed=True):
        coords = [xy(p) for p in points]
        return (
            "M " + " L ".join(f"{_fmt(x)},{_fmt(y)}" for x, y in coords) + (" Z" if closed else "")
        )

    edge_ids = " ".join(escape(s.id, quote=True) for s in pattern.segments)
    metadata = json.dumps(
        _metadata(pattern, units, piece_id, seam_ids, derived, seam_allowance),
        sort_keys=True,
        separators=(",", ":"),
    )
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_dim(width)}{escape(units)}" height="{_dim(height)}{escape(units)}" viewBox="0 0 {_fmt(width)} {_fmt(height)}" data-units="{escape(units, quote=True)}" data-edge-ids="{edge_ids}" data-piece-id="{escape(str(piece_id), quote=True)}">',
        f"  <metadata>{escape(metadata)}</metadata>",
        f'  <g id="sewing-boundary" data-edge-ids="{edge_ids}"><path d="{path(sewing)}" fill="none" stroke="#000000" stroke-width="0.2" stroke-dasharray="2 1" stroke-linecap="round" stroke-linejoin="round"/></g>',
    ]
    if cut_edges or cut_contour:
        notch_ids = (
            " ".join(escape(notch.id, quote=True) for notch in derived.notches) if derived else ""
        )
        cut_points = cut_contour or tuple(point for edge in cut_edges for point in edge.points)
        lines.append(
            f'  <g id="cut-boundary"><path id="cut-perimeter" data-notch-ids="{notch_ids}" d="{path(cut_points, True)}" fill="none" stroke="#000000" stroke-width="0.3" stroke-linecap="round" stroke-linejoin="round"/></g>'
        )
    if derived is not None and derived.marks:
        lines.append('  <g id="construction-marks">')
        for mark in derived.marks:
            x, y = xy(mark_point(pattern, mark))
            angle = radians(mark.angle)
            half = mark.length / 2
            dx, dy = cos(angle) * half, -sin(angle) * half
            lines.append(
                f'    <line id="mark-{escape(mark.id, quote=True)}" x1="{_fmt(x - dx)}" y1="{_fmt(y - dy)}" x2="{_fmt(x + dx)}" y2="{_fmt(y + dy)}" fill="none" stroke="#000000" stroke-width="0.2" stroke-linecap="round" data-kind="{escape(mark.kind, quote=True)}" data-segment="{escape(mark.segment_id, quote=True)}" data-t="{_fmt(mark.t)}"/>'
            )
            if mark.text:
                lines.append(
                    f'    <text x="{_fmt(x)}" y="{_fmt(y)}" fill="#000000" font-family="sans-serif" font-size="3mm" data-mark-id="{escape(mark.id, quote=True)}">{escape(mark.text)}</text>'
                )
        lines.append("  </g>")
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def to_dxf(
    pattern: ParametricPattern,
    curve_samples: int = 32,
    units: str = "mm",
    derived: DerivedPattern | None = None,
    piece_id: str = "",
    seam_ids=(),
    seam_allowance: float = 0.0,
) -> str:
    """Provide the public to dxf operation."""
    units = _validate_units(units)
    sewing = _sampled_sewing(pattern, curve_samples)
    if derived is not None and derived.sewing_boundary is not pattern:
        raise ValueError("derived pattern belongs to a different sewing boundary")
    entities = []

    def polyline(points, layer, closed=True):
        pts = list(points)
        if closed and pts[-1] != pts[0]:
            pts.append(pts[0])
        values = ["0", "LWPOLYLINE", "8", layer, "90", str(len(pts)), "70", "1" if closed else "0"]
        for x, y in pts:
            values += ["10", _fmt(x), "20", _fmt(y)]
        entities.append(values)

    polyline(sewing, "SEWING", True)
    if derived is not None:
        cut_contour = _cut_contour_with_notches(pattern, derived)
        if cut_contour:
            polyline(cut_contour, "CUT", True)
        for mark in derived.marks:
            x, y = mark_point(pattern, mark)
            angle = radians(mark.angle)
            dx, dy = cos(angle) * mark.length / 2, sin(angle) * mark.length / 2
            polyline([(x - dx, y - dy), (x + dx, y + dy)], "MARK", False)
    metadata = json.dumps(
        _metadata(pattern, units, piece_id, seam_ids, derived, seam_allowance),
        sort_keys=True,
        separators=(",", ":"),
    )
    lines = [
        "0",
        "SECTION",
        "2",
        "HEADER",
        "9",
        "$INSUNITS",
        "70",
        "4",
        "9",
        "$COMMENT",
        "1",
        metadata,
        "0",
        "ENDSEC",
        "0",
        "SECTION",
        "2",
        "ENTITIES",
    ]
    for entity in entities:
        lines.extend(entity)
    lines += ["0", "ENDSEC", "0", "EOF", ""]
    return "\n".join(lines)


def from_dxf_metadata(dxf: str) -> dict:
    """Provide the public from dxf metadata operation."""
    marker = "$COMMENT\n1\n"
    if marker not in dxf:
        raise ValueError("DXF does not contain cloth-pattern metadata")
    payload = dxf.split(marker, 1)[1].split("\n0\nENDSEC", 1)[0].strip()
    data = json.loads(payload)
    if data.get("version") != 1 or not data.get("edge_ids"):
        raise ValueError("unsupported or incomplete cloth-pattern metadata")
    return data


def from_svg_metadata(svg: str) -> dict:
    """Read the semantic metadata embedded by :func:`to_svg`."""
    try:
        root = ElementTree.fromstring(svg)
    except ElementTree.ParseError as exc:
        raise ValueError("SVG is not well-formed XML") from exc
    metadata = next((child for child in root if child.tag.rsplit("}", 1)[-1] == "metadata"), None)
    if metadata is None or not (metadata.text or "").strip():
        raise ValueError("SVG does not contain cloth-pattern metadata")
    try:
        data = json.loads(metadata.text)
    except json.JSONDecodeError as exc:
        raise ValueError("SVG contains invalid cloth-pattern metadata") from exc
    if data.get("version") != 1 or not data.get("edge_ids"):
        raise ValueError("unsupported or incomplete cloth-pattern metadata")
    return data


def validate_export(
    pattern: ParametricPattern,
    exported: str,
    format: str,
    curve_samples: int = 32,
    units: str = "mm",
    derived: DerivedPattern | None = None,
    piece_id: str = "",
    seam_ids=(),
    seam_allowance: float = 0.0,
) -> dict:
    """Validate an export against its authoritative pattern model.

    The exporter is deterministic, so byte equality with a freshly generated
    artifact is an intentional release-gate check: geometry, units, edge IDs,
    piece/seam identity and construction-mark metadata cannot drift silently.
    """
    normalized_format = str(format).strip().lower()
    if normalized_format not in {"svg", "dxf"}:
        raise ValueError("format must be 'svg' or 'dxf'")
    expected = (
        to_svg(pattern, curve_samples, units, derived, piece_id, seam_ids, seam_allowance)
        if normalized_format == "svg"
        else to_dxf(pattern, curve_samples, units, derived, piece_id, seam_ids, seam_allowance)
    )
    if exported != expected:
        raise ValueError("export does not match the deterministic authoritative pattern output")
    metadata = (
        from_svg_metadata(exported) if normalized_format == "svg" else from_dxf_metadata(exported)
    )
    return {"format": normalized_format, "valid": True, "metadata": metadata}


def _piece_seams(piece):
    doc = getattr(piece, "Document", None)
    if doc is None:
        raise ValueError("pattern piece is not attached to a FreeCAD document")
    piece_id = str(getattr(piece, "PieceId", "")).strip()
    seams = []
    for obj in getattr(doc, "Objects", ()):
        seam_id = str(getattr(obj, "SeamId", "")).strip()
        if not seam_id:
            continue
        if piece_id not in {str(getattr(obj, "PieceA", "")), str(getattr(obj, "PieceB", ""))}:
            continue
        status = str(getattr(obj, "Status", ""))
        if status != "Valid":
            raise ValueError(
                "cannot export pattern piece while seam {} is {}".format(
                    seam_id, status or "invalid"
                )
            )
        seams.append(seam_id)
    return tuple(sorted(set(seams)))


def _piece_construction_marks(piece, pattern):
    """Materialize persisted native construction marks into the export model."""
    doc = getattr(piece, "Document", None)
    if doc is None:
        raise ValueError("pattern piece is not attached to a FreeCAD document")
    piece_id = str(getattr(piece, "PieceId", "")).strip()
    notches = []
    marks = []
    for obj in getattr(doc, "Objects", ()):
        mark_type = str(getattr(obj, "PatternMarkType", "")).strip()
        if not mark_type or str(getattr(obj, "PieceId", "")).strip() != piece_id:
            continue

        mark_id = str(getattr(obj, "PatternMarkId", "")).strip()
        if not mark_id:
            raise ValueError("construction mark has no persistent identity")

        segment_id = str(getattr(obj, "SegmentId", "")).strip()
        if not segment_id:
            raise ValueError(f"construction mark {mark_id} has no semantic edge reference")
        if segment_id not in pattern.by_id():
            raise ValueError(f"construction mark {mark_id} references missing edge {segment_id}")

        position = float(getattr(obj, "Position", 0.5))
        depth = float(getattr(obj, "Depth", 3.0))
        angle = float(getattr(obj, "Angle", 0.0))
        length = float(getattr(obj, "Length", 40.0))
        text = str(getattr(obj, "Text", ""))
        if mark_type == "Notch":
            notches.append(Notch(mark_id, segment_id, position, depth=depth))
        else:
            marks.append(
                PatternMark(
                    mark_id,
                    mark_type,
                    segment_id=segment_id,
                    t=position,
                    angle=angle,
                    length=length,
                    text=text,
                )
            )
    return (
        tuple(sorted(notches, key=lambda value: value.id)),
        tuple(sorted(marks, key=lambda value: value.id)),
    )


def pattern_from_pattern_piece(piece, curve_samples: int = 64) -> ParametricPattern:
    """Build a deterministic derived export pattern from the authoritative piece."""
    if getattr(piece, "PatternType", "") != "PatternPiece":
        raise ValueError("selected object is not a Cloth PatternPiece")
    if curve_samples < 2:
        raise ValueError("curve_samples must be at least 2")
    sketch = getattr(piece, "Sketch", None)
    if str(getattr(piece, "GeometryAuthority", "")) == "Sketcher":
        if sketch is None:
            raise ValueError("Sketch-authoritative pattern piece has no native Sketcher source")
        from freecad_cloth.pattern.PatternIR import PatternIR
        from freecad_cloth.pattern.PatternModel import PatternPiece
        from freecad_cloth.sewing.SeamGraph import SeamGraph

        model = PatternPiece(
            str(getattr(piece, "Label", piece.Name)),
            [
                (0.0, 0.0),
                (float(piece.Width), 0.0),
                (float(piece.Width), float(piece.Height)),
                (0.0, float(piece.Height)),
            ],
            seam_allowance=float(getattr(piece, "SeamAllowance", 0.0)),
            grainline_angle=float(getattr(piece, "GrainlineAngle", 0.0)),
            id=str(getattr(piece, "PieceId", "")),
        )
        graph = SeamGraph()
        graph.add_piece(model)
        ir = PatternIR.from_sketches(graph, {model.id: sketch}, curve_samples=curve_samples)
        return ParametricPattern(
            [
                PolylineSegment(edge.id, tuple((float(x), float(y)) for x, y, _z in edge.samples))
                for edge in ir.piece(model.id).boundaries
            ]
        )
    try:
        import ast

        raw = getattr(piece, "SewingOutline", "") or getattr(piece, "DraftingBoundary", "")
        points = [(float(p[0]), float(p[1])) for p in ast.literal_eval(str(raw))]
    except (ValueError, SyntaxError, TypeError, IndexError, AttributeError) as exc:
        raise ValueError("pattern piece has no valid authoritative 2D boundary") from exc
    if len(points) < 3:
        raise ValueError("pattern piece boundary needs at least three points")
    return ParametricPattern(
        [
            LineSegment(
                "%s:edge:%d" % (getattr(piece, "PieceId", "piece"), index),
                point,
                points[(index + 1) % len(points)],
            )
            for index, point in enumerate(points)
        ]
    )


def export_pattern_piece(
    piece, path, format: str, *, units: str = "mm", curve_samples: int = 64
) -> dict:
    """Write and validate an SVG/DXF export derived from an authoritative piece."""
    normalized_format = str(format).strip().lower()
    if normalized_format not in {"svg", "dxf"}:
        raise ValueError("format must be 'svg' or 'dxf'")
    units = _validate_units(units)
    pattern = pattern_from_pattern_piece(piece, curve_samples=curve_samples)
    seam_ids = _piece_seams(piece)
    allowance = max(0.0, float(getattr(piece, "SeamAllowance", 0.0)))
    derived = derive_cut_boundary(pattern, allowance, curve_samples=curve_samples)
    notches, marks = _piece_construction_marks(piece, pattern)
    if notches:
        derived = add_notches(derived, notches)
    if marks:
        derived = add_marks(derived, marks)
    if pattern.segments and not any(mark.kind == "Grainline" for mark in derived.marks):
        mark = PatternMark(
            id="{}:grainline".format(str(getattr(piece, "PieceId", "piece"))),
            kind="Grainline",
            segment_id=pattern.segments[0].id,
            angle=float(getattr(piece, "GrainlineAngle", 0.0)),
            length=40.0,
            text="Grain",
        )
        derived = add_marks(derived, (mark,))
    if normalized_format == "svg":
        content = to_svg(
            pattern,
            curve_samples,
            units,
            derived,
            str(getattr(piece, "PieceId", "")),
            seam_ids,
            allowance,
        )
    else:
        content = to_dxf(
            pattern,
            curve_samples,
            units,
            derived,
            str(getattr(piece, "PieceId", "")),
            seam_ids,
            allowance,
        )
    with open(str(path), "w", encoding="utf-8", newline="") as handle:
        handle.write(content)
    return validate_export(
        pattern,
        content,
        normalized_format,
        curve_samples=curve_samples,
        units=units,
        derived=derived,
        piece_id=str(getattr(piece, "PieceId", "")),
        seam_ids=seam_ids,
        seam_allowance=allowance,
    )
