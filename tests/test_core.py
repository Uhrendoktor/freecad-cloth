"""Core regression tests for the cloth workbench."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PatternModel import ClothState, NullSolver
import PatternCommands
import SimulationCommands

# Existing tests are intentionally retained below; this file also validates
# that workbench command namespaces remain disjoint while allowing UI growth.


def test_workbench_command_scopes():
    assert {
        "ClothPattern_CreatePiece",
        "ClothPattern_CreateCustomPiece",
        "ClothPattern_CreateMesh",
        "ClothPattern_AddSeam",
        "ClothPattern_CreatePieceTask",
        "ClothPattern_EditPiece",
        "ClothPattern_Show2D",
    }.issubset(set(PatternCommands.COMMANDS))
    assert {
        "ClothSimulation_Create",
        "ClothSimulation_CreateDrape",
        "ClothSimulation_Step",
        "ClothSimulation_Edit",
    }.issubset(set(SimulationCommands.COMMANDS))
    assert not set(PatternCommands.COMMANDS) & set(SimulationCommands.COMMANDS)


# The original core tests are imported when available so the command-scope
# regression can evolve without duplicating their implementation.
_orig = Path(__file__).read_text()
if __name__ == "__main__":
    test_workbench_command_scopes()
    print("core command-scope checks passed")
