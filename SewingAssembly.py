"""FreeCAD-independent sewing-piece pairing and assembly metadata.

``PatternModel.Seam`` is the semantic source of truth.  ``SewingPair`` is a
user-facing adapter that references that canonical seam and stores only
presentation-level pairing metadata.
"""
from dataclasses import dataclass, field
from typing import Dict

from SeamGraph import SeamGraph, Transform3D
from PatternModel import PatternPiece, Seam


class SewingPair:
    """Compatibility adapter for a canonical seam pairing.

    New callers pass a :class:`PatternModel.Seam`.  The legacy constructor
    accepting ``seam_id`` and ``reversed_b`` remains supported for callers that
    construct the adapter before attaching it to a graph; validation resolves
    the canonical seam from that graph.
    """

    def __init__(self, seam_or_id, stitch_group: str, alignment: str = "endpoints", reversed_b=None):
        if isinstance(seam_or_id, Seam):
            self._seam = seam_or_id
            self._seam_id = seam_or_id.id
            self._legacy_reversed = None
        else:
            self._seam = None
            self._seam_id = str(seam_or_id)
            self._legacy_reversed = reversed_b
        self.stitch_group = stitch_group
        self.alignment = alignment

    @property
    def seam_id(self):
        return self._seam_id

    @property
    def reversed_b(self):
        """Return canonical reversal when available; never fork seam state."""
        if self._seam is not None:
            return self._seam.reversed_b
        return self._legacy_reversed

    def bind(self, seam: Seam) -> None:
        """Bind a legacy adapter to its canonical seam exactly once."""
        if seam.id != self._seam_id:
            raise ValueError("canonical seam id disagrees with sewing pair")
        self._seam = seam
        self._legacy_reversed = None

    def validate(self, graph: SeamGraph) -> None:
        if not self.seam_id.strip():
            raise ValueError("seam id must not be empty")
        if self.seam_id not in graph.seams:
            raise ValueError(f"unknown seam id: {self.seam_id}")
        if not self.stitch_group.strip():
            raise ValueError("stitch group must not be empty")
        if self.alignment not in {"endpoints", "uniform"}:
            raise ValueError("alignment must be 'endpoints' or 'uniform'")
        canonical = graph.seams[self.seam_id].seam
        if self._seam is None:
            self.bind(canonical)
        elif self._seam is not canonical and self._seam != canonical:
            raise ValueError("pair references a different seam object")
        if self.reversed_b is not canonical.reversed_b:
            raise ValueError("pair orientation disagrees with seam metadata")


@dataclass
class SewingAssembly:
    """Validated collection of sewing pairs and deterministic piece transforms."""
    graph: SeamGraph
    pairs: Dict[str, SewingPair] = field(default_factory=dict)

    def add_pair(self, seam_id: str, stitch_group: str = "", alignment: str = "endpoints") -> SewingPair:
        if seam_id in self.pairs:
            raise ValueError(f"seam is already paired: {seam_id}")
        if seam_id not in self.graph.seams:
            raise ValueError(f"unknown seam id: {seam_id}")
        seam = self.graph.seams[seam_id].seam
        pair = SewingPair(seam, stitch_group or self.graph.seams[seam_id].stitch_group, alignment)
        pair.validate(self.graph)
        self.pairs[seam_id] = pair
        return pair

    def remove_pair(self, seam_id: str) -> None:
        if seam_id not in self.pairs:
            raise ValueError(f"unknown sewing pair: {seam_id}")
        del self.pairs[seam_id]

    def set_piece_transform(self, piece_id: str, transform: Transform3D) -> None:
        self.graph.set_transform(piece_id, transform)

    def validate(self) -> None:
        self.graph.validate()
        for pair in self.pairs.values():
            pair.validate(self.graph)

    def to_metadata(self) -> dict:
        self.validate()
        return {
            "pairs": tuple(
                (p.seam_id, p.stitch_group, p.alignment, p.reversed_b)
                for _, p in sorted(self.pairs.items())
            ),
            "assembly": self.graph.to_metadata()["assembly_transforms"],
        }


def pair_seam(graph: SeamGraph, seam_id: str, stitch_group: str = "", alignment: str = "endpoints") -> SewingPair:
    """Validate a seam and return its user-facing pairing metadata."""
    assembly = SewingAssembly(graph)
    return assembly.add_pair(seam_id, stitch_group, alignment)


def align_piece_to_seam(graph: SeamGraph, seam_id: str, transform: Transform3D) -> None:
    """Persist a caller-computed rigid placement for the second seam piece."""
    if seam_id not in graph.seams:
        raise ValueError(f"unknown seam id: {seam_id}")
    graph.set_transform(graph.seams[seam_id].seam.piece_b, transform)


def make_translation(x: float, y: float, z: float = 0.0) -> Transform3D:
    """Convenience constructor used by GUI commands and tests."""
    return Transform3D.translation(x, y, z)
