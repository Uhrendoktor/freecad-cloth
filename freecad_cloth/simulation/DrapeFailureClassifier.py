# Copyright (C) 2026 FreeCAD Cloth contributors
"""Evidence-only classification of canonical drape outcomes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Mapping

from pydantic.dataclasses import dataclass as pydantic_dataclass


class DrapeMetrics(Protocol):
    """Describe the metric attributes consumed by the evidence classifier."""

    finite: bool
    vertices: int
    state: str
    vertical_span_ratio: float
    lateral_span_ratio: float
    target_vertex_clearance: float | None


MIN_VERTICAL_SPAN_RATIO = 0.15
MIN_LATERAL_SPAN_RATIO = 0.35
MAX_NORMALIZED_CLEARANCE_RATIO = 0.30

STATES = (
    "empty",
    "nonfinite",
    "fragmented",
    "edge-on-candidate",
    "detached-candidate",
    "structurally-plausible",
)


@pydantic_dataclass(frozen=True)
class DrapeClassification:
    """Evidence classification; never a claim of physical correctness."""

    state: str
    reasons: tuple[str, ...]


def classify_drape(
    metrics: DrapeMetrics,
    *,
    components: int | None = None,
    target_width: float | None = None,
) -> DrapeClassification:
    """Classify existing garment metrics using evidence-only failure checks.

    Args:
        metrics: Existing finite, span, shape, and target-clearance measurements.
        components: Optional connected-component count; values above one indicate fragmentation.
        target_width: Optional positive target width in millimetres for normalizing vertex clearance.

    Returns:
        Classification state and diagnostic reasons. A plausible state means only that the available
        metrics exposed no failure evidence.
    """
    finite = metrics.finite
    vertices = metrics.vertices
    state = metrics.state
    vertical_ratio = metrics.vertical_span_ratio
    lateral_ratio = metrics.lateral_span_ratio
    clearance = metrics.target_vertex_clearance
    reasons: list[str] = []

    if vertices <= 0 or state == "empty":
        state = "empty"
        reasons.append("garment mesh has no vertices")
    elif not finite or state == "nonfinite":
        state = "nonfinite"
        reasons.append("garment mesh contains non-finite coordinates")
    elif components is not None and int(components) > 1:
        state = "fragmented"
        reasons.append("garment mesh has multiple connected components")
    elif vertical_ratio <= MIN_VERTICAL_SPAN_RATIO and lateral_ratio < MIN_LATERAL_SPAN_RATIO:
        state = "edge-on-candidate"
        reasons.append("vertical and lateral spans are both too small for the target")
    elif (
        clearance is not None
        and target_width is not None
        and target_width > 0
        and float(clearance) / float(target_width) > MAX_NORMALIZED_CLEARANCE_RATIO
    ):
        state = "detached-candidate"
        reasons.append("garment-to-target vertex clearance exceeds 30% of target width")
    elif state in {"edge-on-candidate", "detached-candidate"}:
        reasons.append(f"existing metric state: {state}")
    else:
        state = "structurally-plausible"
        reasons.append("no failure evidence detected by the available metrics")

    return DrapeClassification(state, tuple(reasons))


def summarize_classification(classification: DrapeClassification) -> Mapping[str, object]:
    """Convert the classification into stable JSON-ready values.

    Args:
        classification: Evidence-only state and diagnostic reasons to serialize.

    Returns:
        Mapping containing the state string and a list of reason strings.
    """
    return {
        "state": classification.state,
        "reasons": list(classification.reasons),
    }
