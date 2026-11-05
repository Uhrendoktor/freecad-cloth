# Copyright (C) 2026 FreeCAD Cloth contributors
"""Pydantic schemas for untrusted geometry and numerical inputs.

Validate at API boundaries rather than inside numerical inner loops. These
models normalize finite coordinates once and reject silent type coercion.
"""

from __future__ import annotations

from math import isfinite
from numbers import Real
from typing import TYPE_CHECKING, Annotated, cast

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    TypeAdapter,
    model_validator,
)

if TYPE_CHECKING:
    from collections.abc import Iterable


def _finite_real(value: object) -> float:
    """Normalize a real number to float while rejecting booleans and non-finite values.

    Args:
        value: Candidate numeric value received at the validation boundary.

    Returns:
        The finite real value normalized to a Python float.

    Raises:
        TypeError: If the input is not a supported real number.
        ValueError: If conversion overflows or the value is not finite.
    """
    if isinstance(value, bool) or not isinstance(value, Real):
        msg = "value must be a finite real number"
        raise TypeError(msg)
    try:
        result = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        msg = "value must be a finite real number"
        raise ValueError(msg) from exc
    if not isfinite(result):
        msg = "value must be a finite real number"
        raise ValueError(msg)
    return result


def _pydantic_finite_real(value: object) -> float:
    """Adapt strict numeric type errors to Pydantic's validation contract.

    Args:
        value: Candidate field value passed to the Pydantic annotated type.

    Returns:
        The finite real number normalized by the shared boundary helper.

    Raises:
        ValueError: If the input type is unsupported or its numeric value is invalid.
    """
    try:
        return _finite_real(value)
    except TypeError as exc:
        raise ValueError(str(exc)) from exc


type FiniteNumber = Annotated[float, BeforeValidator(_pydantic_finite_real)]
type Point2D = tuple[FiniteNumber, FiniteNumber]
type Point3D = tuple[FiniteNumber, FiniteNumber, FiniteNumber]
type FinitePoint = tuple[FiniteNumber, ...]
type Triangle = tuple[StrictInt, StrictInt, StrictInt]


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
        """Reject zero or negative rectangle dimensions.

        Returns:
            The same rectangle model after both dimensions pass validation.

        Raises:
            ValueError: If either dimension is not strictly positive.
        """
        if self.width <= 0.0 or self.height <= 0.0:
            msg = "rectangle dimensions must be positive and finite"
            raise ValueError(msg)
        return self


class SeamAllowanceOptions(InputModel):
    """Validated seam offset and sampling count."""

    allowance: FiniteNumber
    curve_samples: StrictInt = Field(ge=2)

    @model_validator(mode="after")
    def allowance_is_nonnegative(self) -> SeamAllowanceOptions:
        """Reject negative seam offsets.

        Returns:
            The same seam-allowance model after its offset passes validation.

        Raises:
            ValueError: If the seam allowance is negative.
        """
        if self.allowance < 0.0:
            msg = "seam allowance cannot be negative"
            raise ValueError(msg)
        return self


class TriangulationOptions(InputModel):
    """Validated options passed to the Triangle library."""

    curve_samples: StrictInt = Field(default=16, ge=2)
    max_area: FiniteNumber | None = None

    @model_validator(mode="after")
    def area_is_positive(self) -> TriangulationOptions:
        """Require positive finite maximum triangle area when it is set.

        Returns:
            The same triangulation options after the optional area limit is checked.

        Raises:
            ValueError: If a configured maximum triangle area is not positive.
        """
        if self.max_area is not None and self.max_area <= 0.0:
            msg = "max_area must be positive and finite"
            raise ValueError(msg)
        return self


class MeshArrays(InputModel):
    """Finite vertex coordinates and integer triangle connectivity."""

    vertices: tuple[Point3D, ...]
    triangles: tuple[Triangle, ...]

    @model_validator(mode="after")
    def face_indices_are_in_range(self) -> MeshArrays:
        """Reject references to vertices outside the supplied array.

        Returns:
            The same mesh arrays after every triangle index has been checked.

        Raises:
            ValueError: If a triangle refers to a vertex outside the vertex array.
        """
        for face in self.triangles:
            if any(index < 0 or index >= len(self.vertices) for index in face):
                msg = "mesh triangle index is out of range"
                raise ValueError(msg)
        return self


class NormalizedRange(InputModel):
    """A finite, non-empty interval contained in [0, 1]."""

    start: FiniteNumber
    end: FiniteNumber

    @model_validator(mode="after")
    def interval_is_valid(self) -> NormalizedRange:
        """Require a strictly increasing interval inside the normalized range.

        Returns:
            The same normalized-range model after its endpoints are checked.

        Raises:
            ValueError: If the interval is empty, reversed, or outside [0, 1].
        """
        if not 0.0 <= self.start < self.end <= 1.0:
            msg = "seam parameter ranges must satisfy 0 <= start < end <= 1"
            raise ValueError(msg)
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
        """Validate paired coordinates and dimensional consistency.

        Returns:
            The same arc-length sampling input after its topology and range are checked.

        Raises:
            ValueError: If point/index counts, point dimensions, or range endpoints are invalid.
        """
        if len(self.values) != len(self.points):
            msg = "arc-length sampling points must match edge vertices"
            raise ValueError(msg)
        if len(self.points) < 2:
            msg = "arc-length sampling needs at least two points"
            raise ValueError(msg)
        dimension = len(self.points[0])
        if dimension < 2 or any(len(point) != dimension for point in self.points):
            msg = "arc-length sampling points must have matching dimensions"
            raise ValueError(msg)
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
        """Reject invalid ranges before generating parameter pairs.

        Returns:
            The same correspondence-sampling input after both ranges are validated.
        """
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
        """Reject invalid lengths and tolerance while preserving range classification.

        Returns:
            The same correspondence-analysis input after length and tolerance checks.

        Raises:
            ValueError: If either seam length is non-positive or tolerance is outside [0, 1).
        """
        if self.length_a <= 0.0 or self.length_b <= 0.0:
            msg = "seam lengths must be positive"
            raise ValueError(msg)
        if not 0.0 <= self.length_tolerance < 1.0:
            msg = "length tolerance must be in [0, 1)"
            raise ValueError(msg)
        return self


class ParticleInput(InputModel):
    """Finite solver particle state with a non-negative inverse mass."""

    x: FiniteNumber
    y: FiniteNumber
    z: FiniteNumber
    inv_mass: FiniteNumber = 1.0

    @model_validator(mode="after")
    def inverse_mass_is_nonnegative(self) -> ParticleInput:
        """Reject a negative inverse mass.

        Returns:
            The same particle model after its inverse mass is checked.

        Raises:
            ValueError: If inverse mass is negative.
        """
        if self.inv_mass < 0.0:
            msg = "inverse mass must be non-negative"
            raise ValueError(msg)
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
        """Require positive dimensions and a finite three-dimensional origin.

        Returns:
            The same grid input after dimension constraints are checked.

        Raises:
            ValueError: If width or height is not strictly positive.
        """
        if self.width <= 0.0 or self.height <= 0.0:
            msg = "grid dimensions must be positive and finite"
            raise ValueError(msg)
        return self


class DistanceConstraintInput(InputModel):
    """Finite distance-constraint values and exact non-negative particle indices."""

    a: StrictInt = Field(ge=0)
    b: StrictInt = Field(ge=0)
    rest: FiniteNumber
    compliance: FiniteNumber = 0.0

    @model_validator(mode="after")
    def physical_parameters_are_nonnegative(self) -> DistanceConstraintInput:
        """Reject negative rest lengths or compliance.

        Returns:
            The same distance-constraint input after physical values are checked.

        Raises:
            ValueError: If rest length or compliance is negative.
        """
        if self.rest < 0.0:
            msg = "constraint rest length must be non-negative"
            raise ValueError(msg)
        if self.compliance < 0.0:
            msg = "constraint compliance must be non-negative"
            raise ValueError(msg)
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
        """Require sixteen finite entries and a usable homogeneous scale.

        Returns:
            The same transform model after matrix dimensions and scale are checked.

        Raises:
            ValueError: If the matrix has the wrong length or a near-zero homogeneous scale.
        """
        if len(self.matrix) != 16:
            msg = "assembly transform must contain 16 values"
            raise ValueError(msg)
        if abs(self.matrix[15]) < 1e-12:
            msg = "assembly transform has an invalid homogeneous scale"
            raise ValueError(msg)
        return self


class CollisionSurfaceInput(InputModel):
    """Validate the finite geometry and topology passed to a collision solver."""

    vertices: tuple[Point3D, ...]
    triangles: tuple[Triangle, ...]
    region: StrictStr = "body"
    thickness: FiniteNumber = 0.0

    @model_validator(mode="after")
    def surface_is_valid(self) -> CollisionSurfaceInput:
        """Reject empty surfaces, invalid connectivity, and invalid thickness or region.

        Returns:
            The same collision-surface model after geometry and topology validation.

        Raises:
            ValueError: If vertices/faces are missing, indices are invalid, or
                thickness/region is invalid.
        """
        if len(self.vertices) < 3 or not self.triangles:
            msg = "collision surface needs vertices and triangles"
            raise ValueError(msg)
        if self.thickness < 0.0:
            msg = "collision thickness must be finite and non-negative"
            raise ValueError(msg)
        if not self.region.strip():
            msg = "collision region must not be empty"
            raise ValueError(msg)
        for triangle in self.triangles:
            if any(index < 0 or index >= len(self.vertices) for index in triangle):
                msg = "collision triangle index out of range"
                raise ValueError(msg)
        return self


class PBDStepInput(InputModel):
    """Validated timestep, iteration count, and gravity for one solver step."""

    dt: FiniteNumber
    iterations: StrictInt = Field(ge=1)
    gravity: Point3D = (0.0, 0.0, -9810.0)

    @model_validator(mode="after")
    def timestep_is_positive(self) -> PBDStepInput:
        """Reject non-positive simulation timesteps.

        Returns:
            The same PBD step input after its timestep is checked.

        Raises:
            ValueError: If the timestep is not strictly positive.
        """
        if self.dt <= 0.0:
            msg = "dt must be positive and finite"
            raise ValueError(msg)
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
        """Require a positive particle spacing for simulation mesh generation.

        Returns:
            The same mesh-quality input after its particle spacing is checked.

        Raises:
            ValueError: If particle spacing is not strictly positive.
        """
        if self.particle_distance <= 0.0:
            msg = "particle_distance must be positive and finite"
            raise ValueError(msg)
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
        """Require identity, a usable outline, and a non-negative seam allowance.

        Returns:
            The same pattern-piece model after its boundary invariants are checked.

        Raises:
            ValueError: If name/ID are empty, the outline has fewer than three points,
                or allowance is negative.
        """
        if not self.name.strip() or not self.id.strip():
            msg = "pattern piece name and id must not be empty"
            raise ValueError(msg)
        if len(self.outline) < 3:
            msg = "pattern piece outline needs at least three points"
            raise ValueError(msg)
        if self.seam_allowance < 0.0:
            msg = "seam allowance must be non-negative and finite"
            raise ValueError(msg)
        return self


class PngCaptureOptions(InputModel):
    """Validate screenshot dimensions and the pixel-content acceptance policy."""

    expected_width: StrictInt | None = Field(default=None, ge=1)
    expected_height: StrictInt | None = Field(default=None, ge=1)
    minimum_pixels: StrictInt = Field(default=64, ge=0)
    min_opaque_pixels: StrictInt = Field(default=64, ge=0)
    min_distinct_rgb: StrictInt = Field(default=8, ge=0)
    pixel_threshold: StrictInt = Field(default=250, ge=0, le=256)
    require_all_channels_below: StrictBool = False


class PngCaptureMetrics(InputModel):
    """Pydantic-validated statistics extracted from a decoded PNG capture."""

    width: StrictInt = Field(ge=1)
    height: StrictInt = Field(ge=1)
    opaque_pixels: StrictInt = Field(ge=0)
    nonwhite_pixels: StrictInt = Field(ge=0)
    distinct_rgb: StrictInt = Field(ge=0)

    @model_validator(mode="after")
    def pixel_counts_are_consistent(self) -> PngCaptureMetrics:
        """Reject impossible image metrics before acceptance checks consume them.

        Returns:
            The same PNG metric model after pixel counts are checked for consistency.

        Raises:
            ValueError: If any pixel count exceeds the dimensions or other counts.
        """
        total_pixels = self.width * self.height
        if self.opaque_pixels > total_pixels:
            msg = "opaque pixel count exceeds image dimensions"
            raise ValueError(msg)
        if self.nonwhite_pixels > self.opaque_pixels:
            msg = "visible pixel count exceeds opaque pixel count"
            raise ValueError(msg)
        if self.distinct_rgb > self.opaque_pixels:
            msg = "distinct color count exceeds opaque pixel count"
            raise ValueError(msg)
        return self


class MeshHealthMetrics(InputModel):
    """Validated diagnostics emitted by the canonical triangle-mesh library."""

    vertices: StrictInt = Field(ge=0)
    faces: StrictInt = Field(ge=0)
    components: StrictInt = Field(ge=0)
    bounds: tuple[
        FiniteNumber,
        FiniteNumber,
        FiniteNumber,
        FiniteNumber,
        FiniteNumber,
        FiniteNumber,
    ]
    surface_area: FiniteNumber = Field(ge=0.0)
    watertight: StrictBool | None
    finite: StrictBool
    degenerate_faces: StrictInt = Field(ge=0)

    @model_validator(mode="after")
    def mesh_metrics_are_consistent(self) -> MeshHealthMetrics:
        """Enforce topology, count, and bounds invariants on library-produced metrics.

        Returns:
            The same mesh-health model after its bounds and counts are checked.

        Raises:
            ValueError: If bounds are unordered or component/degenerate counts exceed face count.
        """
        xmin, xmax, ymin, ymax, zmin, zmax = self.bounds
        if xmin > xmax or ymin > ymax or zmin > zmax:
            msg = "mesh bounds must be ordered minimum/maximum pairs"
            raise ValueError(msg)
        if self.components > self.faces:
            msg = "mesh component count cannot exceed face count"
            raise ValueError(msg)
        if self.degenerate_faces > self.faces:
            msg = "degenerate face count cannot exceed face count"
            raise ValueError(msg)
        return self


Point2DAdapter = TypeAdapter(Point2D)
Points2DAdapter = TypeAdapter(tuple[Point2D, ...])
Points3DAdapter = TypeAdapter(tuple[Point3D, ...])


def validate_finite_number(value: object) -> float:
    """Return a finite real input as float, rejecting bool/string coercion.

    Args:
        value: Candidate value to validate as a finite real number.

    Returns:
        The validated numeric value normalized to a Python float.
    """
    return FiniteScalar(value=cast("FiniteNumber", value)).value


def validate_point2d(value: object) -> Point2D:
    """Validate and normalize one two-dimensional point.

    Args:
        value: Candidate point value supplied by an external caller.

    Returns:
        A finite point containing exactly two normalized coordinates.
    """
    return Point2DAdapter.validate_python(value)


def validate_points2d(values: Iterable[object]) -> tuple[Point2D, ...]:
    """Validate and normalize a sequence of two-dimensional points.

    Args:
        values: Iterable of candidate points supplied by an external caller.

    Returns:
        An immutable tuple of finite two-dimensional points.
    """
    return Points2DAdapter.validate_python(values)


def validate_points3d(values: Iterable[object]) -> tuple[Point3D, ...]:
    """Validate and normalize a sequence of three-dimensional points.

    Args:
        values: Iterable of candidate points supplied by an external caller.

    Returns:
        An immutable tuple of finite three-dimensional points.
    """
    return Points3DAdapter.validate_python(values)
