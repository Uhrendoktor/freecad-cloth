import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from PatternGeometry import LineSegment, ParametricPattern, QuadraticBezier, rectangle
from PatternIR import PatternIR
from PatternModel import PatternPiece, Seam
from SeamGraph import SeamGraph


def _graph():
    graph = SeamGraph()
    graph.add_piece(PatternPiece("front", [(0, 0), (20, 0), (20, 20), (0, 20)], id="front"))
    graph.add_piece(PatternPiece("back", [(0, 0), (20, 0), (20, 20), (0, 20)], id="back"))
    graph.add_seam(Seam("front", 1, "back", "edge:3", id="side", reversed_b=True, alignment="uniform"))
    return graph


def test_integer_and_string_edges_become_semantic_ids():
    ir = PatternIR.from_graph(_graph())
    seam = ir.seams[0]
    assert seam.edge_a == "edge:1"
    assert seam.edge_b == "edge:3"
    assert seam.reversed_b is True
    assert seam.alignment == "uniform"
    ir.validate()


def test_richer_curve_geometry_survives_in_the_ir():
    graph = SeamGraph()
    graph.add_piece(PatternPiece("front", [(0, 0), (10, 0), (0, 10)], id="front"))
    graph.add_piece(PatternPiece("back", [(0, 0), (10, 0), (0, 10)], id="back"))
    graph.add_seam(Seam("front", "curve", "back", "line", id="curve-seam"))
    geometry = {
        "front": ParametricPattern([
            QuadraticBezier("curve", (0, 0), (5, 8), (10, 0)),
            LineSegment("line-a", (10, 0), (0, 10)),
            LineSegment("line-b", (0, 10), (0, 0)),
        ]),
        "back": rectangle(10, 10),
    }
    ir = PatternIR.from_graph(graph, geometry, curve_samples=9)
    boundary = ir.boundary("front", "curve")
    assert boundary.kind == "curve"
    assert boundary.curve_type == "quadratic_bezier"
    assert boundary.control_points == (
        (0.0, 0.0, 0.0),
        (5.0, 8.0, 0.0),
        (10.0, 0.0, 0.0),
    )
    assert len(boundary.samples) == 9
    assert boundary.samples[0] == (0.0, 0.0, 0.0)
    assert boundary.samples[-1] == (10.0, 0.0, 0.0)
    assert boundary.length > 10.0


def test_line_geometry_retains_exact_endpoints_as_provenance():
    ir = PatternIR.from_graph(_graph())
    boundary = ir.boundary("front", "edge:0")
    assert boundary.kind == "line"
    assert boundary.curve_type == "line"
    assert boundary.control_points == boundary.samples


def test_unresolvable_string_reference_fails_closed():
    graph = SeamGraph()
    graph.add_piece(PatternPiece("front", [(0, 0), (10, 0), (0, 10)], id="front"))
    graph.add_piece(PatternPiece("back", [(0, 0), (10, 0), (0, 10)], id="back"))
    with pytest.raises(ValueError, match="unknown pattern piece|outside"):
        graph.add_seam(Seam("front", "missing", "back", 0, id="bad"))
