# Copyright (C) 2026 FreeCAD Cloth contributors
"""Explicit repair/remap helpers for invalid Cloth semantic seam edges."""

from collections.abc import Iterable, Sequence
from typing import Protocol, TypeVar, cast

from freecad_cloth.pattern.PatternObjects import _edge_records
from freecad_cloth.pattern.SeamReference import (
    ChangedEdgeReference,
    EdgeRecord,
    EdgeReference,
    MissingEdgeReference,
    capture_edge_reference,
    resolve_edge_reference,
)


class TopologyRepairError(ValueError):
    """Base error for an invalid topology repair request."""


class InvalidRepairTarget(TopologyRepairError):
    """The selected replacement edge cannot be resolved on the seam piece."""


class PatternPieceFeatureProtocol(Protocol):
    """Minimal native pattern-piece identity required by seam repair."""

    PieceId: str


class SeamFeatureProtocol(Protocol):
    """Native seam properties updated by an explicit topology repair."""

    PatternA: PatternPieceFeatureProtocol
    PatternB: PatternPieceFeatureProtocol
    EdgeAId: str
    EdgeASignature: str
    EdgeA: int
    EdgeBId: str
    EdgeBSignature: str
    EdgeB: int

    def touch(self) -> None: ...


class DocumentTransactionProtocol(Protocol):
    """FreeCAD document transaction surface used by the repair operation."""

    Objects: Sequence[object]

    def openTransaction(self, label: str) -> None: ...

    def recompute(self) -> None: ...

    def commitTransaction(self) -> None: ...

    def abortTransaction(self) -> None: ...


_RepairSeam = TypeVar("_RepairSeam")


def seam_reference_status(seam: object, side: str) -> tuple[bool, str]:
    """Check whether one stored seam side still resolves to its authored edge.

    Args:
        seam: Persistent seam feature holding source piece and edge-signature properties.
        side: Side selector, either A or B.

    Returns:
        Validity flag paired with one of valid, missing, or changed.

    Raises:
        ValueError: If the side selector is not A or B.
    """
    side = str(side).upper()
    if side not in ("A", "B"):
        msg = "seam side must be A or B"
        raise ValueError(msg)
    piece = getattr(seam, "PatternA" if side == "A" else "PatternB", None)
    edge_id = str(getattr(seam, "EdgeAId" if side == "A" else "EdgeBId", ""))
    signature = str(getattr(seam, "EdgeASignature" if side == "A" else "EdgeBSignature", ""))
    if piece is None or not edge_id or not signature:
        return False, "missing"
    try:
        reference = EdgeReference(str(piece.PieceId), edge_id, signature)
    except ValueError:
        return False, "changed"
    try:
        resolve_edge_reference(reference, _edge_records(piece))
    except MissingEdgeReference:
        return False, "missing"
    except ChangedEdgeReference:
        return False, "changed"
    return True, "valid"


def invalid_seam_sides(
    doc: object,
) -> list[tuple[SeamFeatureProtocol, str, str]]:
    """Collect every invalid semantic edge reference in one FreeCAD document.

    Args:
        doc: FreeCAD document whose seam features are inspected.

    Returns:
        Tuples containing each invalid seam feature, side selector, and failure reason.
    """
    result: list[tuple[SeamFeatureProtocol, str, str]] = []
    objects = cast(Sequence[object], getattr(doc, "Objects", ()))
    for obj in objects:
        if getattr(obj, "SeamId", None) is None:
            continue
        for side in ("A", "B"):
            valid, reason = seam_reference_status(obj, side)
            if not valid:
                # SeamId marks a native seam feature with the properties in this protocol.
                result.append((cast(SeamFeatureProtocol, obj), side, reason))
    return result


def current_edge_candidates(seam: object, side: str) -> list[EdgeRecord]:
    """Return current semantic edge records for one seam side's source piece.

    Args:
        seam: Persistent seam feature providing its linked PatternA/PatternB source.
        side: Side selector, either A or B.

    Returns:
        Current semantic edge records, or an empty list when the source piece is absent.

    Raises:
        ValueError: If the side selector is not A or B.
    """
    side = str(side).upper()
    if side not in ("A", "B"):
        msg = "seam side must be A or B"
        raise ValueError(msg)
    piece = getattr(seam, "PatternA" if side == "A" else "PatternB", None)
    if piece is None:
        return []
    return list(_edge_records(piece))


def validate_repair_target(seam: object, side: str, edge_id: str) -> EdgeRecord:
    """Resolve an explicitly selected current edge and return its record.

    Args:
        seam: Persistent seam feature whose source edge is being repaired.
        side: Side selector identifying PatternA or PatternB.
        edge_id: Stable semantic identity of the replacement edge selected by the user.

    Returns:
        Current edge record containing its identity, points, ordinal, and provenance.

    Raises:
        ValueError: If the side selector is not A or B.
        InvalidRepairTarget: If the requested semantic edge is not currently present.
    """
    side = str(side).upper()
    if side not in ("A", "B"):
        msg = "seam side must be A or B"
        raise ValueError(msg)
    edge_id = str(edge_id)
    for record in current_edge_candidates(seam, side):
        if str(record.get("id")) == edge_id:
            return record
    msg = f"edge {edge_id} is not a current semantic edge on seam side {side}"
    raise InvalidRepairTarget(msg)


def build_repair_plan(
    repairs: Iterable[tuple[_RepairSeam, str, str]],
) -> list[tuple[_RepairSeam, str, EdgeRecord]]:
    """Validate and normalize all requested repairs before mutating document objects.

    Args:
        repairs: Iterable of seam, side, and replacement-edge selections.

    Returns:
        Ordered repair plan containing validated current edge records.

    Raises:
        TopologyRepairError: If a repair target is repeated or no repairs were supplied.
        InvalidRepairTarget: If any requested edge is absent from its seam side.
    """
    plan: list[tuple[_RepairSeam, str, EdgeRecord]] = []
    seen: set[tuple[int, str]] = set()
    for seam, side, edge_id in repairs:
        side = str(side).upper()
        key = (id(seam), side)
        if key in seen:
            msg = f"duplicate repair target for seam side {side}"
            raise TopologyRepairError(msg)
        seen.add(key)
        record = validate_repair_target(seam, side, edge_id)
        plan.append((seam, side, record))
    if not plan:
        msg = "no topology repairs were selected"
        raise TopologyRepairError(msg)
    return plan


def apply_repair_plan(
    doc: object,
    repairs: Iterable[tuple[SeamFeatureProtocol, str, str]],
) -> list[tuple[SeamFeatureProtocol, str, EdgeRecord]]:
    """Apply validated semantic seam-edge repairs in one undoable transaction.

    Args:
        doc: FreeCAD document whose seam references and derived state are updated.
        repairs: Iterable of seam, side, and replacement-edge selections.

    Returns:
        Validated repair plan after the document has recomputed successfully.

    Raises:
        TopologyRepairError: If the repair selections are empty or contain duplicates.
        InvalidRepairTarget: If a selected replacement edge cannot be resolved.
    """
    plan = build_repair_plan(repairs)
    document = cast(DocumentTransactionProtocol, doc)
    document.openTransaction("Repair Cloth pattern topology")
    try:
        for seam, side, record in plan:
            if side == "A":
                seam.EdgeAId = str(record["id"])
                seam.EdgeASignature = capture_edge_reference(
                    seam.PatternA.PieceId, record["id"], record["points"], record["provenance"]
                ).signature
                seam.EdgeA = int(record["ordinal"])
            else:
                seam.EdgeBId = str(record["id"])
                seam.EdgeBSignature = capture_edge_reference(
                    seam.PatternB.PieceId, record["id"], record["points"], record["provenance"]
                ).signature
                seam.EdgeB = int(record["ordinal"])
            if hasattr(seam, "touch"):
                seam.touch()
        document.recompute()
        document.commitTransaction()
    except Exception:
        document.abortTransaction()
        raise
    return plan
