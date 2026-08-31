import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pypbd

from PatternGeometry import rectangle
from PatternMesh import triangulate
from XPBD import (
    BendingConstraint,
    DistanceConstraint,
    ShearConstraint,
    XPBDClothSolver,
    bending_constraints,
    shear_constraints,
    structural_constraints,
)
from SimulationBackend import ClothState


def test_structural_constraints_are_unique():
    mesh = triangulate(rectangle(100.0, 50.0))
    constraints = structural_constraints(mesh)
    assert len(constraints) == 5
    assert len({(c.a, c.b) for c in constraints}) == 5


def test_shear_and_bending_constraints_are_explicit():
    mesh = triangulate(rectangle(100.0, 50.0))
    shear = shear_constraints(mesh)
    bending = bending_constraints(mesh)
    assert shear and bending
    assert all(isinstance(c, ShearConstraint) for c in shear)
    assert all(isinstance(c, BendingConstraint) for c in bending)
    assert all(len((c.a, c.b, c.c, c.d)) == 4 for c in bending)


def test_xpbd_solver_uses_pypbd_and_pin_gravity():
    state = ClothState([(0.0, 0.0, 0.0), (100.0, 0.0, 0.0)])
    state.inverse_masses = [0.0, 1.0]
    solver = XPBDClothSolver([DistanceConstraint(0, 1, 100.0)], iterations=4, pinned=[0])
    assert solver.backend_name == "PositionBasedDynamics/pyPBD"
    solver.step(state, 0.001)
    assert state.positions[0] == (0.0, 0.0, 0.0)
    assert state.positions[1][2] < 0.0


def test_zero_constraint_particle_is_integrated_by_pypbd():
    state = ClothState([(0.0, 0.0, 0.0)])
    solver = XPBDClothSolver(gravity=(0.0, 0.0, -1000.0), iterations=2)
    solver.step(state, 0.01)
    assert state.positions[0][2] < 0.0
    assert state.velocities[0][2] < 0.0


def test_primitive_colliders_fail_closed_instead_of_using_python_projection():
    from XPBD import CapsuleCollider
    capsule = CapsuleCollider((0.0, 0.0, -10.0), (0.0, 0.0, 10.0), 5.0)
    try:
        XPBDClothSolver(colliders=[capsule])
    except NotImplementedError:
        pass
    else:
        raise AssertionError("primitive colliders must be routed through pyPBD, not a Python projection fallback")


if __name__ == "__main__":
    for name, fn in globals().copy().items():
        if name.startswith("test_"):
            fn()
    print("xpbd tests passed")
