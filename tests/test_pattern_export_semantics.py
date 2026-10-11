import sys
import re
from pathlib import Path
from unittest import TestCase
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freecad_cloth.pattern.PatternDerivedGeometry import (
    Notch,
    PatternMark,
    add_marks,
    add_notches,
    derive_cut_boundary,
)
from freecad_cloth.pattern.PatternExport import (
    export_pattern_piece,
    from_dxf_metadata,
    from_svg_metadata,
    to_dxf,
    to_svg,
    validate_export,
)
from freecad_cloth.pattern.PatternGeometry import (
    LineSegment,
    ParametricPattern,
    QuadraticBezier,
    rectangle,
)


def _curved_pattern():
    return ParametricPattern(
        [
            LineSegment("bottom", (0.0, 0.0), (100.0, 0.0)),
            LineSegment("right", (100.0, 0.0), (100.0, 60.0)),
            QuadraticBezier("armhole", (100.0, 60.0), (55.0, 85.0), (0.0, 60.0)),
            LineSegment("left", (0.0, 60.0), (0.0, 0.0)),
        ]
    )


def _derived(pattern):
    result = derive_cut_boundary(pattern, 5.0, curve_samples=9)
    result = add_notches(result, [Notch("notch-1", "right", 0.5)])
    return add_marks(
        result,
        [
            PatternMark(
                "grain-1", "Grainline", segment_id="bottom", angle=90, length=40, text="Grain"
            )
        ],
    )


def test_svg_and_dxf_preserve_piece_and_construction_semantics():
    pattern = _curved_pattern()
    derived = _derived(pattern)
    svg = to_svg(
        pattern,
        curve_samples=9,
        derived=derived,
        piece_id="bodice-front",
        seam_ids=("seam-neck", "seam-side"),
    )
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
        "scale": 1.0,
        "seam_allowance_mm": 0.0,
        "notch_ids": ["notch-1"],
        "mark_ids": ["grain-1"],
    }

    dxf = to_dxf(
        pattern,
        curve_samples=9,
        derived=derived,
        piece_id="bodice-front",
        seam_ids=("seam-neck", "seam-side"),
    )
    assert from_dxf_metadata(dxf) == {
        "version": 1,
        "units": "mm",
        "edge_ids": ["bottom", "right", "armhole", "left"],
        "piece_id": "bodice-front",
        "seam_ids": ["seam-neck", "seam-side"],
        "scale": 1.0,
        "seam_allowance_mm": 0.0,
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
    kwargs = dict(
        curve_samples=9,
        derived=derived,
        piece_id="bodice-front",
        seam_ids=("seam-neck", "seam-side"),
    )

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
    tampered_svg = svg.replace(
        "0.000000,12.500000",
        "1.000000,12.500000",
        1,
    )
    assert tampered_svg != svg
    with TestCase().assertRaisesRegex(ValueError, "deterministic authoritative pattern"):
        validate_export(
            pattern,
            tampered_svg,
            "svg",
            curve_samples=9,
            piece_id="bodice-front",
            seam_ids=("seam-neck",),
        )

    dxf = to_dxf(pattern, curve_samples=9, piece_id="bodice-front", seam_ids=("seam-neck",))
    with TestCase().assertRaisesRegex(ValueError, "deterministic authoritative pattern"):
        validate_export(
            pattern,
            dxf.replace("bodice-front", "bodice-back", 1),
            "dxf",
            curve_samples=9,
            piece_id="bodice-front",
            seam_ids=("seam-neck",),
        )


def test_release_gate_rejects_unknown_format():
    with TestCase().assertRaisesRegex(ValueError, "format must be 'svg' or 'dxf'"):
        validate_export(_curved_pattern(), "", "pdf")


def test_svg_contains_visible_print_safe_geometry() -> None:
    pattern = _curved_pattern()
    svg = to_svg(pattern, curve_samples=9, derived=_derived(pattern), piece_id="bodice-front")
    root = ElementTree.fromstring(svg)
    elements = list(root.iter())
    by_id = {element.attrib["id"]: element for element in elements if element.attrib.get("id")}

    sewing_group = by_id["sewing-boundary"]
    sewing_path = next(
        element for element in sewing_group.iter() if element.tag.rsplit("}", 1)[-1] == "path"
    )
    cut_path = by_id["cut-perimeter"]
    grainline = by_id["mark-grain-1"]
    text = next(element for element in elements if element.attrib.get("data-mark-id") == "grain-1")

    for element in (sewing_path, cut_path, grainline):
        assert element.attrib.get("stroke") == "#000000"
    assert cut_path.attrib["data-notch-ids"] == "notch-1"
    assert not any(element.attrib.get("id") == "notch-notch-1" for element in elements)
    assert sewing_path.attrib.get("fill") == "none"
    assert cut_path.attrib.get("fill") == "none"
    assert text.attrib.get("fill") == "#000000"
    assert text.attrib.get("font-size") == "3mm"
    assert root.attrib["width"].endswith("mm")
    assert root.attrib["height"].endswith("mm")



def test_notch_is_cut_into_cut_perimeter_toward_sewing_boundary() -> None:
    pattern = rectangle(100.0, 60.0)
    derived = add_notches(
        derive_cut_boundary(pattern, 5.0),
        [Notch("right-notch", "right", 0.5, depth=3.0)],
    )
    svg = to_svg(pattern, derived=derived)
    root = ElementTree.fromstring(svg)
    cut_path = next(element for element in root.iter() if element.attrib.get("id") == "cut-perimeter")
    coordinates = [
        (float(x), float(y))
        for x, y in re.findall(
            r"(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)",
            cut_path.attrib["d"],
        )
    ]

    # Native apex (102, 30) is transformed by the -5 mm X and -5 mm Y origin.
    apex_index = next(
        index
        for index, (x, y) in enumerate(coordinates)
        if abs(x - 107.0) < 1e-6 and abs(y - 35.0) < 1e-6
    )
    previous = coordinates[apex_index - 1]
    following = coordinates[(apex_index + 1) % len(coordinates)]
    assert previous[0] == 110.0 and following[0] == 110.0
    assert (previous[1] - 35.0) * (following[1] - 35.0) < 0
    assert cut_path.attrib["data-notch-ids"] == "right-notch"

    dxf = to_dxf(pattern, derived=derived)
    cut_section = dxf.split("8\nCUT\n", 1)[1].split("0\nENDSEC", 1)[0]
    assert "10\n102.000000\n20\n30.000000" in cut_section
    assert "8\nMARK\n" not in cut_section


def test_zero_allowance_notch_falls_inward_not_outward() -> None:
    pattern = rectangle(100.0, 60.0)
    derived = add_notches(
        derive_cut_boundary(pattern, 0.0),
        [Notch("right-notch", "right", 0.5, depth=3.0)],
    )
    dxf = to_dxf(pattern, derived=derived)
    cut_section = dxf.split("8\nCUT\n", 1)[1].split("0\nENDSEC", 1)[0]
    assert "10\n97.000000\n20\n30.000000" in cut_section
    assert "10\n103.000000\n20\n30.000000" not in cut_section


def test_export_rejects_units_that_would_relabel_without_conversion() -> None:
    pattern = _curved_pattern()
    with TestCase().assertRaisesRegex(ValueError, "units must be 'mm'"):
        to_svg(pattern, units="in")
    with TestCase().assertRaisesRegex(ValueError, "units must be 'mm'"):
        to_dxf(pattern, units="cm")


def test_dxf_declares_millimetres_in_standard_header() -> None:
    dxf = to_dxf(_curved_pattern())
    assert "$INSUNITS\n70\n4\n" in dxf
    assert from_dxf_metadata(dxf)["units"] == "mm"


def test_cut_perimeter_is_closed_and_has_expected_allowance_extent() -> None:
    pattern = rectangle(100.0, 60.0)
    derived = derive_cut_boundary(pattern, 5.0)
    contour = derived.cut_contour
    assert len(contour) >= 4
    xs = [point[0] for point in contour]
    ys = [point[1] for point in contour]
    assert max(xs) - min(xs) == 110.0
    assert max(ys) - min(ys) == 70.0
    assert all(
        contour[index] != contour[(index + 1) % len(contour)] for index in range(len(contour))
    )
    dxf = to_dxf(pattern, derived=derived)
    assert "8\nCUT\n" in dxf
    cut_section = dxf.split("8\nCUT\n", 1)[1].split("0\nENDSEC", 1)[0]
    assert "70\n1\n" in cut_section


def test_pattern_piece_export_adapter_is_deterministic_and_read_only(tmp_path):
    class Piece:
        PatternType = "PatternPiece"
        Name = "Front"
        Label = "Front"
        PieceId = "piece-front"
        Width = 100.0
        Height = 60.0
        SeamAllowance = 5.0
        GrainlineAngle = 90.0
        GeometryAuthority = ""
        SewingOutline = repr([(0.0, 0.0), (100.0, 0.0), (100.0, 60.0), (0.0, 60.0)])
        DraftingBoundary = SewingOutline

    class Seam:
        SeamId = "front-back"
        PieceA = "piece-front"
        PieceB = "piece-back"
        Status = "Valid"

    class Document:
        Objects = ()

    piece = Piece()
    piece.Document = Document()
    piece.Document.Objects = (piece, Seam())
    before = (piece.Label, piece.SeamAllowance, piece.GrainlineAngle, piece.SewingOutline)

    for fmt, metadata_reader in (("svg", from_svg_metadata), ("dxf", from_dxf_metadata)):
        first = tmp_path / (f"front.{fmt}")
        second = tmp_path / (f"front-second.{fmt}")
        first_result = export_pattern_piece(piece, first, fmt, curve_samples=16)
        export_pattern_piece(piece, second, fmt, curve_samples=16)
        assert first.read_bytes() == second.read_bytes()
        assert first_result["valid"] is True
        metadata = metadata_reader(first.read_text(encoding="utf-8"))
        assert metadata["piece_id"] == "piece-front"
        assert metadata["seam_ids"] == ["front-back"]
        assert metadata["scale"] == 1.0
        assert metadata["seam_allowance_mm"] == 5.0
        assert metadata["mark_ids"] == ["piece-front:grainline"]

    assert before == (piece.Label, piece.SeamAllowance, piece.GrainlineAngle, piece.SewingOutline)


def test_pattern_piece_export_blocks_invalid_semantic_seams(tmp_path):
    class Piece:
        PatternType = "PatternPiece"
        Name = "Front"
        Label = "Front"
        PieceId = "piece-front"
        Width = 100.0
        Height = 60.0
        SeamAllowance = 0.0
        GrainlineAngle = 0.0
        GeometryAuthority = ""
        SewingOutline = repr([(0.0, 0.0), (100.0, 0.0), (100.0, 60.0), (0.0, 60.0)])
        DraftingBoundary = SewingOutline

    class Seam:
        SeamId = "front-back"
        PieceA = "piece-front"
        PieceB = "piece-back"
        Status = "Changed reference"

    class Document:
        Objects = ()

    piece = Piece()
    piece.Document = Document()
    piece.Document.Objects = (piece, Seam())
    with TestCase().assertRaisesRegex(ValueError, "cannot export pattern piece"):
        export_pattern_piece(piece, tmp_path / "invalid.svg", "svg")


def test_export_boundary_is_closed_and_continuous():
    pattern = _curved_pattern()
    svg = to_svg(pattern, curve_samples=24)
    assert '<path d="' in svg
    assert ' Z"' in svg
    dxf = to_dxf(pattern, curve_samples=24)
    assert "\n70\n1\n" in dxf


def test_export_rejects_disconnected_boundary_segments():
    with TestCase().assertRaisesRegex(ValueError, "boundary is not closed"):
        ParametricPattern(
            [
                LineSegment("a", (0.0, 0.0), (10.0, 0.0)),
                LineSegment("b", (10.0, 0.0), (10.0, 10.0)),
                LineSegment("c", (10.0, 10.0), (0.0, 10.0)),
                LineSegment("d", (0.0, 9.0), (0.0, 0.0)),
            ]
        )


def test_pattern_piece_export_uses_persisted_native_construction_marks(tmp_path):
    class Piece:
        PatternType = "PatternPiece"
        Name = "Front"
        Label = "Front"
        PieceId = "piece-front"
        Width = 100.0
        Height = 60.0
        SeamAllowance = 5.0
        GrainlineAngle = 0.0
        GeometryAuthority = ""
        SewingOutline = repr([(0.0, 0.0), (100.0, 0.0), (100.0, 60.0), (0.0, 60.0)])
        DraftingBoundary = SewingOutline

    class Mark:
        def __init__(self, name, mark_type, text="", length=40.0):
            self.Name = name
            self.PatternMarkId = name
            self.PatternMarkType = mark_type
            self.PieceId = "piece-front"
            self.SegmentId = "piece-front:edge:0"
            self.Position = 0.5
            self.Depth = 3.0
            self.Angle = 0.0
            self.Length = length
            self.Text = text

    class Document:
        Objects = ()

    piece = Piece()
    notch = Mark("notch-front", "Notch")
    grainline = Mark("grain-front", "Grainline", length=36.0)
    internal = Mark("mark-front", "InternalMark", text="Internal mark")
    piece.Document = Document()
    piece.Document.Objects = (piece, notch, grainline, internal)

    for fmt, reader in (("svg", from_svg_metadata), ("dxf", from_dxf_metadata)):
        output = tmp_path / (f"front.{fmt}")
        export_pattern_piece(piece, output, fmt)
        payload = output.read_text(encoding="utf-8")
        metadata = reader(payload)
        assert metadata["piece_id"] == "piece-front"
        assert metadata["notch_ids"] == ["notch-front"]
        assert metadata["mark_ids"] == ["grain-front", "mark-front"]

        if fmt == "svg":
            assert 'data-notch-ids="notch-front"' in payload
            assert 'id="mark-grain-front"' in payload
            assert 'id="mark-mark-front"' in payload
            assert '55.000000,67.000000' in payload
            assert 'cx="55.000000" cy="65.000000"' not in payload
            assert 'x1="35.000000" y1="65.000000" x2="75.000000" y2="65.000000"' in payload
        else:
            assert '"notch_ids":["notch-front"]' in payload
            assert '"mark_ids":["grain-front","mark-front"]' in payload
            assert "10\n50.000000\n20\n-2.000000" in payload
            assert "10\n30.000000\n20\n0.000000\n10\n70.000000\n20\n0.000000" in payload


def test_pattern_piece_export_blocks_missing_persisted_mark_edge(tmp_path):
    class Piece:
        PatternType = "PatternPiece"
        Name = "Front"
        Label = "Front"
        PieceId = "piece-front"
        Width = 100.0
        Height = 60.0
        SeamAllowance = 0.0
        GrainlineAngle = 0.0
        GeometryAuthority = ""
        SewingOutline = repr([(0.0, 0.0), (100.0, 0.0), (100.0, 60.0), (0.0, 60.0)])
        DraftingBoundary = SewingOutline

    class Mark:
        PatternMarkId = "mark-front"
        PatternMarkType = "InternalMark"
        PieceId = "piece-front"
        SegmentId = "piece-front:edge:stale"
        Position = 0.5
        Depth = 3.0
        Angle = 0.0
        Length = 40.0
        Text = "Internal mark"

    class Document:
        Objects = ()

    piece = Piece()
    mark = Mark()
    piece.Document = Document()
    piece.Document.Objects = (piece, mark)

    output = tmp_path / "blocked.svg"
    with TestCase().assertRaisesRegex(ValueError, "references missing edge"):
        export_pattern_piece(piece, output, "svg")
    assert not output.exists()
