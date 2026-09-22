import sys
from pathlib import Path
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freecad_cloth.pattern.PatternDerivedGeometry import Notch, PatternMark, add_marks, add_notches, derive_cut_boundary
from freecad_cloth.pattern.PatternExport import _persisted_pattern_marks, export_pattern_piece, from_dxf_metadata, from_svg_metadata, to_dxf, to_svg, validate_export
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


def _persisted_mark(name, kind, piece_id="piece-front", segment_id="bottom", position=0.5, depth=3.0, angle=0.0, length=20.0, text=""):
    return type(
        "PersistedMark",
        (),
        {
            "Name": name,
            "PatternMarkType": kind,
            "PieceId": piece_id,
            "SegmentId": segment_id,
            "Position": position,
            "Depth": depth,
            "Angle": angle,
            "Length": length,
            "Text": text,
        },
    )()


def _piece_with_marks(marks):
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
    piece.Document = Document()
    piece.Document.Objects = (piece,) + tuple(marks)
    return piece


def test_persisted_pattern_marks_are_collected_deterministically():
    pattern = _curved_pattern()
    piece = _piece_with_marks(
        [
            _persisted_mark("grain-persisted", "Grainline", segment_id=""),
            _persisted_mark("notch-persisted", "Notch", segment_id="right", depth=4.0),
            _persisted_mark("internal-persisted", "InternalMark", text="construction"),
        ]
    )
    notches, marks = _persisted_pattern_marks(piece, pattern)

    assert [item.id for item in notches] == ["notch-persisted"]
    assert [
        (item.id, item.kind, item.segment_id, item.t, item.length, item.text)
        for item in marks
    ] == [
        ("grain-persisted", "Grainline", "", 0.5, 20.0, ""),
        ("internal-persisted", "InternalMark", "bottom", 0.5, 20.0, "construction"),
    ]


def test_pattern_piece_export_preserves_persisted_mark_ids_and_suppresses_synthesized_grainline(tmp_path):
    piece = _piece_with_marks(
        [
            _persisted_mark("notch-persisted", "Notch", segment_id="bottom", depth=4.0),
            _persisted_mark("internal-persisted", "InternalMark", text="construction"),
            _persisted_mark("grain-persisted", "Grainline", segment_id=""),
        ]
    )

    for fmt, metadata_reader in (("svg", from_svg_metadata), ("dxf", from_dxf_metadata)):
        path = tmp_path / ("persisted.%s" % fmt)
        result = export_pattern_piece(piece, path, fmt, curve_samples=16)
        metadata = metadata_reader(path.read_text(encoding="utf-8"))
        assert result["valid"] is True
        assert metadata["notch_ids"] == ["notch-persisted"]
        assert metadata["mark_ids"] == ["grain-persisted", "internal-persisted"]
        if fmt == "svg":
            content = path.read_text(encoding="utf-8")
            assert 'data-kind="Grainline"' in content
            assert 'data-kind="InternalMark"' in content
            assert 'id="notch-notch-persisted"' in content
            assert "piece-front:grainline" not in content


def test_persisted_pattern_marks_reject_stale_or_invalid_state():
    cases = [
        ("unknown segment", _persisted_mark("stale", "Notch", segment_id="missing")),
        ("position", _persisted_mark("bad-position", "Notch", position=1.1)),
        ("depth", _persisted_mark("bad-depth", "Notch", depth=0.0)),
        ("length", _persisted_mark("bad-length", "InternalMark", length=float("nan"))),
    ]
    for label, mark in cases:
        with TestCase().assertRaisesRegex(ValueError, "persisted pattern mark|persisted notch"):
            _persisted_pattern_marks(_piece_with_marks([mark]), _curved_pattern())


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
