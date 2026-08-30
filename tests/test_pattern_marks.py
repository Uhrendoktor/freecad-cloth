import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_pattern_mark_module_exposes_persistent_semantic_contract():
    import PatternMarks
    assert hasattr(PatternMarks, "PatternMarkProxy")
    assert hasattr(PatternMarks, "add_pattern_mark")
    assert hasattr(PatternMarks, "create_mark_from_selection")


def test_pattern_mark_edge_resolution_uses_semantic_edge_ids():
    from PatternMarks import _edge_points
    class Piece:
        PieceId = "piece-1"
        SewingOutline = repr([(0, 0), (100, 0), (100, 50), (0, 50)])
    assert _edge_points(Piece(), "piece-1:edge:0") == ((0.0, 0.0), (100.0, 0.0))
    try:
        _edge_points(Piece(), "piece-1:edge:99")
    except ValueError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("missing semantic edge was silently accepted")


def test_pattern_mark_commands_are_registered():
    import PatternCommands
    for command in ("ClothPattern_CreateNotch", "ClothPattern_CreateGrainline", "ClothPattern_CreateInternalMark", "ClothPattern_CreateFoldMark", "ClothPattern_CreateDartMark"):
        assert command in PatternCommands.COMMANDS


if __name__ == "__main__":
    test_pattern_mark_module_exposes_persistent_semantic_contract()
    test_pattern_mark_edge_resolution_uses_semantic_edge_ids()
    test_pattern_mark_commands_are_registered()
    print("pattern mark tests passed")
