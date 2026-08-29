"""Persistable simulation-quality and fabric parameter model.

This module is deliberately FreeCAD-independent.  FreeCAD document objects can
store the values returned by ``preset`` and the simulation backend can consume
``solver_parameters`` without coupling the semantic material model to a GUI.
"""
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class SimulationQuality:
    name: str
    particle_distance: float
    solver_iterations: int
    substeps: int


QUALITY_PRESETS = {
    "Fast": SimulationQuality("Fast", 8.0, 4, 1),
    "Balanced": SimulationQuality("Balanced", 4.0, 8, 1),
    "Final": SimulationQuality("Final", 2.0, 16, 2),
}


@dataclass(frozen=True)
class FabricMaterial:
    """Physical fabric controls in FreeCAD's millimetre/gram unit convention."""
    density_g_m2: float = 150.0
    thickness_mm: float = 0.5
    stretch: float = 0.02
    shear: float = 0.02
    bend: float = 0.01
    friction: float = 0.5

    def validate(self):
        if self.density_g_m2 <= 0:
            raise ValueError("density must be positive")
        if self.thickness_mm <= 0:
            raise ValueError("thickness must be positive")
        for name in ("stretch", "shear", "bend"):
            value = getattr(self, name)
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        if not 0 <= self.friction <= 1:
            raise ValueError("friction must be between 0 and 1")
        return self

    @property
    def mass_per_area_kg_mm2(self):
        # g/m^2 -> kg/mm^2
        return self.density_g_m2 * 1e-9


def preset(name: str) -> SimulationQuality:
    try:
        return QUALITY_PRESETS[str(name)]
    except KeyError as exc:
        raise ValueError(f"unknown simulation quality preset: {name!r}") from exc


def apply_quality(quality: SimulationQuality, *, iterations=None, substeps=None):
    """Return a validated quality profile with explicit overrides."""
    q = preset(quality.name) if isinstance(quality, SimulationQuality) else preset(quality)
    return replace(q,
                   solver_iterations=q.solver_iterations if iterations is None else int(iterations),
                   substeps=q.substeps if substeps is None else int(substeps))


def solver_parameters(quality: SimulationQuality, material: FabricMaterial):
    material.validate()
    quality = apply_quality(quality)
    return {
        "particle_distance": quality.particle_distance,
        "iterations": quality.solver_iterations,
        "substeps": quality.substeps,
        "density_g_m2": material.density_g_m2,
        "thickness_mm": material.thickness_mm,
        "stretch": material.stretch,
        "shear": material.shear,
        "bend": material.bend,
        "friction": material.friction,
    }
