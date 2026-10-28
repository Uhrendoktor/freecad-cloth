# Copyright (C) 2026 FreeCAD Cloth contributors
"""FreeCAD commands for selecting and editing a persistent draping/collision target."""

import contextlib
from collections.abc import Callable, Sequence
from typing import Protocol, cast

from freecad_cloth.common.CommandAdapter import icon_for_command


class _FreeCADDocument(Protocol):
    """FreeCAD document members required by drape-target commands."""

    Objects: Sequence[object]

    def recompute(self) -> None:
        """Recompute the document after target links are assigned."""
        ...


class _SimulationScene(Protocol):
    """Simulation-scene properties owned by the canonical target model."""

    Document: object
    DrapeTarget: object


class _DrapeTarget(Protocol):
    """Persistent target fields updated by the drape-target commands."""

    CollisionDeflection: float
    CollisionThickness: float
    Enabled: bool
    Label: str


_ACTIVE_DIAGNOSTICS_TASK_PANEL: list[object | None] = [None]
_DEFAULT_TARGET_ENABLED = True


def get_active_diagnostics_task_panel() -> object | None:
    """Return the diagnostics task panel opened by the public command.

    Returns:
        The active task panel, or None before the diagnostics command has run.
    """
    return _ACTIVE_DIAGNOSTICS_TASK_PANEL[0]


def _selected_source() -> object:
    """Return the first selected FreeCAD shape or mesh.

    Returns:
        The first selected object that exposes a Shape or Mesh.

    Raises:
        ValueError: If the current selection contains no shape or mesh.
    """
    import FreeCADGui as Gui

    for obj in Gui.Selection.getSelection():
        if hasattr(obj, "Shape") or hasattr(obj, "Mesh"):
            return obj
    msg = "select a FreeCAD shape or mesh as the drape target"
    raise ValueError(msg)


def _get_document_object(doc: object, object_name: str) -> object | None:
    """Look up a named object through FreeCAD's dynamic document API.

    Args:
        doc: FreeCAD document searched for the object.
        object_name: Internal document name to look up.

    Returns:
        The matching document object, or None if it does not exist.
    """
    getter_attribute = "getObject"
    get_object = cast("Callable[[str], object | None]", getattr(doc, getter_attribute))
    return get_object(object_name)


def _target(doc: object) -> object | None:
    """Find the persistent drape target in a document.

    Args:
        doc: FreeCAD document to search.

    Returns:
        The existing DrapeTarget object, or None when it has not been created.
    """
    return _get_document_object(doc, "DrapeTarget")


def _is_simulation_scene(obj: object) -> bool:
    """Return whether an object represents the canonical cloth simulation scene.

    Args:
        obj: Document object inspected for the simulation marker.

    Returns:
        True for the ClothSimulation object or its proxy, otherwise False.
    """
    return (
        getattr(obj, "Name", "") == "ClothSimulation"
        or getattr(getattr(obj, "Proxy", None), "Type", "") == "ClothSimulation"
    )


def _attach_to_simulation(doc: _FreeCADDocument, target: object) -> None:
    """Attach the one persistent DrapeTarget to every simulation scene in a document.

    Args:
        doc: FreeCAD document containing the target and any simulation scenes.
        target: Persistent target object created or updated by the caller.
    """
    for scene in doc.Objects:
        if _is_simulation_scene(scene):
            cast("_SimulationScene", scene).DrapeTarget = target
    doc.recompute()


def set_drape_target_source(
    scene: object | None,
    source: object | None,
    thickness: float = 2.0,
    deflection: float = 1.0,
) -> object:
    """Assign a persistent collision source through the target-neutral API.

    Args:
        scene: ClothSimulation scene receiving the target link.
        source: Shape, mesh, or mannequin used to construct collision geometry.
        thickness: Collision-surface thickness in millimetres.
        deflection: Collision-mesh tessellation deflection in millimetres.

    Returns:
        The source object assigned to the persistent target.

    Raises:
        ValueError: If the scene is not a simulation scene or the source is absent.
    """
    if scene is None or not _is_simulation_scene(scene):
        msg = "expected a ClothSimulation scene"
        raise ValueError(msg)
    if source is None:
        msg = "a drape target source is required"
        raise ValueError(msg)
    from freecad_cloth.simulation.DrapeTarget import assign_drape_target, create_drape_target

    typed_scene = cast("_SimulationScene", scene)
    doc = cast("_FreeCADDocument", typed_scene.Document)
    target = cast(
        "_DrapeTarget | None",
        getattr(typed_scene, "DrapeTarget", None) or _target(doc),
    )
    target_type = (
        "Mannequin"
        if str(getattr(source, "AvatarType", "")) == "ClothAvatar"
        else "FreeCAD Geometry"
    )
    if target is None:
        target = cast(
            "_DrapeTarget",
            create_drape_target(doc, source, target_type, float(deflection), float(thickness)),
        )
    else:
        target.CollisionDeflection = float(deflection)
        target.CollisionThickness = float(thickness)
        assign_drape_target(target, source, target_type)
    _attach_to_simulation(doc, target)
    if hasattr(scene, "DrapeTarget"):
        typed_scene.DrapeTarget = target
    doc.recompute()
    return source


def create_drape_target_from_selection(
    deflection: float = 1.0,
    thickness: float = 2.0,
) -> object:
    """Create or update a persistent target from the active selection.

    Args:
        deflection: Collision-mesh tessellation deflection in millimetres.
        thickness: Collision-surface thickness in millimetres.

    Returns:
        The created or updated persistent DrapeTarget.
    """
    import FreeCAD as App

    from freecad_cloth.simulation.DrapeTarget import assign_drape_target, create_drape_target

    doc = cast("_FreeCADDocument", App.ActiveDocument or App.newDocument("ClothDrape"))
    source = _selected_source()
    target = cast("_DrapeTarget | None", _target(doc))
    if target is None:
        target = cast(
            "_DrapeTarget",
            create_drape_target(doc, source, "FreeCAD Geometry", deflection, thickness),
        )
    else:
        target.CollisionDeflection = float(deflection)
        target.CollisionThickness = float(thickness)
        assign_drape_target(target, source, "FreeCAD Geometry")
    _attach_to_simulation(doc, target)
    doc.recompute()
    return target


def create_mannequin_drape_target() -> object:
    """Create or update the persistent drape target using the Cloth mannequin.

    Returns:
        The persistent DrapeTarget linked to the mannequin.
    """
    import FreeCAD as App

    from freecad_cloth.avatar.AvatarCommands import create_avatar
    from freecad_cloth.simulation.DrapeTarget import (
        DEFAULT_MANNEQUIN_COLLISION_THICKNESS_MM,
        assign_drape_target,
        create_drape_target,
    )

    doc = cast("_FreeCADDocument", App.ActiveDocument or App.newDocument("ClothDrape"))
    mannequin = _get_document_object(doc, "ClothAvatar") or create_avatar()
    target = cast("_DrapeTarget | None", _target(doc))
    if target is None:
        target = cast(
            "_DrapeTarget",
            create_drape_target(
                doc,
                mannequin,
                "Mannequin",
                1.0,
                DEFAULT_MANNEQUIN_COLLISION_THICKNESS_MM,
            ),
        )
    else:
        target.CollisionDeflection = 1.0
        target.CollisionThickness = DEFAULT_MANNEQUIN_COLLISION_THICKNESS_MM
        assign_drape_target(target, mannequin, "Mannequin")
    target.Label = "Drape Target (Mannequin)"
    _attach_to_simulation(doc, target)
    doc.recompute()
    return target


def edit_drape_target() -> object:
    """Open the native task panel for the current persistent DrapeTarget.

    Returns:
        The task panel instance editing the current target.

    Raises:
        ValueError: If no active document exists or no DrapeTarget has been created.
    """
    import FreeCAD as App

    from freecad_cloth.simulation.DrapeGui import show_drape_target_task

    doc = App.ActiveDocument
    if doc is None:
        msg = "create a document before editing the drape target"
        raise ValueError(msg)
    target = _target(doc)
    if target is None:
        msg = "create a drape target first"
        raise ValueError(msg)
    return show_drape_target_task(target)


def refresh_drape_target() -> object:
    """Rebuild collision metadata from the persistent target source.

    Returns:
        The refreshed persistent DrapeTarget.

    Raises:
        ValueError: If there is no active document or no DrapeTarget to refresh.
    """
    import FreeCAD as App

    from freecad_cloth.simulation.DrapeTarget import refresh_drape_target as refresh_target

    doc = App.ActiveDocument
    if doc is None or _target(doc) is None:
        msg = "create a drape target first"
        raise ValueError(msg)
    target = refresh_target(_target(doc))
    doc.recompute()
    return target


def set_drape_target_enabled(enabled: object = _DEFAULT_TARGET_ENABLED) -> object:
    """Enable or disable collision checks for the persistent DrapeTarget.

    Args:
        enabled: Value coerced to a boolean to preserve the command's existing behavior.

    Returns:
        The updated persistent DrapeTarget.

    Raises:
        ValueError: If there is no active document or no DrapeTarget to update.
    """
    import FreeCAD as App

    doc = App.ActiveDocument
    if doc is None:
        msg = "create a drape target first"
        raise ValueError(msg)
    target = cast("_DrapeTarget | None", _target(doc))
    if target is None:
        msg = "create a drape target first"
        raise ValueError(msg)
    target.Enabled = bool(enabled)
    doc.recompute()
    return target


def show_diagnostics() -> object:
    """Open post-simulation stress, strain, fit, and pressure diagnostics.

    Returns:
        The diagnostics task-panel instance.

    Raises:
        ValueError: If no active FreeCAD document is available.
    """
    import FreeCAD as App

    from freecad_cloth.simulation.ClothDiagnosticsGui import show_diagnostics as show_panel

    doc = App.ActiveDocument
    if doc is None:
        msg = "create a simulation before opening diagnostics"
        raise ValueError(msg)
    panel = show_panel()
    _ACTIVE_DIAGNOSTICS_TASK_PANEL[0] = panel
    return panel


def _has_document() -> bool:
    """Return whether a FreeCAD document is available in the current host.

    Returns:
        True when an active document exists, otherwise False.
    """
    try:
        import FreeCAD as App
    except ImportError:
        return False
    else:
        return App.ActiveDocument is not None


def _has_source_selection() -> bool:
    """Return whether the current GUI selection includes a valid source.

    Returns:
        True when the selection contains a shape or mesh, otherwise False.
    """
    try:
        _selected_source()
    except (ImportError, ValueError):
        return False
    else:
        return True


COMMANDS: list[str] = [
    "ClothDrape_CreateTarget",
    "ClothDrape_CreateMannequinTarget",
    "ClothDrape_EditTarget",
    "ClothDrape_RefreshTarget",
    "ClothDrape_EnableTarget",
    "ClothDrape_DisableTarget",
    "ClothDrape_Diagnostics",
]
_HANDLERS: dict[str, Callable[[], object]] = {
    "ClothDrape_CreateTarget": create_drape_target_from_selection,
    "ClothDrape_CreateMannequinTarget": create_mannequin_drape_target,
    "ClothDrape_EditTarget": edit_drape_target,
    "ClothDrape_RefreshTarget": refresh_drape_target,
    "ClothDrape_EnableTarget": lambda: set_drape_target_enabled(True),
    "ClothDrape_DisableTarget": lambda: set_drape_target_enabled(False),
    "ClothDrape_Diagnostics": show_diagnostics,
}
_TOOLTIPS: dict[str, str] = {
    "ClothDrape_CreateTarget": (
        "Use the selected FreeCAD shape or mesh as the persistent drape target"
    ),
    "ClothDrape_CreateMannequinTarget": "Create or select the Cloth mannequin as the drape target",
    "ClothDrape_EditTarget": "Edit the persistent drape target and collision quality settings",
    "ClothDrape_RefreshTarget": "Rebuild collision geometry from the current drape target source",
    "ClothDrape_EnableTarget": "Enable the persistent drape target",
    "ClothDrape_DisableTarget": "Disable the persistent drape target without clearing its source",
    "ClothDrape_Diagnostics": "Analyze simulated cloth with stress, strain, fit, and pressure maps",
}


class _DrapeCommand:
    """Bridge lower-case Python callables to the FreeCAD command callback contract."""

    def __init__(
        self,
        name: str,
        function: Callable[[], object],
        active: Callable[[], bool],
        tooltip: str,
    ) -> None:
        """Store callbacks and presentation metadata for one GUI command.

        Args:
            name: Stable internal command identifier.
            function: Action invoked when the user activates the command.
            active: Predicate determining whether the command is currently enabled.
            tooltip: User-facing description displayed by FreeCAD.
        """
        self.name = name
        self.function = function
        self.active = active
        self.tooltip = tooltip

    def activated(self) -> object:
        """Invoke the command action selected by its identifier.

        Returns:
            The result returned by the registered action.
        """
        return self.function()

    def is_active(self) -> bool:
        """Return whether the command is available in the current document.

        Returns:
            True when the command predicate permits activation, otherwise False.
        """
        return bool(self.active())

    def get_resources(self) -> dict[str, object]:
        """Return labels, help text, and icon data for the FreeCAD toolbar.

        Returns:
            Resource mapping consumed by the native command registry.
        """
        labels = {
            "ClothDrape_EditTarget": "Edit Drape Target",
            "ClothDrape_RefreshTarget": "Refresh Drape Target",
            "ClothDrape_Diagnostics": "Cloth Diagnostics",
        }
        return {
            "MenuText": labels.get(
                self.name, self.name.replace("ClothDrape_", "").replace("_", " ").title()
            ),
            "ToolTip": self.tooltip,
            "Pixmap": icon_for_command(self.name),
        }

    def __getattr__(self, name: str) -> object:
        """Expose the callback spellings required by FreeCAD without duplicate methods.

        Args:
            name: Host callback name requested by FreeCAD.

        Returns:
            A bound Python callback for a recognized FreeCAD command method.

        Raises:
            AttributeError: If the requested name is not a supported callback.
        """
        callbacks: dict[str, Callable[[], object]] = {
            "Activated": self.activated,
            "IsActive": self.is_active,
            "GetResources": self.get_resources,
        }
        try:
            return callbacks[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def register_gui_commands(gui: object | None = None) -> bool:
    """Register the public drape commands explicitly during workbench initialization.

    Args:
        gui: Optional FreeCAD GUI module; imported lazily when not supplied.

    Returns:
        True if commands are registered, or False when FreeCADGui is unavailable.
    """
    if gui is None:
        try:
            import FreeCADGui as Gui
        except ImportError:
            return False
        gui = Gui
    add_command_attribute = "addCommand"
    add_command = cast("Callable[[str, object], None]", getattr(gui, add_command_attribute))
    for name, function in _HANDLERS.items():
        active = _has_source_selection if name == "ClothDrape_CreateTarget" else _has_document
        add_command(name, _DrapeCommand(name, function, active, _TOOLTIPS[name]))
    return True


with contextlib.suppress(ImportError, AttributeError):
    register_gui_commands()
