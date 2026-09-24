import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from freecad_cloth.sewing.SewingObjects import (
    SewingOperationProxy,
    _edge_length,
    _native_edge,
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



def test_sketcher_authority_prefers_sketch_shape_edges():
    class Edge:
        pass
    authoritative = Edge()
    legacy = Edge()
    sketch = SimpleNamespace(Shape=SimpleNamespace(Edges=[authoritative]))
    piece = SimpleNamespace(
        GeometryAuthority="Sketcher",
        Sketch=sketch,
        Shape=SimpleNamespace(Edges=[legacy]),
        SewingOutline=repr([(0, 0), (1, 0)]),
    )
    assert _native_edge(piece, 0) is authoritative


def test_native_edge_endpoint_snap_uses_exact_vertices():
    class Vertex:
        def __init__(self, x, y):
            self.Point = SimpleNamespace(x=x, y=y, z=0.0)

    class Edge:
        Vertexes = [Vertex(0, 0), Vertex(4, 0)]
        def discretize(self, Number=64):
            return [SimpleNamespace(x=0, y=0), SimpleNamespace(x=3.999999, y=0)]

    native = Edge()
    piece = SimpleNamespace(
        Width=4.0,
        Height=1.0,
        SewingOutline=repr([(0, 0), (4, 0), (4, 1)]),
        Shape=SimpleNamespace(Edges=[native]),
        GeometryAuthority="PatternParameters",
    )
    oldf = sys.modules.get("FreeCAD")
    sys.modules["FreeCAD"] = _install_fake_freecad()()
    try:
        from freecad_cloth.sewing.SewingObjects import _edge_samples
        values = _edge_samples(piece, 0, 0.0, 1.0, 2, z=0.4)
    finally:
        if oldf is None: sys.modules.pop("FreeCAD", None)
        else: sys.modules["FreeCAD"] = oldf
    assert values[0].x == 0 and values[0].y == 0
    assert values[-1].x == 4 and values[-1].y == 0


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
    assert endpoint_pairs[1][0].y > 0
    assert endpoint_pairs[1][0].x == uniform_pairs[1][0].x
    assert endpoint_pairs[1][0].y == uniform_pairs[1][0].y
    assert endpoint_pairs[1][1].x == uniform_pairs[1][1].x
    assert endpoint_pairs[1][1].y == uniform_pairs[1][1].y


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

def _execute_fake_proxy(
    width_a=100.0,
    width_b=100.0,
    start_a=0.0,
    end_a=1.0,
    start_b=0.0,
    end_b=1.0,
    reversed_b=False,
    tolerance=0.5,
    relative_tolerance=0.05,
):
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
    sys.modules["Part"] = SimpleNamespace(
        Shape=Shape,
        makePolygon=lambda x: tuple(x),
        makeLine=lambda a, b: (a, b),
        makeCompound=lambda x: tuple(x),
    )
    try:
        seam = SimpleNamespace(
            EdgeA=0,
            StartA=start_a,
            EndA=end_a,
            EdgeB=0,
            StartB=start_b,
            EndB=end_b,
            ReversedB=reversed_b,
        )
        a = SimpleNamespace(
            Width=width_a,
            Height=60,
            SewingOutline=repr([(0, 0), (width_a, 0), (width_a, 60), (0, 60)]),
            Placement=Placement(),
        )
        b = SimpleNamespace(
            Width=width_b,
            Height=60,
            SewingOutline=repr([(0, 0), (width_b, 0), (width_b, 60), (0, 60)]),
            Placement=Placement(),
        )
        obj = SimpleNamespace(
            Seam=seam,
            PieceA=a,
            PieceB=b,
            Tolerance=tolerance,
            RelativeTolerance=relative_tolerance,
            Stitches=4,
            Alignment="endpoints",
            Status="Incomplete",
            CorrespondenceStatus="valid",
            LengthA=0,
            LengthB=0,
            LengthDifference=0,
            StitchCount=0,
            StitchPoints=[],
            Shape=None,
            ReversedB=False,
            AssemblyPlacementB=None,
        )
        SewingOperationProxy().execute(obj)
        return obj
    finally:
        if oldf is None: sys.modules.pop("FreeCAD", None)
        else: sys.modules["FreeCAD"] = oldf
        if oldp is None: sys.modules.pop("Part", None)
        else: sys.modules["Part"] = oldp


def test_proxy_reports_symmetric_relative_mismatch():
    forward = _execute_fake_proxy(width_a=100.0, width_b=120.0)
    reverse = _execute_fake_proxy(width_a=120.0, width_b=100.0)
    assert forward.CorrespondenceStatus == "length_mismatch"
    assert reverse.CorrespondenceStatus == "length_mismatch"


def test_proxy_reports_relative_mismatch_for_subrange():
    obj = _execute_fake_proxy(width_a=100.0, width_b=100.0, start_b=0.0, end_b=0.5)
    assert obj.LengthA == 100.0
    assert obj.LengthB == 50.0
    assert obj.CorrespondenceStatus == "length_mismatch"


def test_proxy_reversed_correspondence_is_valid_and_usable():
    obj = _execute_fake_proxy(reversed_b=True)
    assert obj.CorrespondenceStatus == "reversed"
    assert obj.Status == "Valid"
    assert obj.StitchPoints[0].split("|")[1].startswith("100.000000")


def test_proxy_status_uses_shared_relative_mismatch_contract():
    obj = _execute_fake_proxy(width_a=1.0, width_b=1.06, tolerance=50.0, relative_tolerance=0.05)
    assert obj.Status == "Length mismatch"
    assert obj.CorrespondenceStatus == "length_mismatch"


if __name__ == "__main__":
    test_rectangular_seam_lengths()
    test_polygon_seam_length_uses_stored_outline()
    test_curved_native_edge_uses_arc_length_sampling()
    test_uniform_alignment_follows_curved_edge()
    test_reversed_correspondence_is_applied_once()
    test_boundary_sampling_honors_normalized_range()
    test_proxy_validation_and_reversal()
    print("sewing tests passed")
