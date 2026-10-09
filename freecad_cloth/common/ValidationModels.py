"""Pydantic schemas for untrusted geometry and numerical inputs.

Validate at API boundaries rather than inside numerical inner loops. These
models normalize finite coordinates once and reject silent type coercion.
"""
from __future__ import annotations

from collections.abc import Iterable
from math import isfinite
from numbers import Real
from typing import Annotated, TypeAlias

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StrictBool, StrictInt, TypeAdapter, model_validator


def _finite_real(value: object) -> float:
    """Normalize a real number to float while rejecting bools and non-finite values."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("value must be a finite real number")
    try:
        result = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError("value must be a finite real number") from exc
    if not isfinite(result):
        raise ValueError("value must be a finite real number")
    return result


FiniteNumber: TypeAlias = Annotated[float, BeforeValidator(_finite_real)]
Point2D: TypeAlias = tuple[FiniteNumber, FiniteNumber]
Point3D: TypeAlias = tuple[FiniteNumber, FiniteNumber, FiniteNumber]
FinitePoint: TypeAlias = tuple[FiniteNumber, ...]
Triangle: TypeAlias = tuple[StrictInt, StrictInt, StrictInt]


class InputModel(BaseModel):
    """Shared immutable policy for validation models."""

    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")


class FiniteScalar(InputModel):
    """A single finite real number."""

    value: FiniteNumber


class SampleCount(InputModel):
    """A supported curve/correspondence sampling count."""

    count: StrictInt = Field(ge=2)


class RectangleDimensions(InputModel):
    """Positive finite dimensions for a rectangular pattern."""

    width: FiniteNumber
    height: FiniteNumber

    @model_validator(mode="after")
    def dimensions_are_positive(self) -> RectangleDimensions:
        """Reject zero or negative dimensions."""
        if self.width <= 0.0 or self.height <= 0.0:
            raise ValueError("rectangle dimensions must be positive and finite")
        return self


class SeamAllowanceOptions(InputModel):
    """Validated seam offset and sampling count."""

    allowance: FiniteNumber
    curve_samples: StrictInt = Field(ge=2)

    @model_validator(mode="after")
    def allowance_is_nonnegative(self) -> SeamAllowanceOptions:
        """Reject negative offsets."""
        if self.allowance < 0.0:
            raise ValueError("seam allowance cannot be negative")
        return self


class TriangulationOptions(InputModel):
    """Validated options passed to the Triangle library."""

    curve_samples: StrictInt = Field(default=16, ge=2)
    max_area: FiniteNumber | None = None

    @model_validator(mode="after")
    def area_is_positive(self) -> TriangulationOptions:
        """Require positive finite maximum triangle area when set."""
        if self.max_area is not None and self.max_area <= 0.0:
            raise ValueError("max_area must be positive and finite")
        return self


class MeshArrays(InputModel):
    """Finite vertex coordinates and integer triangle connectivity."""

    vertices: tuple[Point3D, ...]
    triangles: tuple[Triangle, ...]

    @model_validator(mode="after")
    def face_indices_are_in_range(self) -> MeshArrays:
        """Reject references to vertices outside the supplied array."""
        for face in self.triangles:
            if any(index < 0 or index >= len(self.vertices) for index in face):
                raise ValueError("mesh triangle index is out of range")
        return self


class NormalizedRange(InputModel):
    """A finite, non-empty interval contained in [0, 1]."""

    start: FiniteNumber
    end: FiniteNumber

    @model_validator(mode="after")
    def interval_is_valid(self) -> NormalizedRange:
        """Require a strictly increasing normalized interval."""
        if not 0.0 <= self.start < self.end <= 1.0:
            raise ValueError("seam parameter ranges must satisfy 0 <= start < end <= 1")
        return self


class ArcLengthSamplingInput(InputModel):
    """Inputs to select existing vertices by physical arc length."""

    values: tuple[StrictInt, ...]
    points: tuple[FinitePoint, ...]
    count: StrictInt = Field(ge=2)
    start: FiniteNumber = 0.0
    end: FiniteNumber = 1.0

    @model_validator(mode="after")
    def topology_and_range_are_valid(self) -> ArcLengthSamplingInput:
        """Validate paired coordinates and dimensional consistency."""
        if len(self.values) != len(self.points):
            raise ValueError("arc-length sampling points must match edge vertices")
        if len(self.points) < 2:
            raise ValueError("arc-length sampling needs at least two points")
        dimension = len(self.points[0])
        if dimension < 2 or any(len(point) != dimension for point in self.points):
            raise ValueError("arc-length sampling points must have matching dimensions")
        NormalizedRange(start=self.start, end=self.end)
        return self


class CorrespondenceSamplesInput(InputModel):
    """Sample count, ranges, and orientation for seam correspondence."""

    count: StrictInt = Field(ge=2)
    start_a: FiniteNumber = 0.0
    end_a: FiniteNumber = 1.0
    start_b: FiniteNumber = 0.0
    end_b: FiniteNumber = 1.0
    reversed_b: StrictBool = False

    @model_validator(mode="after")
    def both_ranges_are_valid(self) -> CorrespondenceSamplesInput:
        """Reject invalid ranges before generating parameter pairs."""
        NormalizedRange(start=self.start_a, end=self.end_a)
        NormalizedRange(start=self.start_b, end=self.end_b)
        return self


class CorrespondenceAnalysisInput(InputModel):
    """Validate lengths/tolerance, preserving invalid-range report semantics."""

    length_a: FiniteNumber
    length_b: FiniteNumber
    start_a: FiniteNumber = 0.0
    end_a: FiniteNumber = 1.0
    start_b: FiniteNumber = 0.0
    end_b: FiniteNumber = 1.0
    reversed_b: StrictBool = False
    length_tolerance: FiniteNumber = 0.05

    @model_validator(mode="after")
    def lengths_and_tolerance_are_valid(self) -> CorrespondenceAnalysisInput:
        """Reject invalid lengths/tolerances without rejecting classifiable ranges."""
        if self.length_a <= 0.0 or self.length_b <= 0.0:
            raise ValueError("seam lengths must be positive")
        if not 0.0 <= self.length_tolerance < 1.0:
            raise ValueError("length tolerance must be in [0, 1)")
        return self


Point2DAdapter = TypeAdapter(Point2D)
Points2DAdapter = TypeAdapter(tuple[Point2D, ...])
Points3DAdapter = TypeAdapter(tuple[Point3D, ...])


def validate_finite_number(value: object) -> float:
    """Return a finite real input as float, rejecting bool/string coercion."""
    return FiniteScalar(value=value).value


def validate_point2d(value: Iterable[Real]) -> Point2D:
    """Validate and normalize one two-dimensional point."""
    return Point2DAdapter.validate_python(value)


def validate_points2d(values: Iterable[Iterable[Real]]) -> tuple[Point2D, ...]:
    """Validate and normalize a sequence of two-dimensional points."""
    return Points2DAdapter.validate_python(values)


def validate_points3d(values: Iterable[Iterable[Real]]) -> tuple[Point3D, ...]:
    """Validate and normalize a sequence of three-dimensional points."""
    return Points3DAdapter.validate_python(values)
