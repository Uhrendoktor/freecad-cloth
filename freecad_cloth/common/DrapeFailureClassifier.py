"""Evidence-only classification of canonical drape outcomes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


STATES = (
    "empty",
    "nonfinite",
    "fragmented",
    "edge-on-candidate",
    "detached-candidate",
    "structurally-plausible",
)


@dataclass(frozen=True)
class DrapeClassification:
    """Evidence classification; never a claim of physical correctness."""

    state: str
    reasons: tuple[str, ...]


def classify_drape(
    metrics: Any,
    *,
    components: int | None = None,
    target_width: float | None = None,
) -> DrapeClassification:
    """Classify evidence from existing drape metrics without mutating them."""
    finite = bool(getattr(metrics, "finite", False))
    vertices = int(getattr(metrics, "vertices", 0))
    state = str(getattr(metrics, "state", ""))
    vertical_ratio = float(getattr(metrics, "vertical_span_ratio", 0.0))
    lateral_ratio = float(getattr(metrics, "lateral_span_ratio", 0.0))
    clearance = getattr(metrics, "target_vertex_clearance", None)
    reasons: list[str] = []

    if vertices <= 0 or state == "empty":
        reasons.append("garment mesh has no vertices")
        return DrapeClassification("empty", tuple(reasons))
    if not finite or state == "nonfinite":
        reasons.append("garment mesh contains non-finite coordinates")
        return DrapeClassification("nonfinite", tuple(reasons))
    if components is not None and int(components) > 1:
        reasons.append("garment mesh has multiple connected components")
        return DrapeClassification("fragmented", tuple(reasons))
    if vertical_ratio <= 0.15 and lateral_ratio < 0.35:
        reasons.append("vertical and lateral spans are both too small for the target")
        return DrapeClassification("edge-on-candidate", tuple(reasons))
    if clearance is not None and target_width and target_width > 0:
        clearance_ratio = float(clearance) / float(target_width)
        if clearance_ratio > 0.30:
            reasons.append("garment-to-target vertex clearance exceeds 30% of target width")
            return DrapeClassification("detached-candidate", tuple(reasons))

    if state in {"edge-on-candidate", "detached-candidate"}:
        reasons.append(f"existing metric state: {state}")
        return DrapeClassification(state, tuple(reasons))
    reasons.append("no failure evidence detected by the available metrics")
    return DrapeClassification("structurally-plausible", tuple(reasons))


def summarize_classification(classification: DrapeClassification) -> Mapping[str, object]:
    """Return stable JSON-ready evidence for acceptance artifacts."""
    return {
        "state": classification.state,
        "reasons": list(classification.reasons),
    }
