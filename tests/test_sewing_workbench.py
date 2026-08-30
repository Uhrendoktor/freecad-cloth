import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from SewingObjects import SewingOperationProxy, _edge_length, _seam_length


def test_rectangular_seam_lengths():
    piece = SimpleNamespace(Width=100.0, Height=60.0)
    seam = SimpleNamespace(EdgeA=0, StartA=0, EndA=1, EdgeB=1, StartB=0, EndB=.5)
    assert _edge_length(piece, 0) == 100
    assert _edge_length(piece, 1) == 60
    assert _seam_length(piece, seam, "A") == 100
    assert _seam_length(piece, seam, "B") == 30


def test_non_rectangular_outline_drives_seam_length():
    piece = SimpleNamespace(
        Width=100.0,
        Height=60.0,
        SewingOutline=repr([(0.0, 0.0), (100.0, 0.0), (80.0, 60.0), (0.0, 60.0)]),
    )
    assert _edge_length(piece, 1) == (20.0 ** 2 + 60.0 ** 2) ** 0.5
    seam = SimpleNamespace(EdgeA=1, StartA=0, EndA=.5, EdgeB=0, StartB=0, EndB=1)
    assert _seam_length(piece, seam, "A") == _edge_length(piece, 1) * .5


def test_invalid_semantic_seam_is_not_accepted():
    class Shape:
        pass

    old_part = sys.modules.get("Part")
    sys.modules["Part"] = SimpleNamespace(Shape=Shape)
    try:
        seam = SimpleNamespace(EdgeA=0, StartA=0, EndA=1, EdgeB=0, StartB=0, EndB=1, Status="Missing reference")
        a = SimpleNamespace(Width=100, Height=60)
        b = SimpleNamespace(Width=100, Height=60)
        obj = SimpleNamespace(Seam=seam, PieceA=a, PieceB=b, Tolerance=.5, Stitches=8, Status="Incomplete", LengthA=0, LengthB=0, LengthDifference=0, StitchCount=0, Shape=None)
        SewingOperationProxy().execute(obj)
        assert obj.Status == "Invalid seam: Missing reference"
        assert obj.StitchCount == 0
    finally:
        if old_part is None:
            sys.modules.pop("Part", None)
        else:
            sys.modules["Part"] = old_part


def test_proxy_validation_for_equal_rectangular_edges():
    class V:
        def __init__(self, x, y, z=0):
            self.x, self.y, self.z = x, y, z
        def __sub__(self, other):
            return V(self.x - other.x, self.y - other.y, self.z - other.z)
        def __add__(self, other):
            return V(self.x + other.x, self.y + other.y, self.z + other.z)
        def __mul__(self, scalar):
            return V(self.x * scalar, self.y * scalar, self.z * scalar)

    class S:
        pass

    old_freecad, old_part = sys.modules.get("FreeCAD"), sys.modules.get("Part")
    sys.modules["FreeCAD"] = SimpleNamespace(
        Vector=V,
        Placement=lambda *args: args,
        Rotation=lambda *args: args,
    )
    sys.modules["Part"] = SimpleNamespace(
        Shape=S,
        makeLine=lambda a, b: (a, b),
        makeCompound=lambda x: tuple(x),
    )
    try:
        seam = SimpleNamespace(EdgeA=0, StartA=0, EndA=1, EdgeB=0, StartB=0, EndB=1, ReversedB=False, Status="Valid", Alignment="endpoints")
        a = SimpleNamespace(Width=100, Height=60, Placement=None)
        b = SimpleNamespace(Width=100, Height=60, Placement=None)
        obj = SimpleNamespace(Seam=seam, PieceA=a, PieceB=b, Tolerance=.5, Stitches=8, Status="Incomplete", LengthA=0, LengthB=0, LengthDifference=0, StitchCount=0, Shape=None)
        SewingOperationProxy().execute(obj)
        assert obj.Status == "Valid"
        assert obj.LengthDifference == 0
        assert obj.Shape
    finally:
        if old_freecad is None:
            sys.modules.pop("FreeCAD", None)
        else:
            sys.modules["FreeCAD"] = old_freecad
        if old_part is None:
            sys.modules.pop("Part", None)
        else:
            sys.modules["Part"] = old_part


if __name__ == "__main__":
    test_rectangular_seam_lengths()
    test_non_rectangular_outline_drives_seam_length()
    test_invalid_semantic_seam_is_not_accepted()
    test_proxy_validation_for_equal_rectangular_edges()
    print("sewing tests passed")
