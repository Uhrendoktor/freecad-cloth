"""Shared, FreeCAD-independent pattern data model."""
from dataclasses import dataclass, field
from math import isfinite
from typing import Dict, List, Tuple

Point = Tuple[float, float]
Vec3 = Tuple[float, float, float]


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
    """A named connection between two pattern pieces."""
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


@dataclass(frozen=True)
class AssemblyTransform:
    """Rigid transform applied to the second piece of a seam assembly."""
    translation: Vec3 = (0.0, 0.0, 0.0)
    rotation_deg: float = 0.0

    def validate(self) -> None:
        if len(self.translation) != 3 or not all(isfinite(float(value)) for value in self.translation):
            raise ValueError("assembly translation must contain three finite numeric values")
        if not isfinite(float(self.rotation_deg)):
            raise ValueError("assembly rotation must be finite")


class SeamGraph:
    """Validated seam graph with stable seam IDs and assembly transforms."""

    def __init__(self, seams=None, transforms: Dict[str, AssemblyTransform] | None = None):
        self.seams = list(seams or [])
        self.transforms = dict(transforms or {})
        self.validate()

    def validate(self) -> None:
        ids = set()
        for seam in self.seams:
            seam.validate()
            if seam.id in ids:
                raise ValueError(f"duplicate seam id: {seam.id}")
            ids.add(seam.id)
        unknown = set(self.transforms) - ids
        if unknown:
            raise ValueError(f"assembly transform references unknown seam(s): {sorted(unknown)}")
        for transform in self.transforms.values():
            transform.validate()

    def add(self, seam: Seam, transform: AssemblyTransform | None = None) -> None:
        seam.validate()
        if any(existing.id == seam.id for existing in self.seams):
            raise ValueError(f"duplicate seam id: {seam.id}")
        self.seams.append(seam)
        if transform is not None:
            transform.validate()
            self.transforms[seam.id] = transform
        self.validate()

    def by_id(self) -> Dict[str, Seam]:
        return {seam.id: seam for seam in self.seams}

    def transform_for(self, seam_id: str) -> AssemblyTransform:
        if seam_id not in self.by_id():
            raise KeyError(seam_id)
        return self.transforms.get(seam_id, AssemblyTransform())
