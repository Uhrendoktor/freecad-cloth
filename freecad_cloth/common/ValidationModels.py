"""Pydantic schemas for untrusted geometry and numerical inputs.

Validate at API boundaries rather than inside numerical inner loops. These
models normalize finite coordinates once and reject silent type coercion.
"""
from __future__ import annotations

from collections.abc import Iterable
from math import isfinite
from numbers import Real
from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StrictBool, StrictInt, StrictStr, TypeAdapter, model_validator


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


class ParticleInput(InputModel):
    """Finite solver particle state with a non-negative inverse mass."""

    x: FiniteNumber
    y: FiniteNumber
    z: FiniteNumber
    inv_mass: FiniteNumber = 1.0

    @model_validator(mode="after")
    def inverse_mass_is_nonnegative(self) -> ParticleInput:
        """Reject a negative inverse mass."""
        if self.inv_mass < 0.0:
            raise ValueError("inverse mass must be non-negative")
        return self


class GridInput(InputModel):
    """Validate finite rectangular solver dimensions and integer resolution."""

    width: FiniteNumber
    height: FiniteNumber
    nx: StrictInt = Field(ge=2)
    ny: StrictInt = Field(ge=2)
    origin: Point3D = (0.0, 0.0, 0.0)

    @model_validator(mode="after")
    def dimensions_are_positive(self) -> GridInput:
        """Require positive dimensions and a finite three-dimensional origin."""
        if self.width <= 0.0 or self.height <= 0.0:
            raise ValueError("grid dimensions must be positive and finite")
        return self


class DistanceConstraintInput(InputModel):
    """Finite distance-constraint values and exact non-negative particle indices."""

    a: StrictInt = Field(ge=0)
    b: StrictInt = Field(ge=0)
    rest: FiniteNumber
    compliance: FiniteNumber = 0.0

    @model_validator(mode="after")
    def physical_parameters_are_nonnegative(self) -> DistanceConstraintInput:
        """Reject negative rest lengths or compliance."""
        if self.rest < 0.0:
            raise ValueError("constraint rest length must be non-negative")
        if self.compliance < 0.0:
            raise ValueError("constraint compliance must be non-negative")
        return self


class ParticlePairInput(InputModel):
    """Two strict non-negative particle indices."""

    a: StrictInt = Field(ge=0)
    b: StrictInt = Field(ge=0)


class ParticleIndexInput(InputModel):
    """One strict non-negative particle index."""

    index: StrictInt = Field(ge=0)


class TransformMatrixInput(InputModel):
    """Finite row-major 4x4 transform with a non-zero homogeneous scale."""

    matrix: tuple[FiniteNumber, ...]

    @model_validator(mode="after")
    def matrix_shape_and_scale_are_valid(self) -> TransformMatrixInput:
        """Require sixteen finite entries and a usable homogeneous scale."""
        if len(self.matrix) != 16:
            raise ValueError("assembly transform must contain 16 values")
        if abs(self.matrix[15]) < 1e-12:
            raise ValueError("assembly transform has an invalid homogeneous scale")
        return self



class CollisionSurfaceInput(InputModel):
    """Validate the finite geometry and topology passed to a collision solver."""

    vertices: tuple[Point3D, ...]
    triangles: tuple[Triangle, ...]
    region: StrictStr = "body"
    thickness: FiniteNumber = 0.0

    @model_validator(mode="after")
    def surface_is_valid(self) -> CollisionSurfaceInput:
        """Reject empty surfaces, invalid connectivity, and invalid thickness."""
        if len(self.vertices) < 3 or not self.triangles:
            raise ValueError("collision surface needs vertices and triangles")
        if self.thickness < 0.0:
            raise ValueError("collision thickness must be finite and non-negative")
        if not self.region.strip():
            raise ValueError("collision region must not be empty")
        for triangle in self.triangles:
            if any(index < 0 or index >= len(self.vertices) for index in triangle):
                raise ValueError("collision triangle index out of range")
        return self


class PBDStepInput(InputModel):
    """Validated timestep, iteration count, and gravity for one solver step."""

    dt: FiniteNumber
    iterations: StrictInt = Field(ge=1)
    gravity: Point3D = (0.0, 0.0, -9810.0)

    @model_validator(mode="after")
    def timestep_is_positive(self) -> PBDStepInput:
        """Reject non-positive timesteps."""
        if self.dt <= 0.0:
            raise ValueError("dt must be positive and finite")
        return self


class PBDCollisionConfig(InputModel):
    """Validated environment settings for collision voxelization."""

    substeps: StrictInt = Field(ge=1)
    collision_tolerance_mm: FiniteNumber = Field(ge=0.0)
    collision_voxel_mm: FiniteNumber = Field(ge=2.0)


class SimulationMeshQualityInput(InputModel):
    """Validate height and boundary spacing before simulation mesh generation."""

    start_height: FiniteNumber
    particle_distance: FiniteNumber

    @model_validator(mode="after")
    def spacing_is_positive(self) -> SimulationMeshQualityInput:
        """Require a positive particle spacing."""
        if self.particle_distance <= 0.0:
            raise ValueError("particle_distance must be positive and finite")
        return self


class DrapeTargetInput(InputModel):
    """Validate persisted/user-provided collision-target options."""

    target_type: Literal["Mannequin", "FreeCAD Geometry"]
    source_name: StrictStr
    deflection: FiniteNumber = Field(gt=0.0)
    thickness: FiniteNumber = Field(ge=0.0)

    @model_validator(mode="after")
    def source_is_named(self) -> DrapeTargetInput:
        """Reject empty source identifiers."""
        if not self.source_name.strip():
            raise ValueError("drape target source must not be empty")
        return self


class PatternPieceInput(InputModel):
    """Validate the numeric boundary of a canonical 2D pattern piece."""

    name: StrictStr
    outline: tuple[Point2D, ...]
    seam_allowance: FiniteNumber = 0.0
    grainline_angle: FiniteNumber = 0.0
    id: StrictStr

    @model_validator(mode="after")
    def piece_is_valid(self) -> PatternPieceInput:
        """Require identity, a usable outline, and non-negative allowance."""
        if not self.name.strip() or not self.id.strip():
            raise ValueError("pattern piece name and id must not be empty")
        if len(self.outline) < 3:
            raise ValueError("pattern piece outline needs at least three points")
        if self.seam_allowance < 0.0:
            raise ValueError("seam allowance must be non-negative and finite")
        return self


class BoundaryIRInput(InputModel):
    """Validate sampled 3D boundary data crossing into the solver-neutral IR."""

    id: StrictStr
    kind: Literal["line", "arc", "bspline", "bezier", "curve"]
    samples: tuple[Point3D, ...]
    parameter_range: tuple[FiniteNumber, FiniteNumber] = (0.0, 1.0)

    @model_validator(mode="after")
    def boundary_is_valid(self) -> BoundaryIRInput:
        """Require an identity, enough samples, and an increasing finite range."""
        if not self.id.strip():
            raise ValueError("boundary id must not be empty")
        if len(self.samples) < 2:
            raise ValueError("boundary needs at least two samples")
        if not self.parameter_range[1] > self.parameter_range[0]:
            raise ValueError("boundary parameter range must have positive extent")
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
