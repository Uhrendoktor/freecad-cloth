import math

from freecad_cloth.common.PatternSimulationAdapter import (
    resolve_simulation_pattern,
)
from freecad_cloth.sewing.SeamReference import ChangedEdgeReference, capture_edge_reference


class _Point:
    def __init__(self, x, y, z=0.0):
        self.x = x
        self.y = y
        self.z = z


class _Line:
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
    Base = _Point()
    Rotation = type("_Rotation", (), {
        "Angle": 0.0,
        "Axis": _Point(0.0, 0.0, 1.0),
    })()


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
        self.GeometryAuthority = "Sketcher" if sketch is not None else "Legacy"

    @property
    def SewingOutline(self):
        raise AssertionError("Sketch-authoritative adapter accessed legacy outline")

    @property
    def DraftingBoundary(self):
        raise AssertionError("Sketch-authoritative adapter accessed legacy drafting boundary")


class _LegacyPiece:
    PatternType = "PatternPiece"
    GeometryAuthority = "Legacy"
    Sketch = None
    Placement = None
    SeamAllowance = 0.0
    GrainlineAngle = 0.0
    Width = 10.0
    Height = 10.0

    def __init__(self, piece_id):
        self.PieceId = piece_id
        self.Label = piece_id
        self.Name = piece_id
        self.SewingOutline = repr([
            (0.0, 0.0),
            (10.0, 0.0),
            (10.0, 10.0),
            (0.0, 10.0),
        ])
        self.DraftingBoundary = self.SewingOutline


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
        _Line((0.0, 0.0), (10.0, 0.0)),
        ArcOfCircle(bend) if curved else _Line((10.0, 0.0), (10.0, 10.0)),
        _Line((10.0, 10.0), (0.0, 10.0)),
        _Line((0.0, 10.0), (0.0, 0.0)),
    ]
    ids = [
        f"{prefix}:bottom",
        f"{prefix}:side",
        f"{prefix}:top",
        f"{prefix}:left",
    ]
    return _Sketch(geometry, ids)


def test_sketch_authority_resolves_to_pattern_ir_without_reading_legacy_outline():
    front = _Piece("front", _square_sketch("front", curved=True))
    doc = _Doc([front])

    resolved = resolve_simulation_pattern(doc, [front], curve_samples=11)
    piece = resolved.pattern.piece("front")

    assert [boundary.id for boundary in piece.boundaries] == [
        "front:bottom",
        "front:side",
        "front:top",
        "front:left",
    ]
    assert piece.boundaries[1].kind == "arc"
    assert len(piece.boundaries[1].samples) == 11


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


def test_legacy_piece_uses_explicit_patternir_fallback():
    legacy = _LegacyPiece("legacy")
    resolved = resolve_simulation_pattern(_Doc([legacy]), [legacy])

    assert [boundary.id for boundary in resolved.pattern.piece("legacy").boundaries] == [
        "legacy:edge:0",
        "legacy:edge:1",
        "legacy:edge:2",
        "legacy:edge:3",
    ]


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
    raise AssertionError("native Sketcher geometry changes must invalidate the simulation reference")


def test_native_and_legacy_pieces_can_share_one_simulation_pattern():
    front = _Piece("front", _square_sketch("front"))
    back = _LegacyPiece("back")
    resolved = resolve_simulation_pattern(_Doc([front, back]), [front, back])
    pattern = resolved.pattern

    assert pattern.piece("front").boundaries[0].id == "front:bottom"
    assert pattern.piece("back").boundaries[0].id == "back:edge:0"


if __name__ == "__main__":
    pytest.main([__file__])
