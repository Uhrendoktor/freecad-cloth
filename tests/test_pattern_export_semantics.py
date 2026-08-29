import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PatternDerivedGeometry import Notch, PatternMark, add_marks, add_notches, derive_cut_boundary
from PatternExport import from_dxf_metadata, to_dxf, to_svg
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

    dxf = to_dxf(pattern, curve_samples=9, derived=derived, piece_id="bodice-front", seam_ids=("seam-neck", "seam-side"))
    metadata = from_dxf_metadata(dxf)
    assert metadata == {
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
