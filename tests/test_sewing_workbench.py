import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from freecad_cloth.sewing.SewingObjects import (
    SewingOperationProxy,
    _edge_length,
    _seam_correspondence,
    _seam_length,
    _outline_points,
)
from freecad_cloth.simulation.SimulationObjects import _sample_boundary


def _install_fake_freecad():
    class V:
        def __init__(self, x, y, z=0): self.x, self.y, self.z = x, y, z
        def __sub__(self, other): return V(self.x - other.x, self.y - other.y, self.z - other.z)
        def __add__(self, other): return V(self.x + other.x, self.y + other.y, self.z + other.z)
        def __mul__(self, value): return V(self.x * value, self.y * value, self.z * value)
        __rmul__ = __mul__

    class FakeApp:
        Vector = V
        class Rotation:
            def __init__(self, *args): pass
        class Placement:
            def __init__(self, *args): pass

    return FakeApp


def test_rectangular_seam_lengths():
    p = SimpleNamespace(Width=100.0, Height=60.0)
    s = SimpleNamespace(EdgeA=0, StartA=0, EndA=1, EdgeB=1, StartB=0, EndB=.5)
    assert _edge_length(p, 0) == 100
    assert _edge_length(p, 1) == 60
    assert _seam_length(p, s, "A") == 100
    assert _seam_length(p, s, "B") == 30


def test_polygon_seam_length_uses_stored_outline():
    p = SimpleNamespace(Width=999.0, Height=999.0, SewingOutline=repr([(0, 0), (40, 0), (40, 20), (0, 30)]))
    assert _outline_points(p) == [(0.0, 0.0), (40.0, 0.0), (40.0, 20.0), (0.0, 30.0)]
    assert abs(_edge_length(p, 2) - (1700.0 ** 0.5)) < 1e-9


def test_curved_native_edge_uses_arc_length_sampling():
    class Edge:
        def discretize(self, Number=64):
            return [SimpleNamespace(x=0, y=0), SimpleNamespace(x=2, y=2), SimpleNamespace(x=4, y=0)]

    shape = SimpleNamespace(Edges=[Edge(), Edge(), Edge()])
    p = SimpleNamespace(Width=4.0, Height=2.0, SewingOutline=repr([(0, 0), (4, 0), (4, 2)]), Shape=shape)
    assert abs(_edge_length(p, 0) - (8.0 ** 0.5 * 2.0)) < 1e-9


def test_uniform_alignment_follows_curved_edge():
    class Edge:
        def __init__(self, values): self.values = values
        def discretize(self, Number=64): return [SimpleNamespace(x=x, y=y) for x, y in self.values]

    curved = [(0, 0), (2, 2), (4, 0)]
    straight = [(0, 0), (4, 0)]
    a = SimpleNamespace(Width=4, Height=2, SewingOutline=repr([(0, 0), (4, 0), (4, 2)]), Shape=SimpleNamespace(Edges=[Edge(curved), Edge(straight), Edge(straight)]))
    b = SimpleNamespace(Width=4, Height=2, SewingOutline=repr([(0, 0), (4, 0), (4, 2)]), Shape=SimpleNamespace(Edges=[Edge(straight), Edge(straight), Edge(straight)]))
    seam = SimpleNamespace(EdgeA=0, StartA=0, EndA=1, EdgeB=0, StartB=0, EndB=1, ReversedB=False)
    oldf = sys.modules.get("FreeCAD")
    sys.modules["FreeCAD"] = _install_fake_freecad()()
    try:
        endpoint_pairs = _seam_correspondence(a, b, seam, 3, "endpoints")
        uniform_pairs = _seam_correspondence(a, b, seam, 3, "uniform")
    finally:
        if oldf is None: sys.modules.pop("FreeCAD", None)
        else: sys.modules["FreeCAD"] = oldf
    assert endpoint_pairs[1][0].y == 0
    assert uniform_pairs[1][0].y > 0


def test_reversed_correspondence_is_applied_once():
    p = SimpleNamespace(Width=100, Height=60, SewingOutline=repr([(0, 0), (100, 0), (100, 60), (0, 60)]))
    seam = SimpleNamespace(EdgeA=0, StartA=.2, EndA=.8, EdgeB=0, StartB=.2, EndB=.8, ReversedB=True)
    oldf = sys.modules.get("FreeCAD")
    sys.modules["FreeCAD"] = _install_fake_freecad()()
    try:
        pairs = _seam_correspondence(p, p, seam, 3, "endpoints")
    finally:
        if oldf is None: sys.modules.pop("FreeCAD", None)
        else: sys.modules["FreeCAD"] = oldf
    assert pairs[0][1].x == 80
    assert pairs[-1][1].x == 20


def test_boundary_sampling_honors_normalized_range():
    values = (10, 11, 12, 13, 14)
    assert _sample_boundary(values, 0.0, 1.0, 5) == [10, 11, 12, 13, 14]
    assert _sample_boundary(values, 0.25, 0.75, 3) == [11, 12, 13]


def test_proxy_validation_and_reversal():
    class V:
        def __init__(self, x, y, z=0): self.x, self.y, self.z = x, y, z
        def __sub__(self, other): return V(self.x - other.x, self.y - other.y, self.z - other.z)
        def __add__(self, other): return V(self.x + other.x, self.y + other.y, self.z + other.z)
        def __mul__(self, value): return V(self.x * value, self.y * value, self.z * value)
        __rmul__ = __mul__

    class Placement:
        def multVec(self, value): return value

    class Shape: pass
    class FakeApp:
        Vector = V
        class Rotation:
            def __init__(self, *args): pass
        class Placement:
            def __init__(self, *args): pass

    oldf, oldp = sys.modules.get("FreeCAD"), sys.modules.get("Part")
    sys.modules["FreeCAD"] = FakeApp()
    sys.modules["Part"] = SimpleNamespace(Shape=Shape, makePolygon=lambda x: tuple(x), makeLine=lambda a, b: (a, b), makeCompound=lambda x: tuple(x))
    try:
        seam = SimpleNamespace(EdgeA=0, StartA=0, EndA=1, EdgeB=0, StartB=0, EndB=1, ReversedB=True)
        a = SimpleNamespace(Width=100, Height=60, SewingOutline=repr([(0, 0), (100, 0), (100, 60), (0, 60)]), Placement=Placement())
        b = SimpleNamespace(Width=100, Height=60, SewingOutline=repr([(0, 0), (100, 0), (100, 60), (0, 60)]), Placement=Placement())
        obj = SimpleNamespace(Seam=seam, PieceA=a, PieceB=b, Tolerance=.5, Stitches=8, Alignment="endpoints", Status="Incomplete", LengthA=0, LengthB=0, LengthDifference=0, StitchCount=0, StitchPoints=[], Shape=None, ReversedB=False, AssemblyPlacementB=None)
        SewingOperationProxy().execute(obj)
        assert obj.Status == "Valid"
        assert obj.StitchCount == 8
        assert len(obj.StitchPoints) == 8
        assert obj.ReversedB is True
        assert obj.StitchPoints[0].split("|")[1].startswith("100.000000")
    finally:
        if oldf is None: sys.modules.pop("FreeCAD", None)
        else: sys.modules["FreeCAD"] = oldf
        if oldp is None: sys.modules.pop("Part", None)
        else: sys.modules["Part"] = oldp


if __name__ == "__main__":
    test_rectangular_seam_lengths()
    test_polygon_seam_length_uses_stored_outline()
    test_curved_native_edge_uses_arc_length_sampling()
    test_uniform_alignment_follows_curved_edge()
    test_reversed_correspondence_is_applied_once()
    test_boundary_sampling_honors_normalized_range()
    test_proxy_validation_and_reversal()
    print("sewing tests passed")
