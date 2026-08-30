import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PatternModel import PatternPiece
from PatternSketch import create_sketch_for_piece
from PatternDrafting import parse_points, serialize_points, add_point, remove_point, bounds

def test_pattern_sketch_module_is_headless_safe():
    piece=PatternPiece("Front",[(0.0,0.0),(100.0,0.0),(100.0,60.0),(0.0,60.0)],id="front"); piece.validate(); assert [f"{piece.id}:edge:{i}" for i in range(4)]==["front:edge:0","front:edge:1","front:edge:2","front:edge:3"]

def test_pattern_sketch_requires_freecad_when_called():
    piece=PatternPiece("Front",[(0.0,0.0),(100.0,0.0),(100.0,60.0)],id="front")
    if "FreeCAD" in sys.modules: return
    try: create_sketch_for_piece(piece)
    except RuntimeError as exc: assert "FreeCAD Sketcher" in str(exc)
    else: raise AssertionError("headless environment should not create a native Sketcher object")

def test_polygon_drafting_round_trip_and_editing():
    points=((0.0,0.0),(80.0,0.0),(100.0,40.0),(40.0,70.0),(0.0,50.0)); encoded=serialize_points(points); assert parse_points(encoded)==points; edited=add_point(points,90.0,20.0,2); assert len(edited)==6; edited=remove_point(edited,2); assert edited==points; assert bounds(points)==(0.0,0.0,100.0,70.0)

def test_native_piece_command_has_stable_public_name():
    import PatternNativeCommands
    assert PatternNativeCommands.COMMANDS==["ClothPattern_CreateNativePiece"]
    assert hasattr(PatternNativeCommands,"create_native_pattern_piece")

if __name__=="__main__":
    test_pattern_sketch_module_is_headless_safe(); test_pattern_sketch_requires_freecad_when_called(); test_polygon_drafting_round_trip_and_editing(); test_native_piece_command_has_stable_public_name(); print("pattern sketch tests passed")
