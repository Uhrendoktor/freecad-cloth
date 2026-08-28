import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PatternModel import PatternPiece, Seam
from SimulationBackend import ClothState, NullSolver


def test_pattern_piece_validation():
    piece = PatternPiece("front", [(0, 0), (10, 0), (10, 10)], 5)
    piece.validate()


def test_invalid_piece():
    try:
        PatternPiece("", [(0, 0), (1, 0), (0, 1)]).validate()
    except ValueError:
        return
    raise AssertionError("empty name should fail")


def test_seam_validation():
    Seam("front", 0, "back", 2).validate()


def test_null_solver_is_deterministic():
    state = ClothState([(0.0, 0.0, 0.0)])
    assert NullSolver().step(state, 0.01) == state


def run():
    for name, fn in globals().copy().items():
        if name.startswith("test_"):
            fn()
    print("core tests passed")


if __name__ == "__main__":
    run()
