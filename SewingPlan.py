"""FreeCAD-independent validation and topology helpers for sewing plans.

The workbench-facing objects store seams as references to stable pattern-piece
IDs.  This module keeps cross-object validation and topology analysis out of
FreeCAD so it can be reused by GUI and simulation code and tested headlessly.
"""
from collections import defaultdict, deque


def validate_sewing_plan(pieces, seams):
    """Validate seam references against pattern pieces and return a report.

    ``pieces`` may contain PatternPiece instances or any objects exposing an
    ``id`` and ``outline``. ``seams`` may contain Seam instances or equivalent
    objects. A ValueError identifies the first invalid reference.
    """
    piece_map = {}
    for piece in pieces:
        piece_id = str(getattr(piece, "id", "")).strip()
        if not piece_id:
            raise ValueError("pattern piece id must not be empty")
        if piece_id in piece_map:
            raise ValueError(f"duplicate pattern piece id: {piece_id}")
        outline = getattr(piece, "outline", ())
        if len(outline) < 2:
            raise ValueError(f"pattern piece {piece_id} has no usable edges")
        piece_map[piece_id] = piece

    seam_ids = set()
    for seam in seams:
        seam_id = str(getattr(seam, "id", "")).strip()
        if not seam_id:
            raise ValueError("seam id must not be empty")
        if seam_id in seam_ids:
            raise ValueError(f"duplicate seam id: {seam_id}")
        seam_ids.add(seam_id)
        piece_a = str(getattr(seam, "piece_a", ""))
        piece_b = str(getattr(seam, "piece_b", ""))
        if piece_a not in piece_map:
            raise ValueError(f"seam {seam_id} references unknown piece: {piece_a}")
        if piece_b not in piece_map:
            raise ValueError(f"seam {seam_id} references unknown piece: {piece_b}")
        _validate_edge(seam_id, piece_a, getattr(seam, "edge_a", -1), piece_map[piece_a])
        _validate_edge(seam_id, piece_b, getattr(seam, "edge_b", -1), piece_map[piece_b])
        for side in ("a", "b"):
            start = float(getattr(seam, f"start_{side}"))
            end = float(getattr(seam, f"end_{side}"))
            if not 0.0 <= start < end <= 1.0:
                raise ValueError(f"seam {seam_id} has invalid {side} edge range")

    return {"piece_count": len(piece_map), "seam_count": len(seam_ids)}


def _validate_edge(seam_id, piece_id, edge, piece):
    try:
        edge = int(edge)
    except (TypeError, ValueError):
        raise ValueError(f"seam {seam_id} has invalid edge on {piece_id}")
    # A closed polygon with N vertices has N edges. For an explicit repeated
    # closing point, the final duplicate does not introduce another edge.
    count = len(getattr(piece, "outline", ()))
    if count > 1 and getattr(piece, "outline", ())[0] == getattr(piece, "outline", ())[-1]:
        count -= 1
    if edge < 0 or edge >= count:
        raise ValueError(f"seam {seam_id} edge {edge} is out of range for {piece_id}")


def connected_components(pieces, seams):
    """Return connected pattern-piece groups induced by the seam graph.

    Each group is a tuple of piece IDs in deterministic insertion order.
    Unsewn pieces are returned as singleton groups.
    """
    ids = [str(getattr(piece, "id", "")) for piece in pieces]
    graph = defaultdict(set)
    for piece_id in ids:
        graph[piece_id]
    for seam in seams:
        a = str(getattr(seam, "piece_a", ""))
        b = str(getattr(seam, "piece_b", ""))
        if a in graph and b in graph:
            graph[a].add(b)
            graph[b].add(a)

    seen = set()
    groups = []
    for root in ids:
        if root in seen:
            continue
        group = []
        queue = deque([root])
        seen.add(root)
        while queue:
            current = queue.popleft()
            group.append(current)
            for neighbor in sorted(graph[current]):
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        groups.append(tuple(group))
    return tuple(groups)
