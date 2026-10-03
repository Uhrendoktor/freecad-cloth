"""Small deterministic contracts suitable for CrossHair symbolic checking."""

from __future__ import annotations

from freecad_cloth.simulation.ClothSolver import Particle, distance


def particle_distance_contract(a: Particle, b: Particle) -> float:
    """Prove basic metric properties used by the solver-input model."""
    result = distance(a, b)
    assert result >= 0.0
    assert distance(a, a) == 0.0
    assert distance(a, b) == distance(b, a)
    return result
