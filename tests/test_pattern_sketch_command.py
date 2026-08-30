import importlib
import sys
import types
import unittest


class _Doc:
    def __init__(self):
        self.Objects = []
        self.recompute_calls = 0

    def recompute(self):
        self.recompute_calls += 1


class PatternSketchCommandTests(unittest.TestCase):
    def test_one_step_command_creates_piece_and_sketch(self):
        doc = _Doc()
        calls = []

        class Piece:
            def __init__(self, name, outline, id, seam_allowance, grainline_angle):
                self.name = name
                self.outline = outline
                self.id = id
                self.seam_allowance = seam_allowance
                self.grainline_angle = grainline_angle

        class Geometry:
            def sampled_outline(self):
                return [(0, 0), (100, 0), (100, 60), (0, 60)]

        class PatternObject:
            PatternType = "PatternPiece"

            def __init__(self, piece):
                self.Label = piece.name
                self.PieceId = piece.id
                self.SewingOutline = str(piece.outline)
                self.SeamAllowance = piece.seam_allowance
                self.GrainlineAngle = piece.grainline_angle

        def add_pattern_piece(document, piece):
            obj = PatternObject(piece)
            document.Objects.append(obj)
            return obj

        freecad = types.SimpleNamespace(ActiveDocument=doc)
        pattern_model = types.SimpleNamespace(PatternPiece=Piece)
        pattern_objects = types.SimpleNamespace(add_pattern_piece=add_pattern_piece)
        pattern_geometry = types.SimpleNamespace(rectangle=lambda width, height: Geometry())
        pattern_sketch = types.SimpleNamespace(
            create_sketch_for_piece=lambda piece, document: calls.append((piece.id, document)) or "Sketch"
        )

        modules = {
            "FreeCAD": freecad,
            "PatternModel": pattern_model,
            "PatternObjects": pattern_objects,
            "PatternGeometry": pattern_geometry,
            "PatternSketch": pattern_sketch,
        }
        previous = {name: sys.modules.get(name) for name in modules}
        try:
            sys.modules.update(modules)
            sys.modules.pop("FreeCADGui", None)
            sys.modules.pop("PatternCommands", None)
            command = importlib.import_module("PatternCommands")
            piece, sketch = command.create_pattern_piece_sketch()
        finally:
            sys.modules.pop("PatternCommands", None)
            for name, previous_module in previous.items():
                if previous_module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = previous_module

        self.assertEqual(piece.PieceId, "pattern-piece-1")
        self.assertEqual(sketch, "Sketch")
        self.assertEqual(calls, [("pattern-piece-1", doc)])
        self.assertEqual(doc.recompute_calls, 1)

    def test_command_is_exposed_in_pattern_workbench_command_set(self):
        namespace = {}
        source = open("PatternCommands.py", encoding="utf-8").read()
        exec(compile(source, "PatternCommands.py", "exec"), namespace)
        self.assertIn("ClothPattern_CreatePieceSketch", namespace["COMMANDS"])


if __name__ == "__main__":
    unittest.main()
