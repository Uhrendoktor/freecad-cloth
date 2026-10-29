# Copyright (C) 2026 FreeCAD Cloth contributors
"""Shared, FreeCAD-independent pattern value model.

These dataclasses are canonical in-memory/headless representations. Persisted
FreeCAD document objects remain the persistence authority and round-trip these
values rather than being replaced by a second database/model.
"""

from dataclasses import field

from pydantic.dataclasses import dataclass as pydantic_dataclass

from freecad_cloth.common.ValidationModels import NormalizedRange, PatternPieceInput

Point = tuple[float, float]
EdgeRef = int | str


def _empty_points() -> list[Point]:
    """Create an explicitly typed empty point list."""
    return []


def _empty_metadata() -> dict[str, object]:
    """Create an explicitly typed empty metadata mapping."""
    return {}


@pydantic_dataclass
class PatternPiece:
    """A planar sewing piece expressed in millimetres."""

    name: str
    outline: list[Point] = field(default_factory=_empty_points)
    seam_allowance: float = 0.0
    grainline_angle: float = 0.0
    id: str = ""
    metadata: dict[str, object] = field(default_factory=_empty_metadata)

    def validate(self) -> None:
        """Validate this value and raise ValueError when its state is invalid."""
        if not self.name.strip():
            msg = "pattern piece name must not be empty"
            raise ValueError(msg)
        if not self.outline or len(self.outline) < 3:
            msg = "pattern piece outline needs at least three points"
            raise ValueError(msg)
        if self.seam_allowance < 0:
            msg = "seam allowance cannot be negative"
            raise ValueError(msg)
        if not self.id.strip():
            msg = "pattern piece id must not be empty"
            raise ValueError(msg)
        PatternPieceInput.model_validate(
            {
                "name": self.name,
                "outline": self.outline,
                "seam_allowance": self.seam_allowance,
                "grainline_angle": self.grainline_angle,
                "id": self.id,
            }
        )


@pydantic_dataclass(frozen=True)
class Seam:
    """Canonical immutable in-memory sewing contract.

    Edge references may be integer outline indices or stable semantic edge
    identifiers supplied by an adapter. Alignment, stitch grouping, reversal,
    and construction kind are part of this record so document and simulation
    adapters cannot silently maintain competing seam state.
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
    alignment: str = "endpoints"
    stitch_group: str = ""
    kind: str = "plain"

    def validate(self) -> None:
        """Validate this value and raise ValueError when its state is invalid."""
        if not self.id.strip():
            msg = "seam id must not be empty"
            raise ValueError(msg)
        if self.piece_a == self.piece_b and self.edge_a == self.edge_b:
            msg = "a seam cannot connect an edge to itself"
            raise ValueError(msg)
        for edge in (self.edge_a, self.edge_b):
            if isinstance(edge, bool):
                msg = "seam edge references must be integer indices or stable identifiers"
                raise ValueError(msg)
            if isinstance(edge, int) and edge < 0:
                msg = "edge indices must be non-negative"
                raise ValueError(msg)
            if isinstance(edge, str) and not edge.strip():
                msg = "edge identifiers must not be empty"
                raise ValueError(msg)
        NormalizedRange(start=self.start_a, end=self.end_a)
        NormalizedRange(start=self.start_b, end=self.end_b)
        if self.alignment not in {"endpoints", "uniform"}:
            msg = "alignment must be 'endpoints' or 'uniform'"
            raise ValueError(msg)
        if self.kind not in {"plain", "dart", "gather", "pleat", "hem", "fold", "closure"}:
            msg = "unsupported seam construction kind"
            raise ValueError(msg)
        if not isinstance(self.edge_a, (int, str)) or not isinstance(self.edge_b, (int, str)):
            msg = "seam edge references must be integer indices or stable identifiers"
            raise ValueError(msg)
        if self.stitch_group and not self.stitch_group.strip():
            msg = "stitch group must not be whitespace"
            raise ValueError(msg)
