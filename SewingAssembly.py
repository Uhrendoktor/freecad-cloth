"""FreeCAD-independent sewing-piece pairing and assembly metadata.

The assembly is a document-facing adapter around ``PatternModel.Seam`` and
``SeamGraph``.  Orientation/alignment are never copied into a second mutable
source of truth.
"""
from dataclasses import dataclass, field
from typing import Dict

from SeamGraph import SeamGraph, Transform3D


@dataclass(frozen=True)
class SewingPair:
    """User-facing compatibility view of one canonical seam."""
    seam_id: str
    stitch_group: str = ""
    alignment: str = ""

    @property
    def reversed_b(self):
        return False if self._seam is None else self._seam.reversed_b

    _seam: object = field(default=None, repr=False, compare=False)

    def validate(self, graph: SeamGraph) -> None:
        if not self.seam_id.strip():
            raise ValueError("seam id must not be empty")
        if self.seam_id not in graph.seams:
            raise ValueError(f"unknown seam id: {self.seam_id}")
        seam = graph.seams[self.seam_id].seam
        if self.stitch_group and self.stitch_group != (seam.stitch_group or seam.id):
            raise ValueError("pair stitch group disagrees with canonical seam metadata")
        if self.alignment and self.alignment != seam.alignment:
            raise ValueError("pair alignment disagrees with canonical seam metadata")


@dataclass
class SewingAssembly:
    """Validated collection of sewing pairs and deterministic piece transforms."""
    graph: SeamGraph
    pairs: Dict[str, SewingPair] = field(default_factory=dict)

    def add_pair(self, seam_id: str, stitch_group: str = "", alignment: str = "") -> SewingPair:
        if seam_id in self.pairs:
            raise ValueError(f"seam is already paired: {seam_id}")
        if seam_id not in self.graph.seams:
            raise ValueError(f"unknown seam id: {seam_id}")
        seam = self.graph.seams[seam_id].seam
        pair = SewingPair(seam_id, stitch_group, alignment, seam)
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
        return {"pairs": tuple((p.seam_id, p.stitch_group, p.alignment, p.reversed_b)
                                for _, p in sorted(self.pairs.items())),
                "assembly": self.graph.to_metadata()["assembly_transforms"]}


def pair_seam(graph: SeamGraph, seam_id: str, stitch_group: str = "", alignment: str = "") -> SewingPair:
    return SewingAssembly(graph).add_pair(seam_id, stitch_group, alignment)


def align_piece_to_seam(graph: SeamGraph, seam_id: str, transform: Transform3D) -> None:
    if seam_id not in graph.seams:
        raise ValueError(f"unknown seam id: {seam_id}")
    graph.set_transform(graph.seams[seam_id].seam.piece_b, transform)


def make_translation(x: float, y: float, z: float = 0.0) -> Transform3D:
    return Transform3D.translation(x, y, z)
