# Copyright (C) 2026 FreeCAD Cloth contributors
import math

from freecad_cloth.pattern.SeamReference import (
    ChangedEdgeReference,
    MissingEdgeReference,
    capture_edge_reference,
)
from freecad_cloth.simulation.PatternSimulationAdapter import (
    resolve_simulation_pattern,
)


class _Point:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = x
        self.y = y
        self.z = z


class LineSegment:
    def __init__(self, start, end):
        self.StartPoint = _Point(*start)
        self.EndPoint = _Point(*end)


class ArcOfCircle:
    FirstParameter = 0.0
    LastParameter = math.pi

    def __init__(self, bend=1.0):
        self.bend = float(bend)

    def valueAt(self, parameter):
        t = float(parameter) / math.pi
        return _Point(
            10.0 + self.bend * math.sin(math.pi * t),
            10.0 * t,
        )


class _Sketch:
    def __init__(self, geometry, semantic_ids):
        self.Geometry = geometry
        self.SemanticEdgeIds = tuple(semantic_ids)

    def getConstruction(self, index):
        return False


class _Placement:
    Base = _Point(0.0, 0.0)
    Rotation = type(
        "_Rotation",
        (),
        {
            "Angle": 0.0,
            "Axis": _Point(0.0, 0.0, 1.0),
        },
    )()


class _Piece:
    PatternType = "PatternPiece"
    Placement = None
    SeamAllowance = 0.0
    GrainlineAngle = 0.0
    Width = 10.0
    Height = 10.0

    def __init__(self, piece_id, sketch=None):
        self.PieceId = piece_id
        self.Label = piece_id
        self.Name = piece_id
        self.Sketch = sketch
        self.GeometryAuthority = "Sketcher" if sketch is not None else "PatternParameters"

    @property
    def SewingOutline(self):
        msg = "Sketch-authoritative adapter accessed legacy outline"
        raise AssertionError(msg)

    @property
    def DraftingBoundary(self):
        msg = "Sketch-authoritative adapter accessed legacy drafting boundary"
        raise AssertionError(msg)


class _Seam:
    def __init__(
        self,
        seam_id,
        piece_a,
        piece_b,
        edge_a_id,
        edge_b_id,
        edge_a_signature,
        edge_b_signature,
        edge_a=0,
        edge_b=0,
    ):
        self.SeamId = seam_id
        self.PieceA = piece_a
        self.PieceB = piece_b
        self.EdgeAId = edge_a_id
        self.EdgeBId = edge_b_id
        self.EdgeASignature = edge_a_signature
        self.EdgeBSignature = edge_b_signature
        self.EdgeA = edge_a
        self.EdgeB = edge_b
        self.StartA = 0.0
        self.EndA = 1.0
        self.StartB = 0.0
        self.EndB = 1.0
        self.ReversedB = True
        self.Alignment = "uniform"
        self.StitchGroup = "waist"
        self.Kind = "plain"
        self.Status = "Valid"


class _Doc:
    def __init__(self, objects):
        self.Objects = list(objects)


def _edge_reference(piece_id, boundary):
    samples = tuple(tuple(point) for point in boundary.samples)
    points = ((samples[0][0], samples[0][1]), (samples[-1][0], samples[-1][1]))
    provenance = (
        "PatternIR",
        "Sketcher",
        boundary.kind,
        tuple(float(value) for value in boundary.parameter_range),
        samples,
    )
    return capture_edge_reference(piece_id, boundary.id, points, provenance).signature


def _square_sketch(prefix, curved=False, bend=1.0):
    geometry = [
        LineSegment((0.0, 0.0), (10.0, 0.0)),
        ArcOfCircle(bend) if curved else LineSegment((10.0, 0.0), (10.0, 10.0)),
        LineSegment((10.0, 10.0), (0.0, 10.0)),
        LineSegment((0.0, 10.0), (0.0, 0.0)),
    ]
    ids = [
        f"{prefix}:bottom",
        f"{prefix}:side",
        f"{prefix}:top",
        f"{prefix}:left",
    ]
    return _Sketch(geometry, ids)


def test_sketch_authority_resolves_to_pattern_ir_without_reading_cached_outline():
    front = _Piece("front", _square_sketch("front", curved=True))
    doc = _Doc([front])

    resolved = resolve_simulation_pattern(doc, [front], curve_samples=11)
    piece = resolved.pattern.piece("front")

    assert {boundary.id for boundary in piece.boundaries} == {
        "front:bottom",
        "front:side",
        "front:top",
        "front:left",
    }
    curved = resolved.pattern.boundary("front", "front:side")
    assert curved.kind == "arc"
    assert len(curved.samples) == 11


def test_semantic_seam_ids_and_provenance_survive_resolution():
    front = _Piece("front", _square_sketch("front"))
    back = _Piece("back", _square_sketch("back"))
    base = resolve_simulation_pattern(_Doc([front, back]), [front, back])
    front_edge = base.pattern.boundary("front", "front:bottom")
    back_edge = base.pattern.boundary("back", "back:top")

    seam = _Seam(
        "front-back",
        "front",
        "back",
        "front:bottom",
        "back:top",
        _edge_reference("front", front_edge),
        _edge_reference("back", back_edge),
    )
    resolved = resolve_simulation_pattern(_Doc([front, back, seam]), [front, back])
    current = resolved.pattern.seams[0]

    assert current.id == "front-back"
    assert current.edge_a == "front:bottom"
    assert current.edge_b == "back:top"
    assert current.reversed_b is True
    assert current.alignment == "uniform"
    assert current.stitch_group == "waist"


def test_sketcher_authority_without_sketch_fails_closed():
    front = _Piece("front", None)
    front.GeometryAuthority = "Sketcher"
    try:
        resolve_simulation_pattern(_Doc([front]), [front])
    except MissingEdgeReference as exc:
        assert "Sketch-authoritative" in str(exc)
        return
    msg = "Sketcher authority without a Sketch must not use legacy fallback"
    raise AssertionError(msg)


def test_pattern_parameters_without_sketch_fail_closed():
    piece = _Piece("parameterized", None)
    try:
        resolve_simulation_pattern(_Doc([piece]), [piece])
    except MissingEdgeReference as exc:
        assert "geometry authority" in str(exc)
        return
    msg = "PatternParameters without a native Sketch must not be simulated"
    raise AssertionError(msg)


def test_native_sketch_edit_with_same_semantic_id_fails_closed():
    front = _Piece("front", _square_sketch("front", curved=True, bend=1.0))
    back = _Piece("back", _square_sketch("back"))
    base = resolve_simulation_pattern(_Doc([front, back]), [front, back])
    front_edge = base.pattern.boundary("front", "front:side")
    back_edge = base.pattern.boundary("back", "back:top")
    seam = _Seam(
        "front-back",
        "front",
        "back",
        "front:side",
        "back:top",
        _edge_reference("front", front_edge),
        _edge_reference("back", back_edge),
    )

    front.Sketch.Geometry[1] = ArcOfCircle(2.0)
    try:
        resolve_simulation_pattern(_Doc([front, back, seam]), [front, back])
    except ChangedEdgeReference:
        return
    msg = "native Sketcher geometry changes must invalidate the simulation reference"
    raise AssertionError(msg)


def test_native_integer_seam_edge_uses_original_sketch_geometry_index():
    import freecad_cloth.pattern.PatternObjects as pattern_objects

    sketch = _Sketch(
        [LineSegment((0.0, 0.0), (10.0, 0.0)) for _ in range(8)],
        [f"piece:edge:{index}" for index in range(8)],
    )
    piece = _Piece("piece", sketch)
    reordered = []
    for edge_id in (
        "piece:edge:0",
        "piece:edge:7",
        "piece:edge:6",
        "piece:edge:5",
        "piece:edge:4",
        "piece:edge:3",
        "piece:edge:2",
        "piece:edge:1",
    ):
        index = int(edge_id.rsplit(":", 1)[1])
        points = ((float(index), 0.0), (float(index) + 1.0, 0.0))
        reordered.append(
            {
                "id": edge_id,
                "points": points,
                "provenance": (
                    "PatternIR",
                    "Sketcher",
                    "line",
                    (0.0, 1.0),
                    ((points[0][0], points[0][1], 0.0), (points[1][0], points[1][1], 0.0)),
                ),
            }
        )

    def native_edge_records(_piece: object) -> list[dict[str, object]]:
        return reordered

    edge_id, signature = pattern_objects._seam_edge_id(
        piece, 5, "A", native_edge_records_fn=native_edge_records
    )
    assert edge_id == "piece:edge:5"
    assert (
        signature
        == capture_edge_reference(
            "piece", "piece:edge:5", ((5.0, 0.0), (6.0, 0.0)), reordered[3]["provenance"]
        ).signature
    )


def test_native_semantic_seam_edge_keeps_sketch_provenance_signature():
    import freecad_cloth.pattern.PatternObjects as pattern_objects

    sketch = _Sketch(
        [LineSegment((0.0, 0.0), (10.0, 0.0)) for _ in range(4)],
        [f"piece:edge:{index}" for index in range(4)],
    )
    piece = _Piece("piece", sketch)
    provenance = ("PatternIR", "Sketcher", "line", (0.0, 1.0), ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0)))
    records = [
        {"id": "piece:edge:2", "points": ((0.0, 0.0), (10.0, 0.0)), "provenance": provenance}
    ]

    def native_edge_records(_piece: object) -> list[dict[str, object]]:
        return records

    edge_id, signature = pattern_objects._seam_edge_id(
        piece, "piece:edge:2", "A", native_edge_records_fn=native_edge_records
    )
    assert edge_id == "piece:edge:2"
    assert (
        signature
        == capture_edge_reference(
            "piece", "piece:edge:2", records[0]["points"], provenance
        ).signature
    )


if __name__ == "__main__":
    for name, fn in globals().copy().items():
        if name.startswith("test_"):
            fn()
    print("Pattern simulation adapter tests passed")
