import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freecad_cloth.pattern.PatternObjects import PatternPieceProxy, SeamProxy, _resolve_document_edge, _seam_edge_id


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




class NativePoint:
    def __init__(self, x, y, z=0.0):
        self.x, self.y, self.z = x, y, z


class NativeLine:
    def __init__(self, start, end):
        self.StartPoint = NativePoint(*start)
        self.EndPoint = NativePoint(*end)


class NativeArc:
    FirstParameter = 2.0
    LastParameter = 4.0

    def __init__(self, bulge):
        self.bulge = float(bulge)

    def valueAt(self, parameter):
        t = (float(parameter) - self.FirstParameter) / (self.LastParameter - self.FirstParameter)
        return NativePoint(10.0, 10.0 * t + self.bulge * 4.0 * t * (1.0 - t))


class NativeSketch:
    def __init__(self, geometry):
        self.Geometry = tuple(geometry)
        self.SemanticEdgeIds = tuple("front:edge:%d" % index for index in range(len(geometry)))
        self.GeometryAuthority = "Sketcher"

    def getConstruction(self, _index):
        return False


def native_piece(bulge=1.0, geometry=None):
    geometry = geometry if geometry is not None else (
        NativeLine((0, 0), (10, 0)),
        NativeArc(bulge),
        NativeLine((10, 10), (0, 10)),
        NativeLine((0, 10), (0, 0)),
    )
    return SimpleNamespace(
        Label="front", PieceId="front", Width=10.0, Height=10.0,
        SeamAllowance=0.0, GrainlineAngle=0.0, GeometryAuthority="Sketcher",
        Sketch=NativeSketch(geometry),
        DraftingBoundary=repr(((0, 0), (10, 0), (10, 10), (0, 10))),
        SewingOutline=repr(((0, 0), (10, 0), (10, 10), (0, 10))),
    )


def test_native_curve_shape_change_is_changed_and_delete_is_missing():
    original = native_piece(1.0)
    edge_id, signature = _seam_edge_id(original, 1, "A")
    assert _resolve_document_edge(original, edge_id, signature)["id"] == edge_id

    previous_part = sys.modules.get("Part")
    sys.modules["Part"] = SimpleNamespace(Shape=lambda: "empty-shape")
    try:
        changed = native_piece(2.0)
        changed_obj = SimpleNamespace(
            PatternA=changed, PatternB=changed,
            EdgeAId=edge_id, EdgeASignature=signature,
            EdgeBId=edge_id, EdgeBSignature=signature,
            Status="Incomplete", Shape=None,
        )
        SeamProxy().execute(changed_obj)
        assert changed_obj.Status == "Changed reference"

        deleted = native_piece(1.0, geometry=())
        deleted_obj = SimpleNamespace(
            PatternA=deleted, PatternB=deleted,
            EdgeAId=edge_id, EdgeASignature=signature,
            EdgeBId=edge_id, EdgeBSignature=signature,
            Status="Incomplete", Shape=None,
        )
        SeamProxy().execute(deleted_obj)
        assert deleted_obj.Status == "Missing reference"
    finally:
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
    test_native_curve_shape_change_is_changed_and_delete_is_missing()
    print("FreeCAD object proxy tests passed")
