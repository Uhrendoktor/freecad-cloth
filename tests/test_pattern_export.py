import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PatternDerivedGeometry import Notch, add_notches, derive_cut_boundary
from PatternExport import extract_metadata, to_dxf, to_svg
from PatternGeometry import rectangle


def test_svg_export_is_deterministic_and_round_trips_metadata():
    pattern = rectangle(100, 60)
    derived = add_notches(
        derive_cut_boundary(pattern, 5),
        [Notch("waist", "right", 0.5, depth=4)],
    )
    first = to_svg(pattern, derived=derived, metadata={"piece_id": "front"})
    second = to_svg(pattern, derived=derived, metadata={"piece_id": "front"})

    assert first == second
    assert 'id="sewing-boundary"' in first
    assert 'id="cut-bottom"' in first
    assert 'data-edge-id="bottom"' in first
    metadata = extract_metadata(first)
    assert metadata["schema"] == "freecad-cloth.pattern-export.v1"
    assert metadata["edge_ids"] == ["bottom", "right", "top", "left"]
    assert metadata["notches"] == [
        {"id": "waist", "segment_id": "right", "position": 0.5, "depth": 4.0}
    ]
    assert metadata["extra"] == {"piece_id": "front"}


def test_dxf_export_contains_separate_layers_and_metadata():
    pattern = rectangle(100, 60)
    derived = add_notches(derive_cut_boundary(pattern, 5), [Notch("waist", "right", 0.5)])
    first = to_dxf(pattern, derived=derived)
    second = to_dxf(pattern, derived=derived)

    assert first == second
    assert "0\nPOLYLINE\n8\nSEWING" in first
    assert "8\nCUT_bottom" in first
    assert "0\nPOINT\n8\nNOTCH" in first
    metadata = extract_metadata(first)
    assert metadata["has_cut_boundary"] is True
    assert metadata["notches"][0]["id"] == "waist"


def test_export_units_are_preserved_in_metadata_and_svg_dimensions():
    pattern = rectangle(25, 10)
    svg = to_svg(pattern, units="cm")
    assert 'width="25cm"' in svg
    assert 'height="10cm"' in svg
    assert extract_metadata(svg)["units"] == "cm"


def test_export_rejects_missing_or_invalid_units():
    pattern = rectangle(10, 10)
    for exporter in (to_svg, to_dxf):
        try:
            exporter(pattern, units="")
        except ValueError:
            pass
        else:
            raise AssertionError("empty units should fail")
    try:
        extract_metadata("not an export")
    except ValueError:
        pass
    else:
        raise AssertionError("missing metadata should fail")
