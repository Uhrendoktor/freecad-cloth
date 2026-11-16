# Copyright (C) 2026 FreeCAD Cloth contributors
"""Contracts for transient Coin3D cloth-preview geometry publication."""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from typing import TYPE_CHECKING

from freecad_cloth.simulation.RealtimeMeshPreview import RealtimeMeshPreview

if TYPE_CHECKING:
    from pytest import MonkeyPatch


class _Field:
    """Record the bulk field writes made by the transient mesh adapter."""

    def __init__(self) -> None:
        """Initialize an empty field-write log."""
        self.calls: list[tuple[int, int, object]] = []

    def setValues(self, start: int, count: int, values: object) -> None:
        """Record a field update with its exact range and payload."""
        self.calls.append((start, count, values))


class _Separator:
    """Record Coin child nodes added to each transient panel separator."""

    def __init__(self) -> None:
        """Initialize an empty child list."""
        self.children: list[object] = []

    def addChild(self, child: object) -> None:
        """Append a node to the separator."""
        self.children.append(child)


class _SceneGraph:
    """Record transient root nodes added and removed by the preview adapter."""

    def __init__(self) -> None:
        """Initialize an empty root-node list."""
        self.children: list[object] = []

    def addChild(self, child: object) -> None:
        """Append a child node to the active viewport scenegraph."""
        self.children.append(child)

    def removeChild(self, child: object) -> None:
        """Remove a previously added transient viewport node."""
        self.children.remove(child)


class _Coordinate:
    """Provide a fake SoCoordinate3 node with a writable point field."""

    def __init__(self) -> None:
        """Initialize the coordinate point field."""
        self.point = _Field()


class _IndexedFaceSet:
    """Provide a fake SoIndexedFaceSet node with a writable coordinate index."""

    def __init__(self) -> None:
        """Initialize the indexed-face coordinate index field."""
        self.coordIndex = _Field()


def test_transient_preview_updates_only_coordinate_fields_and_restores_visibility(
    monkeypatch: MonkeyPatch,
) -> None:
    """Keep topology resident, update points in bulk, and restore document objects."""
    scene_graph = _SceneGraph()
    view = SimpleNamespace(getSceneGraph=lambda: scene_graph)
    active_document = SimpleNamespace(activeView=lambda: view)
    gui_module = ModuleType("FreeCADGui")
    gui_module.activeDocument = lambda: active_document

    coin_module = SimpleNamespace(
        SoSeparator=_Separator,
        SoMaterial=SimpleNamespace,
        SoCoordinate3=_Coordinate,
        SoIndexedFaceSet=_IndexedFaceSet,
    )
    pivy_module = ModuleType("pivy")
    pivy_module.coin = coin_module
    monkeypatch.setitem(sys.modules, "FreeCADGui", gui_module)
    monkeypatch.setitem(sys.modules, "pivy", pivy_module)

    panel = SimpleNamespace(
        Name="PanelA",
        ViewObject=SimpleNamespace(Visibility=True),
    )
    triangles = ((0, 1, 2),)
    positions = (
        (0.0, 0.0, 0.0),
        (10.0, 0.0, 0.0),
        (0.0, 10.0, 0.0),
    )
    preview = RealtimeMeshPreview(
        (panel,),
        {"PanelA": triangles},
        (0.7, 0.2, 0.3),
        25,
        0.4,
        0.5,
    )

    assert len(scene_graph.children) == 1, (
        "Transient preview must add one Coin separator per document panel."
    )
    assert panel.ViewObject.Visibility is False, (
        "Persistent panel meshes must be hidden to prevent duplicate rendering."
    )
    separator = scene_graph.children[0]
    assert isinstance(separator, _Separator), "The root node must be a separator."
    indexed_faces = separator.children[2]
    assert isinstance(indexed_faces, _IndexedFaceSet), (
        "Panel topology must be stored in one resident indexed-face node."
    )
    assert indexed_faces.coordIndex.calls == [(0, 4, [0, 1, 2, -1])], (
        "Topology must be installed once with a face terminator."
    )

    preview.publish(panel, positions, triangles)
    coordinates = separator.children[1]
    assert isinstance(coordinates, _Coordinate), (
        "The panel must own a persistent SoCoordinate3 node."
    )
    assert coordinates.point.calls == [(0, 3, positions)], (
        "A frame must update the full point field with one bulk operation."
    )

    preview.close()
    preview.close()

    assert scene_graph.children == [], "Closing preview must remove transient Coin nodes."
    assert panel.ViewObject.Visibility is True, (
        "Closing preview must restore each persistent panel's prior visibility."
    )
