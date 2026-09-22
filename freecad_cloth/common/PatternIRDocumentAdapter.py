"""Compile native FreeCAD pattern/seam objects into derived PatternIR runtime data.

FreeCAD document objects remain the persistence authority. This module only
builds an immutable, solver-neutral runtime snapshot for one simulation build.
"""
from __future__ import annotations

from freecad_cloth.common.SketchAuthority import _piece_model, _resolve_sketch_ir
from freecad_cloth.pattern.PatternIR import PatternIR, SeamIR
from freecad_cloth.sewing.SeamGraph import SeamGraph


def compile_pattern_ir(doc, pieces, curve_samples=64):
    """Compile selected document pattern pieces and seams into validated PatternIR."""
    if doc is None:
        raise ValueError("simulation pattern compilation requires a FreeCAD document")

    pieces = tuple(pieces or ())
    if not pieces:
        raise ValueError("simulation pattern compilation requires at least one PatternPiece")

    piece_models = {}
    piece_irs = []
    for obj in pieces:
        piece = _piece_model(obj)
        if piece.id in piece_models:
            raise ValueError(f"duplicate pattern piece ID in simulation: {piece.id}")
        piece_models[piece.id] = obj

        if str(getattr(obj, "GeometryAuthority", "")) == "Sketcher":
            sketch = getattr(obj, "Sketch", None)
            if sketch is None:
                raise ValueError(
                    f"Sketcher-authoritative pattern piece has no native sketch: {piece.id}"
                )
            piece_ir = _resolve_sketch_ir(obj)
        else:
            graph = SeamGraph()
            graph.add_piece(piece)
            piece_ir = PatternIR.from_graph(graph, curve_samples=curve_samples).piece(piece.id)

        piece_irs.append(piece_ir)

    piece_map = {piece.id: piece_ir for piece_ir in piece_irs}
    seams = []
    selected_ids = set(piece_map)

    for seam in getattr(doc, "Objects", ()):
        seam_id = str(getattr(seam, "SeamId", "")).strip()
        if not seam_id:
            continue

        piece_a = _seam_piece_id(seam, "A")
        piece_b = _seam_piece_id(seam, "B")
        selected_a = piece_a in selected_ids
        selected_b = piece_b in selected_ids
        if not selected_a or not selected_b:
            continue

        status = str(getattr(seam, "Status", "Valid"))
        if status != "Valid":
            raise ValueError(f"simulation seam is invalid: {seam_id}: {status}")

        edge_a = _semantic_edge_id(seam, "A", piece_map[piece_a], seam_id)
        edge_b = _semantic_edge_id(seam, "B", piece_map[piece_b], seam_id)
        seams.append(
            SeamIR(
                id=seam_id,
                piece_a=piece_a,
                edge_a=edge_a,
                piece_b=piece_b,
                edge_b=edge_b,
                start_a=float(getattr(seam, "StartA", 0.0)),
                end_a=float(getattr(seam, "EndA", 1.0)),
                start_b=float(getattr(seam, "StartB", 0.0)),
                end_b=float(getattr(seam, "EndB", 1.0)),
                reversed_b=bool(getattr(seam, "ReversedB", False)),
                alignment=str(getattr(seam, "Alignment", "endpoints")),
                stitch_group=str(
                    getattr(seam, "StitchGroup", "") or seam_id
                ),
                kind=str(getattr(seam, "Kind", "plain")),
            )
        )

    result = PatternIR(tuple(piece_irs), tuple(seams))
    result.validate()
    return result


def _seam_piece_id(seam, prefix):
    # Canonical validation branch: this remains derived runtime data only.
    """Use the native PatternA/PatternB document link as seam identity.
    
    PieceA/PieceB remain a compatibility mirror for older documents. This
    keeps the simulation boundary aligned with the document object's actual
    dependency graph and therefore preserves native invalidation semantics.
    """
    linked = getattr(seam, f"Pattern{prefix}", None)
    linked_id = str(getattr(linked, "PieceId", "")).strip() if linked is not None else ""
    if linked_id:
        return linked_id
    return str(getattr(seam, f"Piece{prefix}", "")).strip()



def _semantic_edge_id(seam, prefix, piece_ir, seam_id):
    id_property = f"Edge{prefix}Id"
    index_property = f"Edge{prefix}"
    edge_id = str(getattr(seam, id_property, "")).strip()
    if not edge_id:
        try:
            edge_index = int(getattr(seam, index_property))
        except (TypeError, ValueError):
            raise ValueError(
                f"simulation seam has no resolvable {prefix} edge: {seam_id}"
            ) from None
        boundaries = piece_ir.boundaries
        if edge_index < 0 or edge_index >= len(boundaries):
            raise ValueError(
                f"simulation seam {seam_id} references missing {prefix} edge {edge_index}"
            )
        edge_id = boundaries[edge_index].id

    valid_ids = {boundary.id for boundary in piece_ir.boundaries}
    if edge_id not in valid_ids:
        raise ValueError(
            f"simulation seam {seam_id} references missing {prefix} semantic edge {edge_id}"
        )
    return edge_id
