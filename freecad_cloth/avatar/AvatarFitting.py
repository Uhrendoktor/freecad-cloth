# Copyright (C) 2026 FreeCAD Cloth contributors
"""Solver-neutral body measurement and garment fitting-scene contracts.

This module intentionally does not import FreeCAD. The document workbench uses
these immutable records as its source of truth for fitting metadata.
"""

import json
from collections.abc import Mapping
from dataclasses import field

from pydantic.dataclasses import dataclass as pydantic_dataclass

_COORDINATE_COUNT = 3
_ARRANGEMENT_FIELD_COUNT = 5


def _three_coordinates(
    values: tuple[float, ...],
    *,
    error_message: str,
) -> tuple[float, float, float]:
    """Validate coordinate dimensionality and return a fixed-size tuple.

    Args:
        values: Parsed coordinate values from a serialized fitting record.
        error_message: Description to use when the record has the wrong dimension.

    Returns:
        A statically fixed three-coordinate tuple.

    Raises:
        ValueError: If the tuple does not contain exactly three coordinates.
    """
    if len(values) != _COORDINATE_COUNT:
        raise ValueError(error_message)
    x_coordinate, y_coordinate, z_coordinate = values
    return (x_coordinate, y_coordinate, z_coordinate)


_DEFAULT_MEASUREMENTS = {
    "height": 1700.0,
    "chest": 900.0,
    "waist": 760.0,
    "hip": 960.0,
    "shoulder": 420.0,
}


@pydantic_dataclass(frozen=True)
class BodyMeasurements:
    """Immutable body measurements with canonical units and serialization."""

    values: Mapping[str, float] = field(default_factory=lambda: dict(_DEFAULT_MEASUREMENTS))
    unit: str = "mm"

    def validate(self) -> None:
        """Validate the measurement unit, names, and positive numeric values.

        Raises:
            ValueError: If the unit, mapping, name, or measurement violates the contract.
        """
        if self.unit not in {"mm", "cm", "m"}:
            msg = "measurement unit must be mm, cm, or m"
            raise ValueError(msg)
        if not self.values:
            msg = "at least one body measurement is required"
            raise ValueError(msg)
        for name, value in self.values.items():
            if not str(name).strip():
                msg = "measurement names must not be empty"
                raise ValueError(msg)
            if float(value) <= 0:
                msg = "body measurements must be positive"
                raise ValueError(msg)

    def normalized(self) -> tuple[tuple[str, float], ...]:
        """Return measurement pairs in deterministic name order.

        Returns:
            Sorted measurement names and their values represented as floats.
        """
        self.validate()
        return tuple(sorted((str(k), float(v)) for k, v in self.values.items()))

    def to_json(self) -> str:
        """Serialize validated measurements in canonical JSON form.

        Returns:
            A stable JSON string containing the unit and sorted measurements.
        """
        return json.dumps(
            {"unit": self.unit, "values": dict(self.normalized())},
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, payload: str) -> "BodyMeasurements":
        """Restore body measurements from their JSON representation.

        Args:
            payload: JSON text containing the unit and measurement mapping.

        Returns:
            A validated body-measurement record.
        """
        data = json.loads(str(payload))
        result = cls(data["values"], data["unit"])
        result.validate()
        return result


@pydantic_dataclass(frozen=True)
class PiecePlacement:
    """Home position and z-axis rotation for one pattern piece."""

    piece_id: str
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation_z: float = 0.0

    def validate(self) -> None:
        """Validate the piece identifier and three-dimensional position.

        Raises:
            ValueError: If the identifier is blank or the position has the wrong dimension.
        """
        if not self.piece_id.strip():
            msg = "piece id must not be empty"
            raise ValueError(msg)
        if len(self.position) != _COORDINATE_COUNT:
            msg = "position must contain three coordinates"
            raise ValueError(msg)

    def to_string(self) -> str:
        """Serialize the placement into its stable pipe-delimited record.

        Returns:
            The piece identifier, three position coordinates, and z-axis rotation.
        """
        self.validate()
        return (
            f"{self.piece_id}|{self.position[0]:.12g},"
            f"{self.position[1]:.12g},{self.position[2]:.12g}|"
            f"{self.rotation_z:.12g}"
        )

    @classmethod
    def from_string(cls, value: str) -> "PiecePlacement":
        """Parse one placement from its pipe-delimited serialized record.

        Args:
            value: Record containing the piece identifier, position, and rotation.

        Returns:
            A placement with its position and rotation converted to floats.

        Raises:
            ValueError: If the identifier or position dimension is invalid.
        """
        piece_id, position, rotation = str(value).split("|")
        coords = tuple(float(v) for v in position.split(","))
        rotation_z = float(rotation)
        if not piece_id.strip():
            msg = "piece id must not be empty"
            raise ValueError(msg)
        fixed_position = _three_coordinates(
            coords,
            error_message="position must contain three coordinates",
        )
        result = cls(piece_id, fixed_position, rotation_z)
        result.validate()
        return result


@pydantic_dataclass(frozen=True)
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
        """Validate the point name, wrap direction, and symmetry metadata.

        Raises:
            ValueError: If the name or wrap direction is invalid.
        """
        if not self.name.strip():
            msg = "arrangement point name must not be empty"
            raise ValueError(msg)
        if self.wrap_direction not in self.VALID_WRAP_DIRECTIONS:
            msg = "wrap direction must be front, back, left, or right"
            raise ValueError(msg)
        if self.symmetry_group and not self.symmetry_group.strip():
            msg = "symmetry group must not be whitespace"
            raise ValueError(msg)

    def position(self) -> tuple[float, float, float]:
        """Return the point as its three fitting-plane coordinates.

        Returns:
            The x, y, and signed plane-offset coordinates as floats.
        """
        self.validate()
        return (float(self.x), float(self.y), float(self.offset))

    def mirrored(self, name: str | None = None) -> "ArrangementPoint":
        """Return a reflection across the avatar's vertical symmetry plane.

        Args:
            name: Optional replacement name; otherwise append the suffix .mirror.

        Returns:
            The mirrored point with its lateral direction and rotation reflected.
        """
        self.validate()
        mirror_wrap = {"left": "right", "right": "left"}.get(
            self.wrap_direction, self.wrap_direction
        )
        return ArrangementPoint(
            name or (self.name + ".mirror"),
            -float(self.x),
            float(self.y),
            float(self.offset),
            mirror_wrap,
            -float(self.rotation_z),
            self.symmetry_group,
        )

    def to_string(self) -> str:
        """Serialize the point into its stable pipe-delimited record.

        Returns:
            The name, coordinates, wrap direction, rotation, and symmetry group.
        """
        self.validate()
        return (
            f"{self.name}|{self.x:.12g},{self.y:.12g},{self.offset:.12g}|"
            f"{self.wrap_direction}|{self.rotation_z:.12g}|{self.symmetry_group}"
        )

    @classmethod
    def from_string(cls, value: str) -> "ArrangementPoint":
        """Parse an arrangement point from its pipe-delimited record.

        Args:
            value: Serialized name, coordinates, wrap direction, rotation, and group.

        Returns:
            The validated point with numeric coordinates and rotation.

        Raises:
            ValueError: If the field count, coordinate count, name, or wrap direction is invalid.
        """
        parts = str(value).split("|")
        if len(parts) != _ARRANGEMENT_FIELD_COUNT:
            msg = "arrangement point requires name|x,y,z|wrap|rotation|symmetry"
            raise ValueError(msg)
        name, position, wrap, rotation, symmetry = parts
        coords = tuple(float(v) for v in position.split(","))
        if len(coords) != _COORDINATE_COUNT:
            msg = "arrangement point position requires x, y, and offset"
            raise ValueError(msg)
        result = cls(name, coords[0], coords[1], coords[2], wrap, float(rotation), symmetry)
        result.validate()
        return result


@pydantic_dataclass(frozen=True)
class BoundingVolume:
    """Named axis-aligned avatar volume used for deterministic fitting metadata."""

    name: str
    center: tuple[float, float, float] = (0.0, 0.0, 0.0)
    size: tuple[float, float, float] = (100.0, 100.0, 100.0)

    def validate(self) -> None:
        """Validate the volume name, coordinate dimensions, and positive sizes.

        Raises:
            ValueError: If the name, center, or size violates the volume contract.
        """
        if not self.name.strip():
            msg = "bounding volume name must not be empty"
            raise ValueError(msg)
        if (
            len(self.center) != _COORDINATE_COUNT
            or len(self.size) != _COORDINATE_COUNT
        ):
            msg = "bounding volume center and size require three coordinates"
            raise ValueError(msg)
        if any(float(v) <= 0.0 for v in self.size):
            msg = "bounding volume size must be positive"
            raise ValueError(msg)

    def to_string(self) -> str:
        """Serialize the axis-aligned volume into a stable record.

        Returns:
            The name, center coordinates, and size coordinates.
        """
        self.validate()
        return "{}|{:.12g},{:.12g},{:.12g}|{:.12g},{:.12g},{:.12g}".format(
            self.name, *self.center, *self.size
        )

    @classmethod
    def from_string(cls, value: str) -> "BoundingVolume":
        """Parse a bounding volume from its pipe-delimited record.

        Args:
            value: Serialized name, three-coordinate center, and three-coordinate size.

        Returns:
            The validated axis-aligned volume.

        Raises:
            ValueError: If the name or coordinate dimensions are invalid.
        """
        name, center, size = str(value).split("|")
        center_coordinates = tuple(float(v) for v in center.split(","))
        size_coordinates = tuple(float(v) for v in size.split(","))
        if not name.strip():
            msg = "bounding volume name must not be empty"
            raise ValueError(msg)
        coordinate_error = "bounding volume center and size require three coordinates"
        fixed_center = _three_coordinates(
            center_coordinates,
            error_message=coordinate_error,
        )
        fixed_size = _three_coordinates(
            size_coordinates,
            error_message=coordinate_error,
        )
        result = cls(name, fixed_center, fixed_size)
        result.validate()
        return result


@pydantic_dataclass(frozen=True)
class FittingScene:
    """Immutable fitting metadata for measurements, placements, and volumes."""

    measurements: BodyMeasurements = field(default_factory=BodyMeasurements)
    avatar_name: str = ""
    pieces: tuple[PiecePlacement, ...] = ()
    arrangement_points: tuple[ArrangementPoint, ...] = ()
    bounding_volumes: tuple[BoundingVolume, ...] = ()
    symmetry_enabled: bool = True

    def validate(self) -> None:
        """Validate the measurements and ensure fitting record names are unique.

        Raises:
            ValueError: If a nested record is invalid or a piece, point, or volume is duplicated.
        """
        self.measurements.validate()
        if self.avatar_name and not self.avatar_name.strip():
            msg = "avatar name must not be whitespace"
            raise ValueError(msg)
        seen = set()
        for placement in self.pieces:
            placement.validate()
            if placement.piece_id in seen:
                msg = "pattern piece may only have one fitting placement"
                raise ValueError(msg)
            seen.add(placement.piece_id)
        names = set()
        for point in self.arrangement_points:
            point.validate()
            if point.name in names:
                msg = "arrangement point names must be unique"
                raise ValueError(msg)
            names.add(point.name)
        names = set()
        for volume in self.bounding_volumes:
            volume.validate()
            if volume.name in names:
                msg = "bounding volume names must be unique"
                raise ValueError(msg)
            names.add(volume.name)

    def placement_map(self) -> dict[str, PiecePlacement]:
        """Return placements keyed by their stable piece identifiers.

        Returns:
            A mapping from piece identifiers to validated placements.
        """
        self.validate()
        return {item.piece_id: item for item in self.pieces}

    def arrangement_map(self) -> dict[str, ArrangementPoint]:
        """Return arrangement points keyed by their semantic names.

        Returns:
            A mapping from semantic landmark names to validated points.
        """
        self.validate()
        return {item.name: item for item in self.arrangement_points}

    def to_json(self) -> str:
        """Serialize the validated fitting scene into canonical JSON.

        Returns:
            Stable JSON text containing measurements and sorted fitting records.
        """
        self.validate()
        return json.dumps(
            {
                "avatar": self.avatar_name,
                "measurements": json.loads(self.measurements.to_json()),
                "pieces": [
                    item.to_string() for item in sorted(self.pieces, key=lambda p: p.piece_id)
                ],
                "arrangement_points": [
                    item.to_string()
                    for item in sorted(self.arrangement_points, key=lambda p: p.name)
                ],
                "bounding_volumes": [
                    item.to_string() for item in sorted(self.bounding_volumes, key=lambda v: v.name)
                ],
                "symmetry_enabled": bool(self.symmetry_enabled),
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, payload: str) -> "FittingScene":
        """Restore a fitting scene from its JSON representation.

        Args:
            payload: JSON text containing measurements and fitting metadata.

        Returns:
            A validated fitting-scene record.
        """
        data = json.loads(str(payload))
        result = cls(
            BodyMeasurements.from_json(
                json.dumps(data["measurements"], sort_keys=True, separators=(",", ":"))
            ),
            str(data.get("avatar", "")),
            tuple(PiecePlacement.from_string(v) for v in data.get("pieces", ())),
            tuple(ArrangementPoint.from_string(v) for v in data.get("arrangement_points", ())),
            tuple(BoundingVolume.from_string(v) for v in data.get("bounding_volumes", ())),
            bool(data.get("symmetry_enabled", True)),
        )
        result.validate()
        return result
