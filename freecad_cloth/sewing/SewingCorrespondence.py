"""Solver- and FreeCAD-independent curved seam correspondence helpers.

The Sewing workbench stores seam topology elsewhere.  This module only answers
whether two normalized seam ranges can be paired and how their parameters map.
It deliberately has no FreeCAD/Qt dependency so it can be used by task panels,
headless validation, and future mesh adapters without creating a second seam
model.
"""

from dataclasses import dataclass
import bisect
import math


STATUS_VALID = "valid"
STATUS_REVERSED = "reversed"
STATUS_LENGTH_MISMATCH = "length_mismatch"
STATUS_INVALID_RANGE = "invalid_range"

DEFAULT_RELATIVE_TOLERANCE = 0.05
SEVERITY_OK = "ok"
SEVERITY_WARNING = "warning"
SEVERITY_ERROR = "error"
RECOVERY_LENGTH_MISMATCH = "length mismatch requires editing the pattern or seam ranges; it was not hidden by changing tolerance"
RECOVERY_INVALID_RANGE = "Repair the normalized seam ranges before committing the sewing relationship."
RECOVERY_REVERSED = "Keep the explicit B reversal or switch orientation before committing."
RECOVERY_VALID = "No correspondence repair is required."


@dataclass(frozen=True)
class CorrespondenceReport:
    """Deterministic validation result for a pair of seam ranges."""

    status: str
    message: str
    length_a: float
    length_b: float
    length_ratio: float
    reversed_b: bool
    length_tolerance: float = DEFAULT_RELATIVE_TOLERANCE

    @property
    def valid(self) -> bool:
        """Return whether the correspondence is usable for sewing."""
        return self.status in {STATUS_VALID, STATUS_REVERSED}

    @property
    def severity(self) -> str:
        """Return deterministic diagnostic severity for the correspondence state."""
        if self.status == STATUS_REVERSED:
            return SEVERITY_WARNING
        if self.status in {STATUS_LENGTH_MISMATCH, STATUS_INVALID_RANGE}:
            return SEVERITY_ERROR
        return SEVERITY_OK

    @property
    def tolerance(self) -> float:
        """Return the relative tolerance used for this classification."""
        return float(self.length_tolerance)

    @property
    def recovery(self) -> str:
        """Return deterministic user-facing recovery guidance."""
        return {
            STATUS_LENGTH_MISMATCH: RECOVERY_LENGTH_MISMATCH,
            STATUS_INVALID_RANGE: RECOVERY_INVALID_RANGE,
            STATUS_REVERSED: RECOVERY_REVERSED,
            STATUS_VALID: RECOVERY_VALID,
        }[self.status]


def _range_is_valid(start: float, end: float) -> bool:
    return (
        math.isfinite(start)
        and math.isfinite(end)
        and 0.0 <= start < end <= 1.0
    )


def analyze_correspondence(
    length_a: float,
    length_b: float,
    start_a: float = 0.0,
    end_a: float = 1.0,
    start_b: float = 0.0,
    end_b: float = 1.0,
    reversed_b: bool = False,
    length_tolerance: float = DEFAULT_RELATIVE_TOLERANCE,
) -> CorrespondenceReport:
    """Validate two seam ranges and classify their repair state.

    ``length_a`` and ``length_b`` are the physical lengths of the selected
    ranges in millimetres (or any common unit).  The comparison is symmetric:
    a ratio of ``1.05`` and ``0.95238`` represent the same 5% mismatch.

    Reversal is a usable state rather than an error.  A task panel can expose
    it as an orientation/repair action while still allowing the seam to be
    accepted.  A length mismatch is reported when the relative difference
    exceeds ``length_tolerance``.
    """
    values = (length_a, length_b, length_tolerance)
    if any(not math.isfinite(float(value)) for value in values):
        raise ValueError("seam lengths and tolerance must be finite")
    if length_a <= 0.0 or length_b <= 0.0:
        raise ValueError("seam lengths must be positive")
    if length_tolerance < 0.0 or length_tolerance >= 1.0:
        raise ValueError("length tolerance must be in [0, 1)")

    if not _range_is_valid(start_a, end_a) or not _range_is_valid(start_b, end_b):
        return CorrespondenceReport(
            STATUS_INVALID_RANGE,
            "seam parameter ranges must satisfy 0 <= start < end <= 1",
            float(length_a),
            float(length_b),
            float("inf"),
            bool(reversed_b),
            float(length_tolerance),
        )

    ratio = max(length_a, length_b) / min(length_a, length_b)
    relative_difference = ratio - 1.0
    if relative_difference > length_tolerance:
        return CorrespondenceReport(
            STATUS_LENGTH_MISMATCH,
            "seam lengths differ by %.2f%% (limit %.2f%%)"
            % (relative_difference * 100.0, length_tolerance * 100.0),
            float(length_a),
            float(length_b),
            float(ratio),
            bool(reversed_b),
        )

    if reversed_b:
        return CorrespondenceReport(
            STATUS_REVERSED,
            "seam correspondence is valid with B reversed",
            float(length_a),
            float(length_b),
            float(ratio),
            True,
        )
    return CorrespondenceReport(
        STATUS_VALID,
        "seam correspondence is valid",
        float(length_a),
        float(length_b),
        float(ratio),
        False,
    )


def arc_length_vertex_indices(values, points, count, start=0.0, end=1.0):
    """Select existing edge vertices by physical arc length over a normalized range."""
    if int(count) < 2:
        raise ValueError("at least two correspondence samples are required")
    if not _range_is_valid(float(start), float(end)):
        raise ValueError("seam parameter ranges must satisfy 0 <= start < end <= 1")
    values = tuple(values)
    points = tuple(tuple(float(x) for x in point) for point in points)
    if len(values) != len(points):
        raise ValueError("arc-length sampling points must match edge vertices")
    if len(points) < 2:
        raise ValueError("arc-length sampling needs at least two points")
    dimensions = len(points[0])
    if dimensions < 2 or any(len(point) != dimensions for point in points):
        raise ValueError("arc-length sampling points must have matching dimensions")
    if any(any(not math.isfinite(value) for value in point) for point in points):
        raise ValueError("arc-length sampling points must be finite")
    cumulative=[0.0]
    for first,second in zip(points,points[1:]):
        cumulative.append(cumulative[-1] + math.sqrt(sum((a-b)**2 for a,b in zip(first,second))))
    total=cumulative[-1]
    if total <= 0.0:
        raise ValueError("arc-length sampling needs a positive total length")
    result=[]
    span=float(end)-float(start)
    for sample in range(int(count)):
        local=float(start)+span*sample/float(int(count)-1)
        target=local*total
        right=bisect.bisect_left(cumulative,target)
        if right <= 0:
            index=0
        elif right >= len(cumulative):
            index=len(cumulative)-1
        else:
            left=right-1
            index=left if target-cumulative[left] <= cumulative[right]-target else right
        result.append(index)
    return tuple(result)

def map_parameter(
    parameter_a: float,
    start_a: float = 0.0,
    end_a: float = 1.0,
    start_b: float = 0.0,
    end_b: float = 1.0,
    reversed_b: bool = False,
) -> float:
    """Map a normalized parameter from seam A to seam B deterministically."""
    if not math.isfinite(float(parameter_a)):
        raise ValueError("seam parameter must be finite")
    if not _range_is_valid(start_a, end_a) or not _range_is_valid(start_b, end_b):
        raise ValueError("seam parameter ranges must satisfy 0 <= start < end <= 1")
    if not 0.0 <= parameter_a <= 1.0:
        raise ValueError("seam parameter must be in [0, 1]")

    local = (parameter_a - start_a) / (end_a - start_a)
    local = min(1.0, max(0.0, local))
    if reversed_b:
        local = 1.0 - local
    return start_b + local * (end_b - start_b)


def correspondence_samples(
    count: int,
    start_a: float = 0.0,
    end_a: float = 1.0,
    start_b: float = 0.0,
    end_b: float = 1.0,
    reversed_b: bool = False,
):
    """Return paired normalized parameters for deterministic mesh sampling."""
    if count < 2:
        raise ValueError("at least two correspondence samples are required")
    return tuple(
        (
            start_a + (end_a - start_a) * i / (count - 1),
            map_parameter(
                start_a + (end_a - start_a) * i / (count - 1),
                start_a,
                end_a,
                start_b,
                end_b,
                reversed_b,
            ),
        )
        for i in range(count)
    )
