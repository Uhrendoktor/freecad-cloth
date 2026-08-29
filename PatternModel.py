"""Shared, FreeCAD-independent pattern data model."""
from dataclasses import dataclass, field
from typing import List, Tuple, Union

Point = Tuple[float, float]
EdgeRef = Union[int, str]


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
    """A named connection between two pattern pieces.

    Edge references may be integer outline indices or stable semantic edge
    identifiers supplied by an adapter.  Native mesh consumers should resolve
    semantic identifiers to their concrete outline/mesh edge before sampling.
    """
    piece_a: str
    edge_a: EdgeRef
    piece_b: str
    edge_b: EdgeRef
    id: str = ""
    start_a: float = 0.0
    end_a: float = 1.0
    start_b: float = 0.0
    end_b: float = 1.0
    reversed_b: bool = False

    def validate(self) -> None:
        if not self.id.strip():
            raise ValueError("seam id must not be empty")
        if self.piece_a == self.piece_b and self.edge_a == self.edge_b:
            raise ValueError("a seam cannot connect an edge to itself")
        for edge in (self.edge_a, self.edge_b):
            if not isinstance(edge, (int, str)) or isinstance(edge, bool):
                raise ValueError("seam edge references must be integer indices or stable identifiers")
            if isinstance(edge, int) and edge < 0:
                raise ValueError("edge indices must be non-negative")
            if isinstance(edge, str) and not edge.strip():
                raise ValueError("edge identifiers must not be empty")
        for value in (self.start_a, self.end_a, self.start_b, self.end_b):
            if not 0.0 <= value <= 1.0:
                raise ValueError("seam edge ranges must be normalized")
        if self.start_a >= self.end_a or self.start_b >= self.end_b:
            raise ValueError("seam ranges must have positive extent")
