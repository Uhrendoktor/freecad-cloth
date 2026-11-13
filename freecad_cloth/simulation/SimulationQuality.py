# Copyright (C) 2026 FreeCAD Cloth contributors
"""Persistable simulation-quality and fabric parameter model.

This module is deliberately FreeCAD-independent.  FreeCAD document objects can
store the values returned by ``preset`` and the simulation backend can consume
``solver_parameters`` without coupling the semantic material model to a GUI.
"""

from __future__ import annotations

from dataclasses import replace
from math import isfinite
from typing import TYPE_CHECKING

from pydantic.dataclasses import dataclass as pydantic_dataclass

from freecad_cloth.common.ValidationModels import validate_finite_number

if TYPE_CHECKING:
    from collections.abc import Iterable


@pydantic_dataclass(frozen=True)
class SimulationQuality:
    """Public data model or service class for SimulationQuality."""

    name: str
    particle_distance: float
    solver_iterations: int
    substeps: int


QUALITY_PRESETS = {
    "Fast": SimulationQuality("Fast", 8.0, 4, 1),
    "Balanced": SimulationQuality("Balanced", 4.0, 8, 1),
    "Final": SimulationQuality("Final", 2.0, 16, 2),
}


def normalize_color_rgb(value: Iterable[object]) -> tuple[float, float, float]:
    """Normalize FreeCAD/Python color representations to three RGB floats.

    Args:
        value: Iterable containing three RGB channel values.

    Returns:
        Three normalized channel values in the inclusive range from zero to one.

    Raises:
        ValueError: If fewer than three channels are provided or a channel is out of range.
    """
    try:
        values = tuple(validate_finite_number(item) for item in value)
    except (TypeError, ValueError):
        values = ()
    if len(values) < 3:
        msg = "color_rgb must contain at least three channels"
        raise ValueError(msg)
    values = values[:3]
    if any(item > 1.0 for item in values) and all(0.0 <= item <= 255.0 for item in values):
        values = tuple(item / 255.0 for item in values)
    if any(not 0.0 <= item <= 1.0 for item in values):
        msg = "color_rgb channels must be between 0 and 1 or 0 and 255"
        raise ValueError(msg)
    return values[0], values[1], values[2]


@pydantic_dataclass(frozen=True)
class FabricMaterial:
    """Physical fabric controls plus persisted presentation properties."""

    density_g_m2: float = 150.0
    thickness_mm: float = 0.5
    stretch: float = 0.02
    shear: float = 0.02
    bend: float = 0.01
    friction: float = 0.5
    color_rgb: tuple[float, ...] = (0.72, 0.34, 0.46)
    specular: float = 0.25
    roughness: float = 0.65
    transparency: float = 0.0

    def validate(self) -> FabricMaterial:
        """Validate this value and raise ValueError when its state is invalid.

        Returns:
            This immutable material after all physical and presentation fields pass validation.

        Raises:
            ValueError: If a physical coefficient or presentation value is outside its valid range.
        """
        if not isfinite(self.density_g_m2) or self.density_g_m2 <= 0:
            msg = "density must be positive and finite"
            raise ValueError(msg)
        if not isfinite(self.thickness_mm) or self.thickness_mm <= 0:
            msg = "thickness must be positive and finite"
            raise ValueError(msg)
        for name in ("stretch", "shear", "bend"):
            value = getattr(self, name)
            if not 0 <= value <= 1:
                msg = f"{name} must be between 0 and 1"
                raise ValueError(msg)
        if not 0 <= self.friction <= 1:
            msg = "friction must be between 0 and 1"
            raise ValueError(msg)
        normalize_color_rgb(self.color_rgb)
        if not 0 <= self.specular <= 1:
            msg = "specular must be between 0 and 1"
            raise ValueError(msg)
        if not 0 <= self.roughness <= 1:
            msg = "roughness must be between 0 and 1"
            raise ValueError(msg)
        if not 0 <= self.transparency <= 100:
            msg = "transparency must be between 0 and 100 percent"
            raise ValueError(msg)
        return self

    @property
    def mass_per_area_kg_mm2(self) -> float:
        # g/m^2 -> kg/mm^2
        """Return the fabric mass per unit area in kilograms per square millimetre.

        Returns:
            Surface mass converted from the authored grams per square metre.
        """
        return self.density_g_m2 * 1e-9


def preset(name: str) -> SimulationQuality:
    """Return one of the named, immutable simulation-quality profiles.

    Args:
        name: Case-sensitive preset name from the supported quality catalogue.

    Returns:
        The requested quality profile with its default tessellation and solver settings.

    Raises:
        ValueError: If the requested name is not a supported quality preset.
    """
    try:
        return QUALITY_PRESETS[str(name)]
    except KeyError as exc:
        msg = f"unknown simulation quality preset: {name!r}"
        raise ValueError(msg) from exc


def apply_quality(
    quality: SimulationQuality | str,
    *,
    iterations: int | None = None,
    substeps: int | None = None,
) -> SimulationQuality:
    """Return a validated quality profile with explicit solver overrides.

    Args:
        quality: Preset name or previously constructed quality profile.
        iterations: Optional replacement solver-iteration count.
        substeps: Optional replacement substep count per simulation frame.

    Returns:
        A new profile containing the selected preset and supplied overrides.

    Raises:
        ValueError: If the named preset does not exist or an override cannot be converted.
    """
    q = preset(quality.name) if isinstance(quality, SimulationQuality) else preset(quality)
    return replace(
        q,
        solver_iterations=q.solver_iterations if iterations is None else int(iterations),
        substeps=q.substeps if substeps is None else int(substeps),
    )


def solver_parameters(
    quality: SimulationQuality, material: FabricMaterial
) -> dict[str, float | int]:
    """Build the numeric solver configuration from a quality/material pair.

    Args:
        quality: Authored tessellation and iteration profile.
        material: Validated fabric properties consumed by the solver.

    Returns:
        Mapping of particle spacing, solver settings, and material coefficients.

    Raises:
        ValueError: If the fabric material or requested quality profile is invalid.
    """
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
