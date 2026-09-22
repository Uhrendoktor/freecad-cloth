import tempfile
from pathlib import Path

from freecad_cloth.pattern.PatternExport import (
    _persisted_construction_marks,
    export_pattern_piece,
    from_dxf_metadata,
    from_svg_metadata,
    pattern_from_pattern_piece,
)


class _Piece:
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


class _Mark:
    def __init__(self, name, kind, segment="bottom", position=0.5, depth=3.0, angle=0.0, length=40.0, text="", piece_id="piece-front"):
        self.Name = name
        self.PatternMarkType = kind
        self.PieceId = piece_id
        self.SegmentId = segment
        self.Position = position
        self.Depth = depth
        self.Angle = angle
        self.Length = length
        self.Text = text


def _piece_with_marks(*marks):
    piece = _Piece()
    document = type("Document", (), {})()
    document.Objects = (piece,) + tuple(marks)
    piece.Document = document
    return piece


def test_persisted_marks_are_collected_deterministically_and_by_piece():
    piece = _piece_with_marks(
        _Mark("InternalMark_2", "InternalMark", angle=12.0, text="inside"),
        _Mark("Notch_1", "Notch", depth=4.0),
        _Mark("OtherPiece_1", "Notch", piece_id="piece-other"),
        _Mark("Grainline_1", "Grainline", angle=90.0, length=55.0, text="Grain"),
    )
    pattern = pattern_from_pattern_piece(piece)
    marks = _persisted_construction_marks(piece, pattern)
    assert [(mark.kind, mark.id) for mark in marks] == [
        ("Grainline", "Grainline_1"),
        ("InternalMark", "InternalMark_2"),
        ("Notch", "Notch_1"),
    ]
    assert marks[0].segment_id == "bottom"
    assert marks[2].depth == 4.0


def test_persisted_mark_rejects_unknown_segment():
    piece = _piece_with_marks(_Mark("Notch_1", "Notch", segment="missing-edge"))
    pattern = pattern_from_pattern_piece(piece)
    try:
        _persisted_construction_marks(piece, pattern)
    except ValueError as exc:
        assert "unknown segment" in str(exc)
    else:
        raise AssertionError("stale persisted mark was accepted")


def test_persisted_mark_rejects_non_finite_metadata():
    piece = _piece_with_marks(_Mark("InternalMark_1", "InternalMark", position=float("nan")))
    pattern = pattern_from_pattern_piece(piece)
    try:
        _persisted_construction_marks(piece, pattern)
    except ValueError as exc:
        assert "non-finite" in str(exc)
    else:
        raise AssertionError("invalid persisted mark metadata was accepted")


def test_real_export_round_trip_uses_persisted_mark_ids():
    piece = _piece_with_marks(
        _Mark("Notch_1", "Notch", depth=4.0),
        _Mark("Grainline_1", "Grainline", angle=90.0, length=55.0, text="Grain"),
        _Mark("InternalMark_1", "InternalMark", angle=15.0, length=24.0, text="Internal"),
    )
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for fmt, reader in (("svg", from_svg_metadata), ("dxf", from_dxf_metadata)):
            result = export_pattern_piece(piece, root / ("piece." + fmt), fmt, curve_samples=16)
            metadata = reader((root / ("piece." + fmt)).read_text(encoding="utf-8"))
            assert result["valid"] is True
            assert metadata["notch_ids"] == ["Notch_1"]
            assert metadata["mark_ids"] == ["Grainline_1", "InternalMark_1"]


if __name__ == "__main__":
    for name, fn in sorted(globals().copy().items()):
        if name.startswith("test_"):
            fn()
