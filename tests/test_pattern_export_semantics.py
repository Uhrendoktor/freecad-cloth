# Copyright (C) 2026 FreeCAD Cloth contributors
"""Contract tests for canonical export metadata and native Sketcher boundaries."""

import re
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from typing import Protocol, TypedDict, cast

from defusedxml import ElementTree as ET
import pytest

from freecad_cloth.pattern.PatternDerivedGeometry import (
    DerivedPattern,
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
    validate_svg_export,
)
from freecad_cloth.pattern.PatternGeometry import (
    LineSegment,
    ParametricPattern,
    QuadraticBezier,
    rectangle,
)
from freecad_cloth.pattern.PatternPdfExport import (
    PdfExportOptions,
    from_pdf_metadata,
    to_pdf,
    validate_pdf_export,
)
from freecad_cloth.pattern.PatternSvgValidation import render_svg_for_validation
from tests.support.assertions import require



class _ExportOptions(TypedDict):
    """Typed keyword controls shared by SVG, DXF, and export validation."""

    curve_samples: int
    derived: DerivedPattern
    piece_id: str
    seam_ids: tuple[str, ...]


class _RenderReport(TypedDict):
    """Validated raster evidence returned by the SVG rendering check."""

    valid: bool
    renderer: str
    physical_width_mm: float
    physical_height_mm: float
    viewbox: list[float]
    raster_width_px: int
    raster_height_px: int
    ink_pixel_count: int
    ink_bounds_px: list[int]
    png_path: str


class _NativeSketch(Protocol):
    """Native or test-double sketch properties read by the export adapter."""

    SemanticEdgeIds: tuple[str, ...]


class _PieceSeed(Protocol):
    """Minimum properties required to attach a Sketcher boundary to a piece."""

    PieceId: str
    Width: float
    Height: float


class _ExportDocument(Protocol):
    """Document collection used to discover persisted seams and marks."""

    Objects: tuple[object, ...]


class _PatternPiece(_PieceSeed, Protocol):
    """Pattern-piece fields consumed by export after Sketcher adoption."""

    PatternType: str
    Name: str
    Label: str
    SeamAllowance: float
    GrainlineAngle: float
    GeometryAuthority: str
    Sketch: _NativeSketch
    Document: _ExportDocument



def _curved_pattern() -> ParametricPattern:
    """Create a deterministic curved pattern used by the export contract tests."""
    return ParametricPattern(
        [
            LineSegment("bottom", (0.0, 0.0), (100.0, 0.0)),
            LineSegment("right", (100.0, 0.0), (100.0, 60.0)),
            QuadraticBezier("armhole", (100.0, 60.0), (55.0, 85.0), (0.0, 60.0)),
            LineSegment("left", (0.0, 60.0), (0.0, 0.0)),
        ]
    )


def _derived(pattern: ParametricPattern) -> DerivedPattern:
    """Build the cut contour, notch, and grainline used by export tests.

    Args:
        pattern: Authored sewing boundary from which cut geometry is derived.

    Returns:
        Derived contour with one notch and one grainline mark.
    """
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


def _native_sketch(
    piece_id: str,
    outline: tuple[tuple[float, float], ...],
) -> SimpleNamespace:
    """Build a line-only Sketcher test double with persistent semantic IDs.

    Args:
        piece_id: Stable identity used to name native boundary edges.
        outline: Connected, closed 2D polygon vertices.

    Returns:
        Sketch-like object consumable by PatternIR without importing FreeCAD.
    """

    class Point:
        """Coordinate value exposed by a native Sketcher endpoint."""

        def __init__(self, x: float, y: float) -> None:
            """Store a coordinate in millimetres.

            Args:
                x: Horizontal coordinate.
                y: Vertical coordinate.
            """
            self.x, self.y, self.z = float(x), float(y), 0.0

    class LineSegment:
        """Native line item recognized by PatternIR's Sketcher adapter."""

        def __init__(self, start: tuple[float, float], end: tuple[float, float]) -> None:
            """Store the start and end points of a sketch geometry item.

            Args:
                start: Initial 2D coordinate.
                end: Terminal 2D coordinate.
            """
            self.StartPoint = Point(*start)
            self.EndPoint = Point(*end)

    geometry = tuple(
        LineSegment(start, outline[(index + 1) % len(outline)])
        for index, start in enumerate(outline)
    )
    return cast(
        "_NativeSketch",
        SimpleNamespace(
            Geometry=geometry,
            SemanticEdgeIds=tuple(f"{piece_id}:edge:{index}" for index in range(len(geometry))),
            getConstruction=lambda _index: False,
        ),
    )


def _native_piece(piece: _PieceSeed) -> _PatternPiece:
    """Attach a native rectangular Sketcher boundary to an export test fixture.

    Args:
        piece: Test object exposing PieceId, Width, and Height.

    Returns:
        The same test object with Sketcher as its geometry authority.
    """
    width, height = float(piece.Width), float(piece.Height)
    adopted_piece = cast("_PatternPiece", piece)
    adopted_piece.GeometryAuthority = "Sketcher"
    adopted_piece.Sketch = _native_sketch(
        str(adopted_piece.PieceId),
        ((0.0, 0.0), (width, 0.0), (width, height), (0.0, height)),
    )
    return adopted_piece


def test_svg_and_dxf_preserve_piece_and_construction_semantics() -> None:
    """Verify that SVG and DXF preserve piece identity, construction marks, and seam metadata."""
    pattern = _curved_pattern()
    derived = _derived(pattern)
    svg = to_svg(
        pattern,
        curve_samples=9,
        derived=derived,
        piece_id="bodice-front",
        seam_ids=("seam-neck", "seam-side"),
    )
    require(
        condition=(
            'data-piece-id="bodice-front"' in svg
        ),
        message="Export contract failed: 'data-piece-id=\"bodice-front\"' in svg",
    )
    require(
        condition=(
            'data-edge-ids="bottom right armhole left"' in svg
        ),
        message="Export contract failed: 'data-edge-ids=\"bottom right armhole left\"' i",
    )
    svg_root = ET.fromstring(svg)
    cut_path = next(
        element for element in svg_root.iter() if element.attrib.get("id") == "cut-perimeter"
    )
    require(
        condition=(
            cut_path.attrib["data-notch-ids"] == "notch-1"
        ),
        message="Export contract failed: cut_path.attrib[\"data-notch-ids\"] == \"notch-1",
    )
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
    require(
        condition=(
            (previous_y - apex_y) * (following_y - apex_y) < 0
        ),
        message="Export contract failed: (previous_y - apex_y) * (following_y - apex_y",
    )
    require(
        condition=(
            not any(element.attrib.get("id") == "notch-notch-1" for element in svg_root.iter())
        ),
        message="Export contract failed: not any(element.attrib.get(\"id\") == \"notch-no",
    )
    require(
        condition=(
            'data-mark-id="grain-1"' in svg
        ),
        message="Export contract failed: 'data-mark-id=\"grain-1\"' in svg",
    )
    require(
        condition=(
            from_svg_metadata(svg) == {
            "version": 2,
            "units": "mm",
            "edge_ids": ["bottom", "right", "armhole", "left"],
            "piece_id": "bodice-front",
            "seam_ids": ["seam-neck", "seam-side"],
            "scale": 1.0,
            "seam_allowance_mm": 0.0,
            "notch_ids": ["notch-1"],
            "mark_ids": ["grain-1"],
            }
        ),
        message="Export contract failed: from_svg_metadata(svg) == { \"version\": 2, \"un",
    )

    dxf = to_dxf(
        pattern,
        curve_samples=9,
        derived=derived,
        piece_id="bodice-front",
        seam_ids=("seam-neck", "seam-side"),
    )
    require(
        condition=(
            from_dxf_metadata(dxf) == {
            "version": 2,
            "units": "mm",
            "edge_ids": ["bottom", "right", "armhole", "left"],
            "piece_id": "bodice-front",
            "seam_ids": ["seam-neck", "seam-side"],
            "scale": 1.0,
            "seam_allowance_mm": 0.0,
            "notch_ids": ["notch-1"],
            "mark_ids": ["grain-1"],
            }
        ),
        message="Export contract failed: from_dxf_metadata(dxf) == { \"version\": 2, \"un",
    )
    cut_section = dxf.split("8\nCUT\n", 1)[1].split("0\nENDSEC", 1)[0]
    require(
        condition=(
            "10\n102.000000\n20\n30.000000" in cut_section
        ),
        message="Export contract failed: \"10\\n102.000000\\n20\\n30.000000\" in cut_sectio",
    )


def test_standalone_export_uses_complete_current_metadata_schema() -> None:
    """Emit the complete schema even when standalone geometry has no document ID."""
    metadata = from_dxf_metadata(to_dxf(_curved_pattern()))
    require(
        condition=(
            metadata == {
            "version": 2,
            "units": "mm",
            "edge_ids": ["bottom", "right", "armhole", "left"],
            "piece_id": "",
            "seam_ids": [],
            "scale": 1.0,
            "seam_allowance_mm": 0.0,
            "notch_ids": [],
            "mark_ids": [],
            }
        ),
        message="Export contract failed: metadata == { \"version\": 2, \"units\": \"mm\", \"e",
    )


def test_release_gate_validates_deterministic_svg_and_dxf_round_trip() -> None:
    """Verify deterministic SVG and DXF exports pass the semantic release gate."""
    pattern = _curved_pattern()
    derived = _derived(pattern)
    kwargs: _ExportOptions = {
        "curve_samples": 9,
        "derived": derived,
        "piece_id": "bodice-front",
        "seam_ids": ("seam-neck", "seam-side"),
    }

    svg = to_svg(pattern, **kwargs)
    result = validate_export(pattern, svg, "svg", **kwargs)
    require(
        condition=(
            result["valid"] is True
        ),
        message="Export contract failed: result[\"valid\"] is True",
    )
    require(
        condition=(
            result["metadata"]["piece_id"] == "bodice-front"
        ),
        message="Export contract failed: result[\"metadata\"][\"piece_id\"] == \"bodice-fro",
    )

    dxf = to_dxf(pattern, **kwargs)
    result = validate_export(pattern, dxf, "dxf", **kwargs)
    require(
        condition=(
            result["valid"] is True
        ),
        message="Export contract failed: result[\"valid\"] is True",
    )
    require(
        condition=(
            result["metadata"]["seam_ids"] == ["seam-neck", "seam-side"]
        ),
        message="Export contract failed: result[\"metadata\"][\"seam_ids\"] == [\"seam-neck",
    )


def test_release_gate_rejects_geometry_or_semantic_drift() -> None:
    """Reject modified geometry or metadata instead of accepting export drift."""
    pattern = _curved_pattern()
    svg = to_svg(pattern, curve_samples=9, piece_id="bodice-front", seam_ids=("seam-neck",))
    tampered_svg = svg.replace(
        "0.000000,12.500000",
        "1.000000,12.500000",
        1,
    )
    require(
        condition=(
            tampered_svg != svg
        ),
        message="Export contract failed: tampered_svg != svg",
    )
    with pytest.raises(ValueError, match="deterministic authoritative pattern"):
        validate_export(
            pattern,
            tampered_svg,
            "svg",
            curve_samples=9,
            piece_id="bodice-front",
            seam_ids=("seam-neck",),
        )

    dxf = to_dxf(pattern, curve_samples=9, piece_id="bodice-front", seam_ids=("seam-neck",))
    with pytest.raises(ValueError, match="deterministic authoritative pattern"):
        validate_export(
            pattern,
            dxf.replace("bodice-front", "bodice-back", 1),
            "dxf",
            curve_samples=9,
            piece_id="bodice-front",
            seam_ids=("seam-neck",),
        )


def test_release_gate_rejects_unknown_format() -> None:
    """Reject export formats that are not supported."""
    with pytest.raises(ValueError, match="format must be 'svg' or 'dxf'"):
        validate_export(_curved_pattern(), "", "pdf")


def test_svg_contains_visible_print_safe_geometry() -> None:
    """Verify that svg contains visible print safe geometry."""
    pattern = _curved_pattern()
    svg = to_svg(pattern, curve_samples=9, derived=_derived(pattern), piece_id="bodice-front")
    root = ET.fromstring(svg)
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
        require(
            condition=(
                element.attrib.get("stroke") == "#000000"
            ),
            message="Export contract failed: element.attrib.get(\"stroke\") == \"#000000\"",
        )
    require(
        condition=(
            cut_path.attrib["data-notch-ids"] == "notch-1"
        ),
        message="Export contract failed: cut_path.attrib[\"data-notch-ids\"] == \"notch-1",
    )
    require(
        condition=(
            not any(element.attrib.get("id") == "notch-notch-1" for element in elements)
        ),
        message="Export contract failed: not any(element.attrib.get(\"id\") == \"notch-no",
    )
    require(
        condition=(
            sewing_path.attrib.get("fill") == "none"
        ),
        message="Export contract failed: sewing_path.attrib.get(\"fill\") == \"none\"",
    )
    require(
        condition=(
            cut_path.attrib.get("fill") == "none"
        ),
        message="Export contract failed: cut_path.attrib.get(\"fill\") == \"none\"",
    )
    require(
        condition=(
            text.attrib.get("fill") == "#000000"
        ),
        message="Export contract failed: text.attrib.get(\"fill\") == \"#000000\"",
    )
    # The viewBox coordinates are millimetres, so font-size must be unitless.
    require(
        condition=(
            text.attrib.get("font-size") == "3"
        ),
        message="Export contract failed: text.attrib.get(\"font-size\") == \"3\"",
    )
    require(
        condition=(
            root.attrib["width"].endswith("mm")
        ),
        message="Export contract failed: root.attrib[\"width\"].endswith(\"mm\")",
    )
    require(
        condition=(
            root.attrib["height"].endswith("mm")
        ),
        message="Export contract failed: root.attrib[\"height\"].endswith(\"mm\")",
    )


def test_svg_physical_dimensions_are_independently_rendered_to_png(tmp_path: Path) -> None:
    """Verify that svg physical dimensions are independently rendered to png.

    Args:
        tmp_path: Temporary directory used for generated export artifacts.
    """
    try:
        import_module("PySide.QtSvg")
    except ImportError:
        try:
            import_module("PySide2.QtSvg")
        except ImportError as exc:
            pytest.skip(f"QtSvg requires FreeCAD's Python runtime: {exc}")

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

    require(
        condition=(
            result["valid"] is True
        ),
        message="Export contract failed: result[\"valid\"] is True",
    )
    report = cast("_RenderReport", result["render"])
    require(
        condition=(
            report["valid"] is True
        ),
        message="Export contract failed: report[\"valid\"] is True",
    )
    require(
        condition=(
            report["renderer"] == "QtSvg"
        ),
        message="Export contract failed: report[\"renderer\"] == \"QtSvg\"",
    )
    require(
        condition=(
            report["physical_width_mm"] == 110.0
        ),
        message="Export contract failed: report[\"physical_width_mm\"] == 110.0",
    )
    require(
        condition=(
            report["physical_height_mm"] == 70.0
        ),
        message="Export contract failed: report[\"physical_height_mm\"] == 70.0",
    )
    require(
        condition=(
            report["viewbox"] == [0.0, 0.0, 110.0, 70.0]
        ),
        message="Export contract failed: report[\"viewbox\"] == [0.0, 0.0, 110.0, 70.0]",
    )
    require(
        condition=(
            report["raster_width_px"] == 624
        ),
        message="Export contract failed: report[\"raster_width_px\"] == 624",
    )
    require(
        condition=(
            report["raster_height_px"] == 397
        ),
        message="Export contract failed: report[\"raster_height_px\"] == 397",
    )
    require(
        condition=(
            report["ink_pixel_count"] > 100
        ),
        message="Export contract failed: report[\"ink_pixel_count\"] > 100",
    )
    require(
        condition=(
            report["ink_bounds_px"][2] >= report["ink_bounds_px"][0]
        ),
        message="Export contract failed: report[\"ink_bounds_px\"][2] >= report[\"ink_bou",
    )
    require(
        condition=(
            report["ink_bounds_px"][3] >= report["ink_bounds_px"][1]
        ),
        message="Export contract failed: report[\"ink_bounds_px\"][3] >= report[\"ink_bou",
    )
    require(
        condition=(
            png_path.read_bytes().startswith(bytes((137, 80, 78, 71, 13, 10, 26, 10)))
        ),
        message="Export contract failed: png_path.read_bytes().startswith(bytes((137, ",
    )
    require(
        condition=(
            report["png_path"] == str(png_path)
        ),
        message="Export contract failed: report[\"png_path\"] == str(png_path)",
    )


def test_svg_render_validation_rejects_physical_dimension_drift() -> None:
    """Verify that svg render validation rejects physical dimension drift."""
    svg = to_svg(rectangle(100.0, 60.0))
    root = ET.fromstring(svg)
    original_width = root.attrib["width"]
    malformed = svg.replace(f'width="{original_width}"', 'width="101mm"', 1)

    with pytest.raises(ValueError, match="physical width does not match its viewBox"):
        render_svg_for_validation(malformed)


def test_notch_is_cut_into_cut_perimeter_toward_sewing_boundary() -> None:
    """Verify that notch is cut into cut perimeter toward sewing boundary."""
    pattern = rectangle(100.0, 60.0)
    derived = add_notches(
        derive_cut_boundary(pattern, 5.0),
        [Notch("right-notch", "right", 0.5, depth=3.0)],
    )
    svg = to_svg(pattern, derived=derived)
    root = ET.fromstring(svg)
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
    require(
        condition=(
            previous[0] == 110.0
        ),
        message="Export contract failed: previous[0] == 110.0",
    )
    require(
        condition=(
            following[0] == 110.0
        ),
        message="Export contract failed: following[0] == 110.0",
    )
    require(
        condition=(
            (previous[1] - 35.0) * (following[1] - 35.0) < 0
        ),
        message="Export contract failed: (previous[1] - 35.0) * (following[1] - 35.0) ",
    )
    require(
        condition=(
            cut_path.attrib["data-notch-ids"] == "right-notch"
        ),
        message="Export contract failed: cut_path.attrib[\"data-notch-ids\"] == \"right-n",
    )

    dxf = to_dxf(pattern, derived=derived)
    cut_section = dxf.split("8\nCUT\n", 1)[1].split("0\nENDSEC", 1)[0]
    require(
        condition=(
            "10\n102.000000\n20\n30.000000" in cut_section
        ),
        message="Export contract failed: \"10\\n102.000000\\n20\\n30.000000\" in cut_sectio",
    )
    require(
        condition=(
            "8\nMARK\n" not in cut_section
        ),
        message="Export contract failed: \"8\\nMARK\\n\" not in cut_section",
    )


def test_zero_allowance_notch_falls_inward_not_outward() -> None:
    """Verify that zero allowance notch falls inward not outward."""
    pattern = rectangle(100.0, 60.0)
    derived = add_notches(
        derive_cut_boundary(pattern, 0.0),
        [Notch("right-notch", "right", 0.5, depth=3.0)],
    )
    dxf = to_dxf(pattern, derived=derived)
    cut_section = dxf.split("8\nCUT\n", 1)[1].split("0\nENDSEC", 1)[0]
    require(
        condition=(
            "10\n97.000000\n20\n30.000000" in cut_section
        ),
        message="Export contract failed: \"10\\n97.000000\\n20\\n30.000000\" in cut_section",
    )
    require(
        condition=(
            "10\n103.000000\n20\n30.000000" not in cut_section
        ),
        message="Export contract failed: \"10\\n103.000000\\n20\\n30.000000\" not in cut_se",
    )


def test_pdf_export_is_deterministic_actual_size_and_calibrated() -> None:
    """Verify that pdf export is deterministic actual size and calibrated."""
    pattern = rectangle(100.0, 60.0)
    derived = derive_cut_boundary(pattern, 5.0)
    derived = add_notches(derived, [Notch("right-notch", "right", 0.5, depth=3.0)])
    options = PdfExportOptions(
        derived=derived,
        piece_id="front",
        seam_ids=("front-back",),
        seam_allowance=5.0,
    )
    first = to_pdf(pattern, options)
    second = to_pdf(pattern, options)
    require(
        condition=(
            first == second
        ),
        message="Export contract failed: first == second",
    )
    require(
        condition=(
            first.startswith(b"%PDF-1.4")
        ),
        message="Export contract failed: first.startswith(b\"%PDF-1.4\")",
    )
    require(
        condition=(
            b"/Count 1" in first
        ),
        message="Export contract failed: b\"/Count 1\" in first",
    )
    require(
        condition=(
            b"/MediaBox [0 0 595.27559 841.88976]" in first
        ),
        message="Export contract failed: b\"/MediaBox [0 0 595.27559 841.88976]\" in fir",
    )
    require(
        condition=(
            b"70.86614 70.86614 re S" in first
        ),
        message="Export contract failed: b\"70.86614 70.86614 re S\" in first",
    )
    require(
        condition=(
            first.count(b"25 mm CALIBRATION SQUARE") == 1
        ),
        message="Export contract failed: first.count(b\"25 mm CALIBRATION SQUARE\") == 1",
    )
    require(
        condition=(
            first.count(b"Print at ACTUAL SIZE / 100%") == 1
        ),
        message="Export contract failed: first.count(b\"Print at ACTUAL SIZE / 100%\") =",
    )
    require(
        condition=(
            b"Fit to Page" in first
        ),
        message="Export contract failed: b\"Fit to Page\" in first",
    )
    metadata = from_pdf_metadata(first)
    require(
        condition=(
            metadata["format"] == "pdf"
        ),
        message="Export contract failed: metadata[\"format\"] == \"pdf\"",
    )
    require(
        condition=(
            metadata["units"] == "mm"
        ),
        message="Export contract failed: metadata[\"units\"] == \"mm\"",
    )
    require(
        condition=(
            metadata["scale"] == 1.0
        ),
        message="Export contract failed: metadata[\"scale\"] == 1.0",
    )
    require(
        condition=(
            metadata["paper_size"] == "A4"
        ),
        message="Export contract failed: metadata[\"paper_size\"] == \"A4\"",
    )
    require(
        condition=(
            metadata["page_count"] == 1
        ),
        message="Export contract failed: metadata[\"page_count\"] == 1",
    )
    require(
        condition=(
            metadata["notch_ids"] == ["right-notch"]
        ),
        message="Export contract failed: metadata[\"notch_ids\"] == [\"right-notch\"]",
    )
    require(
        condition=(
            validate_pdf_export(pattern, first, options)["valid"] is True
        ),
        message="Export contract failed: validate_pdf_export(pattern, first, options)[",
    )
    with pytest.raises(ValueError, match="deterministic authoritative"):
        validate_pdf_export(pattern, first + b"tampered", options)


def test_pdf_tiles_long_pattern_with_overlap_and_registration_marks() -> None:
    """Verify that pdf tiles long pattern with overlap and registration marks."""
    pattern = rectangle(500.0, 400.0)
    derived = derive_cut_boundary(pattern, 5.0)
    pdf = to_pdf(
        pattern,
        PdfExportOptions(derived=derived, piece_id="long-panel", seam_allowance=5.0),
    )
    metadata = from_pdf_metadata(pdf)
    require(
        condition=(
            metadata["tile_columns"] == 3
        ),
        message="Export contract failed: metadata[\"tile_columns\"] == 3",
    )
    require(
        condition=(
            metadata["tile_rows"] == 2
        ),
        message="Export contract failed: metadata[\"tile_rows\"] == 2",
    )
    require(
        condition=(
            metadata["page_count"] == 6
        ),
        message="Export contract failed: metadata[\"page_count\"] == 6",
    )
    require(
        condition=(
            b"/Count 6" in pdf
        ),
        message="Export contract failed: b\"/Count 6\" in pdf",
    )
    require(
        condition=(
            pdf.count(b"/Type /Page ") == 6
        ),
        message="Export contract failed: pdf.count(b\"/Type /Page \") == 6",
    )
    require(
        condition=(
            pdf.count(b"25 mm CALIBRATION SQUARE") == 6
        ),
        message="Export contract failed: pdf.count(b\"25 mm CALIBRATION SQUARE\") == 6",
    )
    require(
        condition=(
            pdf.count(b"Print at ACTUAL SIZE / 100%") == 6
        ),
        message="Export contract failed: pdf.count(b\"Print at ACTUAL SIZE / 100%\") == ",
    )
    require(
        condition=(
            b"H1-1" in pdf
        ),
        message="Export contract failed: b\"H1-1\" in pdf",
    )
    require(
        condition=(
            b"V1-1" in pdf
        ),
        message="Export contract failed: b\"V1-1\" in pdf",
    )
    require(
        condition=(
            metadata["overlap_mm"] == 10.0
        ),
        message="Export contract failed: metadata[\"overlap_mm\"] == 10.0",
    )


def test_pdf_letter_page_size_and_layout_validation() -> None:
    """Verify that pdf letter page size and layout validation."""
    pattern = rectangle(100.0, 60.0)
    letter_pdf = to_pdf(pattern, PdfExportOptions(paper_size="Letter"))
    require(
        condition=(
            b"/MediaBox [0 0 612 792]" in letter_pdf
        ),
        message="Export contract failed: b\"/MediaBox [0 0 612 792]\" in letter_pdf",
    )
    require(
        condition=(
            from_pdf_metadata(letter_pdf)["paper_size"] == "Letter"
        ),
        message="Export contract failed: from_pdf_metadata(letter_pdf)[\"paper_size\"] =",
    )
    with pytest.raises(ValueError, match="paper_size"):
        to_pdf(pattern, PdfExportOptions(paper_size="Legal"))
    with pytest.raises(ValueError, match="overlap"):
        to_pdf(pattern, PdfExportOptions(overlap_mm=1000.0))
    with pytest.raises(ValueError, match="overlap"):
        to_pdf(pattern, PdfExportOptions(overlap_mm=0.0))


def test_pattern_piece_pdf_export_is_binary_and_reports_page_layout(tmp_path: Path) -> None:
    """Verify that pattern piece pdf export is binary and reports page layout.

    Args:
        tmp_path: Temporary directory used for generated export artifacts.
    """
    class Piece:
        """Minimal FreeCAD pattern-piece double used by export tests."""
        PatternType = "PatternPiece"
        Name = "Front"
        Label = "Front"
        PieceId = "piece-front"
        Width = 100.0
        Height = 60.0
        SeamAllowance = 5.0
        GrainlineAngle = 90.0

    class Document:
        """Minimal document double that exposes its persisted object collection."""

        Objects: tuple[object, ...] = ()

    piece = _native_piece(Piece())
    piece.Document = Document()
    piece.Document.Objects = (piece,)
    path = tmp_path / "front.pdf"
    result = export_pattern_piece(piece, path, "pdf", curve_samples=16)
    payload = path.read_bytes()
    metadata = from_pdf_metadata(payload)
    require(
        condition=(
            result["valid"] is True
        ),
        message="Export contract failed: result[\"valid\"] is True",
    )
    require(
        condition=(
            payload.startswith(b"%PDF-1.4")
        ),
        message="Export contract failed: payload.startswith(b\"%PDF-1.4\")",
    )
    require(
        condition=(
            metadata["piece_id"] == "piece-front"
        ),
        message="Export contract failed: metadata[\"piece_id\"] == \"piece-front\"",
    )
    require(
        condition=(
            metadata["scale"] == 1.0
        ),
        message="Export contract failed: metadata[\"scale\"] == 1.0",
    )
    require(
        condition=(
            metadata["seam_allowance_mm"] == 5.0
        ),
        message="Export contract failed: metadata[\"seam_allowance_mm\"] == 5.0",
    )
    require(
        condition=(
            metadata["page_count"] == 1
        ),
        message="Export contract failed: metadata[\"page_count\"] == 1",
    )


def test_export_rejects_units_that_would_relabel_without_conversion() -> None:
    """Verify that export rejects units that would relabel without conversion."""
    pattern = _curved_pattern()
    with pytest.raises(ValueError, match="units must be 'mm'"):
        to_svg(pattern, units="in")
    with pytest.raises(ValueError, match="units must be 'mm'"):
        to_dxf(pattern, units="cm")


def test_dxf_declares_millimetres_in_standard_header() -> None:
    """Verify that dxf declares millimetres in standard header."""
    dxf = to_dxf(_curved_pattern())
    require(
        condition=(
            "$INSUNITS\n70\n4\n" in dxf
        ),
        message="Export contract failed: \"$INSUNITS\\n70\\n4\\n\" in dxf",
    )
    require(
        condition=(
            from_dxf_metadata(dxf)["units"] == "mm"
        ),
        message="Export contract failed: from_dxf_metadata(dxf)[\"units\"] == \"mm\"",
    )


def test_cut_perimeter_is_closed_and_has_expected_allowance_extent() -> None:
    """Verify that cut perimeter is closed and has expected allowance extent."""
    pattern = rectangle(100.0, 60.0)
    derived = derive_cut_boundary(pattern, 5.0)
    contour = derived.cut_contour
    require(
        condition=(
            len(contour) >= 4
        ),
        message="Export contract failed: len(contour) >= 4",
    )
    xs = [point[0] for point in contour]
    ys = [point[1] for point in contour]
    require(
        condition=(
            max(xs) - min(xs) == 110.0
        ),
        message="Export contract failed: max(xs) - min(xs) == 110.0",
    )
    require(
        condition=(
            max(ys) - min(ys) == 70.0
        ),
        message="Export contract failed: max(ys) - min(ys) == 70.0",
    )
    require(
        condition=(
            all(
            contour[index] != contour[(index + 1) % len(contour)] for index in range(len(contour))
            )
        ),
        message="Export contract failed: all( contour[index] != contour[(index + 1) % ",
    )
    dxf = to_dxf(pattern, derived=derived)
    require(
        condition=(
            "8\nCUT\n" in dxf
        ),
        message="Export contract failed: \"8\\nCUT\\n\" in dxf",
    )
    cut_section = dxf.split("8\nCUT\n", 1)[1].split("0\nENDSEC", 1)[0]
    require(
        condition=(
            "70\n1\n" in cut_section
        ),
        message="Export contract failed: \"70\\n1\\n\" in cut_section",
    )


def test_pattern_piece_export_adapter_is_deterministic_and_read_only(tmp_path: Path) -> None:
    """Verify piece exports are deterministic and do not mutate the source document.

    Args:
        tmp_path: Temporary directory used for generated export artifacts.
    """
    class Piece:
        """Minimal FreeCAD pattern-piece double used by export tests."""
        PatternType = "PatternPiece"
        Name = "Front"
        Label = "Front"
        PieceId = "piece-front"
        Width = 100.0
        Height = 60.0
        SeamAllowance = 5.0
        GrainlineAngle = 90.0

    class Seam:
        """Persisted seam double used to verify export validation."""
        SeamId = "front-back"
        PieceA = "piece-front"
        PieceB = "piece-back"
        Status = "Valid"

    class Document:
        Objects = ()

    piece = _native_piece(Piece())
    piece.Document = Document()
    piece.Document.Objects = (piece, Seam())
    before = (piece.Label, piece.SeamAllowance, piece.GrainlineAngle, piece.Sketch.SemanticEdgeIds)

    for fmt, metadata_reader in (
        ("svg", from_svg_metadata),
        ("dxf", from_dxf_metadata),
        ("pdf", from_pdf_metadata),
    ):
        first = tmp_path / (f"front.{fmt}")
        second = tmp_path / (f"front-second.{fmt}")
        first_result = export_pattern_piece(piece, first, fmt, curve_samples=16)
        export_pattern_piece(piece, second, fmt, curve_samples=16)
        require(
            condition=(
                first.read_bytes() == second.read_bytes()
            ),
            message="Export contract failed: first.read_bytes() == second.read_bytes()",
        )
        require(
            condition=(
                first_result["valid"] is True
            ),
            message="Export contract failed: first_result[\"valid\"] is True",
        )
        metadata = (
            metadata_reader(first.read_bytes())
            if fmt == "pdf"
            else metadata_reader(first.read_text(encoding="utf-8"))
        )
        require(
            condition=(
                metadata["piece_id"] == "piece-front"
            ),
            message="Export contract failed: metadata[\"piece_id\"] == \"piece-front\"",
        )
        require(
            condition=(
                metadata["seam_ids"] == ["front-back"]
            ),
            message="Export contract failed: metadata[\"seam_ids\"] == [\"front-back\"]",
        )
        require(
            condition=(
                metadata["scale"] == 1.0
            ),
            message="Export contract failed: metadata[\"scale\"] == 1.0",
        )
        require(
            condition=(
                metadata["seam_allowance_mm"] == 5.0
            ),
            message="Export contract failed: metadata[\"seam_allowance_mm\"] == 5.0",
        )
        require(
            condition=(
                metadata["mark_ids"] == ["piece-front:grainline"]
            ),
            message="Export contract failed: metadata[\"mark_ids\"] == [\"piece-front:grainli",
        )

    require(
        condition=(
            before == (
            piece.Label,
            piece.SeamAllowance,
            piece.GrainlineAngle,
            piece.Sketch.SemanticEdgeIds,
            )
        ),
        message="Export contract failed: before == ( piece.Label, piece.SeamAllowance,",
    )


def test_pattern_piece_export_blocks_invalid_semantic_seams(tmp_path: Path) -> None:
    """Reject pattern-piece exports when persisted seams are not valid.

    Args:
        tmp_path: Temporary directory used for generated export artifacts.
    """
    class Piece:
        """Minimal FreeCAD pattern-piece double used by export tests."""
        PatternType = "PatternPiece"
        Name = "Front"
        Label = "Front"
        PieceId = "piece-front"
        Width = 100.0
        Height = 60.0
        SeamAllowance = 0.0
        GrainlineAngle = 0.0

    class Seam:
        """Persisted seam double used to verify export validation."""
        SeamId = "front-back"
        PieceA = "piece-front"
        PieceB = "piece-back"
        Status = "Changed reference"

    class Document:
        Objects = ()

    piece = _native_piece(Piece())
    piece.Document = Document()
    piece.Document.Objects = (piece, Seam())
    with pytest.raises(ValueError, match="cannot export pattern piece"):
        export_pattern_piece(piece, tmp_path / "invalid.svg", "svg")


def test_export_boundary_is_closed_and_continuous() -> None:
    """Verify SVG and DXF export a closed, continuous boundary."""
    pattern = _curved_pattern()
    svg = to_svg(pattern, curve_samples=24)
    require(
        condition=(
            '<path d="' in svg
        ),
        message="Export contract failed: '<path d=\"' in svg",
    )
    require(
        condition=(
            ' Z"' in svg
        ),
        message="Export contract failed: ' Z\"' in svg",
    )
    dxf = to_dxf(pattern, curve_samples=24)
    require(
        condition=(
            "\n70\n1\n" in dxf
        ),
        message="Export contract failed: \"\\n70\\n1\\n\" in dxf",
    )


def test_export_rejects_disconnected_boundary_segments() -> None:
    """Reject authored geometry whose segments do not form a closed boundary."""
    with pytest.raises(ValueError, match="boundary is not closed"):
        ParametricPattern(
            [
                LineSegment("a", (0.0, 0.0), (10.0, 0.0)),
                LineSegment("b", (10.0, 0.0), (10.0, 10.0)),
                LineSegment("c", (10.0, 10.0), (0.0, 10.0)),
                LineSegment("d", (0.0, 9.0), (0.0, 0.0)),
            ]
        )


def test_pattern_piece_export_uses_persisted_native_construction_marks(tmp_path: Path) -> None:
    """Verify exports use construction marks persisted on the native Sketcher piece.

    Args:
        tmp_path: Temporary directory used for generated export artifacts.
    """
    class Piece:
        """Minimal FreeCAD pattern-piece double used by export tests."""
        PatternType = "PatternPiece"
        Name = "Front"
        Label = "Front"
        PieceId = "piece-front"
        Width = 100.0
        Height = 60.0
        SeamAllowance = 5.0
        GrainlineAngle = 0.0

    class Mark:
        """Persisted construction-mark double consumed by native-piece export."""

        def __init__(self, name: str, mark_type: str, text: str = "", length: float = 40.0) -> None:
            """Store the fields read by the export adapter.

            Args:
                name: Stable document object name and persisted mark identifier.
                mark_type: Mark category, such as a notch or grainline.
                text: Optional visible label for the mark.
                length: Authored construction-mark length in millimetres.
            """
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

    piece = _native_piece(Piece())
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
            require(
                condition=(
                    metadata["piece_id"] == "piece-front"
                ),
                message="Export contract failed: metadata[\"piece_id\"] == \"piece-front\"",
            )
            require(
                condition=(
                    metadata["notch_ids"] == ["notch-front"]
                ),
                message="Export contract failed: metadata[\"notch_ids\"] == [\"notch-front\"]",
            )
            require(
                condition=(
                    metadata["mark_ids"] == ["grain-front", "mark-front"]
                ),
                message="Export contract failed: metadata[\"mark_ids\"] == [\"grain-front\", \"mark",
            )
            require(
                condition=(
                    b"25 mm CALIBRATION SQUARE" in raw_payload
                ),
                message="Export contract failed: b\"25 mm CALIBRATION SQUARE\" in raw_payload",
            )
            continue
        payload = raw_payload.decode("utf-8")
        metadata = reader(payload)
        require(
            condition=(
                metadata["piece_id"] == "piece-front"
            ),
            message="Export contract failed: metadata[\"piece_id\"] == \"piece-front\"",
        )
        require(
            condition=(
                metadata["notch_ids"] == ["notch-front"]
            ),
            message="Export contract failed: metadata[\"notch_ids\"] == [\"notch-front\"]",
        )
        require(
            condition=(
                metadata["mark_ids"] == ["grain-front", "mark-front"]
            ),
            message="Export contract failed: metadata[\"mark_ids\"] == [\"grain-front\", \"mark",
        )

        if fmt == "svg":
            require(
                condition=(
                    'data-notch-ids="notch-front"' in payload
                ),
                message="Export contract failed: 'data-notch-ids=\"notch-front\"' in payload",
            )
            require(
                condition=(
                    'id="mark-grain-front"' in payload
                ),
                message="Export contract failed: 'id=\"mark-grain-front\"' in payload",
            )
            require(
                condition=(
                    'id="mark-mark-front"' in payload
                ),
                message="Export contract failed: 'id=\"mark-mark-front\"' in payload",
            )
            require(
                condition=(
                    "55.000000,67.000000" in payload
                ),
                message="Export contract failed: \"55.000000,67.000000\" in payload",
            )
            require(
                condition=(
                    'cx="55.000000" cy="65.000000"' not in payload
                ),
                message="Export contract failed: 'cx=\"55.000000\" cy=\"65.000000\"' not in payloa",
            )
            require(
                condition=(
                    'x1="35.000000" y1="65.000000" x2="75.000000" y2="65.000000"' in payload
                ),
                message="Export contract failed: 'x1=\"35.000000\" y1=\"65.000000\" x2=\"75.000000\"",
            )
        else:
            require(
                condition=(
                    '"notch_ids":["notch-front"]' in payload
                ),
                message="Export contract failed: '\"notch_ids\":[\"notch-front\"]' in payload",
            )
            require(
                condition=(
                    '"mark_ids":["grain-front","mark-front"]' in payload
                ),
                message="Export contract failed: '\"mark_ids\":[\"grain-front\",\"mark-front\"]' in ",
            )
            require(
                condition=(
                    "10\n50.000000\n20\n-2.000000" in payload
                ),
                message="Export contract failed: \"10\\n50.000000\\n20\\n-2.000000\" in payload",
            )
            require(
                condition=(
                    "10\n30.000000\n20\n0.000000\n10\n70.000000\n20\n0.000000" in payload
                ),
                message="Export contract failed: \"10\\n30.000000\\n20\\n0.000000\\n10\\n70.000000\\n",
            )


def test_pattern_piece_export_blocks_missing_persisted_mark_edge(tmp_path: Path) -> None:
    """Reject export when a persisted mark refers to an edge that does not exist.

    Args:
        tmp_path: Temporary directory used for generated export artifacts.
    """
    class Piece:
        """Minimal FreeCAD pattern-piece double used by export tests."""
        PatternType = "PatternPiece"
        Name = "Front"
        Label = "Front"
        PieceId = "piece-front"
        Width = 100.0
        Height = 60.0
        SeamAllowance = 0.0
        GrainlineAngle = 0.0

    class Mark:
        """Persisted construction-mark double consumed by the export adapter."""
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

    piece = _native_piece(Piece())
    mark = Mark()
    piece.Document = Document()
    piece.Document.Objects = (piece, mark)

    output = tmp_path / "blocked.svg"
    with pytest.raises(ValueError, match="references missing edge"):
        export_pattern_piece(piece, output, "svg")
    require(
        condition=(
            not output.exists()
        ),
        message="Export contract failed: not output.exists()",
    )
