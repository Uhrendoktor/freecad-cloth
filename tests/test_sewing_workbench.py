import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from SewingObjects import SewingOperationProxy, _edge_length, _seam_length


def test_rectangular_seam_lengths():
    piece = SimpleNamespace(Width=100.0, Height=60.0)
    seam = SimpleNamespace(EdgeA=0, StartA=0.0, EndA=1.0, EdgeB=1, StartB=0.0, EndB=0.5)
    assert _edge_length(piece, 0) == 100.0
    assert _edge_length(piece, 1) == 60.0
    assert _seam_length(piece, seam, "A") == 100.0
    assert _seam_length(piece, seam, "B") == 30.0


def test_proxy_validates_and_updates_shape():
    class Vector:
        def __init__(self, x, y, z=0.0):
            self.x, self.y, self.z = x, y, z

    class Shape:
        pass

    fake_freecad = SimpleNamespace(Vector=Vector)
    fake_part = SimpleNamespace(
        Shape=Shape,
        makeLine=lambda a, b: (a, b),
        makeCompound=lambda shapes: tuple(shapes),
    )
    previous_freecad = sys.modules.get("FreeCAD")
    previous_part = sys.modules.get("Part")
    sys.modules["FreeCAD"] = fake_freecad
    sys.modules["Part"] = fake_part
    try:
        seam = SimpleNamespace(
            EdgeA=0, StartA=0.0, EndA=1.0,
            EdgeB=0, StartB=0.0, EndB=1.0, ReversedB=False,
        )
        piece_a = SimpleNamespace(Width=100.0, Height=60.0)
        piece_b = SimpleNamespace(Width=100.2, Height=60.0)
        obj = SimpleNamespace(
            Seam=seam, PieceA=piece_a, PieceB=piece_b,
            Tolerance=0.5, Stitches=8, Status="Incomplete",
            LengthA=0.0, LengthB=0.0, LengthDifference=0.0,
            StitchCount=0, Shape=None,
        )
        SewingOperationProxy().execute(obj)
        assert obj.Status == "Valid"
        assert obj.LengthA == 100.0
        assert obj.LengthB == 100.2
        assert obj.LengthDifference == 0.2
        assert obj.StitchCount == 8
        assert obj.Shape
        obj.Tolerance = 0.1
        SewingOperationProxy().execute(obj)
        assert obj.Status == "Length mismatch"
    finally:
        if previous_freecad is None:
            sys.modules.pop("FreeCAD", None)
        else:
            sys.modules["FreeCAD"] = previous_freecad
        if previous_part is None:
            sys.modules.pop("Part", None)
        else:
            sys.modules["Part"] = previous_part


if __name__ == "__main__":
    test_rectangular_seam_lengths()
    test_proxy_validates_and_updates_shape()
    print("Sewing workbench object tests passed")
