import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ClothSolver import ClothSystem
from DrapeQuality import assert_quality, benchmark, measure
from DrapeTarget import DrapeTargetSpec, source_signature


def test_metrics_capture_constraint_residual_and_displacement():
    system = ClothSystem.grid(40, 20, nx=4, ny=3)
    initial = [p.position() for p in system.particles]
    system.step(dt=1 / 60, iterations=8, gravity=(0, 0, -98.1))
    metrics = measure(system, initial)
    assert metrics.particle_count == 12
    assert metrics.constraint_count == 29
    assert metrics.max_displacement > 0
    assert metrics.max_constraint_error <= 0.5
    assert_quality(metrics)


def test_benchmark_repeats_are_deterministic():
    result = benchmark(lambda: ClothSystem.grid(30, 15, nx=4, ny=3), steps=4, iterations=6, repeats=2, gravity=(0, 0, -98.1))
    assert len(result["runs"]) == 2
    assert result["runs"][0]["metrics"] == result["runs"][1]["metrics"]
    assert result["runs"][0]["runtime_seconds"] >= 0


def test_quality_rejects_non_finite_state():
    system = ClothSystem.grid(10, 10, nx=2, ny=2)
    system.particles[0].x = float("nan")
    metrics = measure(system)
    assert not metrics.finite
    try: assert_quality(metrics)
    except AssertionError: pass
    else: raise AssertionError("non-finite state must fail quality gate")


def test_drape_target_contract_tracks_source_changes():
    class Vec:
        def __init__(self, x=0, y=0, z=0): self.x, self.y, self.z = x, y, z
    class Rot:
        Angle = 0.0
        Axis = Vec(0, 0, 1)
    class PlacementType:
        Base = Vec()
        Rotation = Rot()
    class ShapeType:
        value = 1
        def isNull(self): return False
        def hashCode(self): return self.value
    class Target:
        Name = "Target"
        Label = "Target"
        Placement = PlacementType()
        Shape = ShapeType()
    DrapeTargetSpec("Mannequin", "ClothAvatar", 1.0, 2.0).validate()
    DrapeTargetSpec("FreeCAD Geometry", "Target", 1.0, 2.0).validate()
    target = Target(); baseline = source_signature(target, 1.0, 2.0)
    target.Shape.value = 2
    assert source_signature(target, 1.0, 2.0) != baseline


if __name__ == "__main__":
    for name, fn in globals().copy().items():
        if name.startswith("test_"): fn()
    print("drape quality and target tests passed")
