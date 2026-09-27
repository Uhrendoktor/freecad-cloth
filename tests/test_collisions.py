from math import sqrt

from freecad_cloth.avatar.AvatarCollision import coarsen_collision_surface, surface_from_triangles
from freecad_cloth.pattern.PatternGeometry import rectangle
from freecad_cloth.pattern.PatternMesh import triangulate
from freecad_cloth.simulation.SimulationBackend import ClothState
from freecad_cloth.simulation.XPBD import DistanceConstraint, SphereCollider, XPBDClothSolver


def test_sphere_collision_pushes_particle_outside_surface():
    state = ClothState([(0.0, 0.0, 0.0)], inverse_masses=[1.0])
    solver = XPBDClothSolver(gravity=(0.0, 0.0, 0.0), colliders=[SphereCollider((0.0, 0.0, 0.0), 10.0)], iterations=2)
    solver.step(state, 0.01)
    assert state.positions[0] == (0.0, 0.0, 10.0)


def test_collision_and_structural_constraints_can_coexist():
    mesh = triangulate(rectangle(20.0, 20.0))
    constraints = [DistanceConstraint(0, 1, 20.0)]
    solver = XPBDClothSolver(constraints, gravity=(0.0, 0.0, 0.0), colliders=[SphereCollider((0.0, 0.0, 0.0), 5.0)], iterations=16)
    state = ClothState([(0.0, 0.0, 0.0), (20.0, 0.0, 0.0)])
    solver.step(state, 0.01)
    x, y, z = state.positions[0]
    # Structural projection may pull a colliding vertex microscopically below
    # the contact surface; the invariant is enforced within solver tolerance.
    assert sqrt(x * x + y * y + z * z) >= 4.9



def _synthetic_triangle_surface():
    vertices = []
    triangles = []

    def add_triangle(center, scale=0.5):
        base = len(vertices)
        x, y, z = center
        vertices.extend(((x + scale, y, z), (x, y + scale, z), (x, y, z + scale)))
        triangles.append((base, base + 1, base + 2))

    # Six distant axis-extreme regions plus a dense central cluster. A spatial
    # sampler should preserve the extremes instead of consuming the budget in
    # the dense center.
    for center in (
        (-100.0, 0.0, 0.0),
        (100.0, 0.0, 0.0),
        (0.0, -100.0, 0.0),
        (0.0, 100.0, 0.0),
        (0.0, 0.0, -100.0),
        (0.0, 0.0, 100.0),
    ):
        add_triangle(center)
    for index in range(40):
        offset = float(index % 5) * 0.5
        add_triangle((offset, offset, offset))

    return surface_from_triangles(vertices, triangles, thickness=0.25)


def test_collision_surface_sampling_is_deterministic_and_spatially_broad():
    surface = _synthetic_triangle_surface()
    first = coarsen_collision_surface(surface, max_triangles=6)
    second = coarsen_collision_surface(surface, max_triangles=6)

    assert first.triangles == second.triangles
    assert len(first.triangles) == 6
    assert len(set(first.triangles)) == 6

    selected_x = []
    selected_y = []
    selected_z = []
    for triangle in first.triangles:
        centroid = tuple(sum(first.vertices[index][axis] for index in triangle) / 3.0 for axis in range(3))
        selected_x.append(centroid[0])
        selected_y.append(centroid[1])
        selected_z.append(centroid[2])

    assert min(selected_x) < -90.0 and max(selected_x) > 90.0
    assert min(selected_y) < -90.0 and max(selected_y) > 90.0
    assert min(selected_z) < -90.0 and max(selected_z) > 90.0


if __name__ == "__main__":
    test_sphere_collision_pushes_particle_outside_surface()
    test_collision_and_structural_constraints_can_coexist()
    print("collision tests passed")
