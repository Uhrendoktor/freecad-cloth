import sys
from pathlib import Path
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PatternDerivedGeometry import Notch, PatternMark, add_marks, add_notches, derive_cut_boundary
from PatternExport import from_dxf_metadata, from_svg_metadata, to_dxf, to_svg, validate_export
from PatternGeometry import LineSegment, ParametricPattern, QuadraticBezier


def _curved_pattern():
    return ParametricPattern([
        LineSegment("bottom", (0.0, 0.0), (100.0, 0.0)),
        LineSegment("right", (100.0, 0.0), (100.0, 60.0)),
        QuadraticBezier("armhole", (100.0, 60.0), (55.0, 85.0), (0.0, 60.0)),
        LineSegment("left", (0.0, 60.0), (0.0, 0.0)),
    ])


def _derived(pattern):
    result = derive_cut_boundary(pattern, 5.0, curve_samples=9)
    result = add_notches(result, [Notch("notch-1", "right", 0.5)])
    return add_marks(result, [PatternMark("grain-1", "Grainline", segment_id="bottom", angle=90, length=40, text="Grain")])


def test_svg_and_dxf_preserve_piece_and_construction_semantics():
    pattern = _curved_pattern()
    derived = _derived(pattern)
    svg = to_svg(pattern, curve_samples=9, derived=derived, piece_id="bodice-front", seam_ids=("seam-neck", "seam-side"))
    assert 'data-piece-id="bodice-front"' in svg
    assert 'data-edge-ids="bottom right armhole left"' in svg
    assert 'id="notch-notch-1"' in svg
    assert 'data-mark-id="grain-1"' in svg
    assert from_svg_metadata(svg) == {
        "version": 1,
        "units": "mm",
        "edge_ids": ["bottom", "right", "armhole", "left"],
        "piece_id": "bodice-front",
        "seam_ids": ["seam-neck", "seam-side"],
        "notch_ids": ["notch-1"],
        "mark_ids": ["grain-1"],
    }

    dxf = to_dxf(pattern, curve_samples=9, derived=derived, piece_id="bodice-front", seam_ids=("seam-neck", "seam-side"))
    assert from_dxf_metadata(dxf) == {
        "version": 1,
        "units": "mm",
        "edge_ids": ["bottom", "right", "armhole", "left"],
        "piece_id": "bodice-front",
        "seam_ids": ["seam-neck", "seam-side"],
        "notch_ids": ["notch-1"],
        "mark_ids": ["grain-1"],
    }


def test_legacy_export_metadata_remains_compatible():
    dxf = to_dxf(_curved_pattern())
    assert from_dxf_metadata(dxf) == {
        "version": 1,
        "units": "mm",
        "edge_ids": ["bottom", "right", "armhole", "left"],
    }


def test_release_gate_validates_deterministic_svg_and_dxf_round_trip():
    pattern = _curved_pattern()
    derived = _derived(pattern)
    kwargs = dict(curve_samples=9, derived=derived, piece_id="bodice-front", seam_ids=("seam-neck", "seam-side"))

    svg = to_svg(pattern, **kwargs)
    result = validate_export(pattern, svg, "svg", **kwargs)
    assert result["valid"] is True
    assert result["metadata"]["piece_id"] == "bodice-front"

    dxf = to_dxf(pattern, **kwargs)
    result = validate_export(pattern, dxf, "dxf", **kwargs)
    assert result["valid"] is True
    assert result["metadata"]["seam_ids"] == ["seam-neck", "seam-side"]


def test_release_gate_rejects_geometry_or_semantic_drift():
    pattern = _curved_pattern()
    svg = to_svg(pattern, curve_samples=9, piece_id="bodice-front", seam_ids=("seam-neck",))
    with TestCase().assertRaisesRegex(ValueError, "deterministic authoritative pattern"):
        validate_export(pattern, svg.replace("100.000000,0.000000", "101.000000,0.000000", 1), "svg", curve_samples=9, piece_id="bodice-front", seam_ids=("seam-neck",))

    dxf = to_dxf(pattern, curve_samples=9, piece_id="bodice-front", seam_ids=("seam-neck",))
    with TestCase().assertRaisesRegex(ValueError, "deterministic authoritative pattern"):
        validate_export(pattern, dxf.replace("bodice-front", "bodice-back", 1), "dxf", curve_samples=9, piece_id="bodice-front", seam_ids=("seam-neck",))


def test_release_gate_rejects_unknown_format():
    with TestCase().assertRaisesRegex(ValueError, "format must be 'svg' or 'dxf'"):
        validate_export(_curved_pattern(), "", "pdf")
