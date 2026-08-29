"""Deterministic M:N and free-sewing relationships.

A sewing network is represented as a set of ordinary canonical ``Seam``
records sharing one relationship id. Member ranges may cover arbitrary
sub-ranges of an edge, so the same machinery handles free sewing and 1:1,
1:N, M:1, and M:N relationships.
"""
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

from PatternModel import Seam


@dataclass(frozen=True)
class SewingMember:
    """One directed segment participating in a sewing relationship."""

    piece_id: str
    edge: int
    start: float = 0.0
    end: float = 1.0

    def validate(self) -> None:
        if not str(self.piece_id).strip():
            raise ValueError("sewing member piece id must not be empty")
        if isinstance(self.edge, bool) or not isinstance(self.edge, int) or self.edge < 0:
            raise ValueError("sewing member edge must be a non-negative integer")
        if not 0.0 <= float(self.start) < float(self.end) <= 1.0:
            raise ValueError("sewing member range must be normalized with positive extent")


def _member_length(member: SewingMember, edge_lengths) -> float:
    """Resolve a member's physical edge length from a mapping or callback."""
    if callable(edge_lengths):
        length = edge_lengths(member.piece_id, member.edge)
    else:
        length = edge_lengths[(member.piece_id, member.edge)]
    length = float(length)
    if length <= 0.0:
        raise ValueError("sewing member edge length must be positive")
    return length * (float(member.end) - float(member.start))


def _breakpoints(lengths: Sequence[float]) -> List[float]:
    total = sum(lengths)
    if total <= 0.0:
        raise ValueError("sewing relationship has zero total length")
    points = [0.0]
    for length in lengths:
        points.append(points[-1] + float(length) / total)
    points[-1] = 1.0
    return points


def build_mn_seams(
    relationship_id: str,
    side_a: Iterable[SewingMember],
    side_b: Iterable[SewingMember],
    edge_lengths,
    *,
    reversed_b: bool = False,
    alignment: str = "uniform",
    kind: str = "plain",
) -> Tuple[Seam, ...]:
    """Expand an M:N relationship into deterministic canonical seam segments.

    Members are ordered as supplied. Their physical lengths define cumulative
    normalized ranges. Overlapping ranges become canonical seams, so one member
    can deterministically connect to multiple members without a second seam
    representation. ``edge_lengths`` is either ``{(piece, edge): length}`` or a
    callable returning a length in millimetres.
    """
    relationship_id = str(relationship_id).strip()
    if not relationship_id:
        raise ValueError("relationship id must not be empty")
    if alignment not in {"endpoints", "uniform"}:
        raise ValueError("alignment must be 'endpoints' or 'uniform'")
    a = tuple(side_a)
    b = tuple(side_b)
    if not a or not b:
        raise ValueError("an M:N sewing relationship needs members on both sides")
    for member in a + b:
        member.validate()
    if len({m.piece_id for m in a}) != 1 or len({m.piece_id for m in b}) != 1:
        raise ValueError("each sewing side must belong to exactly one pattern piece")

    a_lengths = tuple(_member_length(m, edge_lengths) for m in a)
    b_lengths = tuple(_member_length(m, edge_lengths) for m in b)
    a_breaks = _breakpoints(a_lengths)
    b_breaks = _breakpoints(b_lengths)

    seams = []
    i = j = 0
    while i < len(a) and j < len(b):
        lo = max(a_breaks[i], b_breaks[j])
        hi = min(a_breaks[i + 1], b_breaks[j + 1])
        if hi > lo + 1e-12:
            a_span = a_breaks[i + 1] - a_breaks[i]
            b_span = b_breaks[j + 1] - b_breaks[j]
            a_start = float(a[i].start) + (float(a[i].end) - float(a[i].start)) * (lo - a_breaks[i]) / a_span
            a_end = float(a[i].start) + (float(a[i].end) - float(a[i].start)) * (hi - a_breaks[i]) / a_span
            b_start = float(b[j].start) + (float(b[j].end) - float(b[j].start)) * (lo - b_breaks[j]) / b_span
            b_end = float(b[j].start) + (float(b[j].end) - float(b[j].start)) * (hi - b_breaks[j]) / b_span
            seams.append(Seam(
                piece_a=a[i].piece_id,
                edge_a=a[i].edge,
                piece_b=b[j].piece_id,
                edge_b=b[j].edge,
                id=f"{relationship_id}-{i + 1}-{j + 1}",
                start_a=a_start,
                end_a=a_end,
                start_b=b_start,
                end_b=b_end,
                reversed_b=bool(reversed_b),
                alignment=alignment,
                stitch_group=relationship_id,
                kind=kind,
            ))
        if a_breaks[i + 1] < b_breaks[j + 1] - 1e-12:
            i += 1
        elif b_breaks[j + 1] < a_breaks[i + 1] - 1e-12:
            j += 1
        else:
            i += 1
            j += 1

    if not seams:
        raise ValueError("sewing relationship produced no overlapping segments")
    for seam in seams:
        seam.validate()
    return tuple(seams)


def member_lengths_from_pattern(pieces, members: Iterable[SewingMember]):
    """Build an edge-length mapping from FreeCAD pattern objects."""
    from SewingObjects import _edge_length

    result = {}
    for member in members:
        piece = pieces.get(member.piece_id)
        if piece is None:
            raise ValueError(f"unknown pattern piece: {member.piece_id}")
        result[(member.piece_id, member.edge)] = _edge_length(piece, member.edge)
    return result


def _network_lengths(seams):
    """Resolve physical lengths for persisted seam document objects."""
    from SewingObjects import _seam_length

    total_a = total_b = 0.0
    pieces = {}
    for seam in seams:
        document = getattr(seam, "Document", None)
        if document is not None:
            pieces.update({
                str(getattr(piece, "PieceId", "")): piece
                for piece in getattr(document, "Objects", ())
                if getattr(piece, "PatternType", "") == "PatternPiece"
            })
        piece_a = pieces.get(str(getattr(seam, "PieceA", "")))
        piece_b = pieces.get(str(getattr(seam, "PieceB", "")))
        if piece_a is None or piece_b is None:
            raise ValueError("sewing network references missing pattern pieces")
        total_a += _seam_length(piece_a, seam, "A")
        total_b += _seam_length(piece_b, seam, "B")
    return total_a, total_b


class SewingNetworkProxy:
    """Recomputable validation summary for a persisted M:N relationship."""

    Type = "ClothSewingNetwork"

    def execute(self, obj):
        seams = tuple(getattr(obj, "Seams", ()) or ())
        if not seams:
            obj.Status = "Incomplete"
            obj.SegmentCount = 0
            obj.LengthA = obj.LengthB = obj.LengthDifference = 0.0
            return
        ids = [str(getattr(seam, "SeamId", "")) for seam in seams]
        if any(not sid for sid in ids) or len(ids) != len(set(ids)):
            raise ValueError("sewing network contains invalid or duplicate seams")
        relationship_id = str(getattr(obj, "RelationshipId", "")).strip()
        groups = {str(getattr(seam, "StitchGroup", "")) for seam in seams}
        if not relationship_id or groups != {relationship_id}:
            raise ValueError("sewing network seams must share the relationship id")
        total_a, total_b = _network_lengths(seams)
        obj.SegmentCount = len(seams)
        obj.LengthA = total_a
        obj.LengthB = total_b
        obj.LengthDifference = abs(total_a - total_b)
        tolerance = max(0.0, float(getattr(obj, "Tolerance", 0.5)))
        obj.Status = "Valid" if obj.LengthDifference <= tolerance else "Length mismatch"


def add_sewing_network(doc, seams, relationship_id, name="SewingNetwork"):
    """Persist an M:N relationship as one editable FreeCAD network object."""
    seams = tuple(seams)
    relationship_id = str(relationship_id).strip()
    if not seams or not relationship_id:
        raise ValueError("a sewing network needs seams and a relationship id")
    groups = {str(getattr(seam, "StitchGroup", "")) for seam in seams}
    if groups != {relationship_id}:
        raise ValueError("all seams must use the network relationship id")
    obj = doc.addObject("App::FeaturePython", name)
    obj.Label = relationship_id
    obj.addProperty("App::PropertyString", "SewingType", "Sewing").SewingType = "SewingNetwork"
    obj.addProperty("App::PropertyString", "RelationshipId", "Sewing").RelationshipId = relationship_id
    obj.addProperty("App::PropertyLinkList", "Seams", "Sewing").Seams = list(seams)
    obj.addProperty("App::PropertyInteger", "SideACount", "Sewing").SideACount = len({(s.PieceA, s.EdgeA) for s in seams})
    obj.addProperty("App::PropertyInteger", "SideBCount", "Sewing").SideBCount = len({(s.PieceB, s.EdgeB) for s in seams})
    obj.addProperty("App::PropertyInteger", "SegmentCount", "Sewing").SegmentCount = len(seams)
    obj.addProperty("App::PropertyLength", "Tolerance", "Validation").Tolerance = 0.5
    obj.addProperty("App::PropertyLength", "LengthA", "Validation").LengthA = 0.0
    obj.addProperty("App::PropertyLength", "LengthB", "Validation").LengthB = 0.0
    obj.addProperty("App::PropertyLength", "LengthDifference", "Validation").LengthDifference = 0.0
    obj.addProperty("App::PropertyString", "Status", "Validation").Status = "Incomplete"
    obj.Proxy = SewingNetworkProxy()
    obj.Proxy.execute(obj)
    return obj
