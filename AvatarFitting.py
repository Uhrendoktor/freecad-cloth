"""Solver-neutral body measurement and garment fitting-scene contracts.

This module intentionally does not import FreeCAD.  The document workbench uses
these small immutable records as its source of truth for fitting metadata.
"""
from dataclasses import dataclass, field
import json
from typing import Dict, Mapping, Tuple


_DEFAULT_MEASUREMENTS = {
    "height": 1700.0,
    "chest": 900.0,
    "waist": 760.0,
    "hip": 960.0,
    "shoulder": 420.0,
}


@dataclass(frozen=True)
class BodyMeasurements:
    """Canonical body measurements, stored in the selected unit."""

    values: Mapping[str, float] = field(default_factory=lambda: dict(_DEFAULT_MEASUREMENTS))
    unit: str = "mm"

    def validate(self) -> None:
        if self.unit not in {"mm", "cm", "m"}:
            raise ValueError("measurement unit must be mm, cm, or m")
        if not self.values:
            raise ValueError("at least one body measurement is required")
        for name, value in self.values.items():
            if not str(name).strip():
                raise ValueError("measurement names must not be empty")
            if float(value) <= 0:
                raise ValueError("body measurements must be positive")

    def normalized(self) -> Tuple[Tuple[str, float], ...]:
        self.validate()
        return tuple(sorted((str(k), float(v)) for k, v in self.values.items()))

    def to_json(self) -> str:
        return json.dumps({"unit": self.unit, "values": dict(self.normalized())},
                          sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, payload: str) -> "BodyMeasurements":
        data = json.loads(str(payload))
        result = cls(data["values"], data["unit"])
        result.validate()
        return result


@dataclass(frozen=True)
class PiecePlacement:
    """Deterministic translation/rotation metadata for a pattern piece."""

    piece_id: str
    position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation_z: float = 0.0

    def validate(self) -> None:
        if not self.piece_id.strip():
            raise ValueError("piece id must not be empty")
        if len(self.position) != 3:
            raise ValueError("position must contain three coordinates")

    def to_string(self) -> str:
        self.validate()
        return "%s|%.12g,%.12g,%.12g|%.12g" % (
            self.piece_id, self.position[0], self.position[1], self.position[2], self.rotation_z
        )

    @classmethod
    def from_string(cls, value: str) -> "PiecePlacement":
        piece_id, position, rotation = str(value).split("|")
        coords = tuple(float(v) for v in position.split(","))
        result = cls(piece_id, coords, float(rotation))
        result.validate()
        return result


@dataclass(frozen=True)
class FittingScene:
    """Reproducible fitting scene independent of the FreeCAD document format."""

    measurements: BodyMeasurements = field(default_factory=BodyMeasurements)
    avatar_name: str = ""
    pieces: Tuple[PiecePlacement, ...] = ()

    def validate(self) -> None:
        self.measurements.validate()
        if self.avatar_name and not self.avatar_name.strip():
            raise ValueError("avatar name must not be whitespace")
        seen = set()
        for placement in self.pieces:
            placement.validate()
            if placement.piece_id in seen:
                raise ValueError("pattern piece may only have one fitting placement")
            seen.add(placement.piece_id)

    def placement_map(self) -> Dict[str, PiecePlacement]:
        self.validate()
        return {item.piece_id: item for item in self.pieces}

    def to_json(self) -> str:
        self.validate()
        return json.dumps({
            "avatar": self.avatar_name,
            "measurements": json.loads(self.measurements.to_json()),
            "pieces": [item.to_string() for item in sorted(self.pieces, key=lambda p: p.piece_id)],
        }, sort_keys=True, separators=(",", ":"))
