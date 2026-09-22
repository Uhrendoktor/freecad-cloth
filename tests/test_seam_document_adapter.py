from types import SimpleNamespace

import pytest

from freecad_cloth.pattern.PatternObjects import _edge_records, _resolve_document_edge, _seam_edge_id
from freecad_cloth.sewing.SeamReference import ChangedEdgeReference, MissingEdgeReference, capture_edge_reference


def _piece(points=((0, 0), (10, 0), (10, 10), (0, 10))):
    return SimpleNamespace(PieceId="front", SewingOutline=repr(points))


def test_pattern_edges_have_persistent_semantic_ids():
    records = _edge_records(_piece())
    assert [record["id"] for record in records] == [
        "front:edge:0",
        "front:edge:1",
        "front:edge:2",
        "front:edge:3",
    ]
    assert records[0]["ordinal"] == 0


def test_document_edge_resolution_rejects_geometry_change():
    piece = _piece()
    record = _edge_records(piece)[0]
    reference = capture_edge_reference(piece.PieceId, record["id"], record["points"])
    assert _resolve_document_edge(piece, reference.edge_id, reference.signature)["id"] == reference.edge_id
    changed = _piece(((0, 0), (12, 0), (10, 10), (0, 10)))
    with pytest.raises(ChangedEdgeReference):
        _resolve_document_edge(changed, reference.edge_id, reference.signature)


def test_document_edge_resolution_rejects_missing_semantic_id():
    piece = _piece()
    with pytest.raises(MissingEdgeReference):
        _resolve_document_edge(piece, "front:edge:99", "deadbeef")


class _Point:
    def __init__(self, x, y, z=0.0):
        self.x, self.y, self.z = x, y, z


class LineSegment:
    def __init__(self, start, end):
        self.StartPoint = _Point(*start)
        self.EndPoint = _Point(*end)


class ArcOfCircle:
    FirstParameter = 2.0
    LastParameter = 4.0

    def __init__(self, bulge):
        self.bulge = float(bulge)

    def valueAt(self, parameter):
        t = (float(parameter) - self.FirstParameter) / (self.LastParameter - self.FirstParameter)
        return _Point(10.0, 10.0 * t + self.bulge * 4.0 * t * (1.0 - t))


class _Sketch:
    def __init__(self, geometry):
        self.Geometry = tuple(geometry)
        self.SemanticEdgeIds = tuple(f"front:edge:{index}" for index in range(len(geometry)))
        self.GeometryAuthority = "Sketcher"

    def getConstruction(self, _index):
        return False


def _native_piece(bulge=1.0, geometry=None):
    geometry = geometry if geometry is not None else (
        LineSegment((0, 0), (10, 0)),
        ArcOfCircle(bulge),
        LineSegment((10, 10), (0, 10)),
        LineSegment((0, 10), (0, 0)),
    )
    return SimpleNamespace(
        Label="front",
        PieceId="front",
        Width=10.0,
        Height=10.0,
        SeamAllowance=0.0,
        GrainlineAngle=0.0,
        GeometryAuthority="Sketcher",
        Sketch=_Sketch(geometry),
        DraftingBoundary=repr(((0, 0), (10, 0), (10, 10), (0, 10))),
        SewingOutline=repr(((0, 0), (10, 0), (10, 10), (0, 10))),
    )


def test_native_curve_shape_change_with_identical_endpoints_is_changed_reference():
    original = _native_piece(1.0)
    original_record = _edge_records(original)[1]
    edge_id, signature = _seam_edge_id(original, 1, "A")
    assert edge_id == original_record["id"]
    assert original_record["points"] == ((10.0, 0.0), (10.0, 10.0))
    assert original_record["native_signature"] == signature
    assert signature.startswith("native-v1:")
    assert _resolve_document_edge(original, edge_id, signature)["id"] == edge_id

    changed = _native_piece(2.0)
    changed_record = _edge_records(changed)[1]
    assert changed_record["points"] == original_record["points"]
    assert changed_record["native_signature"] != original_record["native_signature"]
    with pytest.raises(ChangedEdgeReference, match="native Sketcher edge reference"):
        _resolve_document_edge(changed, edge_id, signature)


def test_semantic_seam_status_distinguishes_changed_from_missing(monkeypatch):
    import sys
    from freecad_cloth.pattern.PatternObjects import SeamProxy

    monkeypatch.setitem(
        sys.modules,
        "Part",
        SimpleNamespace(
            Shape=lambda: "empty-shape",
            makeLine=lambda *_points: "line",
            makeCompound=lambda _shapes: "compound",
        ),
    )
    original = _native_piece(1.0)
    edge_id, signature = _seam_edge_id(original, 1, "A")
    obj = SimpleNamespace(PatternA=original, PatternB=original, EdgeAId=edge_id, EdgeASignature=signature,
                          EdgeBId=edge_id, EdgeBSignature=signature, Status="Incomplete", Shape=None)
    SeamProxy().execute(obj)
    assert obj.Status == "Valid"

    changed = _native_piece(2.0)
    obj.PatternA = changed
    SeamProxy().execute(obj)
    assert obj.Status == "Changed reference"

    deleted = _native_piece(1.0, geometry=())
    obj.PatternA = deleted
    SeamProxy().execute(obj)
    assert obj.Status == "Missing reference"


def test_deleted_native_geometry_is_missing_not_retargeted():
    original = _native_piece(1.0)
    edge_id, signature = _seam_edge_id(original, 1, "A")
    deleted = _native_piece(1.0, geometry=())
    with pytest.raises(MissingEdgeReference, match="native Sketcher edge reference"):
        _resolve_document_edge(deleted, edge_id, signature)


def test_legacy_polyline_reference_remains_compatible():
    piece = _piece()
    record = _edge_records(piece)[0]
    reference = capture_edge_reference(piece.PieceId, record["id"], record["points"])
    assert _resolve_document_edge(piece, record["id"], reference.signature)["id"] == record["id"]
