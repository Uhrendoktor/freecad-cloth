import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freecad_cloth.sewing.SewingCorrespondence import (
    STATUS_INVALID_RANGE,
    STATUS_LENGTH_MISMATCH,
    STATUS_REVERSED,
    STATUS_VALID,
    analyze_correspondence,
    correspondence_recovery,
    correspondence_samples,
    arc_length_vertex_indices,
    map_parameter,
)


def test_equal_length_seam_is_valid():
    report = analyze_correspondence(120.0, 120.0)
    assert report.status == STATUS_VALID
    assert report.valid
    assert report.length_ratio == 1.0


def test_reversed_seam_is_usable_and_explicit():
    report = analyze_correspondence(120.0, 121.0, reversed_b=True)
    assert report.status == STATUS_REVERSED
    assert report.valid
    assert report.reversed_b
    assert map_parameter(0.0, reversed_b=True) == 1.0
    assert map_parameter(1.0, reversed_b=True) == 0.0


def test_length_mismatch_is_actionable():
    report = analyze_correspondence(100.0, 120.0, length_tolerance=0.05)
    assert report.status == STATUS_LENGTH_MISMATCH
    assert not report.valid
    assert "16.67%" in report.message


def test_invalid_ranges_are_reported_without_silent_repair():
    report = analyze_correspondence(100.0, 100.0, start_a=0.8, end_a=0.2)
    assert report.status == STATUS_INVALID_RANGE
    assert not report.valid
    with pytest.raises(ValueError, match="parameter ranges"):
        map_parameter(0.5, start_a=0.8, end_a=0.2)


def test_partial_ranges_map_proportionally():
    assert map_parameter(0.25, 0.0, 0.5, 0.25, 0.75) == pytest.approx(0.5)
    assert map_parameter(0.5, 0.0, 0.5, 0.25, 0.75, reversed_b=True) == pytest.approx(0.25)


def test_samples_are_deterministic_and_include_endpoints():
    expected = ((0.2, 0.8), (0.4, 0.6), (0.6, 0.4), (0.8, 0.2))
    assert correspondence_samples(4, 0.2, 0.8, 0.2, 0.8, True) == pytest.approx(expected)


def test_arc_length_vertex_sampling_uses_physical_distance_not_vertex_index():
    values = (10, 11, 12, 13, 14)
    points = ((0.0, 0.0), (0.2, 0.1), (3.0, 1.0), (4.4, 4.0), (10.0, 4.0))
    assert arc_length_vertex_indices(values, points, 3) == (10, 13, 14)


def test_mismatch_recovery_and_severity_are_shared_machine_contract():
    report = analyze_correspondence(100.0, 120.0, length_tolerance=0.05)
    assert report.severity == "error"
    assert report.recovery == correspondence_recovery(report.status)
    assert report.evidence() == {
        "status": STATUS_LENGTH_MISMATCH,
        "severity": "error",
        "message": "seam lengths differ by 20.00% (limit 5.00%)",
        "length_a": 100.0,
        "length_b": 120.0,
        "length_ratio": 1.2,
        "reversed_b": False,
        "recovery": "edit the pattern geometry or seam ranges; do not hide the mismatch with tolerance",
    }


def test_reversal_keeps_forward_contract_and_recovery_is_stable():
    report = analyze_correspondence(100.0, 100.0, reversed_b=True)
    assert report.severity == "info"
    assert report.valid
    assert report.recovery == "keep the explicit B reversal or use Reverse B"
    assert report.evidence()["reversed_b"] is True


def test_bad_length_inputs_are_rejected():
    with pytest.raises(ValueError, match="positive"):
        analyze_correspondence(0.0, 10.0)
    with pytest.raises(ValueError, match="tolerance"):
        analyze_correspondence(10.0, 10.0, length_tolerance=1.0)
