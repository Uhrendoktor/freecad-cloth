import sys
from pathlib import Path
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freecad_cloth.pattern.PatternDerivedGeometry import Notch, PatternMark, add_marks, add_notches, derive_cut_boundary
from freecad_cloth.pattern.PatternExport import export_pattern_piece, from_dxf_metadata, from_svg_metadata, to_dxf, to_svg, validate_export
from freecad_cloth.pattern.PatternGeometry import LineSegment, ParametricPattern, QuadraticBezier


def _curved_pattern():
    return ParametricPattern([
        LineSegment("bottom", (0.0, 0.0), (100.0, 0.0)),
        LineSegment("right", (100.0, 0.0), (100.0, 60.0)),
        QuadraticBezier("armhole", (100.0, 60.0), (55.0, 85.0), (0.0, 60.0)),
        LineSegment("left", (0.0, 60.0), (0.0, 0.0)),
    ])


def _derived(pattern):
    result = derive_cut_boundary(pattern, 5.0, curve_samples=9)
    result = add_notches(result, [Notch("notch-1", "right", 0.5)])
    return add_marks(result, [PatternMark("grain-1", "Grainline", segment_id="bottom", angle=90, length=40, text="Grain")])


def test_svg_and_dxf_preserve_piece_and_construction_semantics():
    pattern = _curved_pattern()
    derived = _derived(pattern)
    svg = to_svg(pattern, curve_samples=9, derived=derived, piece_id="bodice-front", seam_ids=("seam-neck", "seam-side"))
    assert 'data-piece-id="bodice-front"' in svg
    assert 'data-edge-ids="bottom right armhole left"' in svg
    assert 'id="notch-notch-1"' in svg
    assert 'data-mark-id="grain-1"' in svg
    assert from_svg_metadata(svg) == {
        "version": 1,
        "units": "mm",
        "edge_ids": ["bottom", "right", "armhole", "left"],
        "piece_id": "bodice-front",
        "seam_ids": ["seam-neck", "seam-side"],
        "scale": 1.0,
        "seam_allowance_mm": 0.0,
        "notch_ids": ["notch-1"],
        "mark_ids": ["grain-1"],
    }

    dxf = to_dxf(pattern, curve_samples=9, derived=derived, piece_id="bodice-front", seam_ids=("seam-neck", "seam-side"))
    assert from_dxf_metadata(dxf) == {
        "version": 1,
        "units": "mm",
        "edge_ids": ["bottom", "right", "armhole", "left"],
        "piece_id": "bodice-front",
        "seam_ids": ["seam-neck", "seam-side"],
        "scale": 1.0,
        "seam_allowance_mm": 0.0,
        "notch_ids": ["notch-1"],
        "mark_ids": ["grain-1"],
    }


def test_legacy_export_metadata_remains_compatible():
    dxf = to_dxf(_curved_pattern())
    assert from_dxf_metadata(dxf) == {
        "version": 1,
        "units": "mm",
        "edge_ids": ["bottom", "right", "armhole", "left"],
    }


def test_release_gate_validates_deterministic_svg_and_dxf_round_trip():
    pattern = _curved_pattern()
    derived = _derived(pattern)
    kwargs = dict(curve_samples=9, derived=derived, piece_id="bodice-front", seam_ids=("seam-neck", "seam-side"))

    svg = to_svg(pattern, **kwargs)
    result = validate_export(pattern, svg, "svg", **kwargs)
    assert result["valid"] is True
    assert result["metadata"]["piece_id"] == "bodice-front"

    dxf = to_dxf(pattern, **kwargs)
    result = validate_export(pattern, dxf, "dxf", **kwargs)
    assert result["valid"] is True
    assert result["metadata"]["seam_ids"] == ["seam-neck", "seam-side"]


def test_release_gate_rejects_geometry_or_semantic_drift():
    pattern = _curved_pattern()
    svg = to_svg(pattern, curve_samples=9, piece_id="bodice-front", seam_ids=("seam-neck",))
    with TestCase().assertRaisesRegex(ValueError, "deterministic authoritative pattern"):
        validate_export(pattern, svg.replace("100.000000,0.000000", "101.000000,0.000000", 1), "svg", curve_samples=9, piece_id="bodice-front", seam_ids=("seam-neck",))

    dxf = to_dxf(pattern, curve_samples=9, piece_id="bodice-front", seam_ids=("seam-neck",))
    with TestCase().assertRaisesRegex(ValueError, "deterministic authoritative pattern"):
        validate_export(pattern, dxf.replace("bodice-front", "bodice-back", 1), "dxf", curve_samples=9, piece_id="bodice-front", seam_ids=("seam-neck",))


def test_release_gate_rejects_unknown_format():
    with TestCase().assertRaisesRegex(ValueError, "format must be 'svg' or 'dxf'"):
        validate_export(_curved_pattern(), "", "pdf")


def test_pattern_piece_export_adapter_is_deterministic_and_read_only(tmp_path):
    class Piece:
        PatternType = "PatternPiece"
        Name = "Front"
        Label = "Front"
        PieceId = "piece-front"
        Width = 100.0
        Height = 60.0
        SeamAllowance = 5.0
        GrainlineAngle = 90.0
        GeometryAuthority = ""
        SewingOutline = repr([(0.0, 0.0), (100.0, 0.0), (100.0, 60.0), (0.0, 60.0)])
        DraftingBoundary = SewingOutline

    class Seam:
        SeamId = "front-back"
        PieceA = "piece-front"
        PieceB = "piece-back"
        Status = "Valid"

    class Mark:
        def __init__(self, name, mark_type, segment_id, position=0.5, depth=3.0, angle=0.0, length=40.0, text=""):
            self.Name = name
            self.PatternMarkId = name
            self.PatternMarkType = mark_type
            self.PieceId = "piece-front"
            self.SegmentId = segment_id
            self.Position = position
            self.Depth = depth
            self.Angle = angle
            self.Length = length
            self.Text = text

    class Document:
        Objects = ()

    notch = Mark("notch-front", "Notch", "piece-front:edge:0", position=0.5, depth=3.0)
    construction = Mark("mark-front", "InternalMark", "piece-front:edge:0", position=0.5, length=20.0, text="Internal")
    piece = Piece()
    piece.Document = Document()
    piece.Document.Objects = (piece, Seam(), notch, construction)
    before = (piece.Label, piece.SeamAllowance, piece.GrainlineAngle, piece.SewingOutline, notch.PatternMarkId, notch.SegmentId, construction.PatternMarkId, construction.SegmentId)

    for fmt, metadata_reader in (("svg", from_svg_metadata), ("dxf", from_dxf_metadata)):
        first = tmp_path / ("front.%s" % fmt)
        second = tmp_path / ("front-second.%s" % fmt)
        first_result = export_pattern_piece(piece, first, fmt, curve_samples=16)
        export_pattern_piece(piece, second, fmt, curve_samples=16)
        assert first.read_bytes() == second.read_bytes()
        assert first_result["valid"] is True
        metadata = metadata_reader(first.read_text(encoding="utf-8"))
        assert metadata["piece_id"] == "piece-front"
        assert metadata["seam_ids"] == ["front-back"]
        assert metadata["scale"] == 1.0
        assert metadata["seam_allowance_mm"] == 5.0
        assert metadata["notch_ids"] == ["notch-front"]
        assert metadata["mark_ids"] == ["mark-front"]
        output = first.read_text(encoding="utf-8")
        if fmt == "svg":
            assert 'id="notch-notch-front"' in output
            assert 'data-segment="piece-front:edge:0" data-t="0.500000"' in output
            assert 'id="mark-mark-front"' in output
            assert 'data-kind="InternalMark"' in output
            assert 'x1="45.000000" y1="65.000000" x2="65.000000" y2="65.000000"' in output
        else:
            assert "10\n50.000000\n20\n0.000000\n10\n50.000000\n20\n3.000000" in output
            assert "10\n40.000000\n20\n0.000000\n10\n60.000000\n20\n0.000000" in output

    assert before == (piece.Label, piece.SeamAllowance, piece.GrainlineAngle, piece.SewingOutline, notch.PatternMarkId, notch.SegmentId, construction.PatternMarkId, construction.SegmentId)


def test_pattern_piece_export_blocks_stale_construction_mark(tmp_path):
    class Piece:
        PatternType = "PatternPiece"
        Name = "Front"
        Label = "Front"
        PieceId = "piece-front"
        Width = 100.0
        Height = 60.0
        SeamAllowance = 0.0
        GrainlineAngle = 0.0
        GeometryAuthority = ""
        SewingOutline = repr([(0.0, 0.0), (100.0, 0.0), (100.0, 60.0), (0.0, 60.0)])
        DraftingBoundary = SewingOutline

    class Mark:
        Name = "notch-stale"
        PatternMarkId = "notch-stale"
        PatternMarkType = "Notch"
        PieceId = "piece-front"
        SegmentId = "piece-front:edge:missing"
        Position = 0.5
        Depth = 3.0
        Angle = 0.0
        Length = 40.0
        Text = ""

    class Document:
        Objects = ()

    piece = Piece()
    piece.Document = Document()
    piece.Document.Objects = (piece, Mark())
    with TestCase().assertRaisesRegex(ValueError, "construction mark notch-stale references missing edge"):
        export_pattern_piece(piece, tmp_path / "stale.svg", "svg")


def test_pattern_piece_export_blocks_invalid_semantic_seams(tmp_path):
    class Piece:
        PatternType = "PatternPiece"
        Name = "Front"
        Label = "Front"
        PieceId = "piece-front"
        Width = 100.0
        Height = 60.0
        SeamAllowance = 0.0
        GrainlineAngle = 0.0
        GeometryAuthority = ""
        SewingOutline = repr([(0.0, 0.0), (100.0, 0.0), (100.0, 60.0), (0.0, 60.0)])
        DraftingBoundary = SewingOutline

    class Seam:
        SeamId = "front-back"
        PieceA = "piece-front"
        PieceB = "piece-back"
        Status = "Changed reference"

    class Document:
        Objects = ()

    piece = Piece()
    piece.Document = Document()
    piece.Document.Objects = (piece, Seam())
    with TestCase().assertRaisesRegex(ValueError, "cannot export pattern piece"):
        export_pattern_piece(piece, tmp_path / "invalid.svg", "svg")

def test_export_boundary_is_closed_and_continuous():
    pattern = _curved_pattern()
    points = pattern.sampled_outline(24)
    assert len(points) >= 3
    for start, end in zip(points, points[1:] + points[:1]):
        assert ((start[0] - end[0]) ** 2 + (start[1] - end[1]) ** 2) <= 1e-12


def test_export_rejects_disconnected_boundary_segments():
    with TestCase().assertRaisesRegex(ValueError, "boundary is not closed"):
        ParametricPattern(
            [
                LineSegment("a", (0.0, 0.0), (10.0, 0.0)),
                LineSegment("b", (10.0, 0.0), (10.0, 10.0)),
                LineSegment("c", (10.0, 10.0), (0.0, 10.0)),
                LineSegment("d", (0.0, 9.0), (0.0, 0.0)),
            ]
        )
