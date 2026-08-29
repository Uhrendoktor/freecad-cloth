import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from SewingObjects import _edge_length, _edge_points


class _Vector:
    def __init__(self, x, y, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)


class _RotatedPlacement:
    """Minimal FreeCAD Placement stand-in for a 90-degree Z rotation + translation."""

    def __init__(self, dx=0.0, dy=0.0, dz=0.0):
        self.dx, self.dy, self.dz = dx, dy, dz

    def multVec(self, value):
        # (x, y) -> (-y, x), then translate.
        return _Vector(
            -value.y + self.dx,
            value.x + self.dy,
            value.z + self.dz,
        )


def _install_fake_freecad():
    class FakeApp:
        Vector = _Vector

    return FakeApp


def test_closed_outline_edge_index_wraps_to_first_vertex():
    piece = SimpleNamespace(
        Width=999.0,
        Height=999.0,
        SewingOutline=repr([(0, 0), (4, 0), (4, 3)]),
    )

    # Edge 2 is the closing segment from the final point back to the first.
    assert _edge_length(piece, 2) == 5.0


def test_edge_points_apply_rotated_piece_placement_once():
    piece = SimpleNamespace(
        Width=4.0,
        Height=3.0,
        SewingOutline=repr([(0, 0), (4, 0), (4, 3)]),
        Placement=_RotatedPlacement(dx=10, dy=-5, dz=2),
    )

    old_freecad = sys.modules.get("FreeCAD")
    sys.modules["FreeCAD"] = _install_fake_freecad()
    try:
        start, end = _edge_points(piece, 1, 0.0, 1.0, z=0.2)
    finally:
        if old_freecad is None:
            sys.modules.pop("FreeCAD", None)
        else:
            sys.modules["FreeCAD"] = old_freecad

    # Local edge 1 is (4, 0) -> (4, 3). After a 90-degree rotation and
    # translation it becomes (10, -1, 2.2) -> (7, -1, 2.2).
    assert (start.x, start.y, start.z) == (10.0, -1.0, 2.2)
    assert (end.x, end.y, end.z) == (7.0, -1.0, 2.2)
