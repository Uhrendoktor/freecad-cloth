"""Backward-compatible seam semantics adapter.

The authoritative seam record is :class:`PatternModel.Seam`.  Older callers
can keep importing ``SeamConstraint`` while new code should construct and
validate ``PatternModel.Seam`` directly.
"""
from dataclasses import dataclass

from PatternModel import Seam


@dataclass(frozen=True)
class SeamConstraint:
    """Legacy string-edge view mapped to the canonical seam contract."""
    id: str
    piece_a: str
    edge_a: str
    piece_b: str
    edge_b: str
    reversed_b: bool = False
    kind: str = "plain"

    def to_seam(self) -> Seam:
        def edge_index(value):
            text = str(value)
            return int(text.split(":")[-1]) if ":" in text else int(text)
        return Seam(self.piece_a, edge_index(self.edge_a), self.piece_b, edge_index(self.edge_b),
                    id=self.id, reversed_b=self.reversed_b, kind=self.kind)

    def validate(self, pieces: set[str], edges: dict[str, set[str]]) -> None:
        seam = self.to_seam()
        seam.validate()
        if self.piece_a not in pieces or self.piece_b not in pieces:
            raise ValueError("seam references unknown piece")
        if str(self.edge_a) not in edges.get(self.piece_a, set()) and self.edge_a not in edges.get(self.piece_a, set()):
            raise ValueError("seam references unknown edge")
        if str(self.edge_b) not in edges.get(self.piece_b, set()) and self.edge_b not in edges.get(self.piece_b, set()):
            raise ValueError("seam references unknown edge")


def validate_seam_graph(seams, pieces, edges):
    ids = [s.id for s in seams]
    if len(ids) != len(set(ids)):
        raise ValueError("seam IDs must be unique")
    for seam in seams:
        seam.validate(set(pieces), edges)
    return True
