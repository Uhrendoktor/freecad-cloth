"""Solver-independent sewing construction semantics and validation."""
from dataclasses import dataclass

@dataclass(frozen=True)
class SeamConstraint:
    id: str
    piece_a: str
    edge_a: str
    piece_b: str
    edge_b: str
    reversed_b: bool = False
    kind: str = "plain"

    def validate(self, pieces: set[str], edges: dict[str, set[str]]) -> None:
        if not self.id or self.piece_a not in pieces or self.piece_b not in pieces:
            raise ValueError("seam references unknown piece")
        if self.edge_a not in edges.get(self.piece_a, set()) or self.edge_b not in edges.get(self.piece_b, set()):
            raise ValueError("seam references unknown edge")
        if self.piece_a == self.piece_b and self.edge_a == self.edge_b:
            raise ValueError("seam cannot connect an edge to itself")
        if self.kind not in {"plain", "dart", "gather", "pleat", "hem", "fold", "closure"}:
            raise ValueError("unsupported seam construction kind")

def validate_seam_graph(seams, pieces, edges):
    ids = [s.id for s in seams]
    if len(ids) != len(set(ids)):
        raise ValueError("seam IDs must be unique")
    for seam in seams:
        seam.validate(set(pieces), edges)
    return True
