# Copyright (C) 2026 FreeCAD Cloth contributors
"""Contract tests for rounded Coin3D foreground gizmo primitives."""

from types import SimpleNamespace

from freecad_cloth.shared.ViewportGizmoGeometry import (
    add_capsule,
    add_sphere,
    create_foreground_layer,
)


class _Field:
    """Small Coin-field stand-in that retains scalar and vector assignments."""

    def __init__(self) -> None:
        self.value = None

    def setValue(self, *values: object) -> None:
        self.value = values[0] if len(values) == 1 else values


class _Group:
    """Coin group stand-in retaining child order and the node name."""

    def __init__(self) -> None:
        self.children: list[object] = []
        self.name = ""

    def addChild(self, child: object) -> None:
        self.children.append(child)

    def setName(self, name: str) -> None:
        self.name = str(name)


class _DepthBuffer:
    """Coin depth-state stand-in for compatibility fallback coverage."""

    def __init__(self) -> None:
        self.test = True
        self.write = True


class _Transform:
    """Coin transform stand-in with translation and rotation fields."""

    def __init__(self) -> None:
        self.translation = _Field()
        self.rotation = _Field()


class _Color:
    """Coin base-color stand-in retaining RGB values."""

    def __init__(self) -> None:
        self.rgb = None


class _Sphere:
    """Coin sphere stand-in with a radius field."""

    def __init__(self) -> None:
        self.radius = _Field()


class _Cylinder:
    """Coin cylinder stand-in with radius and height fields."""

    def __init__(self) -> None:
        self.radius = _Field()
        self.height = _Field()


def _coin(*, annotation: bool = True) -> SimpleNamespace:
    """Create the Coin subset needed by the shared viewport-geometry helpers."""
    values = {
        "SoSeparator": _Group,
        "SoDepthBuffer": _DepthBuffer,
        "SoTransform": _Transform,
        "SoBaseColor": _Color,
        "SoSphere": _Sphere,
        "SoCylinder": _Cylinder,
        "SbVec3f": lambda *items: tuple(float(item) for item in items),
        "SbRotation": lambda start, end: (start, end),
    }
    if annotation:
        values["SoAnnotation"] = _Group
    return SimpleNamespace(**values)


def test_foreground_layer_prefers_coin_annotation() -> None:
    """Use Coin's delayed annotation pass rather than scene-order depth-state tricks."""
    layer = create_foreground_layer(_coin(), "avatar-test-overlay")

    assert isinstance(layer, _Group)
    assert layer.name == "avatar-test-overlay"
    assert layer.children == []


def test_foreground_layer_falls_back_to_depth_disabled_separator() -> None:
    """Keep older Coin builds usable when SoAnnotation is not exposed by Pivy."""
    layer = create_foreground_layer(_coin(annotation=False), "avatar-fallback")

    assert isinstance(layer, _Group)
    assert layer.name == "avatar-fallback"
    assert len(layer.children) == 1
    depth = layer.children[0]
    assert isinstance(depth, _DepthBuffer)
    assert depth.test is False
    assert depth.write is False


def test_measurement_grip_uses_positioned_sphere_geometry() -> None:
    """Render a measurement grip as a smooth 3D sphere rather than a point sprite."""
    coin = _coin()
    layer = _Group()
    add_sphere(layer, coin, (1.0, 2.0, 3.0), 8.5, (0.2, 0.7, 0.9))

    assert len(layer.children) == 1
    marker = layer.children[0]
    assert isinstance(marker, _Group)
    transform, color, sphere = marker.children
    assert transform.translation.value == (1.0, 2.0, 3.0)
    assert color.rgb == (0.2, 0.7, 0.9)
    assert sphere.radius.value == 8.5


def test_bone_capsule_aligns_cylinder_between_joint_endpoints() -> None:
    """Orient the rounded bone shaft along the measured skeleton segment."""
    coin = _coin()
    layer = _Group()
    add_capsule(layer, coin, (0.0, 0.0, 0.0), (0.0, 25.0, 0.0), 3.5, (0.7, 0.7, 0.8))

    assert len(layer.children) == 1
    segment = layer.children[0]
    transform, color, cylinder = segment.children
    assert transform.translation.value == (0.0, 12.5, 0.0)
    assert transform.rotation.value == ((0.0, 1.0, 0.0), (0.0, 1.0, 0.0))
    assert color.rgb == (0.7, 0.7, 0.8)
    assert cylinder.radius.value == 3.5
    assert cylinder.height.value == 25.0


def test_degenerate_bone_segment_becomes_a_joint_sphere() -> None:
    """Avoid zero-height cylinders when a skeleton joint pair is coincident."""
    coin = _coin()
    layer = _Group()
    add_capsule(layer, coin, (2.0, 3.0, 4.0), (2.0, 3.0, 4.0), 4.0, (1.0, 0.8, 0.2))

    sphere = layer.children[0].children[2]
    assert sphere.radius.value == 4.0
