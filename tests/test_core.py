import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freecad_cloth.pattern.PatternModel import PatternPiece, Seam
from freecad_cloth.pattern.PatternGeometry import LineSegment, ParametricPattern, QuadraticBezier, rectangle
from freecad_cloth.pattern.PatternSchema import PatternDocument, dumps, loads
from freecad_cloth.simulation.SimulationBackend import ClothState, NullSolver
from freecad_cloth.pattern import PatternCommands as _PatMod
from freecad_cloth.sewing import SewingCommands as _SewMod
from freecad_cloth.simulation import SimulationCommands as _SimMod




def test_garment_hierarchy_classifies_authoritative_objects():
    from freecad_cloth.common.GarmentDocument import classify_members, classify_object

    def obj(name, **props):
        return SimpleNamespace(Name=name, Label=name, **props)

    front = obj("Front", PatternType="PatternPiece")
    seam = obj("Seam", SeamId="side")
    network = obj("SewingNetwork", SewingType="SewingNetwork")
    fitting = obj("FittingScene", FittingType="FittingScene")
    point = obj("ArrangementPoint_waist", FittingType="ArrangementPoint")
    avatar = obj("ClothAvatar", AvatarType="ClothAvatar")
    target = obj("DrapeTarget")
    simulation = obj("ClothSimulation", Proxy=SimpleNamespace(Type="ClothSimulation"))

    assert classify_object(front) == "pattern"
    assert classify_object(seam) == "sewing"
    assert classify_object(network) == "sewing"
    assert classify_object(fitting) == "fitting"
    assert classify_object(point) == "fitting"
    assert classify_object(avatar) == "avatar"
    assert classify_object(target) == "simulation"
    assert classify_object(simulation) == "simulation"

    members = classify_members((front, seam, network, fitting, point, avatar, target, simulation, front))
    assert [item.Name for item in members["pattern"]] == ["Front"]
    assert [item.Name for item in members["sewing"]] == ["Seam", "SewingNetwork"]
    assert [item.Name for item in members["fitting"]] == ["ArrangementPoint_waist", "FittingScene"]
    assert [item.Name for item in members["avatar"]] == ["ClothAvatar"]
    assert [item.Name for item in members["simulation"]] == ["ClothSimulation", "DrapeTarget"]


def test_pattern_piece_validation():
    piece = PatternPiece("front", [(0, 0), (10, 0), (10, 10)], 5, id="front")
    piece.validate()


def test_invalid_piece():
    try: PatternPiece("", [(0, 0), (1, 0), (0, 1)], id="x").validate()
    except ValueError: return
    raise AssertionError("empty name should fail")


def test_seam_validation(): Seam("front", 0, "back", 2, id="shoulder").validate()

def test_rectangle_is_closed_and_stable():
    first, second = rectangle(100, 60), rectangle(100, 60)
    assert [s.id for s in first.segments] == ["bottom", "right", "top", "left"]
    assert first.sampled_outline() == second.sampled_outline(); assert first.lengths() == second.lengths()

def test_parametric_dimensions_change_geometry_not_topology():
    small, large = rectangle(100, 60), rectangle(120, 80)
    assert [s.id for s in small.segments] == [s.id for s in large.segments]
    assert large.lengths()["bottom"] == 120; assert large.lengths()["right"] == 80

def test_quadratic_bezier_is_sampleable():
    curve = QuadraticBezier("armhole", (0, 0), (5, 10), (10, 0))
    assert curve.point(0) == (0, 0); assert curve.point(1) == (10, 0); assert len(curve.polyline(5)) == 5

def test_custom_closed_curve_pattern():
    pattern = ParametricPattern([LineSegment("bottom", (0, 0), (10, 0)), LineSegment("right", (10, 0), (10, 5)), QuadraticBezier("top", (10, 5), (5, 9), (0, 5)), LineSegment("left", (0, 5), (0, 0))])
    assert set(pattern.by_id()) == {"bottom", "right", "top", "left"}; assert pattern.lengths()["top"] > 10

def test_invalid_geometry_is_rejected():
    try: ParametricPattern([LineSegment("a", (0, 0), (1, 0)), LineSegment("b", (2, 0), (2, 1)), LineSegment("c", (2, 1), (0, 0))])
    except ValueError: return
    raise AssertionError("open boundary should fail")

def test_pattern_document_round_trip_is_canonical():
    document = PatternDocument("garment-1", "Test garment", pieces=[{"id": "front", "name": "Front"}, {"id": "back", "name": "Back"}], seams=[{"id": "side", "piece_a": "front", "piece_b": "back"}], metadata={"units": "mm"})
    encoded = dumps(document); assert dumps(loads(encoded)) == encoded

def test_pattern_document_rejects_malformed_input():
    for text in ["[]", '{"schema_version": 99, "pattern_id": "x", "name": "x"}']:
        try: loads(text)
        except ValueError: continue
        raise AssertionError("malformed document should fail")

def test_null_solver_is_deterministic():
    state = ClothState([(0.0, 0.0, 0.0)]); assert NullSolver().step(state, 0.01) == state

def test_workbench_command_scopes():
    assert {"ClothPattern_CreatePiece", "ClothPattern_CreateCustomPiece", "ClothPattern_CreateMesh", "ClothPattern_AddSeam", "ClothPattern_CreatePieceTask", "ClothPattern_EditPiece", "ClothPattern_Show2D"}.issubset(set(_PatMod.COMMANDS))
    assert {"ClothSewing_CreateSeam", "ClothSewing_CreateMNSewing", "ClothSewing_CreateOperation", "ClothSewing_Validate"}.issubset(set(_SewMod.COMMANDS))
    assert {"ClothSimulation_Create", "ClothSimulation_CreateDrape", "ClothSimulation_Step", "ClothSimulation_Edit"}.issubset(set(_SimMod.COMMANDS))
    assert not set(_PatMod.COMMANDS) & set(_SewMod.COMMANDS)
    assert not set(_SewMod.COMMANDS) & set(_SimMod.COMMANDS)

def run():
    for name, fn in globals().copy().items():
        if name.startswith("test_"): fn()
    print("core tests passed")

if __name__ == "__main__": run()