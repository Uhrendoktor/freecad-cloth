import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PatternGeometry import rectangle
from PatternExport import to_svg
from SewingSemantics import SeamConstraint, validate_seam_graph
from AvatarCollision import AvatarSpec, CollisionSurface, surface_from_triangles
from ClothSolver import ClothSystem, Particle
from fixtures.garment_fixtures import two_piece_rectangle, mirrored_pair, multi_piece


def test_svg_units_and_stable_ids():
    svg = to_svg(rectangle(100, 50))
    assert 'data-units="mm"' in svg and 'data-edge-ids="bottom right top left"' in svg
    assert 'width="100mm"' in svg and 'height="50mm"' in svg


def test_seam_semantics():
    seams = [SeamConstraint('s1', 'a', 'edge0', 'b', 'edge1')]
    assert validate_seam_graph(seams, {'a','b'}, {'a': {'edge0'}, 'b': {'edge1'}})


def test_avatar_contract():
    surface = CollisionSurface(((0,0,0),(1,0,0),(0,1,0)), ((0,1,2),), thickness=1.0)
    avatar = AvatarSpec('fixture', collision=surface)
    avatar.validate()
    assert surface.center == (1/3, 1/3, 0.0)


def test_triangle_surface_collision():
    surface = surface_from_triangles(
        ((-10,-10,0),(10,-10,0),(10,10,0),(-10,10,0)),
        ((0,1,2),(0,2,3)),
        thickness=1.0,
    )
    system = ClothSystem([Particle(0, 0, -0.25)])
    system.step(dt=1/60, iterations=1, gravity=(0,0,0), surface=surface)
    assert system.particles[0].z >= 0.99


def test_golden_fixtures_are_deterministic():
    assert two_piece_rectangle()['pieces'][0].sampled_outline() == two_piece_rectangle()['pieces'][0].sampled_outline()
    assert mirrored_pair()['mirrored'] is True
    assert multi_piece()['seams'] == 3


if __name__ == '__main__':
    for name, fn in globals().copy().items():
        if name.startswith('test_'): fn()
    print('side-task tests passed')
