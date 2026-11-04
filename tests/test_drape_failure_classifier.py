# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression tests for evidence-only drape failure classification."""

from freecad_cloth.simulation.DrapeFailureClassifier import (
    classify_drape,
    summarize_classification,
)
from freecad_cloth.simulation.DrapeVisualSanity import inspect_drape, seam_correspondence_gap

TARGET = (
    (-100.0, -50.0, 0.0),
    (100.0, -50.0, 0.0),
    (-100.0, 50.0, 1750.0),
    (100.0, 50.0, 1750.0),
)


def test_empty() -> None:
    """Classify an empty garment mesh before evaluating shape quality."""
    result = classify_drape(inspect_drape((), TARGET), target_width=200.0)
    assert (
        result.state == "empty"
    ), "Empty garment classification should remain empty."


def test_nonfinite() -> None:
    """Classify non-finite garment coordinates before evaluating shape quality."""
    metrics = inspect_drape(((0.0, 0.0, float("nan")),), TARGET)
    result = classify_drape(metrics, target_width=200.0)
    assert (
        result.state == "nonfinite"
    ), "Non-finite garment coordinates should be classified as non-finite."


def test_clean_canonical_style_geometry() -> None:
    """Accept canonical-style geometry when the available metrics show no failure."""
    garment = (
        (-140.0, -90.0, 250.0),
        (140.0, -90.0, 250.0),
        (-140.0, 90.0, 1500.0),
        (140.0, 90.0, 1500.0),
    )
    metrics = inspect_drape(garment, TARGET, target_height=1750.0, target_width=1000.0)
    result = classify_drape(metrics, components=1, target_width=1000.0)
    assert (
        result.state == "structurally-plausible"
    ), "Geometry without failure evidence should remain structurally plausible."
    assert (
        "no failure evidence" in result.reasons[0]
    ), "The plausible classification should explain the absence of failure evidence."


def test_fragmented() -> None:
    """Classify disconnected garment geometry as fragmented."""
    garment = ((0.0, 0.0, 100.0), (100.0, 0.0, 100.0), (0.0, 0.0, 1000.0))
    metrics = inspect_drape(garment, TARGET, target_height=1750.0, target_width=1000.0)
    result = classify_drape(metrics, components=2, target_width=1000.0)
    assert (
        result.state == "fragmented"
    ), "Disconnected garment geometry should be classified as fragmented."
    assert (
        "multiple connected components" in result.reasons[0]
    ), "Fragmentation should be supported by the component-count diagnostic."


def test_broken_edge_correspondence() -> None:
    """Report large gaps between corresponding seam edges."""
    left = ((0.0, 0.0, 0.0), (100.0, 0.0, 0.0))
    right = ((1000.0, 0.0, 0.0), (1100.0, 0.0, 0.0))
    assert (
        seam_correspondence_gap(left, right, 0, 0) > 500.0
    ), "Separated corresponding seam edges should report a large gap."


def test_edge_on_candidate() -> None:
    """Classify geometry whose vertical and lateral spans are both too small."""
    garment = ((0.0, 0.0, 700.0), (0.0, 10.0, 700.0), (0.0, 0.0, 710.0))
    metrics = inspect_drape(garment, TARGET, target_height=1750.0, target_width=1000.0)
    result = classify_drape(metrics, target_width=1000.0)
    assert (
        result.state == "edge-on-candidate"
    ), "A narrow edge-on garment should be marked as an edge-on candidate."


def test_detached_candidate_uses_normalized_clearance() -> None:
    """Normalize clearance by target width before classifying a detached garment."""
    garment = (
        (1000.0, 1000.0, 300.0),
        (1100.0, 1000.0, 300.0),
        (1000.0, 1000.0, 1500.0),
    )
    metrics = inspect_drape(garment, TARGET, target_height=1750.0, target_width=1000.0)
    result = classify_drape(metrics, target_width=200.0)
    assert (
        result.state == "detached-candidate"
    ), "Excessive normalized clearance should classify the garment as detached."


def test_structurally_plausible() -> None:
    """Serialize a plausible classification into stable JSON-ready values."""
    garment = (
        (-140.0, -90.0, 250.0),
        (140.0, -90.0, 250.0),
        (-140.0, 90.0, 1500.0),
        (140.0, 90.0, 1500.0),
    )
    metrics = inspect_drape(garment, TARGET, target_height=1750.0, target_width=1000.0)
    result = classify_drape(metrics, target_width=1000.0)
    assert (
        result.state == "structurally-plausible"
    ), "Plausible geometry should retain its structural classification."
    data = summarize_classification(result)
    assert (
        data["state"] == "structurally-plausible"
    ), "Serialized classification should preserve its state."
    assert (
        isinstance(data["reasons"], list)
    ), "Serialized classification reasons should be a JSON-ready list."
