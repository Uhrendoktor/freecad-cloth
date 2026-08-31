import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from freecad_cloth.pattern.PatternGeometry import LineSegment, ParametricPattern, QuadraticBezier, rectangle
from freecad_cloth.pattern.PatternExport import from_dxf_metadata, to_dxf, to_svg
from freecad_cloth.pattern.PatternDerivedGeometry import Notch, PatternMark, add_marks, add_notches, derive_cut_boundary, notch_point
from freecad_cloth.sewing.SewingSemantics import SeamConstraint, validate_seam_graph
from freecad_cloth.sewing.SewingObjects import _edge_length, _edge_points
from freecad_cloth.avatar.AvatarCollision import AvatarSpec, CollisionSurface, surface_from_triangles
from ClothSolver import ClothSystem, Particle
from fixtures.garment_fixtures import two_piece_rectangle, mirrored_pair, multi_piece


def test_svg_units_and_stable_ids():
    svg=to_svg(rectangle(100,50)); assert 'data-units="mm"' in svg and 'data-edge-ids="bottom right top left"' in svg; assert 'width="100mm"' in svg and 'height="50mm"' in svg

def test_seam_semantics():
    seams=[SeamConstraint('s1','a','edge0','b','edge1')]; assert validate_seam_graph(seams,{'a','b'},{'a':{'edge0'},'b':{'edge1'}})

def test_avatar_contract():
    surface=CollisionSurface(((0,0,0),(1,0,0),(0,1,0)),((0,1,2),),thickness=1.0); avatar=AvatarSpec('fixture',collision=surface); avatar.validate(); assert surface.center==(1/3,1/3,0.0)

def test_triangle_surface_collision():
    surface=surface_from_triangles(((-10,-10,0),(10,-10,0),(10,10,0),(-10,10,0)),((0,1,2),(0,2,3)),thickness=1.0); system=ClothSystem([Particle(0,0,-0.25)]); system.step(dt=1/60,iterations=1,gravity=(0,0,0),surface=surface); assert system.particles[0].z>=0.99

def test_golden_fixtures_are_deterministic():
    assert two_piece_rectangle()['pieces'][0].sampled_outline()==two_piece_rectangle()['pieces'][0].sampled_outline(); assert mirrored_pair()['mirrored'] is True; assert multi_piece()['seams']==3

def test_pattern_construction_and_dxf_export():
    pattern=rectangle(100,60); derived=add_notches(derive_cut_boundary(pattern,5),[Notch('waist','right',0.5)]); derived=add_marks(derived,[PatternMark('grain','Grainline',angle=90,length=40,text='Grain')]); svg=to_svg(pattern,derived=derived); assert 'id="sewing-boundary"' in svg and 'id="cut-boundary"' in svg and 'id="notch-waist"' in svg and 'data-kind="Grainline"' in svg
    dxf=to_dxf(pattern,derived=derived); assert 'LWPOLYLINE' in dxf and '8\nSEWING' in dxf and '8\nCUT' in dxf; assert from_dxf_metadata(dxf)=={'version':1,'units':'mm','edge_ids':['bottom','right','top','left']}

def test_pattern_offset_supports_curves_and_per_edge_widths():
    pattern=ParametricPattern([LineSegment('bottom',(0,0),(10,0)),LineSegment('right',(10,0),(10,5)),QuadraticBezier('top',(10,5),(5,9),(0,5)),LineSegment('left',(0,5),(0,0))]); derived=derive_cut_boundary(pattern,2,{'right':4},curve_samples=8); assert derived.cut_boundary[1].points[0]==(14.0,0.0) and len(derived.cut_boundary[2].points)==8

def test_invalid_pattern_mark_reference_is_rejected():
    try: add_marks(derive_cut_boundary(rectangle(10,10),1),[PatternMark('bad','Fold',segment_id='missing')]); assert False
    except ValueError: pass


def test_closed_sewing_outline_edge_wraps_to_first_vertex():
    piece = SimpleNamespace(Width=999.0, Height=999.0, SewingOutline=repr([(0, 0), (4, 0), (4, 3)]))
    assert _edge_length(piece, 2) == 5.0


def test_sewing_edge_points_apply_rotated_piece_placement_once():
    class Vector:
        def __init__(self, x, y, z=0.0): self.x, self.y, self.z = float(x), float(y), float(z)

    class RotatedPlacement:
        def multVec(self, value):
            return Vector(-value.y + 10, value.x - 5, value.z + 2)

    FakeApp = type("FakeApp", (), {"Vector": Vector})

    piece = SimpleNamespace(
        Width=4.0,
        Height=3.0,
        SewingOutline=repr([(0, 0), (4, 0), (4, 3)]),
        Placement=RotatedPlacement(),
    )
    old_freecad = sys.modules.get('FreeCAD')
    sys.modules['FreeCAD'] = FakeApp()
    try:
        start, end = _edge_points(piece, 1, 0.0, 1.0, z=0.2)
    finally:
        if old_freecad is None: sys.modules.pop('FreeCAD', None)
        else: sys.modules['FreeCAD'] = old_freecad
    assert (start.x, start.y, start.z) == (10.0, -1.0, 2.2)
    assert (end.x, end.y, end.z) == (7.0, -1.0, 2.2)

if __name__=='__main__':
    for name,fn in globals().copy().items():
        if name.startswith('test_'): fn()
    print('side-task tests passed')