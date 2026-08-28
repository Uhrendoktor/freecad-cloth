"""FreeCAD-independent sewing-piece pairing and assembly metadata.

This module deliberately stores semantic seam pairing separately from solver
particle indices.  FreeCAD GUI objects can use it to persist a reproducible
piece arrangement while the existing SeamGraph remains the simulation source.
"""
from dataclasses import dataclass, field
from typing import Dict, Tuple

from SeamGraph import SeamGraph, SeamPair, Transform3D
from PatternModel import PatternPiece, Seam


@dataclass(frozen=True)
class SewingPair:
    """A user-facing seam pairing with an explicit assembly orientation."""
    seam_id: str
    stitch_group: str
    alignment: str = "endpoints"
    reversed_b: bool = False

    def validate(self, graph: SeamGraph) -> None:
        if not self.seam_id.strip():
            raise ValueError("seam id must not be empty")
        if self.seam_id not in graph.seams:
            raise ValueError(f"unknown seam id: {self.seam_id}")
        if not self.stitch_group.strip():
            raise ValueError("stitch group must not be empty")
        if self.alignment not in {"endpoints", "uniform"}:
            raise ValueError("alignment must be 'endpoints' or 'uniform'")
        seam = graph.seams[self.seam_id].seam
        if seam.reversed_b != self.reversed_b:
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
        pair = SewingPair(seam_id, stitch_group or self.graph.seams[seam_id].stitch_group, alignment, seam.reversed_b)
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
