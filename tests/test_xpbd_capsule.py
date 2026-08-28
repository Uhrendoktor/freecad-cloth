import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from SimulationBackend import ClothState
from XPBD import CapsuleCollider, XPBDClothSolver


def test_capsule_pushes_particle_to_surface():
    state = ClothState([(0.0, 0.0, 0.0)])
    state.inverse_masses = [1.0]
    state.velocities = [(0.0, 0.0, 0.0)]
    capsule = CapsuleCollider((0.0, 0.0, -10.0), (0.0, 0.0, 10.0), 5.0)
    solver = XPBDClothSolver(gravity=(0.0, 0.0, 0.0), iterations=2, colliders=[capsule])
    solver.step(state, 0.1)
    assert state.positions[0] == (5.0, 0.0, 0.0)


def test_capsule_collision_is_deterministic():
    capsule = CapsuleCollider((-2.0, 0.0, -5.0), (-2.0, 0.0, 5.0), 3.0, 0.5)
    results = []
    for _ in range(2):
        state = ClothState([(-2.0, 2.0, 0.0)])
        state.inverse_masses = [1.0]
        state.velocities = [(0.0, 0.0, 0.0)]
        XPBDClothSolver(gravity=(0.0, 0.0, 0.0), iterations=4, colliders=[capsule]).step(state, 0.1)
        results.append(tuple(state.positions[0]))
    assert results[0] == results[1]
    assert results[0][1] == 5.5


def test_capsule_validation_rejects_degenerate_segment():
    try:
        CapsuleCollider((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 1.0).validate()
    except ValueError:
        return
    raise AssertionError("degenerate capsule must be rejected")


if __name__ == "__main__":
    test_capsule_pushes_particle_to_surface()
    test_capsule_collision_is_deterministic()
    test_capsule_validation_rejects_degenerate_segment()
    print("capsule collision tests passed")
