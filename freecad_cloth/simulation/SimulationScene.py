"""FreeCAD-independent simulation scene assembly and stepping helpers.

The scene layer bridges a pattern mesh and a solver without making the solver
know about FreeCAD.  It is deliberately small so a future collision backend
can replace the planar avatar and XPBD reference implementation.
"""
from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from freecad_cloth.pattern.PatternMesh import TriangleMesh
from freecad_cloth.simulation.SimulationBackend import ClothState, Vec3, ClothSolver
from freecad_cloth.simulation.XPBD import DistanceConstraint, XPBDClothSolver, structural_constraints


@dataclass
class SimulationScene:
    """A single cloth mesh, its dynamic state, and solver configuration."""
    mesh: TriangleMesh
    state: ClothState
    solver: ClothSolver

    @classmethod
    def from_mesh(
        cls,
        mesh: TriangleMesh,
        *,
        gravity: Vec3 = (0.0, 0.0, -9810.0),
        iterations: int = 8,
        pinned: Iterable[int] = (),
        constraints: Optional[Iterable[DistanceConstraint]] = None,
    ) -> "SimulationScene":
        mesh.validate()
        positions = [(float(x), float(y), 0.0) for x, y in mesh.vertices]
        pin_set = frozenset(pinned)
        inverse_masses = [0.0 if i in pin_set else 1.0 for i in range(len(positions))]
        state = ClothState(positions, inverse_masses=inverse_masses)
        solver_constraints = tuple(constraints) if constraints is not None else structural_constraints(mesh)
        solver = XPBDClothSolver(solver_constraints, gravity=gravity, iterations=iterations, pinned=pin_set)
        return cls(mesh, state, solver)

    def step(self, dt: float) -> ClothState:
        self.state = self.solver.step(self.state, dt)
        return self.state

    def step_many(self, steps: int, dt: float) -> ClothState:
        if steps < 0:
            raise ValueError("steps must be non-negative")
        for _ in range(steps):
            self.step(dt)
        return self.state

    def triangles(self) -> Tuple[Tuple[Vec3, Vec3, Vec3], ...]:
        return tuple(
            (self.state.positions[a], self.state.positions[b], self.state.positions[c])
            for a, b, c in self.mesh.triangles
        )
