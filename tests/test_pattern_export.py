import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PatternDerivedGeometry import Notch, PatternMark, add_marks, add_notches, derive_cut_boundary
from PatternExport import from_dxf_metadata, to_dxf, to_svg
from PatternGeometry import rectangle


def test_svg_contains_distinct_sewing_cut_and_construction_semantics():
    pattern = rectangle(100, 60)
    derived = add_notches(derive_cut_boundary(pattern, 5), [Notch("waist", "right", 0.5)])
    derived = add_marks(derived, [PatternMark("grain", "Grainline", angle=90, length=40, text="Grain")])
    svg = to_svg(pattern, derived=derived)
    assert '<g id="sewing-boundary"' in svg
    assert '<g id="cut-boundary"' in svg
    assert 'id="notch-waist"' in svg
    assert 'data-kind="Grainline"' in svg
    assert 'Grain' in svg
    assert 'data-edge-ids="bottom right top left"' in svg


def test_dxf_is_deterministic_and_round_trips_metadata():
    pattern = rectangle(100, 60)
    derived = derive_cut_boundary(pattern, 5)
    first = to_dxf(pattern, derived=derived)
    second = to_dxf(pattern, derived=derived)
    assert first == second
    assert "LWPOLYLINE" in first
    assert "8\nSEWING" in first
    assert "8\nCUT" in first
    assert from_dxf_metadata(first) == {"version": 1, "units": "mm", "edge_ids": ["bottom", "right", "top", "left"]}


def test_export_rejects_mismatched_derived_pattern():
    pattern = rectangle(100, 60)
    other = rectangle(80, 40)
    derived = derive_cut_boundary(other, 5)
    try:
        to_svg(pattern, derived=derived)
    except ValueError:
        pass
    else:
        raise AssertionError("derived geometry from another pattern must fail")
