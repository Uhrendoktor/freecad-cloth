"""Dependency-free, deterministic SVG/DXF interchange for sewing patterns."""
import json
from html import escape
from math import cos, isfinite, radians, sin
from xml.etree import ElementTree
from freecad_cloth.pattern.PatternDerivedGeometry import DerivedPattern, PatternMark, add_marks, derive_cut_boundary, mark_point, notch_point
from freecad_cloth.pattern.PatternGeometry import LineSegment, ParametricPattern, PolylineSegment


def _fmt(value): return f"{float(value):.6f}"
def _dim(value): return f"{float(value):g}"
def _sampled_sewing(pattern, curve_samples):
    points=pattern.sampled_outline(curve_samples)
    if not points: raise ValueError("pattern has no outline")
    return points


def _metadata(pattern, units, piece_id="", seam_ids=(), derived=None, seam_allowance=0.0):
    data={"version":1,"units":units,"edge_ids":[s.id for s in pattern.segments]}
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
        data["mark_types"] = [
            {"id": str(value.id), "kind": str(value.kind)}
            for value in derived.marks
        ]
    return data


def to_svg(pattern: ParametricPattern, curve_samples: int = 32, units: str = "mm", derived: DerivedPattern | None = None, piece_id: str = "", seam_ids=(), seam_allowance: float = 0.0) -> str:
    if not units.strip(): raise ValueError("units must not be empty")
    sewing=_sampled_sewing(pattern,curve_samples)
    if derived is not None and derived.sewing_boundary is not pattern: raise ValueError("derived pattern belongs to a different sewing boundary")
    cut_edges=derived.cut_boundary if derived is not None else (); xs=[p[0] for p in sewing]; ys=[p[1] for p in sewing]
    for edge in cut_edges: xs.extend(p[0] for p in edge.points); ys.extend(p[1] for p in edge.points)
    min_x,max_x,min_y,max_y=min(xs),max(xs),min(ys),max(ys); width,height=max_x-min_x,max_y-min_y
    if width<=0 or height<=0: raise ValueError("pattern must have non-zero extent")
    def xy(point): return (point[0]-min_x,height-(point[1]-min_y))
    def path(points,closed=True):
        coords=[xy(p) for p in points]; return "M "+" L ".join(f"{_fmt(x)},{_fmt(y)}" for x,y in coords)+(" Z" if closed else "")
    edge_ids=" ".join(escape(s.id,quote=True) for s in pattern.segments); metadata=json.dumps(_metadata(pattern,units,piece_id,seam_ids,derived,seam_allowance),sort_keys=True,separators=(",",":"))
    lines=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{_dim(width)}{escape(units)}" height="{_dim(height)}{escape(units)}" viewBox="0 0 {_fmt(width)} {_fmt(height)}" data-units="{escape(units,quote=True)}" data-edge-ids="{edge_ids}" data-piece-id="{escape(str(piece_id),quote=True)}">',f'  <metadata>{escape(metadata)}</metadata>',f'  <g id="sewing-boundary" data-edge-ids="{edge_ids}"><path d="{path(sewing)}" fill="none"/></g>']
    if cut_edges:
        lines.append('  <g id="cut-boundary">')
        for edge in cut_edges: lines.append(f'    <path id="cut-{escape(edge.id,quote=True)}" d="{path(edge.points,False)}" fill="none"/>')
        lines.append('  </g>')
    if derived is not None and (derived.notches or derived.marks):
        lines.append('  <g id="construction-marks">')
        for notch in derived.notches:
            x,y=xy(notch_point(pattern,notch)); lines.append(f'    <circle id="notch-{escape(notch.id,quote=True)}" cx="{_fmt(x)}" cy="{_fmt(y)}" r="{_fmt(max(0.5,notch.depth/4))}" data-segment="{escape(notch.segment_id,quote=True)}" data-t="{_fmt(notch.t)}"/>')
        for mark in derived.marks:
            x,y=xy(mark_point(pattern,mark)); angle=radians(mark.angle); half=mark.length/2; dx,dy=cos(angle)*half,-sin(angle)*half
            lines.append(f'    <line id="mark-{escape(mark.id,quote=True)}" x1="{_fmt(x-dx)}" y1="{_fmt(y-dy)}" x2="{_fmt(x+dx)}" y2="{_fmt(y+dy)}" data-kind="{escape(mark.kind,quote=True)}" data-segment="{escape(mark.segment_id,quote=True)}" data-t="{_fmt(mark.t)}"/>')
            if mark.text: lines.append(f'    <text x="{_fmt(x)}" y="{_fmt(y)}" data-mark-id="{escape(mark.id,quote=True)}">{escape(mark.text)}</text>')
        lines.append('  </g>')
    lines.append('</svg>'); return "\n".join(lines)+"\n"


def to_dxf(pattern: ParametricPattern, curve_samples: int = 32, units: str = "mm", derived: DerivedPattern | None = None, piece_id: str = "", seam_ids=(), seam_allowance: float = 0.0) -> str:
    if not units.strip(): raise ValueError("units must not be empty")
    sewing=_sampled_sewing(pattern,curve_samples)
    if derived is not None and derived.sewing_boundary is not pattern: raise ValueError("derived pattern belongs to a different sewing boundary")
    entities=[]
    def polyline(points,layer,closed=True):
        pts=list(points)
        if closed and pts[-1]!=pts[0]: pts.append(pts[0])
        values=["0","LWPOLYLINE","8",layer,"90",str(len(pts)),"70","1" if closed else "0"]
        for x,y in pts: values += ["10",_fmt(x),"20",_fmt(y)]
        entities.append(values)
    polyline(sewing,"SEWING",True)
    if derived is not None:
        for edge in derived.cut_boundary: polyline(edge.points,"CUT",False)
        for notch in derived.notches:
            x,y=notch_point(pattern,notch); polyline([(x,y),(x,y+notch.depth)],"MARK",False)
        for mark in derived.marks:
            x,y=mark_point(pattern,mark); angle=radians(mark.angle); dx,dy=cos(angle)*mark.length/2,sin(angle)*mark.length/2; polyline([(x-dx,y-dy),(x+dx,y+dy)],"MARK",False)
    metadata=json.dumps(_metadata(pattern,units,piece_id,seam_ids,derived,seam_allowance),sort_keys=True,separators=(",",":")); lines=["0","SECTION","2","HEADER","9","$COMMENT","1",metadata,"0","ENDSEC","0","SECTION","2","ENTITIES"]
    for entity in entities: lines.extend(entity)
    lines += ["0","ENDSEC","0","EOF",""]; return "\n".join(lines)


def from_dxf_metadata(dxf: str) -> dict:
    marker="$COMMENT\n1\n"
    if marker not in dxf: raise ValueError("DXF does not contain cloth-pattern metadata")
    payload=dxf.split(marker,1)[1].split("\n0\nENDSEC",1)[0].strip(); data=json.loads(payload)
    if data.get("version") != 1 or not data.get("edge_ids"): raise ValueError("unsupported or incomplete cloth-pattern metadata")
    return data


def from_svg_metadata(svg: str) -> dict:
    """Read the semantic metadata embedded by :func:`to_svg`."""
    try:
        root=ElementTree.fromstring(svg)
    except ElementTree.ParseError as exc:
        raise ValueError("SVG is not well-formed XML") from exc
    metadata=next((child for child in root if child.tag.rsplit("}",1)[-1] == "metadata"), None)
    if metadata is None or not (metadata.text or "").strip():
        raise ValueError("SVG does not contain cloth-pattern metadata")
    try:
        data=json.loads(metadata.text)
    except json.JSONDecodeError as exc:
        raise ValueError("SVG contains invalid cloth-pattern metadata") from exc
    if data.get("version") != 1 or not data.get("edge_ids"):
        raise ValueError("unsupported or incomplete cloth-pattern metadata")
    return data


def validate_export(pattern: ParametricPattern, exported: str, format: str, curve_samples: int = 32, units: str = "mm", derived: DerivedPattern | None = None, piece_id: str = "", seam_ids=(), seam_allowance: float = 0.0) -> dict:
    """Validate an export against its authoritative pattern model.

    The exporter is deterministic, so byte equality with a freshly generated
    artifact is an intentional release-gate check: geometry, units, edge IDs,
    piece/seam identity and construction-mark metadata cannot drift silently.
    """
    normalized_format=str(format).strip().lower()
    if normalized_format not in {"svg", "dxf"}:
        raise ValueError("format must be 'svg' or 'dxf'")
    expected = to_svg(pattern, curve_samples, units, derived, piece_id, seam_ids, seam_allowance) if normalized_format == "svg" else to_dxf(pattern, curve_samples, units, derived, piece_id, seam_ids, seam_allowance)
    if exported != expected:
        raise ValueError("export does not match the deterministic authoritative pattern output")
    metadata = from_svg_metadata(exported) if normalized_format == "svg" else from_dxf_metadata(exported)
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
            raise ValueError("cannot export pattern piece while seam %s is %s" % (seam_id, status or "invalid"))
        seams.append(seam_id)
    return tuple(sorted(set(seams)))


def _persisted_construction_marks(piece, pattern):
    """Adapt persisted PatternMark document objects into deterministic export marks."""
    doc = getattr(piece, "Document", None)
    if doc is None:
        raise ValueError("pattern piece is not attached to a FreeCAD document")
    piece_id = str(getattr(piece, "PieceId", "")).strip()
    persisted = []
    for obj in getattr(doc, "Objects", ()):
        if str(getattr(obj, "PieceId", "")).strip() != piece_id:
            continue
        mark_type = str(getattr(obj, "PatternMarkType", "")).strip()
        if not mark_type:
            continue
        mark_id = str(getattr(obj, "PatternMarkId", "")).strip() or str(getattr(obj, "Name", "")).strip()
        if not mark_id:
            raise ValueError("persisted pattern mark has no stable identity")
        segment_id = str(getattr(obj, "SegmentId", "")).strip()
        if segment_id == "bottom" and pattern.segments:
            # PatternMarks historically persisted the human-facing "bottom"
            # token. The public mark commands use that token for the default
            # rectangular piece; normalize it to the authoritative first edge
            # rather than treating a valid legacy document as stale.
            segment_id = str(pattern.segments[0].id)
        if segment_id and segment_id not in pattern.by_id():
            raise ValueError(
                "persisted pattern mark %s references unknown segment: %s"
                % (mark_id, segment_id)
            )
        try:
            position = float(getattr(obj, "Position", 0.5))
            depth = float(getattr(obj, "Depth", 3.0))
            angle = float(getattr(obj, "Angle", 0.0))
            length = float(getattr(obj, "Length", 40.0))
        except (TypeError, ValueError) as exc:
            raise ValueError("persisted pattern mark %s has invalid numeric values" % mark_id) from exc
        if not isfinite(position) or not 0.0 <= position <= 1.0:
            raise ValueError("persisted pattern mark %s has invalid position" % mark_id)
        if not isfinite(angle):
            raise ValueError("persisted pattern mark %s has invalid angle" % mark_id)
        if not isfinite(depth) or depth <= 0.0:
            raise ValueError("persisted pattern mark %s has invalid depth" % mark_id)
        if not isfinite(length) or length <= 0.0:
            raise ValueError("persisted pattern mark %s has invalid length" % mark_id)
        persisted.append((str(getattr(obj, "Name", mark_id)), mark_id, mark_type, segment_id, position, depth, angle, length, str(getattr(obj, "Text", "")).strip()))
    persisted.sort(key=lambda value: (value[0], value[1], value[2]))
    ids = set()
    notches = []
    marks = []
    for _name, mark_id, mark_type, segment_id, position, depth, angle, length, text in persisted:
        if mark_id in ids:
            raise ValueError("duplicate persisted construction mark ID: %s" % mark_id)
        ids.add(mark_id)
        if mark_type.casefold() == "notch":
            if not segment_id:
                raise ValueError("persisted notch %s must reference a segment" % mark_id)
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
    return tuple(notches), tuple(marks)


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
        from freecad_cloth.pattern.PatternModel import PatternPiece
        from freecad_cloth.pattern.PatternIR import PatternIR
        from freecad_cloth.sewing.SeamGraph import SeamGraph
        model = PatternPiece(
            str(getattr(piece, "Label", piece.Name)),
            [(0.0, 0.0), (float(piece.Width), 0.0), (float(piece.Width), float(piece.Height)), (0.0, float(piece.Height))],
            seam_allowance=float(getattr(piece, "SeamAllowance", 0.0)),
            grainline_angle=float(getattr(piece, "GrainlineAngle", 0.0)),
            id=str(getattr(piece, "PieceId", "")),
        )
        graph = SeamGraph()
        graph.add_piece(model)
        ir = PatternIR.from_sketches(graph, {model.id: sketch}, curve_samples=curve_samples)
        return ParametricPattern([
            PolylineSegment(edge.id, tuple((float(x), float(y)) for x, y, _z in edge.samples))
            for edge in ir.piece(model.id).boundaries
        ])
    try:
        import ast
        raw = getattr(piece, "SewingOutline", "") or getattr(piece, "DraftingBoundary", "")
        points = [(float(p[0]), float(p[1])) for p in ast.literal_eval(str(raw))]
    except (ValueError, SyntaxError, TypeError, IndexError, AttributeError) as exc:
        raise ValueError("pattern piece has no valid authoritative 2D boundary") from exc
    if len(points) < 3:
        raise ValueError("pattern piece boundary needs at least three points")
    return ParametricPattern([
        LineSegment("%s:edge:%d" % (getattr(piece, "PieceId", "piece"), index), point, points[(index + 1) % len(points)])
        for index, point in enumerate(points)
    ])


def export_pattern_piece(piece, path, format: str, *, units: str = "mm", curve_samples: int = 64) -> dict:
    """Write and validate an SVG/DXF export derived from an authoritative piece."""
    normalized_format = str(format).strip().lower()
    if normalized_format not in {"svg", "dxf"}:
        raise ValueError("format must be 'svg' or 'dxf'")
    if not str(units).strip():
        raise ValueError("units must not be empty")
    pattern = pattern_from_pattern_piece(piece, curve_samples=curve_samples)
    seam_ids = _piece_seams(piece)
    allowance = max(0.0, float(getattr(piece, "SeamAllowance", 0.0)))
    derived = derive_cut_boundary(pattern, allowance, curve_samples=curve_samples)
    persisted_notches, persisted_marks = _persisted_construction_marks(piece, pattern)
    if persisted_notches:
        derived = add_notches(derived, persisted_notches)
    if persisted_marks:
        derived = add_marks(derived, persisted_marks)
    if not any(str(mark.kind).strip().casefold() == "grainline" for mark in derived.marks) and pattern.segments:
        mark = PatternMark(
            id="%s:grainline" % str(getattr(piece, "PieceId", "piece")),
            kind="Grainline",
            segment_id=pattern.segments[0].id,
            angle=float(getattr(piece, "GrainlineAngle", 0.0)),
            length=40.0,
            text="Grain",
        )
        derived = add_marks(derived, (mark,))
    if normalized_format == "svg":
        content = to_svg(pattern, curve_samples, units, derived, str(getattr(piece, "PieceId", "")), seam_ids, allowance)
    else:
        content = to_dxf(pattern, curve_samples, units, derived, str(getattr(piece, "PieceId", "")), seam_ids, allowance)
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
