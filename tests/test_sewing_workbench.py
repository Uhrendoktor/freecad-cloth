    # physical half-length lies 2 mm into the second segment at (2.2, 1.2).
    curved = [(0, 0), (1, 0), (4, 3)]
    straight = [(0, 0), (4, 0)]
    a = SimpleNamespace(Width=4, Height=3, SewingOutline=repr([(0, 0), (4, 0), (4, 3)]), Shape=SimpleNamespace(Edges=[Edge(curved), Edge(straight), Edge(straight)]))
    b = SimpleNamespace(Width=4, Height=3, SewingOutline=repr([(0, 0), (4, 0), (4, 3)]), Shape=SimpleNamespace(Edges=[Edge(straight), Edge(straight), Edge(straight)]))
    seam = SimpleNamespace(EdgeA=0, StartA=0, EndA=1, EdgeB=0, StartB=0, EndB=1, ReversedB=False)
    oldf = sys.modules.get("FreeCAD")
    sys.modules["FreeCAD"] = _install_fake_freecad()()
    try:
        endpoint_pairs = _seam_correspondence(a, b, seam, 3, "endpoints")
        seam.ReversedB = True
        reversed_pairs = _seam_correspondence(a, b, seam, 3, "endpoints")
    finally:
        if oldf is None: sys.modules.pop("FreeCAD", None)
        else: sys.modules["FreeCAD"] = oldf

    midpoint = endpoint_pairs[1][0]
    assert abs(midpoint.x - 2.146446609406726) < 1e-9
    assert abs(midpoint.y - 1.146446609406726) < 1e-9
    assert abs(reversed_pairs[0][1].x - endpoint_pairs[-1][1].x) < 1e-9
    assert abs(reversed_pairs[0][1].y - endpoint_pairs[-1][1].y) < 1e-9
    assert abs(reversed_pairs[-1][1].x - endpoint_pairs[0][1].x) < 1e-9
    assert abs(reversed_pairs[-1][1].y - endpoint_pairs[0][1].y) < 1e-9