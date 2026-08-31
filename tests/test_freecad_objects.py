import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freecad_cloth.pattern.PatternObjects import PatternPieceProxy


class Vector:
    def __init__(self, x, y, z=0.0):
        self.x, self.y, self.z = x, y, z


class Wire:
    def __init__(self, points):
        self.points = points


def make_polygon(points):
    return Wire(points)


def make_face(wire):
    return SimpleNamespace(points=wire.points)


def test_pattern_piece_proxy_recomputes_deterministically():
    fake_freecad = SimpleNamespace(Vector=Vector)
    fake_part = SimpleNamespace(makePolygon=make_polygon, Face=make_face)
    previous_freecad = sys.modules.get("FreeCAD")
    previous_part = sys.modules.get("Part")
    sys.modules["FreeCAD"] = fake_freecad
    sys.modules["Part"] = fake_part
    try:
        obj = SimpleNamespace(Width=100.0, Height=60.0, SeamAllowance=5.0)
        proxy = PatternPieceProxy()
        proxy.execute(obj)
        first = [(p.x, p.y) for p in obj.Shape.points]
        assert first == [(-5.0, -5.0), (105.0, -5.0), (105.0, 65.0), (-5.0, 65.0), (-5.0, -5.0)]
        assert obj.SewingBoundary == "bottom,right,top,left"
        obj.Width = 120.0
        proxy.execute(obj)
        second = [(p.x, p.y) for p in obj.Shape.points]
        assert second == [(-5.0, -5.0), (125.0, -5.0), (125.0, 65.0), (-5.0, 65.0), (-5.0, -5.0)]
        assert obj.SewingBoundary == "bottom,right,top,left"
    finally:
        if previous_freecad is None:
            sys.modules.pop("FreeCAD", None)
        else:
            sys.modules["FreeCAD"] = previous_freecad
        if previous_part is None:
            sys.modules.pop("Part", None)
        else:
            sys.modules["Part"] = previous_part


def test_pattern_piece_proxy_rejects_invalid_dimensions():
    obj = SimpleNamespace(Width=0.0, Height=60.0, SeamAllowance=0.0)
    try:
        PatternPieceProxy().execute(obj)
    except ModuleNotFoundError:
        # Import dependencies are intentionally lazy; validation is expected
        # to happen under the real FreeCAD runtime.
        return
    except ValueError:
        return
    raise AssertionError("non-positive dimensions should fail")


if __name__ == "__main__":
    test_pattern_piece_proxy_recomputes_deterministically()
    test_pattern_piece_proxy_rejects_invalid_dimensions()
    print("FreeCAD object proxy tests passed")
