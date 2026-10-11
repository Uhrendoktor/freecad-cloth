import re
import sys
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
    from_pdf_metadata,
    from_svg_metadata,
    to_dxf,
    to_pdf,
    to_svg,
    validate_export,
    validate_pdf_export,
    validate_svg_export,
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
    svg_root = ElementTree.fromstring(svg)
    cut_path = next(
        element for element in svg_root.iter() if element.attrib.get("id") == "cut-perimeter"
    )
    assert cut_path.attrib["data-notch-ids"] == "notch-1"
    coordinates = [
        (float(x), float(y))
        for x, y in re.findall(
            r"(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)",
            cut_path.attrib["d"],
        )
    ]
    notch_apex = next(
        index
        for index, (x, _y) in enumerate(coordinates)
        if abs(x - 107.0) < 1e-6
        and abs(coordinates[index - 1][0] - 110.0) < 1e-6
        and abs(coordinates[(index + 1) % len(coordinates)][0] - 110.0) < 1e-6
    )
    previous_y = coordinates[notch_apex - 1][1]
    apex_y = coordinates[notch_apex][1]
    following_y = coordinates[(notch_apex + 1) % len(coordinates)][1]
    assert (previous_y - apex_y) * (following_y - apex_y) < 0
    assert not any(element.attrib.get("id") == "notch-notch-1" for element in svg_root.iter())
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
    cut_section = dxf.split("8\nCUT\n", 1)[1].split("0\nENDSEC", 1)[0]
    assert "10\n102.000000\n20\n30.000000" in cut_section


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


def test_svg_physical_dimensions_are_independently_rendered_to_png(tmp_path: Path) -> None:
    pattern = rectangle(100.0, 60.0)
    derived = derive_cut_boundary(pattern, 5.0)
    svg = to_svg(pattern, derived=derived)
    png_path = tmp_path / "rendered-pattern.png"

    result = validate_svg_export(
        pattern,
        svg,
        derived=derived,
        dpi=144,
        output_path=png_path,
    )

    assert result["valid"] is True
    report = result["render"]
    assert report["valid"] is True
    assert report["renderer"] == "QtSvg"
    assert report["physical_width_mm"] == 110.0
    assert report["physical_height_mm"] == 70.0
    assert report["viewbox"] == [0.0, 0.0, 110.0, 70.0]
    assert report["raster_width_px"] == 624
    assert report["raster_height_px"] == 397
    assert report["ink_pixel_count"] > 100
    assert report["ink_bounds_px"][2] >= report["ink_bounds_px"][0]
    assert report["ink_bounds_px"][3] >= report["ink_bounds_px"][1]
    assert png_path.read_bytes().startswith(b"\\x89PNG\\r\\n\\x1a\\n")
    assert report["png_path"] == str(png_path)


def test_svg_render_validation_rejects_physical_dimension_drift() -> None:
    from freecad_cloth.pattern.PatternSvgValidation import render_svg_for_validation

    svg = to_svg(rectangle(100.0, 60.0))
    root = ElementTree.fromstring(svg)
    original_width = root.attrib["width"]
    malformed = svg.replace(f'width="{original_width}"', 'width="101mm"', 1)

    with TestCase().assertRaisesRegex(ValueError, "physical width does not match its viewBox"):
        render_svg_for_validation(malformed)

def test_notch_is_cut_into_cut_perimeter_toward_sewing_boundary() -> None:
    pattern = rectangle(100.0, 60.0)
    derived = add_notches(
        derive_cut_boundary(pattern, 5.0),
        [Notch("right-notch", "right", 0.5, depth=3.0)],
    )
    svg = to_svg(pattern, derived=derived)
    root = ElementTree.fromstring(svg)
    cut_path = next(
        element for element in root.iter() if element.attrib.get("id") == "cut-perimeter"
    )
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


def test_pdf_export_is_deterministic_actual_size_and_calibrated() -> None:
    pattern = rectangle(100.0, 60.0)
    derived = derive_cut_boundary(pattern, 5.0)
    derived = add_notches(derived, [Notch("right-notch", "right", 0.5, depth=3.0)])
    first = to_pdf(
        pattern,
        derived=derived,
        piece_id="front",
        seam_ids=("front-back",),
        seam_allowance=5.0,
    )
    second = to_pdf(
        pattern,
        derived=derived,
        piece_id="front",
        seam_ids=("front-back",),
        seam_allowance=5.0,
    )
    assert first == second
    assert first.startswith(b"%PDF-1.4")
    assert b"/Count 1" in first
    assert b"/MediaBox [0 0 595.27559 841.88976]" in first
    assert b"70.86614 70.86614 re S" in first
    assert first.count(b"25 mm CALIBRATION SQUARE") == 1
    assert first.count(b"Print at ACTUAL SIZE / 100%") == 1
    assert b"Fit to Page" in first
    metadata = from_pdf_metadata(first)
    assert metadata["format"] == "pdf"
    assert metadata["units"] == "mm"
    assert metadata["scale"] == 1.0
    assert metadata["paper_size"] == "A4"
    assert metadata["page_count"] == 1
    assert metadata["notch_ids"] == ["right-notch"]
    assert (
        validate_pdf_export(
            pattern,
            first,
            derived=derived,
            piece_id="front",
            seam_ids=("front-back",),
            seam_allowance=5.0,
        )["valid"]
        is True
    )
    with TestCase().assertRaisesRegex(ValueError, "deterministic authoritative"):
        validate_pdf_export(pattern, first + b"tampered")


def test_pdf_tiles_long_pattern_with_overlap_and_registration_marks() -> None:
    pattern = rectangle(500.0, 400.0)
    derived = derive_cut_boundary(pattern, 5.0)
    pdf = to_pdf(pattern, derived=derived, piece_id="long-panel", seam_allowance=5.0)
    metadata = from_pdf_metadata(pdf)
    assert metadata["tile_columns"] == 3
    assert metadata["tile_rows"] == 2
    assert metadata["page_count"] == 6
    assert b"/Count 6" in pdf
    assert pdf.count(b"/Type /Page ") == 6
    assert pdf.count(b"25 mm CALIBRATION SQUARE") == 6
    assert pdf.count(b"Print at ACTUAL SIZE / 100%") == 6
    assert b"H1-1" in pdf
    assert b"V1-1" in pdf
    assert metadata["overlap_mm"] == 10.0


def test_pdf_letter_page_size_and_layout_validation() -> None:
    pattern = rectangle(100.0, 60.0)
    letter_pdf = to_pdf(pattern, paper_size="Letter")
    assert b"/MediaBox [0 0 612 792]" in letter_pdf
    assert from_pdf_metadata(letter_pdf)["paper_size"] == "Letter"
    with TestCase().assertRaisesRegex(ValueError, "paper_size"):
        to_pdf(pattern, paper_size="Legal")
    with TestCase().assertRaisesRegex(ValueError, "overlap"):
        to_pdf(pattern, overlap_mm=1000.0)
    with TestCase().assertRaisesRegex(ValueError, "overlap"):
        to_pdf(pattern, overlap_mm=0.0)


def test_pattern_piece_pdf_export_is_binary_and_reports_page_layout(tmp_path: Path) -> None:
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

    class Document:
        Objects = ()

    piece = Piece()
    piece.Document = Document()
    piece.Document.Objects = (piece,)
    path = tmp_path / "front.pdf"
    result = export_pattern_piece(piece, path, "pdf", curve_samples=16)
    payload = path.read_bytes()
    metadata = from_pdf_metadata(payload)
    assert result["valid"] is True
    assert payload.startswith(b"%PDF-1.4")
    assert metadata["piece_id"] == "piece-front"
    assert metadata["scale"] == 1.0
    assert metadata["seam_allowance_mm"] == 5.0
    assert metadata["page_count"] == 1


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

    for fmt, metadata_reader in (
        ("svg", from_svg_metadata),
        ("dxf", from_dxf_metadata),
        ("pdf", from_pdf_metadata),
    ):
        first = tmp_path / (f"front.{fmt}")
        second = tmp_path / (f"front-second.{fmt}")
        first_result = export_pattern_piece(piece, first, fmt, curve_samples=16)
        export_pattern_piece(piece, second, fmt, curve_samples=16)
        assert first.read_bytes() == second.read_bytes()
        assert first_result["valid"] is True
        metadata = (
            metadata_reader(first.read_bytes())
            if fmt == "pdf"
            else metadata_reader(first.read_text(encoding="utf-8"))
        )
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

    for fmt, reader in (
        ("svg", from_svg_metadata),
        ("dxf", from_dxf_metadata),
        ("pdf", from_pdf_metadata),
    ):
        output = tmp_path / (f"front.{fmt}")
        export_pattern_piece(piece, output, fmt)
        raw_payload = output.read_bytes()
        if fmt == "pdf":
            metadata = reader(raw_payload)
            assert metadata["piece_id"] == "piece-front"
            assert metadata["notch_ids"] == ["notch-front"]
            assert metadata["mark_ids"] == ["grain-front", "mark-front"]
            assert b"25 mm CALIBRATION SQUARE" in raw_payload
            continue
        payload = raw_payload.decode("utf-8")
        metadata = reader(payload)
        assert metadata["piece_id"] == "piece-front"
        assert metadata["notch_ids"] == ["notch-front"]
        assert metadata["mark_ids"] == ["grain-front", "mark-front"]

        if fmt == "svg":
            assert 'data-notch-ids="notch-front"' in payload
            assert 'id="mark-grain-front"' in payload
            assert 'id="mark-mark-front"' in payload
            assert "55.000000,67.000000" in payload
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
