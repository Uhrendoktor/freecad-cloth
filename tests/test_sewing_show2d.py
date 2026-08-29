import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from SewingView import pattern_pieces_for_2d


def test_2d_focus_includes_only_authoritative_pattern_pieces_in_document_order():
    first = SimpleNamespace(Name="PatternA", PatternType="PatternPiece")
    seam = SimpleNamespace(Name="Seam", SeamId="seam-1")
    second = SimpleNamespace(Name="PatternB", PatternType="PatternPiece")
    operation = SimpleNamespace(Name="Operation", SewingType="SewingOperation")
    assert pattern_pieces_for_2d([first, seam, second, operation]) == [first, second]


def test_2d_focus_ignores_unrelated_objects_without_freecad_runtime():
    objects = [
        SimpleNamespace(Name="Body"),
        SimpleNamespace(Name="Pattern", PatternType="PatternPiece"),
        SimpleNamespace(Name="Sketch"),
    ]
    result = pattern_pieces_for_2d(objects)
    assert [obj.Name for obj in result] == ["Pattern"]


if __name__ == "__main__":
    test_2d_focus_includes_only_authoritative_pattern_pieces_in_document_order()
    test_2d_focus_ignores_unrelated_objects_without_freecad_runtime()
    print("sewing Show 2D tests passed")
