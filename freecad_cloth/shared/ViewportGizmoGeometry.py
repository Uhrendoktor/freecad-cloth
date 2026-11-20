# Copyright (C) 2026 FreeCAD Cloth contributors
"""Reusable Coin3D geometry primitives for foreground avatar gizmos.

Interactive controls use real rounded 3D geometry. Coin's annotation node places
that geometry after ordinary scene rendering, while the fallback keeps depth
testing disabled on builds that do not expose SoAnnotation.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from types import ModuleType
from typing import Protocol, cast


class _CoinGroup(Protocol):
    """Coin group node with the child operations required by these helpers."""

    def addChild(self, child: _CoinGroup) -> None:
        """Append one transient geometry node."""


def create_foreground_layer(coin: ModuleType, name: str) -> _CoinGroup:
    """Create a depth-independent layer rendered after the mannequin.

    Args:
        coin: Loaded Pivy Coin module.
        name: Stable diagnostic name assigned to the scene-graph node.

    Returns:
        Coin annotation group, or a depth-disabled separator compatibility fallback.
    """
    annotation_type = getattr(coin, "SoAnnotation", None)
    layer = None
    if annotation_type is not None:
        try:
            layer = annotation_type()
        except (AttributeError, RuntimeError, TypeError):
            layer = None

    if layer is None:
        layer = coin.SoSeparator()
        depth = coin.SoDepthBuffer()
        depth.test = False
        depth.write = False
        layer.addChild(depth)

    layer.setName(str(name))
    return cast(_CoinGroup, layer)


def add_sphere(
    parent: _CoinGroup,
    coin: ModuleType,
    point: Sequence[float],
    radius: float,
    color: Sequence[float],
) -> None:
    """Add a smooth, positioned sphere to a foreground control layer.

    Args:
        parent: Foreground group that receives the sphere.
        coin: Loaded Pivy Coin module.
        point: Sphere center in mannequin/world coordinates.
        radius: Sphere radius in model units.
        color: Normalized RGB color.

    Raises:
        ValueError: If the point/color are not 3D/RGB or the radius is not positive.
    """
    if len(point) != 3 or len(color) != 3 or float(radius) <= 0.0:
        raise ValueError("A gizmo sphere requires a 3D point, positive radius and RGB color.")

    marker = coin.SoSeparator()
    transform = coin.SoTransform()
    transform.translation.setValue(coin.SbVec3f(*(float(value) for value in point)))
    base = coin.SoBaseColor()
    base.rgb = tuple(float(value) for value in color)
    sphere = coin.SoSphere()
    sphere.radius.setValue(float(radius))
    marker.addChild(transform)
    marker.addChild(base)
    marker.addChild(sphere)
    parent.addChild(marker)


def add_capsule(
    parent: _CoinGroup,
    coin: ModuleType,
    start: Sequence[float],
    end: Sequence[float],
    radius: float,
    color: Sequence[float],
) -> None:
    """Add a rounded-end bone segment aligned between two 3D joint positions.

    A cylinder forms the shaft; the skeleton's spherical joint controls provide
    the rounded endpoints and visually connect adjacent segments.

    Args:
        parent: Foreground group that receives the bone geometry.
        coin: Loaded Pivy Coin module.
        start: First endpoint in mannequin/world coordinates.
        end: Second endpoint in mannequin/world coordinates.
        radius: Bone shaft radius in model units.
        color: Normalized RGB color.

    Raises:
        ValueError: If either endpoint/color has invalid dimensions or the radius is not positive.
    """
    if len(start) != 3 or len(end) != 3 or len(color) != 3 or float(radius) <= 0.0:
        raise ValueError("A bone capsule requires two 3D endpoints, positive radius and RGB color.")

    direction = tuple(float(end[index]) - float(start[index]) for index in range(3))
    length = math.sqrt(sum(component * component for component in direction))
    if length <= 1e-8:
        add_sphere(parent, coin, start, radius, color)
        return

    unit_direction = tuple(component / length for component in direction)
    center = tuple(
        (float(start[index]) + float(end[index])) * 0.5 for index in range(3)
    )
     segment = coin.SoSeparator()
    transform = coin.SoTransform()
    transform.translation.setValue(coin.SbVec3f(*(float(value) for value in center)))
    transform.rotation.setValue(
        coin.SbRotation(
            coin.SbVec3f(0.0, 1.0, 0.0),
            coin.SbVec3f(*(float(value) for value in unit_direction)),
        )
    )
    base = coin.SoBaseColor()
    base.rgb = tuple(float(value) for value in color)
    cylinder = coin.SoCylinder()
    cylinder.radius.setValue(float(radius))
    cylinder.height.setValue(float(length))
    segment.addChild(transform)
    segment.addChild(base)
    segment.addChild(cylinder)
    parent.addChild(segment)
