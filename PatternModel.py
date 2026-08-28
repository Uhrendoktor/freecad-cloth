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

    def validate(self) -> None:
        if not self.name.strip():
            raise ValueError("pattern piece name must not be empty")
        if len(self.outline) < 3:
            raise ValueError("pattern piece outline needs at least three points")
        if self.seam_allowance < 0:
            raise ValueError("seam allowance cannot be negative")


@dataclass(frozen=True)
class Seam:
    """A named connection between two pattern pieces."""
    piece_a: str
    edge_a: int
    piece_b: str
    edge_b: int

    def validate(self) -> None:
        if self.piece_a == self.piece_b and self.edge_a == self.edge_b:
            raise ValueError("a seam cannot connect an edge to itself")
        if self.edge_a < 0 or self.edge_b < 0:
            raise ValueError("edge indices must be non-negative")
