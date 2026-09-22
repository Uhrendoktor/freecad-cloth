from pathlib import Path
from types import SimpleNamespace

import pytest

from freecad_cloth.pattern.PatternExport import export_pattern_piece, from_svg_metadata


class Document:
    def __init__(self, objects):
        self.Objects = tuple(objects)


def _piece_with_marks(segment_ids):
    piece = SimpleNamespace(
        PatternType="PatternPiece",
        Name="Front",
        Label="Front",
        PieceId="piece-front",
        Width=100.0,
        Height=60.0,
        SeamAllowance=5.0,
        GrainlineAngle=90.0,
        GeometryAuthority="",
        SewingOutline=repr([(0.0, 0.0), (100.0, 0.0), (100.0, 60.0), (0.0, 60.0)]),
        DraftingBoundary=repr([(0.0, 0.0), (100.0, 0.0), (100.0, 60.0), (0.0, 60.0)]),
    )
    marks = [
        SimpleNamespace(Name="Notch_1", PatternMarkId="piece-front:notch:1", PatternMarkType="Notch", PieceId="piece-front", SegmentId=segment_ids[0], Position=0.5, Depth=3.0, Angle=0.0, Length=40.0, Text=""),
        SimpleNamespace(Name="InternalMark_1", PatternMarkId="piece-front:internalmark:1", PatternMarkType="InternalMark", PieceId="piece-front", SegmentId=segment_ids[1], Position=0.25, Depth=3.0, Angle=15.0, Length=20.0, Text="Internal"),
    ]
    piece.Document = Document([piece, *marks])
    return piece


def test_export_round_trips_persisted_marks_and_is_deterministic(tmp_path):
    piece = _piece_with_marks(("piece-front:edge:0", "piece-front:edge:1"))
    first = tmp_path / "first.svg"
    second = tmp_path / "second.svg"
    export_pattern_piece(piece, first, "svg")
    export_pattern_piece(piece, second, "svg")
    assert first.read_bytes() == second.read_bytes()
    metadata = from_svg_metadata(first.read_text(encoding="utf-8"))
    assert metadata["notch_ids"] == ["piece-front:notch:1"]
    assert metadata["internal_mark_ids"] == ["piece-front:internalmark:1"]
    assert metadata["mark_ids"] == ["piece-front:grainline", "piece-front:internalmark:1"]


def test_export_rejects_missing_persisted_mark_reference(tmp_path):
    piece = _piece_with_marks(("piece-front:edge:missing", "piece-front:edge:1"))
    with pytest.raises(ValueError, match="missing its semantic edge ID|unknown segment"):
        export_pattern_piece(piece, Path(tmp_path) / "bad.svg", "svg")
