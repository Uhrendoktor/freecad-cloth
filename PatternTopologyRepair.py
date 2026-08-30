"""Explicit repair/remap helpers for invalid Cloth semantic seam edges.

The repair path is deliberately fail-closed: a seam with a missing or changed
semantic edge reference is never retargeted automatically. A caller must
provide the intended current edge for each affected seam side. Changes are
applied transactionally by the FreeCAD-facing command layer.
"""

from SeamReference import (
    ChangedEdgeReference,
    MissingEdgeReference,
    capture_edge_reference,
    resolve_edge_reference,
)
from PatternObjects import _edge_records


class TopologyRepairError(ValueError):
    """Base error for an invalid topology repair request."""


class InvalidRepairTarget(TopologyRepairError):
    """The selected replacement edge cannot be resolved on the seam piece."""


def seam_reference_status(seam, side):
    """Return ``(valid, reason)`` for seam side ``A`` or ``B``."""
    side = str(side).upper()
    if side not in ("A", "B"):
        raise ValueError("seam side must be A or B")
    piece = getattr(seam, "PatternA" if side == "A" else "PatternB", None)
    edge_id = str(getattr(seam, "EdgeAId" if side == "A" else "EdgeBId", ""))
    signature = str(getattr(seam, "EdgeASignature" if side == "A" else "EdgeBSignature", ""))
    if piece is None or not edge_id or not signature:
        return False, "missing"
    reference = capture_edge_reference(str(piece.PieceId), edge_id, ((0.0, 0.0), (1.0, 0.0)))
    reference = type(reference)(reference.piece_id, reference.edge_id, signature)
    try:
        resolve_edge_reference(reference, _edge_records(piece))
    except MissingEdgeReference:
        return False, "missing"
    except ChangedEdgeReference:
        return False, "changed"
    return True, "valid"


def invalid_seam_sides(doc):
    """Return ``[(seam, side, reason), ...]`` for all invalid seam sides."""
    result = []
    for obj in getattr(doc, "Objects", ()):
        if getattr(obj, "SeamId", None) is None:
            continue
        for side in ("A", "B"):
            valid, reason = seam_reference_status(obj, side)
            if not valid:
                result.append((obj, side, reason))
    return result


def current_edge_candidates(seam, side):
    """Return current semantic edge records for one seam side's piece."""
    side = str(side).upper()
    if side not in ("A", "B"):
        raise ValueError("seam side must be A or B")
    piece = getattr(seam, "PatternA" if side == "A" else "PatternB", None)
    if piece is None:
        return []
    return list(_edge_records(piece))


def validate_repair_target(seam, side, edge_id):
    """Resolve an explicitly selected current edge and return its record."""
    side = str(side).upper()
    if side not in ("A", "B"):
        raise ValueError("seam side must be A or B")
    edge_id = str(edge_id)
    for record in current_edge_candidates(seam, side):
        if str(record.get("id")) == edge_id:
            return record
    raise InvalidRepairTarget(
        "edge %s is not a current semantic edge on seam side %s" % (edge_id, side)
    )


def build_repair_plan(repairs):
    """Validate and normalize a repair mapping before mutating any object.

    ``repairs`` is an iterable of ``(seam, side, edge_id)`` tuples. Duplicate
    seam-side entries are rejected so an operation cannot partially overwrite
    an earlier choice.
    """
    plan = []
    seen = set()
    for seam, side, edge_id in repairs:
        side = str(side).upper()
        key = (id(seam), side)
        if key in seen:
            raise TopologyRepairError("duplicate repair target for seam side %s" % side)
        seen.add(key)
        record = validate_repair_target(seam, side, edge_id)
        plan.append((seam, side, record))
    if not plan:
        raise TopologyRepairError("no topology repairs were selected")
    return plan


def apply_repair_plan(doc, repairs):
    """Apply an already validated repair plan in one FreeCAD undo transaction."""
    plan = build_repair_plan(repairs)
    doc.openTransaction("Repair Cloth pattern topology")
    try:
        for seam, side, record in plan:
            if side == "A":
                seam.EdgeAId = str(record["id"])
                seam.EdgeASignature = capture_edge_reference(
                    seam.PatternA.PieceId, record["id"], record["points"]
                ).signature
                seam.EdgeA = int(record["ordinal"])
            else:
                seam.EdgeBId = str(record["id"])
                seam.EdgeBSignature = capture_edge_reference(
                    seam.PatternB.PieceId, record["id"], record["points"]
                ).signature
                seam.EdgeB = int(record["ordinal"])
            if hasattr(seam, "touch"):
                seam.touch()
        doc.recompute()
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    return plan
