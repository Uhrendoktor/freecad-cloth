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
        "mark_types": [{"id": "grain-1", "kind": "Grainline"}],
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

    class Document:
        Objects = ()

    piece = Piece()
    piece.Document = Document()
    piece.Document.Objects = (piece, Seam())
    before = (piece.Label, piece.SeamAllowance, piece.GrainlineAngle, piece.SewingOutline)

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
        assert metadata["mark_ids"] == ["piece-front:grainline"]

    assert before == (piece.Label, piece.SeamAllowance, piece.GrainlineAngle, piece.SewingOutline)


def _piece_with_marks(mark_objects):
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

    class Document:
        Objects = ()

    piece = Piece()
    document = Document()
    document.Objects = tuple([piece, *mark_objects])
    piece.Document = document
    return piece


def _mark(name, mark_type="InternalMark", segment_id="piece-front:edge:0", position=0.5, depth=3.0, angle=0.0, length=25.0, text=""):
    class Mark:
        pass
    obj = Mark()
    obj.Name = name
    obj.PatternMarkType = mark_type
    obj.PieceId = "piece-front"
    obj.SegmentId = segment_id
    obj.Position = position
    obj.Depth = depth
    obj.Angle = angle
    obj.Length = length
    obj.Text = text
    return obj


def test_pattern_piece_export_round_trips_persisted_notch_and_internal_mark(tmp_path):
    piece = _piece_with_marks([
        _mark("InternalMark_1", "InternalMark", text="Construction"),
        _mark("Notch_1", "Notch", position=0.25, depth=4.0),
    ])
    result = export_pattern_piece(piece, tmp_path / "piece.svg", "svg", curve_samples=16)
    metadata = from_svg_metadata((tmp_path / "piece.svg").read_text(encoding="utf-8"))
    assert result["valid"] is True
    assert metadata["notch_ids"] == ["Notch_1"]
    assert metadata["mark_ids"] == ["InternalMark_1", "piece-front:grainline"]
    assert metadata["mark_types"] == [
        {"id": "InternalMark_1", "kind": "InternalMark"},
        {"id": "piece-front:grainline", "kind": "Grainline"},
    ]


def test_persisted_grainline_replaces_synthesized_grainline(tmp_path):
    piece = _piece_with_marks([
        _mark("Grainline_1", "Grainline", segment_id="piece-front:edge:1", angle=15.0, length=55.0, text="Bias"),
    ])
    export_pattern_piece(piece, tmp_path / "piece.svg", "svg", curve_samples=16)
    metadata = from_svg_metadata((tmp_path / "piece.svg").read_text(encoding="utf-8"))
    assert metadata["mark_ids"] == ["Grainline_1"]
    assert metadata["mark_types"] == [{"id": "Grainline_1", "kind": "Grainline"}]


def test_persisted_pattern_mark_rejects_unknown_segment(tmp_path):
    piece = _piece_with_marks([_mark("Notch_1", "Notch", segment_id="missing-edge")])
    with TestCase().assertRaisesRegex(ValueError, "references unknown segment"):
        export_pattern_piece(piece, tmp_path / "piece.svg", "svg")


def test_persisted_pattern_mark_rejects_invalid_position(tmp_path):
    piece = _piece_with_marks([_mark("Mark_1", position=1.5)])
    with TestCase().assertRaisesRegex(ValueError, "invalid position"):
        export_pattern_piece(piece, tmp_path / "piece.svg", "svg")


def test_persisted_pattern_mark_rejects_invalid_depth_and_length(tmp_path):
    bad_depth = _piece_with_marks([_mark("Mark_1", depth=0.0)])
    with TestCase().assertRaisesRegex(ValueError, "invalid depth"):
        export_pattern_piece(bad_depth, tmp_path / "depth.svg", "svg")
    bad_length = _piece_with_marks([_mark("Mark_2", length=0.0)])
    with TestCase().assertRaisesRegex(ValueError, "invalid length"):
        export_pattern_piece(bad_length, tmp_path / "length.svg", "svg")


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
