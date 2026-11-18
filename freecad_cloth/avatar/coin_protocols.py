# Copyright (C) 2026 FreeCAD Cloth contributors
"""Structural interfaces for the dynamically loaded Pivy Coin viewport API.

The FreeCAD runtime supplies Pivy through SWIG rather than typed Python stubs.
These narrow protocols describe only the Coin members used by Pose Mode.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol, overload


class _CoinVector3(Protocol):
    """Three-dimensional value accepted by native Coin vector fields."""

    x: float
    y: float
    z: float


class _CoinRotation(Protocol):
    """Native rotation value exposing its scalar-first quaternion."""

    def getValue(self) -> Sequence[float]:
        """Return quaternion components in native Coin order."""
        ...


type CoinCoordinates = tuple[float, float, float]
type CoinFieldSequenceValue = int | CoinCoordinates
type CoinFieldValue = str | int | float | bool | CoinCoordinates | _CoinVector3 | _CoinRotation


class _CoinField(Protocol):
    """Writable Coin field supporting scalar and multi-value assignment."""

    def setValue(self, *values: CoinFieldValue) -> None:
        """Assign supported scalar, coordinate, or rotation values."""
        ...

    def setValues(
        self,
        start: int,
        count: int,
        values: Sequence[CoinFieldSequenceValue],
    ) -> None:
        """Assign a contiguous sequence of integer or coordinate values."""
        ...


class _CoinRotationField(_CoinField, Protocol):
    """Coin field storing a quaternion-backed rotation value."""

    def getValue(self) -> _CoinRotation:
        """Return the native rotation stored in this field."""
        ...


class _CoinNode(Protocol):
    """Scene-graph node that can receive child nodes."""

    def addChild(self, child: _CoinNode) -> None:
        """Append a child node to this scene graph."""
        ...


class _CoinSeparator(_CoinNode, Protocol):
    """Coin separator node supporting the scene graph operations used here."""

    def setName(self, name: str) -> None:
        """Assign a stable diagnostic name to this node."""
        ...

    def getNumChildren(self) -> int:
        """Return the number of children currently attached."""
        ...

    @overload
    def removeChild(self, index: int) -> None:
        """Remove the child at the requested index."""
        ...

    @overload
    def removeChild(self, child: _CoinNode) -> None:
        """Remove the supplied child node from this separator."""
        ...


class _CoinDepthBuffer(_CoinNode, Protocol):
    """Depth-buffer node with writable testing and depth-write switches."""

    test: bool
    write: bool


class _CoinDrawStyle(_CoinNode, Protocol):
    """Coin draw-style node used for bone and joint overlays."""

    lineWidth: float
    pointSize: float


class _CoinBaseColor(_CoinNode, Protocol):
    """Coin base-color node used for pose overlay geometry."""

    rgb: tuple[float, float, float]


class _CoinCoordinate3(_CoinNode, Protocol):
    """Coin coordinate node containing an editable point field."""

    point: _CoinField


class _CoinLineSet(_CoinNode, Protocol):
    """Coin line-set node containing a vertex-count field."""

    numVertices: _CoinField


class _CoinPointSet(_CoinNode, Protocol):
    """Coin point-set node with a writable point count."""

    numPoints: int


class _CoinTranslation(_CoinNode, Protocol):
    """Coin translation node exposing its writable translation field."""

    translation: _CoinField


class _CoinText2(_CoinNode, Protocol):
    """Coin screen-space text node exposing its writable text field."""

    string: _CoinField


class _CoinTransform(_CoinNode, Protocol):
    """Coin transform node used to position a rotation manipulator."""

    translation: _CoinField
    rotation: _CoinRotationField


class _CoinName(Protocol):
    """String value returned by a native Coin node name."""

    def getString(self) -> str:
        """Return the node name as a Python string."""
        ...


class _CoinClassType(Protocol):
    """Runtime Coin type identifier accepted by FreeCAD's Pivy event hooks."""

    def getName(self) -> _CoinName:
        """Return the stable name of the registered Coin event type."""
        ...


class _CoinRotatorGeometry(_CoinNode, Protocol):
    """Coin geometry fields used to draw native colored rotation rings."""

    arcAngle: _CoinField
    arcRadius: _CoinField
    arcThickness: _CoinField
    sphereRadius: _CoinField
    coneBottomRadius: _CoinField
    coneHeight: _CoinField
    leftArrowVisible: _CoinField
    rightArrowVisible: _CoinField


class _CoinDynamicDragger(_CoinSeparator, Protocol):
    """Dynamic rotation/trackball dragger fields and callback registration."""

    isActive: bool
    rotation: _CoinRotationField
    rotationIncrement: _CoinField
    geometryScale: _CoinField
    color: _CoinField
    activeColor: _CoinField
    baseGeomVisible: _CoinField
    scaleFactor: _CoinField

    def setPart(self, name: str, part: _CoinNode) -> bool:
        """Replace a named dragger part with the supplied Coin node."""
        ...

    def setAnimationEnabled(self, enabled: bool) -> None:
        """Enable or disable dragger animation."""
        ...

    def addStartCallback(self, callback: Callable[..., None]) -> None:
        """Register the callback invoked when a drag starts."""
        ...

    def addMotionCallback(self, callback: Callable[..., None]) -> None:
        """Register the callback invoked while a drag moves."""
        ...

    def addFinishCallback(self, callback: Callable[..., None]) -> None:
        """Register the callback invoked when a drag finishes."""
        ...

    def getName(self) -> _CoinName:
        """Return the native Coin node name."""
        ...


class _CoinType(Protocol):
    """Registered Coin node type that can create one dynamic node instance."""

    def isBad(self) -> bool:
        """Return whether the native Coin type is unavailable."""
        ...

    def createInstance(self) -> _CoinDynamicDragger | None:
        """Create an instance of the registered Coin node type."""
        ...


class _CoinTypeRegistry(Protocol):
    """Static Coin type registry used to resolve runtime node names."""

    def fromName(self, name: str) -> _CoinType:
        """Resolve a registered Coin node type by name."""
        ...


class _CoinEventType(Protocol):
    """Coin event class exposing its runtime type identifier."""

    def getClassTypeId(self) -> _CoinClassType:
        """Return the native event type identifier."""
        ...


class _CoinMouseButtonEventType(_CoinEventType, Protocol):
    """Mouse event class with the press and primary-button constants."""

    DOWN: int
    UP: int
    BUTTON1: int


class _CoinEvent(Protocol):
    """Mouse/location event values delivered by a Pivy callback."""

    def getState(self) -> int:
        """Return the native mouse-button event state."""
        ...

    def getButton(self) -> int:
        """Return the native mouse button identifier."""
        ...

    def getPosition(self) -> Sequence[float]:
        """Return the event position in viewport pixels."""
        ...


class _CoinEventCallback(Protocol):
    """Callback wrapper that exposes its current native Coin event."""

    def setHandled(self) -> None:
        """Mark the native event as handled by the current callback."""
        ...

    def getEvent(self) -> _CoinEvent:
        """Return the event associated with this callback invocation."""
        ...


class _CoinModule(Protocol):
    """Subset of the dynamically loaded Pivy Coin module used by Pose Mode."""

    SoType: _CoinTypeRegistry
    SoMouseButtonEvent: _CoinMouseButtonEventType
    SoLocation2Event: _CoinEventType
    SoSeparator: Callable[[], _CoinSeparator]
    SoDepthBuffer: Callable[[], _CoinDepthBuffer]
    SoDrawStyle: Callable[[], _CoinDrawStyle]
    SoBaseColor: Callable[[], _CoinBaseColor]
    SoCoordinate3: Callable[[], _CoinCoordinate3]
    SoLineSet: Callable[[], _CoinLineSet]
    SoPointSet: Callable[[], _CoinPointSet]
    SoTranslation: Callable[[], _CoinTranslation]
    SoText2: Callable[[], _CoinText2]
    SoTransform: Callable[[], _CoinTransform]
    SoTrackballDragger: Callable[[], _CoinDynamicDragger]
    SbVec3f: Callable[..., _CoinVector3]
    SbRotation: Callable[..., _CoinRotation]


# Public structural aliases for consumers crossing module boundaries.
CoinClassType = _CoinClassType
CoinDynamicDragger = _CoinDynamicDragger
CoinEventCallback = _CoinEventCallback
CoinModule = _CoinModule
CoinNode = _CoinNode
CoinSeparator = _CoinSeparator
CoinTransform = _CoinTransform
CoinType = _CoinType
CoinVector3 = _CoinVector3
CoinRotatorGeometry = _CoinRotatorGeometry
