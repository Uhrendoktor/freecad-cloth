"""Shared, FreeCAD-independent pattern data model."""
from dataclasses import dataclass, field
from typing import List, Tuple

Point = Tuple[float, float]


@dataclass
class PatternPiece:
    """A planar sewing piece expressed in millimetres."""
    name: str
    outline: List[Point] = field(default_factory=list)
    seam_allowance: float = 0.0
    grainline_angle: float = 0.0
    id: str = ""
    metadata: dict = field(default_factory=dict)

    def validate(self) -> None:
        if not self.name.strip():
            raise ValueError("pattern piece name must not be empty")
        if not self.outline or len(self.outline) < 3:
            raise ValueError("pattern piece outline needs at least three points")
        if self.seam_allowance < 0:
            raise ValueError("seam allowance cannot be negative")
        if not self.id.strip():
            raise ValueError("pattern piece id must not be empty")


@dataclass(frozen=True)
class Seam:
    """The authoritative semantic sewing contract.

    Geometry, FreeCAD document objects, and solver constraints are adapters of
    this record.  ``alignment`` and ``stitch_group`` intentionally live here so
    presentation and simulation cannot silently maintain competing seam state.
    """
    piece_a: str
    edge_a: int
    piece_b: str
    edge_b: int
    id: str = ""
    start_a: float = 0.0
    end_a: float = 1.0
    start_b: float = 0.0
    end_b: float = 1.0
    reversed_b: bool = False
    alignment: str = "endpoints"
    stitch_group: str = ""
    kind: str = "plain"

    def validate(self) -> None:
        if not self.id.strip():
            raise ValueError("seam id must not be empty")
        if self.piece_a == self.piece_b and self.edge_a == self.edge_b:
            raise ValueError("a seam cannot connect an edge to itself")
        if self.edge_a < 0 or self.edge_b < 0:
            raise ValueError("edge indices must be non-negative")
        for value in (self.start_a, self.end_a, self.start_b, self.end_b):
            if not 0.0 <= value <= 1.0:
                raise ValueError("seam edge ranges must be normalized")
        if self.start_a >= self.end_a or self.start_b >= self.end_b:
            raise ValueError("seam ranges must have positive extent")
        if self.alignment not in {"endpoints", "uniform"}:
            raise ValueError("alignment must be 'endpoints' or 'uniform'")
        if self.kind not in {"plain", "dart", "gather", "pleat", "hem", "fold", "closure"}:
            raise ValueError("unsupported seam construction kind")
        if self.stitch_group and not self.stitch_group.strip():
            raise ValueError("stitch group must not be whitespace")
