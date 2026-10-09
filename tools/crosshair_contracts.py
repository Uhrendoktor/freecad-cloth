"""Symbolic contracts that call production Python math implementations.

CrossHair explores these contracts with symbolic inputs and reports counterexamples.
The contracts intentionally target pure, bounded helpers rather than FreeCAD/OCCT
objects or native solver state, which CrossHair cannot model exhaustively.
"""

from __future__ import annotations

from freecad_cloth.pattern.PatternGeometry import _lerp, _line_intersection
from freecad_cloth.sewing.SewingCorrespondence import map_parameter
from freecad_cloth.simulation.ClothSolver import Particle, distance


def particle_distance_contract(a: Particle, b: Particle) -> float:
    """Check metric identities against the production solver-input distance."""
    result = distance(a, b)
    assert result >= 0.0
    assert distance(a, a) == 0.0
    assert distance(a, b) == distance(b, a)
    return result


def normalized_seam_mapping_contract(parameter_a: float, reversed_b: bool) -> float:
    """Check direction complement and normalized bounds on the real seam mapper."""
    if not 0.0 <= parameter_a <= 1.0:
        return 0.0
    result = map_parameter(parameter_a, reversed_b=reversed_b)
    complementary = map_parameter(parameter_a, reversed_b=not reversed_b)
    assert 0.0 <= result <= 1.0
    assert 0.0 <= complementary <= 1.0
    assert result + complementary == 1.0
    return result


def ranged_seam_mapping_contract(
    parameter_a: float,
    start_a: float,
    end_a: float,
    start_b: float,
    end_b: float,
    reversed_b: bool,
) -> float:
    """Check interval bounds and endpoint mapping through the production seam mapper."""
    assert 0.0 <= parameter_a <= 1.0
    assert 0.0 <= start_a < end_a <= 1.0
    assert 0.0 <= start_b < end_b <= 1.0
    result = map_parameter(parameter_a, start_a, end_a, start_b, end_b, reversed_b)
    assert start_b <= result <= end_b
    if parameter_a == start_a:
        assert result == (end_b if reversed_b else start_b)
    if parameter_a == end_a:
        assert result == (start_b if reversed_b else end_b)
    return result


def interpolation_contract(start: float, end: float, fraction: float) -> float:
    """Check the production interpolation helper preserves its convex interval."""
    assert -1e100 <= start <= 1e100
    assert -1e100 <= end <= 1e100
    assert 0.0 <= fraction <= 1.0
    result = _lerp(start, end, fraction)
    assert min(start, end) <= result <= max(start, end)
    if fraction == 0.0:
        assert result == start
    if fraction == 1.0:
        assert result == end
    return result


def perpendicular_line_intersection_contract(x: float, y: float) -> tuple[float, float]:
    """Check the production line-intersection math on symbolic perpendicular lines."""
    assert -1e6 <= x <= 1e6
    assert -1e6 <= y <= 1e6
    result = _line_intersection((-1.0, y), (1.0, y), (x, -1.0), (x, 1.0))
    assert result is not None
    assert result[0] == x
    assert result[1] == y
    return result
