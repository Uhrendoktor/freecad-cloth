"""Compatibility adapters for the canonical :mod:`PatternModel` seam.

``PatternModel.Seam`` is the authoritative semantic representation. This
module keeps the older ``SeamConstraint`` API available while delegating seam
identity, endpoints, ranges, and reversal to the canonical model.
"""

from PatternModel import Seam


class SeamConstraint:
    """Backward-compatible adapter around :class:`PatternModel.Seam`."""

    _KINDS = {"plain", "dart", "gather", "pleat", "hem", "fold", "closure"}

    def __init__(
        self,
        id: str,
        piece_a: str,
        edge_a,
        piece_b: str,
        edge_b,
        reversed_b: bool = False,
        kind: str = "plain",
    ) -> None:
        self._seam = Seam(
            piece_a=piece_a,
            edge_a=edge_a,
            piece_b=piece_b,
            edge_b=edge_b,
            id=id,
            reversed_b=bool(reversed_b),
        )
        self.kind = kind

    @property
    def seam(self) -> Seam:
        """Return the authoritative canonical seam object."""
        return self._seam

    @property
    def id(self):
        return self._seam.id

    @property
    def piece_a(self):
        return self._seam.piece_a

    @property
    def edge_a(self):
        return self._seam.edge_a

    @property
    def piece_b(self):
        return self._seam.piece_b

    @property
    def edge_b(self):
        return self._seam.edge_b

    @property
    def reversed_b(self):
        return self._seam.reversed_b

    def validate(self, pieces: set[str], edges: dict[str, set[str]]) -> None:
        """Validate the canonical seam against legacy piece/edge registries."""
        self._seam.validate()
        if not self.id or self.piece_a not in pieces or self.piece_b not in pieces:
            raise ValueError("seam references unknown piece")
        for piece_id, edge in ((self.piece_a, self.edge_a), (self.piece_b, self.edge_b)):
            legacy_edges = edges.get(piece_id, set())
            if edge not in legacy_edges and str(edge) not in legacy_edges:
                raise ValueError("seam references unknown edge")
        if self.kind not in self._KINDS:
            raise ValueError("unsupported seam construction kind")

    def to_seam(self) -> Seam:
        """Return the canonical seam for new code and persistence adapters."""
        return self._seam


def validate_seam_graph(seams, pieces, edges):
    """Validate legacy adapters without maintaining a second seam graph."""
    ids = [seam.id for seam in seams]
    if len(ids) != len(set(ids)):
        raise ValueError("seam IDs must be unique")
    for seam in seams:
        seam.validate(set(pieces), edges)
    return True
