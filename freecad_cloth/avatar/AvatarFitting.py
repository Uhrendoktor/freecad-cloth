"""Solver-neutral body measurement and garment fitting-scene contracts.

This module intentionally does not import FreeCAD. The document workbench uses
these immutable records as its source of truth for fitting metadata.
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
class ArrangementPoint:
    """Named avatar fitting point in deterministic world coordinates.

    ``x``/``y`` locate the point on the fitting plane and ``offset`` is the
    signed distance from that plane. ``wrap_direction`` describes the side of
    the avatar to which a piece should face and is deliberately an enum-like
    string so it survives FreeCAD document serialization unchanged.
    """

    name: str
    x: float = 0.0
    y: float = 0.0
    offset: float = 0.0
    wrap_direction: str = "front"
    rotation_z: float = 0.0
    symmetry_group: str = ""

    VALID_WRAP_DIRECTIONS = ("front", "back", "left", "right")

    def validate(self) -> None:
        if not self.name.strip():
            raise ValueError("arrangement point name must not be empty")
        if self.wrap_direction not in self.VALID_WRAP_DIRECTIONS:
            raise ValueError("wrap direction must be front, back, left, or right")
        if self.symmetry_group and not self.symmetry_group.strip():
            raise ValueError("symmetry group must not be whitespace")

    def position(self) -> Tuple[float, float, float]:
        self.validate()
        return (float(self.x), float(self.y), float(self.offset))

    def mirrored(self, name=None) -> "ArrangementPoint":
        self.validate()
        mirror_wrap = {"left": "right", "right": "left"}.get(self.wrap_direction, self.wrap_direction)
        return ArrangementPoint(
            name or (self.name + ".mirror"), -float(self.x), float(self.y), float(self.offset),
            mirror_wrap, -float(self.rotation_z), self.symmetry_group,
        )

    def to_string(self) -> str:
        self.validate()
        return "%s|%.12g,%.12g,%.12g|%s|%.12g|%s" % (
            self.name, self.x, self.y, self.offset, self.wrap_direction,
            self.rotation_z, self.symmetry_group,
        )

    @classmethod
    def from_string(cls, value: str) -> "ArrangementPoint":
        name, position, wrap, rotation, symmetry = str(value).split("|")
        coords = tuple(float(v) for v in position.split(","))
        if len(coords) != 3:
            raise ValueError("arrangement point position requires x, y, and offset")
        result = cls(name, coords[0], coords[1], coords[2], wrap, float(rotation), symmetry)
        result.validate()
        return result


@dataclass(frozen=True)
class BoundingVolume:
    """Named axis-aligned avatar volume used for deterministic fitting metadata."""

    name: str
    center: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    size: Tuple[float, float, float] = (100.0, 100.0, 100.0)

    def validate(self) -> None:
        if not self.name.strip():
            raise ValueError("bounding volume name must not be empty")
        if len(self.center) != 3 or len(self.size) != 3:
            raise ValueError("bounding volume center and size require three coordinates")
        if any(float(v) <= 0.0 for v in self.size):
            raise ValueError("bounding volume size must be positive")

    def to_string(self) -> str:
        self.validate()
        return "%s|%.12g,%.12g,%.12g|%.12g,%.12g,%.12g" % (
            self.name, *self.center, *self.size
        )

    @classmethod
    def from_string(cls, value: str) -> "BoundingVolume":
        name, center, size = str(value).split("|")
        result = cls(name, tuple(float(v) for v in center.split(",")), tuple(float(v) for v in size.split(",")))
        result.validate()
        return result


@dataclass(frozen=True)
class FittingScene:
    measurements: BodyMeasurements = field(default_factory=BodyMeasurements)
    avatar_name: str = ""
    pieces: Tuple[PiecePlacement, ...] = ()
    arrangement_points: Tuple[ArrangementPoint, ...] = ()
    bounding_volumes: Tuple[BoundingVolume, ...] = ()
    symmetry_enabled: bool = True

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
        names = set()
        for point in self.arrangement_points:
            point.validate()
            if point.name in names:
                raise ValueError("arrangement point names must be unique")
            names.add(point.name)
        names = set()
        for volume in self.bounding_volumes:
            volume.validate()
            if volume.name in names:
                raise ValueError("bounding volume names must be unique")
            names.add(volume.name)

    def placement_map(self) -> Dict[str, PiecePlacement]:
        self.validate()
        return {item.piece_id: item for item in self.pieces}

    def arrangement_map(self) -> Dict[str, ArrangementPoint]:
        self.validate()
        return {item.name: item for item in self.arrangement_points}

    def to_json(self) -> str:
        self.validate()
        return json.dumps({
            "avatar": self.avatar_name,
            "measurements": json.loads(self.measurements.to_json()),
            "pieces": [item.to_string() for item in sorted(self.pieces, key=lambda p: p.piece_id)],
            "arrangement_points": [item.to_string() for item in sorted(self.arrangement_points, key=lambda p: p.name)],
            "bounding_volumes": [item.to_string() for item in sorted(self.bounding_volumes, key=lambda v: v.name)],
            "symmetry_enabled": bool(self.symmetry_enabled),
        }, sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, payload: str) -> "FittingScene":
        data = json.loads(str(payload))
        result = cls(
            BodyMeasurements.from_json(json.dumps(data["measurements"], sort_keys=True, separators=(",", ":"))),
            str(data.get("avatar", "")),
            tuple(PiecePlacement.from_string(v) for v in data.get("pieces", ())),
            tuple(ArrangementPoint.from_string(v) for v in data.get("arrangement_points", ())),
            tuple(BoundingVolume.from_string(v) for v in data.get("bounding_volumes", ())),
            bool(data.get("symmetry_enabled", True)),
        )
        result.validate()
        return result
