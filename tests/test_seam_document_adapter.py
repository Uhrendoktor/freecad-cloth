# Copyright (C) 2026 FreeCAD Cloth contributors
"""Contract tests for semantic seam references against native Sketcher provenance."""

from types import SimpleNamespace

import pytest

from freecad_cloth.pattern.PatternObjects import _edge_records, _resolve_document_edge
from freecad_cloth.pattern.SeamReference import (
    ChangedEdgeReference,
    MissingEdgeReference,
    capture_edge_reference,
)


def _piece(
    points: tuple[tuple[float, float], ...] = (
        (0.0, 0.0),
        (10.0, 0.0),
        (10.0, 10.0),
        (0.0, 10.0),
    ),
) -> SimpleNamespace:
    """Build a piece with an injected native-record source for adapter tests.

    Args:
        points: Ordered local 2D coordinates for the test sketch boundary.

    Returns:
        A document-like object declaring native Sketcher authority.
    """
    return SimpleNamespace(
        PieceId="front",
        GeometryAuthority="Sketcher",
        Sketch=object(),
        NativePoints=points,
    )


def _native_records(piece: SimpleNamespace) -> list[dict[str, object]]:
    """Create semantic edge records with signatures tied to current geometry.

    Args:
        piece: Test piece exposing NativePoints and PieceId.

    Returns:
        Ordered edge records carrying stable IDs and native provenance.
    """
    points = piece.NativePoints
    records = []
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        provenance = ("PatternIR", "Sketcher", "line", (0.0, 1.0), (start, end))
        records.append(
            {
                "piece_id": piece.PieceId,
                "id": f"{piece.PieceId}:edge:{index}",
                "points": (start, end),
                "ordinal": index,
                "provenance": provenance,
            }
        )
    return records


def test_piece_without_sketcher_authority_fails_closed() -> None:
    """Reject cached outline data when the piece has no native Sketcher source."""
    piece = SimpleNamespace(
        PieceId="front",
        SewingOutline="[(0, 0), (10, 0), (10, 10)]",
    )
    with pytest.raises(MissingEdgeReference, match="no native Sketcher authority"):
        _edge_records(piece)


def test_semantic_edge_records_come_from_native_reader() -> None:
    """Expose semantic identifiers and provenance from the injected native reader."""
    piece = _piece()
    records = _edge_records(piece, native_edge_records_fn=_native_records)
    assert [record["id"] for record in records] == [
        "front:edge:0",
        "front:edge:1",
        "front:edge:2",
        "front:edge:3",
    ]
    assert records[0]["ordinal"] == 0
    assert records[0]["provenance"][1] == "Sketcher"


def test_document_resolution_accepts_current_signature() -> None:
    """Resolve a saved semantic ID when its current geometry and provenance match."""
    piece = _piece()
    record = _edge_records(piece, native_edge_records_fn=_native_records)[0]
    reference = capture_edge_reference(
        piece.PieceId,
        record["id"],
        record["points"],
        record["provenance"],
    )
    resolved = _resolve_document_edge(
        piece,
        reference.edge_id,
        reference.signature,
        native_edge_records_fn=_native_records,
    )
    assert resolved["id"] == reference.edge_id


def test_document_resolution_rejects_changed_geometry() -> None:
    """Reject an existing semantic ID when its geometry signature has changed."""
    piece = _piece()
    record = _edge_records(piece, native_edge_records_fn=_native_records)[0]
    reference = capture_edge_reference(
        piece.PieceId,
        record["id"],
        record["points"],
        record["provenance"],
    )
    changed = _piece(((0.0, 0.0), (12.0, 0.0), (10.0, 10.0), (0.0, 10.0)))
    with pytest.raises(ChangedEdgeReference):
        _resolve_document_edge(
            changed,
            reference.edge_id,
            reference.signature,
            native_edge_records_fn=_native_records,
        )


def test_document_resolution_rejects_missing_semantic_id() -> None:
    """Reject an edge ID that no longer exists in the native boundary."""
    piece = _piece()
    with pytest.raises(MissingEdgeReference):
        _resolve_document_edge(
            piece,
            "front:edge:99",
            "native-v1:deadbeef",
            native_edge_records_fn=_native_records,
        )
