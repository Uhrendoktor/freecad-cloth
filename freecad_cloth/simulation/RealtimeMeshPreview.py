# Copyright (C) 2026 FreeCAD Cloth contributors
"""Transient Coin3D mesh presentation for interactive cloth preview frames."""

from collections.abc import Sequence
from typing import Protocol, cast

type _Position = tuple[float, float, float]
type _Triangle = tuple[int, int, int]


class _CoinNode(Protocol):
    """Common opaque node accepted by the Coin3D scenegraph."""

    def __repr__(self) -> str: ...


class _CoordinateField(Protocol):
    """Expose the bulk coordinate update used by Pivy Coin fields."""

    def setValues(self, start: int, count: int, values: Sequence[_Position]) -> None: ...


class _IndexField(Protocol):
    """Expose the bulk face-index update used by Pivy Coin fields."""

    def setValues(self, start: int, count: int, values: Sequence[int]) -> None: ...


class _CoinSeparator(_CoinNode, Protocol):
    """Expose the child operation required by transient panel separators."""

    def addChild(self, child: _CoinNode) -> None: ...


class _CoinSceneGraph(Protocol):
    """Expose root scenegraph operations required by the preview adapter."""

    def addChild(self, child: _CoinNode) -> None: ...

    def removeChild(self, child: _CoinNode) -> None: ...


class _CoinMaterial(_CoinNode, Protocol):
    """Expose the material fields configured once for each transient panel."""

    diffuseColor: tuple[float, float, float]
    transparency: float
    specularColor: tuple[float, float, float]
    shininess: float


class _CoordinateNode(_CoinNode, Protocol):
    """Expose the mutable point field on a Coin3D coordinate node."""

    point: _CoordinateField


class _IndexedFaceNode(_CoinNode, Protocol):
    """Expose the fixed coordinate-index field on a Coin3D indexed face node."""

    coordIndex: _IndexField


class _PanelViewObject(Protocol):
    """Expose the visibility state changed while transient geometry is active."""

    Visibility: bool


class _PreviewPanel(Protocol):
    """Expose the document panel metadata whose persistent mesh is hidden in preview."""

    Name: str
    ViewObject: _PanelViewObject


class RealtimeMeshPreview:
    """Render each cloth panel as an ephemeral Coin3D indexed face set.

    The durable Mesh::Feature objects are hidden while the preview is active.
    Only the SoCoordinate3 point fields are changed on a frame; topology and
    materials stay resident in the Coin scenegraph. Closing the preview removes
    these transient nodes and restores the original document-object visibility.
    """

    def __init__(
        self,
        panels: Sequence[_PreviewPanel],
        panel_triangles: dict[str, Sequence[_Triangle]],
        color: Sequence[float],
        transparency: int,
        specular: float,
        roughness: float,
    ) -> None:
        """Create one cached Coin3D node per persistent simulation output panel.

        Args:
            panels: Persistent document panel objects used to identify preview outputs.
            panel_triangles: Fixed indexed topology for each panel, keyed by object name.
            color: RGB fabric color in normalized channel units.
            transparency: Fabric transparency as an integer percentage.
            specular: Normalized fabric specular intensity.
            roughness: Normalized fabric surface roughness.

        Raises:
            RuntimeError: If no active GUI document is available.
            ValueError: If the fabric color does not contain three channels.
        """
        import FreeCADGui as Gui
        from pivy import coin

        active_document = Gui.activeDocument()
        if active_document is None:
            msg = "Realtime cloth preview requires an active FreeCAD GUI document"
            raise RuntimeError(msg)
        if len(color) < 3:
            msg = "Realtime preview material color must contain three channels"
            raise ValueError(msg)

        view = active_document.activeView()
        scene_graph = cast("_CoinSceneGraph", view.getSceneGraph())
        self._scene_graph = scene_graph
        self._nodes: dict[str, tuple[_CoinSeparator, _CoordinateNode, tuple[int, ...]]] = {}
        self._visibility: list[tuple[_PanelViewObject, bool]] = []
        self._closed = False

        material_color = (float(color[0]), float(color[1]), float(color[2]))
        material_transparency = max(0.0, min(1.0, float(transparency) / 100.0))
        material_specular = max(0.0, min(1.0, float(specular)))
        material_shininess = max(0.0, min(1.0, 1.0 - float(roughness)))

        try:
            from freecad_cloth.simulation.SimulationObjects import _indexed_mesh_topology

            for panel in panels:
                triangles = tuple(
                    (int(triangle[0]), int(triangle[1]), int(triangle[2]))
                    for triangle in panel_triangles.get(panel.Name, ())
                )
                if not triangles:
                    continue
                vertex_indices, faces = _indexed_mesh_topology(triangles)
                separator = cast("_CoinSeparator", coin.SoSeparator())
                material = cast("_CoinMaterial", coin.SoMaterial())
                material.diffuseColor = material_color
                material.transparency = material_transparency
                material_specular_color: tuple[float, float, float] = (
                    material_specular,
                    material_specular,
                    material_specular,
                )
                material.specularColor = material_specular_color
                material.shininess = material_shininess
                coordinates = cast("_CoordinateNode", coin.SoCoordinate3())
                indexed_faces = cast("_IndexedFaceNode", coin.SoIndexedFaceSet())
                face_indices = [value for face in faces for value in (*face, -1)]
                indexed_faces.coordIndex.setValues(0, len(face_indices), face_indices)
                separator.addChild(material)
                separator.addChild(coordinates)
                separator.addChild(indexed_faces)
                scene_graph.addChild(separator)

                view_object = panel.ViewObject
                visible = bool(getattr(view_object, "Visibility", True))
                self._visibility.append((view_object, visible))
                view_object.Visibility = False
                self._nodes[panel.Name] = (separator, coordinates, vertex_indices)
        except Exception:
            self.close()
            raise

    def publish(
        self,
        panel: _PreviewPanel,
        positions: Sequence[_Position],
        triangles: Sequence[_Triangle],
    ) -> None:
        """Update one panel's transient coordinates without touching its document mesh.

        Args:
            panel: Persistent panel whose cached Coin3D coordinates are updated.
            positions: Current backend particle positions in document space.
            triangles: Fixed panel topology; retained for the publisher callback contract.
        """
        _ = triangles
        node = self._nodes.get(panel.Name)
        if node is None:
            return
        _separator, coordinates, vertex_indices = node
        points = tuple(positions[index] for index in vertex_indices)
        coordinates.point.setValues(0, len(points), points)

    def publish_all(
        self,
        panels: Sequence[_PreviewPanel],
        positions: Sequence[_Position],
        panel_triangles: dict[str, Sequence[_Triangle]],
    ) -> None:
        """Seed every transient panel from the current backend position snapshot.

        Args:
            panels: Persistent panels whose transient geometry should be initialized.
            positions: Current backend particle positions in document space.
            panel_triangles: Fixed indexed topology for each panel, keyed by object name.
        """
        for panel in panels:
            self.publish(
                panel,
                positions,
                panel_triangles.get(panel.Name, ()),
            )

    def close(self) -> None:
        """Remove transient scenegraph nodes and restore persistent panel visibility."""
        if self._closed:
            return
        self._closed = True
        for separator, _coordinates, _vertex_indices in self._nodes.values():
            try:
                self._scene_graph.removeChild(separator)
            except (AttributeError, ReferenceError, RuntimeError):
                pass
        self._nodes.clear()
        for view_object, visible in self._visibility:
            try:
                view_object.Visibility = visible
            except (AttributeError, ReferenceError, RuntimeError):
                pass
        self._visibility.clear()
