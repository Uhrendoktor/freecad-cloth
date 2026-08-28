import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PatternExport import dxf_metadata, to_dxf, to_svg
from PatternGeometry import rectangle


def test_dxf_is_deterministic_and_preserves_metadata():
    pattern = rectangle(100, 50)
    first = to_dxf(pattern)
    second = to_dxf(pattern)
    assert first == second
    assert first.endswith("0\nEOF\n")
    assert dxf_metadata(first) == {
        "units": "mm",
        "edge_ids": ("bottom", "right", "top", "left"),
    }


def test_dxf_coordinates_use_local_origin():
    dxf = to_dxf(rectangle(20, 10))
    assert "10\n0.000000" in dxf
    assert "20\n10.000000" in dxf


def test_svg_contract_remains_unchanged():
    svg = to_svg(rectangle(100, 50))
    assert 'data-units="mm"' in svg
    assert 'data-edge-ids="bottom right top left"' in svg


if __name__ == "__main__":
    for name, fn in globals().copy().items():
        if name.startswith("test_"):
            fn()
    print("pattern export tests passed")
