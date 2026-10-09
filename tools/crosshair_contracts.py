"""Small deterministic contracts suitable for CrossHair symbolic checking."""

from __future__ import annotations

from freecad_cloth.sewing.SewingCorrespondence import map_parameter
from freecad_cloth.simulation.ClothSolver import Particle, distance


def particle_distance_contract(a: Particle, b: Particle) -> float:
    """Prove basic metric properties used by the solver-input model."""
    result = distance(a, b)
    assert result >= 0.0
    assert distance(a, a) == 0.0
    assert distance(a, b) == distance(b, a)
    return result



def normalized_seam_mapping_contract(parameter_a: float, reversed_b: bool) -> float:
    """Symbolically check range bounds and complementary orientation for seam mapping."""
    if not 0.0 <= parameter_a <= 1.0:
        return 0.0
    result = map_parameter(parameter_a, reversed_b=reversed_b)
    complementary = map_parameter(parameter_a, reversed_b=not reversed_b)
    assert 0.0 <= result <= 1.0
    assert 0.0 <= complementary <= 1.0
    assert result + complementary == 1.0
    return result
