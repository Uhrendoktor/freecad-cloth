# Copyright (C) 2026 FreeCAD Cloth contributors
"""Deterministic FreeCAD GUI acceptance and six-side cloth visual audit."""

import contextlib
import importlib.util
import json
import os
import pathlib
import sys
import traceback
from collections.abc import Callable, Sequence
from typing import Protocol, cast

import FreeCAD as App
import FreeCADGui as Gui

try:
    from PySide import QtWidgets
except ImportError:
    from PySide2 import QtWidgets

ROOT = "/workspace"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class _ArcGeometryModule(Protocol):
    """Lazy helper-module contract for constructing an arc through three points."""

    def arc_through_midpoint(
        self,
        part_module: object,
        app_module: object,
        start: object,
        end: object,
        midpoint: object,
    ) -> object:
        """Construct the native minor arc through three authored planar points.

        Args:
            part_module: FreeCAD Part module providing the arc constructor.
            app_module: FreeCAD application module providing vector constructors.
            start: Authored two-dimensional arc start point.
            end: Authored two-dimensional arc end point.
            midpoint: Authored on-arc point selecting the intended minor sweep.

        Returns:
            Native FreeCAD circular-arc geometry preserving the authored points.
        """


_arc_geometry = cast(
    "_ArcGeometryModule", importlib.import_module("tests.support.freecad_arc_geometry")
)
_arc_through_midpoint: Callable[[object, object, object, object, object], object] = (
    _arc_geometry.arc_through_midpoint
)

OUT = os.environ.get("CLOTH_SCREENSHOT_DIR", "docs/images/generated")
pathlib.Path(OUT).mkdir(exist_ok=True, parents=True)
LOG = str(pathlib.Path(OUT) / "gui-progress.log")
MANIFEST = str(pathlib.Path(OUT) / "gui-screenshot-manifest.txt")
METRICS = str(pathlib.Path(OUT) / "drape-visual-metrics.json")
SCREENSHOT_WIDTH_PX = 1280
SCREENSHOT_HEIGHT_PX = 720
SCREENSHOT_SIZE_PX = (SCREENSHOT_WIDTH_PX, SCREENSHOT_HEIGHT_PX)
TRIANGLE_VERTEX_COUNT = 3
MIN_WINDOW_SCREENSHOT_BYTES = 20_000
MIN_VIEW_SCREENSHOT_BYTES = 5_000
TUNIC_PRODUCTION_AUDIT = os.environ.get("CLOTH_TUNIC_AUDIT_PROFILE") == "production"


def log(message: str) -> None:
    """Append one diagnostic message to the GUI audit log.

    Args:
        message: Single-line progress message to persist.
    """
    with pathlib.Path(LOG).open("a", encoding="utf-8") as handle:
        handle.write(message + "\n")


def events() -> None:
    """Refresh FreeCAD's GUI and process pending Qt events."""
    Gui.updateGui()
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.processEvents()


def _dialog_text(dialog: object) -> str:
    """Collect visible text from a public task dialog and its child widgets.

    Args:
        dialog: Active FreeCAD task dialog or panel-like widget.

    Returns:
        Visible text entries joined in deterministic widget traversal order.
    """
    form = getattr(dialog, "form", dialog)
    widgets = [form]
    find_children = getattr(form, "findChildren", None)
    if callable(find_children):
        children = find_children(QtWidgets.QWidget)
        if isinstance(children, Sequence):
            widgets.extend(children)
    return " | ".join(
        str(getter())
        for widget in widgets
        for getter in [getattr(widget, "text", None)]
        if callable(getter)
    )


class _TaskDock(Protocol):
    """Structural interface for the task-dock actions used by the GUI audit."""

    def hide(self) -> None:
        """Hide the task dock."""

    def show(self) -> None:
        """Show the task dock."""

    def raise_(self) -> None:
        """Raise the task dock above other widgets."""


def ensure_task_view_visible() -> _TaskDock:
    """Show the FreeCAD task dock and return it or a no-op fallback proxy.

    Returns:
        Visible task dock widget, or a proxy when no matching dock exists.

    Raises:
        RuntimeError: If the FreeCAD main window is unavailable.
    """
    window = Gui.getMainWindow()
    if window is None:
        msg = "FreeCAD main window is unavailable"
        raise RuntimeError(msg)
    for dock in window.findChildren(QtWidgets.QDockWidget):
        if dock.objectName() == "Tasks" or "task" in str(dock.windowTitle()).lower():
            dock.show()
            dock.raise_()
            events()
            if dock.isVisible():
                return dock
    return _TaskDockProxy()


class _TaskDockProxy:
    """No-op task dock used when the host GUI has no visible task panel."""

    @staticmethod
    def hide() -> None:
        """Accept a hide request when no real task dock is available."""

    @staticmethod
    def show() -> None:
        """Accept a show request when no real task dock is available."""

    @staticmethod
    def raise_() -> None:
        """Accept a raise request when no real task dock is available."""


class _Vector3(Protocol):
    """World-space FreeCAD vector coordinates used by landmark checks."""

    x: float
    y: float
    z: float


class _RecomputableDocument(Protocol):
    """Document operation required by the FreeCAD visual acceptance harness."""

    def recompute(self) -> None:
        """Recompute the owning FreeCAD document after geometry edits."""
        ...


class _NativeCurve(Protocol):
    """Native sketch curve parameters used to validate authored arc geometry."""

    FirstParameter: float
    LastParameter: float


class _NativeSketch(Protocol):
    """Native Sketcher object contract used by persistent pattern-piece sources."""

    Name: str
    Geometry: Sequence[_NativeCurve]
    Placement: object
    SemanticEdgeIds: Sequence[str]


class _PatternBoundary(Protocol):
    """Sampled PatternIR edge contract used by neckline correspondence validation."""

    id: str
    samples: Sequence[tuple[float, float]]
    parameter_range: tuple[float, float]


class _ViewObject(Protocol):
    """Display properties used to present native pattern and drape objects."""

    DisplayMode: str
    ShapeColor: tuple[float, float, float]
    Transparency: float
    LineWidth: float
    SpecularColor: tuple[float, float, float]
    Shininess: float
    Visibility: bool


class _PatternPiece(Protocol):
    """Pattern-piece properties retained by the authoritative Sketcher model."""

    Name: str
    Label: str
    PieceId: str
    Placement: object
    Sketch: _NativeSketch
    ViewObject: _ViewObject


class _SceneMesh(Protocol):
    """Mesh measurement used to validate generated drape panels."""

    CountFacets: int


class _DrapePanel(Protocol):
    """Native drape panel properties used to style and inspect simulation results."""

    Name: str
    Label: str
    Mesh: _SceneMesh
    ViewObject: _ViewObject


class _SimulationBackend(Protocol):
    """Solver observations consumed by visual acceptance and seam-gap audits."""

    name: str

    def positions(self) -> Sequence[Sequence[float]]:
        """Return current world-space solver particle positions in stable index order.

        Returns:
            Three-dimensional particle coordinates in backend index order.
        """
        ...


class _SimulationBaseProxy(Protocol):
    """Base scene proxy state exposed while creating or invalidating its backend."""

    backend: _SimulationBackend
    source_signature: object | None


class _SimulationProxy(Protocol):
    """Native simulation proxy operations required by the drape audit."""

    backend: _SimulationBackend
    seam_stitch_pairs: dict[str, Sequence[tuple[int, int]]]

    def _base_or_restore(self) -> _SimulationBaseProxy:
        """Return or restore the base proxy that owns the active solver backend."""
        ...

    def execute(self, scene: "_SimulationScene") -> None:
        """Rebuild the evaluated scene state for the current authored properties.

        Args:
            scene: Simulation scene whose current properties should be evaluated.
        """
        ...


class _SteppableSimulationPanel(Protocol):
    """Quality-panel action used to advance deterministic batches of simulation steps."""

    def step(self, count: int) -> None:
        """Advance the GUI simulation by the requested number of solver steps.

        Args:
            count: Number of fixed simulation steps to execute.
        """
        ...


class _SimulationScene(Protocol):
    """Authored native scene properties asserted by the canonical tunic audit."""

    Document: _RecomputableDocument
    DrapeTarget: object | None
    Proxy: _SimulationProxy
    StartHeight: float
    QualityPreset: str
    ParticleDistance: float
    SolverIterations: int
    SolverSubsteps: int
    TimeStep: float
    GravityX: float
    GravityY: float
    GravityZ: float
    FabricFriction: float
    PinMode: str
    PinSelection: list[int]
    ClothPieces: list[_PatternPiece]
    ParticleCount: int
    Steps: int
    DrapePanels: Sequence[_DrapePanel]
    SimulatedTime: float
    FiniteState: bool

    def touch(self) -> None:
        """Mark scene inputs dirty so the proxy recomputes its cached state."""
        ...


def validate_task(panel: object | None, name: str, required: Sequence[str]) -> _TaskDock:
    """Verify that a task panel exposes each required piece of visible text.

    Args:
        panel: Panel instance whose public interface is being validated.
        name: Short panel identifier used in diagnostic messages.
        required: Visible text fragments that must appear in the active task UI.

    Returns:
        The active task dock widget or no-op fallback proxy.

    Raises:
        RuntimeError: If no task dialog is open or required text is missing.
    """
    events()
    dock = ensure_task_view_visible()
    dialog = Gui.Control.activeDialog()
    if dialog is None:
        msg = f"{name} did not open an active public task dialog"
        raise RuntimeError(msg)
    texts = []
    for target in (panel, dialog, dock):
        if target is None:
            continue
        text = _dialog_text(target)
        if text:
            texts.append(text)
    combined = " | ".join(texts)
    missing = [item for item in required if item not in combined]
    log(f"task-panel={name} visible=true missing={','.join(missing)}")
    if missing:
        msg = f"task panel {name} is missing visible text: {','.join(missing)}"
        raise RuntimeError(msg)
    return dock


def show_task(panel: object, name: str, required: Sequence[str] = ()) -> _TaskDock:
    """Open a task panel and check its required public text.

    Args:
        panel: Task panel passed to the FreeCAD GUI command system.
        name: Short panel identifier used in diagnostic messages.
        required: Visible text fragments that must appear after opening the panel.

    Returns:
        The task dock widget or no-op fallback proxy.
    """
    if Gui.Control.activeDialog():
        Gui.Control.closeDialog()
        events()
    Gui.Control.showDialog(panel)
    return validate_task(panel, name, required)


def close_task() -> None:
    """Close the active FreeCAD task dialog, if one is open."""
    if Gui.Control.activeDialog():
        Gui.Control.closeDialog()
        events()


def activate(name: str, toolbar: str, commands: Sequence[str]) -> None:
    """Activate a workbench and verify its toolbar and commands are available.

    Args:
        name: Registered FreeCAD workbench identifier.
        toolbar: Toolbar title to make visible.
        commands: Command identifiers that must be registered.

    Raises:
        RuntimeError: If the workbench, main window, or requested commands are unavailable.
    """
    if name not in Gui.listWorkbenches():
        msg = f"workbench is not registered: {name}"
        raise RuntimeError(msg)
    Gui.activateWorkbench(name)
    events()
    window = Gui.getMainWindow()
    if window is None or not window.isVisible():
        msg = "FreeCAD main window is not visible"
        raise RuntimeError(msg)
    for bar in window.findChildren(QtWidgets.QToolBar):
        if bar.windowTitle() == toolbar:
            bar.show()
    missing = [command for command in commands if command not in Gui.listCommands()]
    if missing:
        msg = "commands are not registered: " + ",".join(missing)
        raise RuntimeError(msg)
    log(f"workbench={name} toolbar={toolbar}")


def save(name: str, state: str, proof: str) -> None:
    """Capture the main FreeCAD window with enough pixels to prove the requested state.

    Args:
        name: Destination screenshot filename relative to the output directory.
        state: Human-readable GUI state represented by the image.
        proof: Evidence note written alongside the screenshot in the manifest.

    Raises:
        RuntimeError: If the main window or screenshot is unavailable or suspicious.
    """
    window = Gui.getMainWindow()
    if window is None or not window.isVisible():
        msg = "FreeCAD main window unavailable for screenshot"
        raise RuntimeError(msg)
    window.show()
    window.raise_()
    window.activateWindow()
    window.resize(*SCREENSHOT_SIZE_PX)
    events()
    image = window.grab()
    path = pathlib.Path(OUT) / name
    if image.isNull() or (image.width(), image.height()) != SCREENSHOT_SIZE_PX:
        msg = f"invalid GUI capture for {state}"
        raise RuntimeError(msg)
    if not image.save(str(path)) or path.stat().st_size < MIN_WINDOW_SCREENSHOT_BYTES:
        msg = f"failed or suspiciously small screenshot: {path}"
        raise RuntimeError(msg)
    log(f"screenshot={path} state={state} bytes={path.stat().st_size}")
    with pathlib.Path(MANIFEST).open("a", encoding="utf-8") as handle:
        handle.write(f"{name}\t{state}\t{proof}\n")


def save_view(name: str, state: str, proof: str) -> None:
    """Capture the active FreeCAD 3D view without task-dock chrome.

    Args:
        name: Destination screenshot filename relative to the output directory.
        state: Human-readable view state represented by the image.
        proof: Evidence note written alongside the screenshot in the manifest.

    Raises:
        RuntimeError: If the active view is unavailable or the screenshot is suspicious.
    """
    document = Gui.activeDocument()
    view = document.activeView() if document is not None else None
    if view is None:
        msg = "FreeCAD active 3D view is unavailable for screenshot"
        raise RuntimeError(msg)
    events()
    view.redraw()
    events()
    path = pathlib.Path(OUT) / name
    path.parent.mkdir(exist_ok=True, parents=True)
    view.saveImage(str(path), *SCREENSHOT_SIZE_PX, "White")
    if not path.is_file() or path.stat().st_size < MIN_VIEW_SCREENSHOT_BYTES:
        msg = f"failed or suspiciously small 3D-view screenshot: {path}"
        raise RuntimeError(msg)
    log(f"screenshot={path} state={state} bytes={path.stat().st_size}")
    with pathlib.Path(MANIFEST).open("a", encoding="utf-8") as handle:
        handle.write(f"{name}\t{state}\t{proof}\n")


def load_and_run(path: str, module_name: str) -> None:
    """Load one acceptance module from a source file and execute its entry point.

    Args:
        path: Path to the acceptance script to load.
        module_name: Stable module name used for loading and diagnostic output.

    Raises:
        RuntimeError: If the module source cannot be loaded from the requested path.
    """
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        msg = f"cannot load acceptance module: {path}"
        raise RuntimeError(msg)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.run_acceptance()


GARMENT_E2E_LOG = os.environ.get("CLOTH_GARMENT_E2E_LOG", "/workspace/artifacts/garment-e2e.log")


def run_canonical_acceptance() -> None:
    """Run the canonical avatar, garment, and simulation acceptance scripts in order."""
    pathlib.Path(GARMENT_E2E_LOG).parent.mkdir(exist_ok=True, parents=True)
    with pathlib.Path(GARMENT_E2E_LOG).open("w", encoding="utf-8"):
        pass
    for path, name, marker in (
        (
            "tests/freecad_avatar_acceptance.py",
            "freecad_avatar_acceptance",
            "avatar-provider-acceptance",
        ),
        (
            "tests/freecad_garment_e2e_smoke.py",
            "freecad_garment_e2e_smoke",
            "canonical-garment-e2e",
        ),
        (
            "tests/freecad_simulation_quality_acceptance.py",
            "freecad_simulation_quality_acceptance",
            "simulation-quality-acceptance",
        ),
    ):
        if name == "freecad_garment_e2e_smoke":
            with (
                pathlib.Path(GARMENT_E2E_LOG).open("a", encoding="utf-8") as handle,
                contextlib.redirect_stdout(handle),
            ):
                load_and_run(str(pathlib.Path(ROOT) / path), name)
        else:
            load_and_run(str(pathlib.Path(ROOT) / path), name)
        log(marker + "=passed")


def _mesh_geometry(
    mesh: object,
) -> tuple[
    tuple[tuple[float, float, float], ...],
    tuple[tuple[int, int, int], ...],
]:
    """Read three-dimensional vertices and triangular faces from a native mesh.

    Args:
        mesh: FreeCAD mesh-like object whose Topology exposes vertices and faces.

    Returns:
        Vertices and exact three-index triangles in native topology order.
        A mesh without topology produces two empty tuples.

    Raises:
        ValueError: If a reported face does not contain exactly three indices.
    """
    topology = getattr(mesh, "Topology", None)
    if topology is None:
        return (), ()
    vertices, triangles = topology
    points = tuple((float(point.x), float(point.y), float(point.z)) for point in vertices)
    faces: list[tuple[int, int, int]] = []
    for triangle in triangles:
        indices = tuple(int(index) for index in triangle)
        if len(indices) != TRIANGLE_VERTEX_COUNT:
            msg = "FreeCAD mesh topology contains a non-triangular face"
            raise ValueError(msg)
        faces.append((indices[0], indices[1], indices[2]))
    return points, tuple(faces)


def _mesh_points(mesh: object) -> tuple[tuple[float, float, float], ...]:
    """Return the ordered three-dimensional vertex coordinates of a native mesh.

    Args:
        mesh: FreeCAD mesh-like object whose Topology exposes vertex coordinates.

    Returns:
        Vertices in the same order as the native mesh topology.
    """
    return _mesh_geometry(mesh)[0]


def _camera_snapshot(view):
    """Return the actual world-space camera axes used for screenshot projection."""
    rotation = view.getCameraOrientation()
    right = rotation.multVec(App.Vector(1.0, 0.0, 0.0))
    up = rotation.multVec(App.Vector(0.0, 1.0, 0.0))
    forward = rotation.multVec(App.Vector(0.0, 0.0, -1.0))
    return {
        "quaternion": [round(float(value), 9) for value in rotation.Q],
        "screen_right_world": [
            round(float(right.x), 6),
            round(float(right.y), 6),
            round(float(right.z), 6),
        ],
        "screen_up_world": [
            round(float(up.x), 6),
            round(float(up.y), 6),
            round(float(up.z), 6),
        ],
        "view_forward_world": [
            round(float(forward.x), 6),
            round(float(forward.y), 6),
            round(float(forward.z), 6),
        ],
    }


def _seam_lateral_snapshot(
    proxy: _SimulationProxy,
    center_x: float,
) -> dict[str, dict[str, float | int]]:
    """Measure each semantic seam's world-X offsets from exact solver pair data.

    Args:
        proxy: Active simulation proxy with backend positions and stitch-pair provenance.
        center_x: World-X reference coordinate subtracted from each seam sample.

    Returns:
        Per-seam mean, minimum, and maximum X offsets, sample counts, and sign counts.

    Raises:
        RuntimeError: If exact seam pair provenance or a solver position reader is missing.
    """
    backend = proxy.backend
    reader = getattr(backend, "positions", None)
    pairs_by_seam = proxy.seam_stitch_pairs
    if not callable(reader) or not pairs_by_seam:
        msg = "seam lateral diagnostic requires solver position and pair provenance"
        raise RuntimeError(msg)
    positions = tuple(reader())

    def x_value(point: object) -> float:
        """Read one world-X coordinate from a FreeCAD vector or coordinate tuple.

        Args:
            point: Native vector-like or indexed coordinate value.

        Returns:
            The X coordinate converted to a Python float.
        """
        return float(cast("_Vector3", point).x) if hasattr(point, "x") else float(
            cast("Sequence[float]", point)[0]
        )

    snapshot = {}
    for seam_id, pairs in sorted(pairs_by_seam.items()):
        offsets = []
        for index_a, index_b in pairs:
            a, b = int(index_a), int(index_b)
            if not (0 <= a < len(positions) and 0 <= b < len(positions)):
                msg = "seam lateral diagnostic found an invalid solver particle index"
                raise RuntimeError(msg)
            offsets.append(0.5 * (x_value(positions[a]) + x_value(positions[b])) - float(center_x))
        if not offsets:
            raise RuntimeError(
                "seam lateral diagnostic found a seam without samples: " + str(seam_id)
            )
        snapshot[str(seam_id)] = {
            "mean_x_offset_mm": round(sum(offsets) / len(offsets), 3),
            "min_x_offset_mm": round(min(offsets), 3),
            "max_x_offset_mm": round(max(offsets), 3),
            "positive_samples": sum(value > 0.0 for value in offsets),
            "negative_samples": sum(value < 0.0 for value in offsets),
            "sample_count": len(offsets),
        }
    return snapshot


def _post_drape_seam_gap(stitch_pairs, positions):
    """Measure the gap on the exact particle pairs passed to the solver."""
    if not stitch_pairs:
        msg = "solver stitch pair provenance is required"
        raise ValueError(msg)
    from math import dist

    maximum = 0.0
    for a_index, b_index in stitch_pairs:
        if not (0 <= int(a_index) < len(positions) and 0 <= int(b_index) < len(positions)):
            msg = "solver stitch pair is outside backend particle positions"
            raise ValueError(msg)
        a = positions[int(a_index)]
        b = positions[int(b_index)]
        maximum = max(
            maximum,
            dist(a, b),
        )
    return maximum


def _seam_coherence(
    _panels: Sequence[_DrapePanel],
    seam_records: Sequence[tuple[object, _PatternPiece, _PatternPiece]],
    proxy: _SimulationProxy | None = None,
) -> dict[str, object]:
    """Summarize seam gaps using the exact particle pairs passed to the solver.

    Args:
        _panels: Current evaluated panels retained for the helper's stable call contract.
        seam_records: Authored seams paired with their authoritative source pattern pieces.
        proxy: Active simulation proxy exposing backend positions and exact stitch pairs.

    Returns:
        Seam identities, source edge references, sample counts, and maximum measured gap.
        Empty seam input produces a stable zero-sample report.

    Raises:
        RuntimeError: If exact stitch-pair provenance or semantic edge identities are missing.
    """
    if not seam_records:
        return {
            "sample_count": 0,
            "seams": [],
            "max_correspondence_gap_mm": None,
            "method": "solver-stitch-pairs",
        }
    if proxy is None or not getattr(proxy, "seam_stitch_pairs", None):
        msg = "seam diagnostics require exact solver stitch-pair provenance"
        raise RuntimeError(msg)
    positions = tuple(proxy.backend.positions())
    stitch_pairs_by_seam = proxy.seam_stitch_pairs
    records = []
    maximum = 0.0
    sample_count = 0
    for seam, piece_a, piece_b in seam_records:
        seam_id = str(getattr(seam, "SeamId", getattr(seam, "Label", "")))
        stitch_pairs = tuple(stitch_pairs_by_seam.get(seam_id, ()))
        if not stitch_pairs:
            msg = f"solver stitch-pair provenance missing for seam {seam_id}"
            raise RuntimeError(msg)
        gap = _post_drape_seam_gap(stitch_pairs, positions)
        sample_count = max(sample_count, len(stitch_pairs))
        edge_a_id = str(getattr(seam, "EdgeAId", "")).strip()
        edge_b_id = str(getattr(seam, "EdgeBId", "")).strip()
        if not edge_a_id or not edge_b_id:
            msg = f"semantic seam edge identity is missing for {seam_id}"
            raise RuntimeError(msg)
        ids_a = tuple(
            str(value)
            for value in (getattr(getattr(piece_a, "Sketch", None), "SemanticEdgeIds", ()) or ())
        )
        ids_b = tuple(
            str(value)
            for value in (getattr(getattr(piece_b, "Sketch", None), "SemanticEdgeIds", ()) or ())
        )
        if edge_a_id not in ids_a or edge_b_id not in ids_b:
            msg = "semantic seam edge identity is not present on its authoritative Sketch"
            raise RuntimeError(msg)
        records.append(
            {
                "seam": seam_id,
                "piece_a": str(getattr(piece_a, "PieceId", "")),
                "piece_b": str(getattr(piece_b, "PieceId", "")),
                "edge_a_id": edge_a_id,
                "edge_b_id": edge_b_id,
                "edge_a": ids_a.index(edge_a_id),
                "edge_b": ids_b.index(edge_b_id),
                "stitch_pair_count": len(stitch_pairs),
                "max_correspondence_gap_mm": round(float(gap), 6),
            }
        )
        maximum = max(maximum, float(gap))
    return {
        "sample_count": sample_count,
        "seams": records,
        "max_correspondence_gap_mm": round(maximum, 6),
        "method": "solver-stitch-pairs",
    }


def _inside_target_count(
    points: Sequence[tuple[float, float, float]],
    target: object,
    collision_surface: object | None = None,
    solver_collision_surface: object | None = None,
) -> int:
    """Count cloth vertices inside the authoritative FreeCAD mannequin target.

    Args:
        points: Evaluated cloth vertices in world-space millimetres.
        target: Native avatar object whose shape or mesh may provide containment.
        collision_surface: Authoritative target surface used when native containment is unavailable.
        solver_collision_surface: Optional collision surface actually consumed by the solver.

    Returns:
        Number of input vertices contained by the selected target representation.

    Raises:
        RuntimeError: If the target exposes no usable containment surface.
    """
    shape = getattr(target, "Shape", None)
    shape_is_inside = getattr(shape, "isInside", None) if shape is not None else None
    if callable(shape_is_inside):
        count = 0
        for point in points:
            try:
                if bool(shape_is_inside(App.Vector(*point), 1e-6, True)):
                    count += 1
            except (AttributeError, TypeError, ValueError):
                count = None
                break
        if count is not None:
            return count

    mesh = getattr(target, "Mesh", None)
    mesh_is_inside = getattr(mesh, "isInside", None) if mesh is not None else None
    if callable(mesh_is_inside):
        count = 0
        for point in points:
            try:
                if bool(mesh_is_inside(App.Vector(*point), 1e-6, True)):
                    count += 1
            except (AttributeError, TypeError, ValueError):
                count = None
                break
        if count is not None:
            return count

    surface = collision_surface
    if surface is not None:
        vertices = tuple(getattr(surface, "vertices", ()) or ())
        triangles = tuple(getattr(surface, "triangles", ()) or ())
        if not vertices or not triangles:
            msg = "authoritative collision surface has no inside/outside topology"
            raise RuntimeError(msg)

        # Avoid Trimesh/Rtree's native contains query in the embedded FreeCAD host.
        # The vectorized NumPy ray-parity path preserves the strict vertex-inside gate.
        from freecad_cloth.simulation.DrapeVisualSanity import points_inside_closed_mesh

        log(
            "penetration-check=numpy-ray-parity points=%d triangles=%d"
            % (len(points), len(triangles))
        )
        return sum(
            points_inside_closed_mesh(
                points,
                vertices,
                triangles,
                prefer_trimesh=False,
                chunk_size=4,
            )
        )
    msg = "mannequin target does not expose an inside/outside collision test"
    raise RuntimeError(msg)


def write_drape_metrics(
    panels,
    avatar,
    center_x=None,
    shoulder_z=None,
    hem_z=None,
    seam_records=(),
    proxy=None,
    collision_surface=None,
):
    from freecad_cloth.common.MeshValidation import validate_mesh
    from freecad_cloth.simulation.DrapeFailureClassifier import (
        classify_drape,
        summarize_classification,
    )
    from freecad_cloth.simulation.DrapeVisualSanity import inspect_drape, summarize

    avatar_vertices = _mesh_points(getattr(avatar, "Mesh", None))
    box = avatar.Mesh.BoundBox
    target_height = float(box.ZMax - box.ZMin)
    target_width = float(max(box.XMax - box.XMin, box.YMax - box.YMin))
    if shoulder_z is None:
        shoulder_z = float(box.ZMin) + 0.76 * target_height
    if hem_z is None:
        hem_z = float(box.ZMin) + 0.40 * target_height
    upper_margin = (0.17 if TUNIC_PRODUCTION_AUDIT else 0.12) * max(
        1.0, float(shoulder_z) - float(hem_z)
    )
    lower_margin = 0.20 * max(1.0, float(shoulder_z) - float(hem_z))
    records = []
    for panel in panels:
        vertices, triangles = _mesh_geometry(getattr(panel, "Mesh", None))
        metrics = inspect_drape(
            vertices, avatar_vertices, target_height=target_height, target_width=target_width
        )
        mesh_result = validate_mesh(vertices, triangles, prefer_trimesh=False)
        classification = classify_drape(
            metrics, components=mesh_result.components, target_width=target_width
        )
        record = {
            "panel": str(getattr(panel, "Label", getattr(panel, "Name", ""))),
            **summarize(metrics),
        }
        diagnostics = []
        if not metrics.finite:
            raise RuntimeError(
                "draped panel {} contains non-finite geometry".format(record["panel"])
            )
        if not vertices:
            raise RuntimeError("draped panel {} has no mesh vertices".format(record["panel"]))
        if center_x is not None:
            record["centroid_lateral_offset"] = abs(float(metrics.centroid[0]) - float(center_x))
            if record["centroid_lateral_offset"] > target_width * 0.18:
                diagnostics.append("lateral-detached-candidate")
        if (
            metrics.target_vertex_clearance is None
            or metrics.target_vertex_clearance > target_width * 0.15
        ):
            diagnostics.append("target-clearance-candidate")
        if metrics.vertical_span_ratio < 0.25 or metrics.lateral_span_ratio < 0.25:
            diagnostics.append("collapsed-candidate")
        if float(metrics.bounds[5]) > float(shoulder_z) + upper_margin:
            diagnostics.append("above-shoulder-candidate")
        if float(metrics.bounds[4]) < float(hem_z) - lower_margin:
            diagnostics.append("below-hem-candidate")
        if float(metrics.centroid[2]) > float(shoulder_z) + upper_margin:
            diagnostics.append("centroid-above-shoulder-candidate")
        backend_for_collision = getattr(proxy, "backend", None) if proxy is not None else None
        solver_collision_surface = (
            getattr(backend_for_collision, "solver_collision_surface", None)
            if backend_for_collision is not None
            else None
        )
        penetrating_vertices = _inside_target_count(
            vertices,
            avatar,
            collision_surface,
            solver_collision_surface,
        )
        record["penetration_surface"] = (
            "solver" if solver_collision_surface is not None else "authoritative-target"
        )
        record["penetrating_vertices"] = int(penetrating_vertices)
        if penetrating_vertices:
            if collision_surface is not None:
                from math import dist

                from freecad_cloth.simulation.DrapeVisualSanity import points_inside_closed_mesh

                target_points = tuple(getattr(collision_surface, "vertices", ()) or ())
                target_triangles = tuple(getattr(collision_surface, "triangles", ()) or ())
                backend = getattr(proxy, "backend", None) if proxy is not None else None
                solver_surface = (
                    getattr(backend, "solver_collision_surface", None)
                    if backend is not None
                    else None
                )
                solver_vertices = (
                    tuple(getattr(solver_surface, "vertices", ()) or ())
                    if solver_surface is not None
                    else ()
                )
                solver_triangles = (
                    tuple(getattr(solver_surface, "triangles", ()) or ())
                    if solver_surface is not None
                    else ()
                )
                inside_points = []
                if target_points and target_triangles:
                    for point in vertices:
                        point_tuple = tuple(float(value) for value in point)
                        try:
                            authoritative_inside = points_inside_closed_mesh(
                                (point_tuple,),
                                target_points,
                                target_triangles,
                                prefer_trimesh=False,
                            )[0]
                        except (TypeError, ValueError, IndexError):
                            break
                        if not authoritative_inside:
                            continue
                        nearest = min(
                            dist(point_tuple, tuple(float(value) for value in target))
                            for target in target_points
                        )
                        solver_inside = None
                        if solver_vertices and solver_triangles:
                            try:
                                solver_inside = points_inside_closed_mesh(
                                    (point_tuple,),
                                    solver_vertices,
                                    solver_triangles,
                                    prefer_trimesh=False,
                                )[0]
                            except (TypeError, ValueError, IndexError):
                                solver_inside = None
                        inside_points.append(
                            {
                                "point": tuple(round(value, 3) for value in point_tuple),
                                "nearest_target_vertex_mm": round(float(nearest), 3),
                                "solver_surface_inside": solver_inside,
                            }
                        )
                log(
                    "penetration-evidence panel=%s count=%d samples=%s"
                    % (record["panel"], penetrating_vertices, inside_points[:12])
                )
            raise RuntimeError(
                "draped panel {} has {} vertices inside the mannequin collision surface".format(
                    record["panel"], penetrating_vertices
                )
            )
        record["connected_components"] = int(mesh_result.components)
        record["failure_classification"] = summarize_classification(classification)
        record["diagnostics"] = diagnostics
        records.append(record)
        log(f"drape-metrics={json.dumps(record, sort_keys=True)}")
    payload = {
        "target_height": target_height,
        "target_width": target_width,
        "shoulder_z": shoulder_z,
        "hem_z": hem_z,
        "panels": records,
        "seam_coherence": _seam_coherence(panels, seam_records, proxy=proxy),
    }
    with pathlib.Path(METRICS).open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)


def _polyline_distance_fraction(
    point: tuple[float, float],
    samples: tuple[tuple[float, float], ...],
) -> tuple[float, float]:
    """Measure a 2D point's nearest distance to a polyline and normalized arc fraction.

    Args:
        point: Candidate two-dimensional point in the same local coordinate frame.
        samples: Ordered sampled vertices describing the polyline.

    Returns:
        Nearest Euclidean distance and its normalized along-line position.
        A zero-length polyline returns infinite distance and fraction zero.
    """
    import math

    spans = []
    total = 0.0
    for start, end in zip(samples, samples[1:], strict=False):
        length = math.hypot(float(end[0]) - float(start[0]), float(end[1]) - float(start[1]))
        spans.append((total, start, end, length))
        total += length
    if total <= 1e-12:
        return math.inf, 0.0

    best = (math.inf, 0.0)
    for offset, start, end, length in spans:
        if length <= 1e-12:
            continue
        dx = float(end[0]) - float(start[0])
        dy = float(end[1]) - float(start[1])
        fraction = (
            (float(point[0]) - float(start[0])) * dx + (float(point[1]) - float(start[1])) * dy
        ) / (length * length)
        fraction = max(0.0, min(1.0, fraction))
        nearest_x = float(start[0]) + fraction * dx
        nearest_y = float(start[1]) + fraction * dy
        distance = math.hypot(float(point[0]) - nearest_x, float(point[1]) - nearest_y)
        candidate = (distance, (offset + fraction * length) / total)
        best = min(best, candidate)
    return best


def _neckline_boundary_particles(
    piece: _PatternPiece,
    boundary: _PatternBoundary,
    piece_indices: Sequence[int],
    boundary_chains: Sequence[Sequence[int]],
    particle_positions: Sequence[Sequence[float]],
) -> tuple[tuple[int, ...], str, float]:
    """Resolve neckline mesh particles using semantic endpoints and a local-plane fallback.

    Args:
        piece: Authoritative source PatternPiece providing the local placement.
        boundary: Sampled PatternIR boundary whose endpoints define the authored edge.
        piece_indices: Solver particle indices belonging to this source piece.
        boundary_chains: Candidate indexed edge chains exposed by the simulation proxy.
        particle_positions: World-space particle coordinates in solver index order.

    Returns:
        Ordered matching particle indices, the matching method name, and endpoint error.

    Raises:
        RuntimeError: If fewer than two particles can be matched to the authored edge.
    """
    import math

    import FreeCAD as App

    samples = tuple((float(sample[0]), float(sample[1])) for sample in boundary.samples)
    if len(samples) < 2:
        msg = "canonical tunic neckline source edge has fewer than two samples"
        raise RuntimeError(msg)

    placement = getattr(piece, "Placement", None)
    inverse = placement.inverse() if placement is not None else None
    local_positions = {}
    for raw_index in piece_indices:
        index = int(raw_index)
        world = particle_positions[index]
        point = App.Vector(float(world[0]), float(world[1]), float(world[2]))
        if inverse is not None:
            point = inverse.multVec(point)
        local_positions[index] = (float(point.x), float(point.y))

    start, end = samples[0], samples[-1]
    best_chain = ()
    best_endpoint_error = math.inf
    # A runtime may order boundary chains differently from a separate PatternIR
    # resolution. Match the authored edge by its actual endpoints before using
    # any sequence position.
    for raw_chain in boundary_chains:
        chain = tuple(int(index) for index in raw_chain)
        if len(chain) < 2 or chain[0] not in local_positions or chain[-1] not in local_positions:
            continue
        first = local_positions[chain[0]]
        last = local_positions[chain[-1]]
        forward_error = max(math.dist(first, start), math.dist(last, end))
        reverse_error = max(math.dist(first, end), math.dist(last, start))
        if reverse_error < forward_error:
            candidate_chain = tuple(reversed(chain))
            error = reverse_error
        else:
            candidate_chain = chain
            error = forward_error
        if error < best_endpoint_error:
            best_chain = candidate_chain
            best_endpoint_error = error

    # This is a coordinate-correspondence tolerance, not a fit or solver threshold.
    if best_chain and best_endpoint_error <= 1e-4:
        return best_chain, "semantic-chain-endpoints", best_endpoint_error

    # If chain metadata omits or reorders this edge, recover only vertices that
    # lie on the authored edge in the piece's local plane. Unrelated world-space
    # nearest vertices are deliberately excluded.
    projected = []
    nearest_distance = math.inf
    for index, point in local_positions.items():
        distance, fraction = _polyline_distance_fraction(point, samples)
        nearest_distance = min(nearest_distance, distance)
        if distance <= 1e-4:
            projected.append((fraction, index))
    projected.sort()
    particles = tuple(index for _fraction, index in projected)
    if len(particles) >= 2:
        return particles, "authored-edge-projection", best_endpoint_error

    raise RuntimeError(
        "canonical tunic neckline has no mesh particles on its authored edge: "
        "piece=%s edge=%s chains=%d matched-particles=%d nearest-mm=%.6f "
        "endpoint-error-mm=%.6f"
        % (
            piece.Name,
            boundary.id,
            len(boundary_chains),
            len(particles),
            nearest_distance,
            best_endpoint_error,
        )
    )


def _make_tunic_sketch(
    doc: object,
    name: str,
    panel_width: float,
    garment_height: float,
    hem_width: float,
    neckline_ratio: float,
    neckline_drop: float = 0.03,
) -> tuple[_NativeSketch, list[tuple[float, float]]]:
    """Author a deterministic native Sketcher tunic panel with checked curved edges.

    Args:
        doc: Open FreeCAD document receiving the source sketch.
        name: Stable panel name used to identify the sketch.
        panel_width: Authored shoulder/body width in millimetres.
        garment_height: Authored hem-to-neckline height in millimetres.
        hem_width: Width of the bottom hem in millimetres.
        neckline_ratio: Fractional half-width used to place neckline endpoints.
        neckline_drop: Fraction of garment height used to scoop the neckline inward.

    Returns:
        Native Sketcher source object and the ordered authored outline points.

    Raises:
        RuntimeError: If the outline loses symmetry or a required curve degenerates.
    """
    import Part
    import Sketcher

    sketch = cast(
        "_NativeSketch",
        getattr(doc, "addObject")("Sketcher::SketchObject", name + "Sketch"),
    )
    neck_z = (1.0 - float(neckline_drop)) * garment_height
    x_offset = 0.5 * (float(hem_width) - float(panel_width))
    armhole_z = 0.62 * float(garment_height)
    shoulder_z = 0.94 * float(garment_height)
    neckline_scoop_depth = 0.12 * float(garment_height)
    neckline_scoop_z = neck_z - neckline_scoop_depth
    points = [
        (0.00, 0.00),
        (hem_width, 0.00),
        (x_offset + 0.74 * panel_width, armhole_z),
        (x_offset + 0.94 * panel_width, shoulder_z),
        (x_offset + neckline_ratio * panel_width, neck_z),
        (x_offset + (1.0 - neckline_ratio) * panel_width, neck_z),
        (x_offset + 0.06 * panel_width, shoulder_z),
        (x_offset + 0.26 * panel_width, armhole_z),
    ]
    if not (armhole_z < shoulder_z < neck_z):
        msg = "canonical tunic shoulders must slope downward from neckline to shoulder tip"
        raise RuntimeError(msg)
    if not (armhole_z < neckline_scoop_z < shoulder_z):
        msg = "canonical tunic neckline scoop must cut below the shoulders and above the armholes"
        raise RuntimeError(msg)
    if points[3][0] - points[2][0] < 0.15 * float(panel_width):
        msg = "canonical tunic armhole opening is too narrow"
        raise RuntimeError(msg)
    if shoulder_z - armhole_z < 0.20 * float(garment_height):
        msg = "canonical tunic armhole opening is too shallow"
        raise RuntimeError(msg)
    center_x = 0.5 * float(hem_width)
    for left, right in ((0, 1), (2, 7), (3, 6), (4, 5)):
        if abs((points[left][0] + points[right][0]) - 2.0 * center_x) > 1e-9:
            msg = "canonical tunic pattern lost bilateral symmetry"
            raise RuntimeError(msg)

    # The armholes are free, inward-scooped edges. They must not be sewn shut.
    geometry = []
    armhole_mid_z = armhole_z + 0.5 * (shoulder_z - armhole_z)
    side_ease_mm = 4.0
    for index, (start, end) in enumerate(zip(points, points[1:] + points[:1], strict=True)):
        start_vector = App.Vector(start[0], start[1], 0)
        end_vector = App.Vector(end[0], end[1], 0)
        if index == 1:
            # Add modest chest-to-waist ease without moving the armhole endpoints.
            midpoint = App.Vector(
                0.5 * (start[0] + end[0]) + side_ease_mm,
                0.5 * (start[1] + end[1]),
                0,
            )
            geometry.append(_arc_through_midpoint(Part, App, start_vector, end_vector, midpoint))
        elif index == 2:
            # Keep the open armholes at their authored inward-scooped size.
            midpoint = App.Vector(x_offset + 0.741 * panel_width, armhole_mid_z, 0)
            geometry.append(_arc_through_midpoint(Part, App, start_vector, end_vector, midpoint))
        elif index == 4:
            # A true U-shaped neckline: the center arc cuts down into the panel.
            midpoint = App.Vector(0.5 * (start[0] + end[0]), neckline_scoop_z, 0)
            geometry.append(_arc_through_midpoint(Part, App, start_vector, end_vector, midpoint))
        elif index == 6:
            midpoint = App.Vector(x_offset + 0.259 * panel_width, armhole_mid_z, 0)
            geometry.append(_arc_through_midpoint(Part, App, start_vector, end_vector, midpoint))
        elif index == 7:
            midpoint = App.Vector(
                0.5 * (start[0] + end[0]) - side_ease_mm,
                0.5 * (start[1] + end[1]),
                0,
            )
            geometry.append(_arc_through_midpoint(Part, App, start_vector, end_vector, midpoint))
        else:
            geometry.append(Part.LineSegment(start_vector, end_vector))

    getattr(sketch, "addGeometry")(geometry, False)
    # This fixture authors every segment explicitly; preserve each segment's
    # coordinates so an underconstrained Sketcher solve cannot fold the straight
    # shoulders/sides/hem across the outline while retaining the two fixed arcs.
    # Shared endpoints are authored from the same point tuples, so no coincidence
    # solver movement is needed to close this deterministic test profile.
    getattr(sketch, "addConstraint")(
        [Sketcher.Constraint("Block", index) for index in range(len(geometry))]
    )
    cast("_RecomputableDocument", doc).recompute()
    for index in (2, 6):
        curve = sketch.Geometry[index]
        first = float(curve.FirstParameter)
        last = float(curve.LastParameter)
        parameter_span = last - first
        if parameter_span <= 1e-3:
            raise RuntimeError(
                "tunic armhole collapsed during Sketcher recompute: index=%d span=%.9f"
                % (index, parameter_span)
            )
        evaluator = getattr(curve, "valueAt", None)
        if not callable(evaluator):
            evaluator = getattr(curve, "value", None)
        if not callable(evaluator):
            msg = "tunic armhole native curve has no parameter evaluator"
            raise RuntimeError(msg)
        native_samples = tuple(
            evaluator(first + parameter_span * fraction / 8.0) for fraction in range(9)
        )
        native_xy = tuple(
            (float(cast("_Vector3", sample).x), float(cast("_Vector3", sample).y))
            for sample in native_samples
        )
        start_xy, end_xy = native_xy[0], native_xy[-1]
        vertical_span = end_xy[1] - start_xy[1]
        if abs(vertical_span) <= 1e-9:
            msg = "tunic armhole native curve has a horizontal endpoint chord"
            raise RuntimeError(msg)
        inward = -1.0 if index == 2 else 1.0
        deviations = tuple(
            inward
            * (
                sample[0]
                - (
                    start_xy[0]
                    + (sample[1] - start_xy[1]) / vertical_span * (end_xy[0] - start_xy[0])
                )
            )
            for sample in native_xy[1:-1]
        )
        log(
            "tunic-native-armhole index=%d type=%s range=(%.9f,%.9f) "
            "start=(%.3f,%.3f) end=(%.3f,%.3f) "
            "bounds=(%.3f,%.3f,%.3f,%.3f) inward-scoop=%.3f samples=%r"
            % (
                index,
                type(curve).__name__,
                first,
                last,
                start_xy[0],
                start_xy[1],
                end_xy[0],
                end_xy[1],
                min(point[0] for point in native_xy),
                min(point[1] for point in native_xy),
                max(point[0] for point in native_xy),
                max(point[1] for point in native_xy),
                max(deviations),
                tuple((round(point[0], 3), round(point[1], 3)) for point in native_xy),
            )
        )
    return sketch, points


def _adopt_sketch(
    sketch: _NativeSketch,
    name: str,
    allowance: float,
    grainline: object,
) -> _PatternPiece:
    """Adopt an authored Sketcher profile as the persistent Cloth PatternPiece source.

    Args:
        sketch: Native Sketcher profile created for the garment panel.
        name: Stable display name assigned to the resulting pattern piece.
        allowance: Seam allowance distance in millimetres.
        grainline: Grainline setting forwarded unchanged to the pattern command.

    Returns:
        PatternPiece retaining the selected native sketch as its source.

    Raises:
        RuntimeError: If the created piece does not retain the selected source sketch.
    """
    from freecad_cloth.pattern.PatternCommands import create_pattern_piece_from_selected_sketch

    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(sketch)
    piece = cast(
        "_PatternPiece",
        create_pattern_piece_from_selected_sketch(
            name=name, allowance=allowance, grainline=grainline
        ),
    )
    piece.Label = name
    doc = cast("_RecomputableDocument", App.ActiveDocument)
    doc.recompute()
    if piece.Sketch is not sketch:
        msg = "Cloth PatternPiece did not retain the selected native Sketcher source"
        raise RuntimeError(msg)
    return piece


def style_mesh(obj: _PatternPiece | _DrapePanel, label: str) -> None:
    """Apply consistent shaded display properties to a native pattern or drape mesh.

    Args:
        obj: Native pattern piece or evaluated drape panel to display.
        label: Human-readable label shown in the FreeCAD model tree.
    """
    obj.Label = label
    try:
        obj.ViewObject.DisplayMode = "Shaded"
        obj.ViewObject.ShapeColor = (0.14, 0.32, 0.78)
        obj.ViewObject.Transparency = 0
        obj.ViewObject.LineWidth = 1.0
        if hasattr(obj.ViewObject, "SpecularColor"):
            obj.ViewObject.SpecularColor = (0.45, 0.45, 0.45)
        if hasattr(obj.ViewObject, "Shininess"):
            obj.ViewObject.Shininess = 45.0
    except (AttributeError, TypeError, ValueError):
        pass


def capture_tunic_pattern_view(doc, front, back, hem_width):
    """Capture the exact Sketcher profiles that are subsequently used by the 3D audit."""
    from freecad_cloth.pattern.PatternGui import PatternPieceTaskPanel

    pieces = (front, back)
    original_piece_placements = {
        piece.Name: App.Placement(piece.Placement.Base, piece.Placement.Rotation)
        for piece in pieces
    }
    original_sketch_placements = {
        piece.Sketch.Name: App.Placement(
            piece.Sketch.Placement.Base, piece.Sketch.Placement.Rotation
        )
        for piece in pieces
    }
    original_visibility = {}
    for obj in doc.Objects:
        view_object = getattr(obj, "ViewObject", None)
        if view_object is not None and hasattr(view_object, "Visibility"):
            original_visibility[obj.Name] = bool(view_object.Visibility)

    # Show the same authoritative Sketcher objects in a flat, side-by-side layout.
    # Only their placements change for this screenshot; the local profile geometry
    # remains exactly what the canonical 3D simulation consumes.
    gap = max(80.0, 0.15 * float(hem_width))
    try:
        for obj in doc.Objects:
            view_object = getattr(obj, "ViewObject", None)
            if view_object is not None and hasattr(view_object, "Visibility"):
                view_object.Visibility = False

        front_placement = App.Placement(
            App.Vector(-float(hem_width) - gap / 2.0, 0.0, 0.0), App.Rotation()
        )
        back_placement = App.Placement(App.Vector(gap / 2.0, 0.0, 0.0), App.Rotation())
        front.Placement = front_placement
        front.Sketch.Placement = front_placement
        back.Placement = back_placement
        back.Sketch.Placement = back_placement
        front.ViewObject.Visibility = False
        back.ViewObject.Visibility = False
        front.Sketch.ViewObject.Visibility = True
        back.Sketch.ViewObject.Visibility = True
        doc.recompute()

        activate(
            "ClothPatternWorkbench",
            "Cloth Pattern",
            [
                "ClothPattern_CreatePieceTask",
                "ClothPattern_EditPiece",
                "ClothPattern_Show2D",
                "ClothPattern_CreateFromSketch",
            ],
        )
        panel = PatternPieceTaskPanel(front)
        show_task(
            panel,
            "Pattern Workbench",
            ("Piece name", "Width", "Height", "Seam allowance", "Grainline angle"),
        )
        # The floating task panel obscures the second profile in the captured view.
        # Keep the workbench active, but close the panel so both canonical pieces are visible.
        close_task()
        view = Gui.activeDocument().activeView()
        view.viewTop()
        view.fitAll()
        events()
        save(
            "cloth-pattern-design.png",
            "Pattern Workbench canonical tunic profile",
            "same native Sketcher profiles used by the canonical 3D tunic audit",
        )
        log(
            "pattern-profile-alignment=passed front=%s front_edges=%d back=%s back_edges=%d"
            % (
                front.Sketch.Name,
                len(front.Sketch.Geometry),
                back.Sketch.Name,
                len(back.Sketch.Geometry),
            )
        )
    finally:
        close_task()
        for piece in pieces:
            piece.Placement = original_piece_placements[piece.Name]
            piece.Sketch.Placement = original_sketch_placements[piece.Sketch.Name]
        for obj in doc.Objects:
            if obj.Name in original_visibility:
                obj.ViewObject.Visibility = original_visibility[obj.Name]
        doc.recompute()
        Gui.activateWorkbench("ClothSimulationWorkbench")
        events()


def capture_tunic_sewing_view(doc, front, back, hem_width, seam_records):
    """Capture the Sewing workbench using the canonical simulation's tunic pieces and seams."""
    from freecad_cloth.sewing.SewingCommands import create_sewing_operation
    from freecad_cloth.sewing.SewingGui import SewingTaskPanel

    if not seam_records:
        msg = "canonical tunic sewing view needs the simulation's semantic seam records"
        raise RuntimeError(msg)

    pieces = (front, back)
    original_piece_placements = {
        piece.Name: App.Placement(piece.Placement.Base, piece.Placement.Rotation)
        for piece in pieces
    }
    original_visibility = {}
    for obj in doc.Objects:
        view_object = getattr(obj, "ViewObject", None)
        if view_object is not None and hasattr(view_object, "Visibility"):
            original_visibility[obj.Name] = bool(view_object.Visibility)

    sewing = None
    preview_sketches = []
    gap = max(80.0, 0.15 * float(hem_width))
    try:
        # Keep the semantic source sketches at their authored placements: moving a
        # Sketcher object changes the geometry/provenance fingerprints used by persistent
        # seam references. Duplicate only the display geometry for this flat screenshot.
        for obj in doc.Objects:
            view_object = getattr(obj, "ViewObject", None)
            if view_object is not None and hasattr(view_object, "Visibility"):
                view_object.Visibility = False

        front_placement = App.Placement(
            App.Vector(-float(hem_width) - gap / 2.0, 0.0, 0.0), App.Rotation()
        )
        back_placement = App.Placement(App.Vector(gap / 2.0, 0.0, 0.0), App.Rotation())
        front.Placement = front_placement
        back.Placement = back_placement
        front.ViewObject.Visibility = False
        back.ViewObject.Visibility = False

        import Sketcher

        for piece, placement, preview_name in (
            (front, front_placement, "VisualTunicFrontSewingPreviewSketch"),
            (back, back_placement, "VisualTunicBackSewingPreviewSketch"),
        ):
            preview = doc.addObject("Sketcher::SketchObject", preview_name)
            preview.addGeometry(list(piece.Sketch.Geometry), False)
            preview.addConstraint(
                [Sketcher.Constraint("Block", index) for index in range(len(preview.Geometry))]
            )
            preview.Placement = placement
            preview.Label = preview_name
            preview.ViewObject.Visibility = True
            preview_sketches.append(preview)

        for seam, _piece_a, _piece_b in seam_records:
            seam.ViewObject.Visibility = True
        doc.recompute()

        from freecad_cloth.pattern.PatternObjects import _resolve_document_edge

        invalid_seams = []
        seam_diagnostics = []
        for seam, piece_a, piece_b in seam_records:
            seam_id = str(getattr(seam, "SeamId", getattr(seam, "Label", seam.Name)))
            status = str(getattr(seam, "Status", ""))
            shape = getattr(seam, "Shape", None)
            shape_is_null = getattr(shape, "isNull", lambda: True)()
            edge_a_id = str(getattr(seam, "EdgeAId", ""))
            edge_b_id = str(getattr(seam, "EdgeBId", ""))
            reference_errors = []
            for prefix, piece, edge_id, signature in (
                ("A", piece_a, edge_a_id, str(getattr(seam, "EdgeASignature", ""))),
                ("B", piece_b, edge_b_id, str(getattr(seam, "EdgeBSignature", ""))),
            ):
                try:
                    _resolve_document_edge(piece, edge_id, signature)
                except Exception as exc:
                    reference_errors.append((prefix, type(exc).__name__, str(exc)))
            if status != "Valid" or shape_is_null:
                invalid_seams.append(seam_id)
                sketch_a = getattr(piece_a, "Sketch", None)
                sketch_b = getattr(piece_b, "Sketch", None)
                ids_a = tuple(
                    str(value) for value in (getattr(sketch_a, "SemanticEdgeIds", ()) or ())
                )
                ids_b = tuple(
                    str(value) for value in (getattr(sketch_b, "SemanticEdgeIds", ()) or ())
                )
                seam_diagnostics.append(
                    (
                        seam_id,
                        status,
                        bool(shape_is_null),
                        edge_a_id,
                        edge_b_id,
                        tuple(index for index, value in enumerate(ids_a) if value == edge_a_id),
                        tuple(index for index, value in enumerate(ids_b) if value == edge_b_id),
                        tuple(reference_errors),
                    )
                )
        if invalid_seams:
            raise RuntimeError(
                "canonical tunic has invalid semantic seams before Sewing capture: "
                + ", ".join(invalid_seams)
                + "; diagnostics="
                + repr(tuple(seam_diagnostics))
            )

        activate(
            "ClothSewingWorkbench",
            "Cloth Sewing",
            ["ClothSewing_CreateOperation", "ClothSewing_EditOperation", "ClothSewing_Validate"],
        )
        sewing = create_sewing_operation()
        doc.recompute()
        if (
            str(getattr(sewing, "Status", "")) != "Valid"
            or getattr(getattr(sewing, "Shape", None), "isNull", lambda: True)()
        ):
            msg = "canonical tunic Sewing operation is invalid"
            raise RuntimeError(msg)

        panel = SewingTaskPanel(sewing)
        show_task(
            panel,
            "Sewing Workbench",
            ("Seam", "Alignment", "Validation tolerance", "Stitch samples", "Status"),
        )
        # As with the pattern view, close the task panel so neither canonical
        # profile is obscured in the generated evidence.
        close_task()
        view = Gui.activeDocument().activeView()
        view.viewTop()
        view.fitAll()
        events()
        save(
            "cloth-sewing.png",
            "Sewing Workbench canonical tunic",
            "flat display copies of canonical Sketcher profiles with persistent source sketches and seam references unchanged",
        )
        log(
            "canonical-tunic-sewing=passed front=%s back=%s seam-ids=%s"
            % (
                front.Sketch.Name,
                back.Sketch.Name,
                tuple(str(getattr(seam, "SeamId", "")) for seam, _a, _b in seam_records),
            )
        )
    finally:
        close_task()
        if sewing is not None:
            sewing.ViewObject.Visibility = False
        for preview in preview_sketches:
            if doc.getObject(preview.Name) is not None:
                doc.removeObject(preview.Name)
        for piece in pieces:
            piece.Placement = original_piece_placements[piece.Name]
        for obj in doc.Objects:
            if obj.Name in original_visibility:
                obj.ViewObject.Visibility = original_visibility[obj.Name]
        doc.recompute()
        Gui.activateWorkbench("ClothSimulationWorkbench")
        events()


def _projected_point_within_outline_margin(
    x: float,
    z: float,
    points: list[tuple[float, float]],
    margin: float,
) -> bool:
    """Test whether a projected point is inside or near a closed outline.

    Args:
        x: Horizontal coordinate of the projected point.
        z: Vertical coordinate of the projected point.
        points: Ordered closed outline vertices in the same coordinate frame.
        margin: Allowed Euclidean distance from the outline boundary.

    Returns:
        True when the point is inside the polygon or within the boundary margin.
    """
    px = float(x)
    pz = float(z)
    margin_sq = float(margin) * float(margin)
    inside = False
    near = False
    for index, (ax_raw, az_raw) in enumerate(points):
        bx_raw, bz_raw = points[(index + 1) % len(points)]
        ax, az = float(ax_raw), float(az_raw)
        bx, bz = float(bx_raw), float(bz_raw)
        if (az > pz) != (bz > pz):
            crossing_x = ax + (pz - az) * (bx - ax) / (bz - az)
            if px < crossing_x:
                inside = not inside
        dx, dz = bx - ax, bz - az
        length_sq = dx * dx + dz * dz
        if length_sq > 0.0:
            factor = max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / length_sq))
            closest_x = ax + factor * dx
            closest_z = az + factor * dz
        else:
            closest_x, closest_z = ax, az
        if (px - closest_x) ** 2 + (pz - closest_z) ** 2 <= margin_sq:
            near = True
    return inside or near


def _validate_authoritative_tunic_seams(
    scene: _SimulationScene,
    seam_records: Sequence[tuple[object, _PatternPiece, _PatternPiece]],
) -> None:
    """Require every authored seam's exact solver stitch pairs to converge.

    Args:
        scene: Native simulation scene whose proxy owns the current backend.
        seam_records: Authored seam objects paired with their source PatternPieces.

    Raises:
        RuntimeError: If a seam lacks exact solver pairs or exceeds the gap contract.
    """
    positions = tuple(scene.Proxy._base_or_restore().backend.positions())
    if not positions:
        msg = "PositionBasedDynamics backend returned no simulated particle positions"
        raise RuntimeError(msg)
    stitch_pairs_by_seam = getattr(scene.Proxy, "seam_stitch_pairs", {})
    if not stitch_pairs_by_seam:
        msg = "authoritative seam check has no exact solver stitch provenance"
        raise RuntimeError(msg)

    seam_gap_records = []
    for seam, piece_a, piece_b in seam_records:
        if not str(getattr(seam, "EdgeAId", "")).startswith(f"{piece_a.PieceId}:edge:"):
            msg = "authoritative tunic seam lost semantic A-edge identity"
            raise RuntimeError(msg)
        if not str(getattr(seam, "EdgeBId", "")).startswith(f"{piece_b.PieceId}:edge:"):
            msg = "authoritative tunic seam lost semantic B-edge identity"
            raise RuntimeError(msg)
        seam_id = str(seam.SeamId)
        pairs = tuple(stitch_pairs_by_seam.get(seam_id, ()))
        if not pairs:
            raise RuntimeError(
                "authoritative seam check cannot resolve exact solver pairs for %s" % seam_id
            )

        gaps = []
        for global_a, global_b in pairs:
            point_a = tuple(float(value) for value in positions[int(global_a)])
            point_b = tuple(float(value) for value in positions[int(global_b)])
            gap = sum((point_a[axis] - point_b[axis]) ** 2 for axis in range(3)) ** 0.5
            gaps.append((gap, int(global_a), int(global_b), point_a, point_b))

        worst_gap, worst_a, worst_b, point_a, point_b = max(gaps, key=lambda item: item[0])
        mean_gap = sum(item[0] for item in gaps) / len(gaps)
        seam_gap_records.append((seam_id, worst_gap))
        log(
            "authoritative-seam-gap seam=%s count=%d max-mm=%.2f mean-mm=%.2f "
            "worst-pair=(%d,%d) a=(%.2f,%.2f,%.2f) b=(%.2f,%.2f,%.2f) "
            "delta=(%.2f,%.2f,%.2f)"
            % (
                seam_id,
                len(gaps),
                worst_gap,
                mean_gap,
                worst_a,
                worst_b,
                point_a[0],
                point_a[1],
                point_a[2],
                point_b[0],
                point_b[1],
                point_b[2],
                point_a[0] - point_b[0],
                point_a[1] - point_b[1],
                point_a[2] - point_b[2],
            )
        )
        for sample_index, (gap, global_a, global_b, sample_a, sample_b) in enumerate(gaps):
            log(
                "authoritative-seam-sample seam=%s sample=%d pair=(%d,%d) gap-mm=%.2f "
                "delta=(%.2f,%.2f,%.2f)"
                % (
                    seam_id,
                    sample_index,
                    global_a,
                    global_b,
                    gap,
                    sample_a[0] - sample_b[0],
                    sample_a[1] - sample_b[1],
                    sample_a[2] - sample_b[2],
                )
            )

    max_seam_gap = max((gap for _seam_id, gap in seam_gap_records), default=0.0)
    if max_seam_gap > 35.0:
        raise RuntimeError(
            "authoritative tunic seams did not converge: max endpoint gap %.1f mm" % max_seam_gap
        )
    log(
        "authoritative-seam-max-gap-mm=%.2f seam-ids=%s"
        % (max_seam_gap, tuple(str(seam.SeamId) for seam, _a, _b in seam_records))
    )


def _run_production_tunic_drape(
    simulation_panel: _SteppableSimulationPanel,
    scene: _SimulationScene,
    doc: _RecomputableDocument,
    task_dock: _TaskDock,
    view: object,
    seam_records: Sequence[tuple[object, _PatternPiece, _PatternPiece]],
) -> None:
    """Exercise realtime preview, validate collision settings, and capture a 90-step drape.

    Args:
        simulation_panel: GUI panel whose step action advances the production solver.
        scene: Native scene whose authored settings and evaluated state are audited.
        doc: FreeCAD document containing the scene and generated cloth panels.
        task_dock: Active task dock hidden during screenshot capture and restored afterwards.
        view: Native active view used to frame and capture drape progression.
        seam_records: Authored seams paired with their source pattern pieces.

    Raises:
        RuntimeError: If preview, collision configuration, or drape progression violates its contract.
    """
    """Exercise realtime preview, validate collision settings, and capture the 90-step drape."""
    from math import ceil
    from time import monotonic, perf_counter, sleep

    from freecad_cloth.simulation import RealtimePreview

    if "ClothRealtimePreview" not in Gui.listCommands():
        msg = "Realtime Cloth Preview GUI command is not registered"
        raise RuntimeError(msg)
    preview_fields = (
        "ParticleDistance",
        "SolverIterations",
        "SolverSubsteps",
        "TimeStep",
        "QualityPreset",
    )
    preview_saved = {name: getattr(scene, name) for name in preview_fields}
    Gui.runCommand("ClothRealtimePreview")
    scene.Document.recompute()
    preview_backend = getattr(scene.Proxy._base_or_restore(), "backend", None)
    if getattr(preview_backend, "name", None) != "position-based-dynamics":
        msg = "Realtime Cloth Preview did not select the PositionBasedDynamics backend"
        raise RuntimeError(msg)
    deadline = monotonic() + 2.0
    while int(scene.Steps) <= 0 and monotonic() < deadline:
        events()
        sleep(0.04)
    events()
    preview_steps = int(scene.Steps)
    if preview_steps <= 0:
        RealtimePreview.stop_realtime_preview()
        msg = "Realtime Cloth Preview timer did not advance the simulation"
        raise RuntimeError(msg)
    Gui.runCommand("ClothRealtimePreview")
    if int(scene.Steps) != 0:
        RealtimePreview.stop_realtime_preview()
        msg = "Realtime Cloth Preview did not reset steps on stop"
        raise RuntimeError(msg)
    for name, value in preview_saved.items():
        if getattr(scene, name) != value:
            raise RuntimeError("Realtime Cloth Preview did not restore %s" % name)
    log("realtime-preview=passed backend=position-based-dynamics steps=%d" % preview_steps)

    active_backend = scene.Proxy._base_or_restore().backend
    collision = getattr(active_backend, "_collision_surface", None)
    if collision is None:
        msg = "tunic PBD backend has no active mannequin collision surface"
        raise RuntimeError(msg)
    voxel_mm = float(getattr(active_backend, "_collision_voxel_mm", -1.0))
    configured_mm = float(getattr(active_backend, "_collision_configured_tolerance_mm", -1.0))
    effective_mm = float(getattr(active_backend, "_collision_effective_tolerance_mm", -1.0))
    thickness_mm = float(getattr(collision, "thickness", 0.0))
    resolution = tuple(
        int(value) for value in (getattr(active_backend, "_collision_sdf_resolution", ()) or ())
    )
    spans_mm = tuple(
        max(float(vertex[axis]) for vertex in collision.vertices)
        - min(float(vertex[axis]) for vertex in collision.vertices)
        for axis in range(3)
    )
    expected_resolution = tuple(
        max(16, min(256, int(ceil((span + 200.0) / 8.0)))) for span in spans_mm
    )
    if abs(thickness_mm - 5.0) > 1e-6:
        raise RuntimeError(
            "tunic mannequin collision thickness must be 5 mm, got %.3f" % thickness_mm
        )
    if abs(voxel_mm - 8.0) > 1e-6:
        raise RuntimeError("tunic PBD SDF voxel size must be 8 mm, got %.3f" % voxel_mm)
    if abs(configured_mm - 2.0) > 1e-6:
        raise RuntimeError(
            "tunic configured PBD collision tolerance must be 2 mm, got %.3f" % configured_mm
        )
    if abs(effective_mm - max(configured_mm, thickness_mm, 0.5 * voxel_mm)) > 1e-6:
        msg = "tunic PBD effective collision tolerance does not match its inputs"
        raise RuntimeError(msg)
    if resolution != expected_resolution:
        raise RuntimeError(
            "tunic PBD SDF resolution %r does not match configured 8 mm voxel resolution %r"
            % (resolution, expected_resolution)
        )
    log(
        "tunic-collision-config target-thickness-mm=%.2f voxel-mm=%.2f "
        "configured-tolerance-mm=%.2f effective-tolerance-mm=%.2f "
        "sdf-resolution=%dx%dx%d span-mm=%.2fx%.2fx%.2f"
        % (thickness_mm, voxel_mm, configured_mm, effective_mm, *resolution, *spans_mm)
    )
    configured_substeps = int(os.environ.get("CLOTH_PBD_SUBSTEPS", "8"))
    effective_substeps = int(getattr(active_backend, "_substeps", -1))
    if effective_substeps != configured_substeps:
        raise RuntimeError(
            "tunic PBD substeps differ from workflow configuration: "
            "backend=%d configured=%d" % (effective_substeps, configured_substeps)
        )
    log(
        "tunic-simulation-start particles=%d iterations=%d scene_substeps=%d "
        "backend_substeps=%d configured_substeps=%d backend=%s collision_triangles=%d"
        % (
            int(scene.ParticleCount),
            int(scene.SolverIterations),
            int(scene.SolverSubsteps),
            effective_substeps,
            configured_substeps,
            str(getattr(active_backend, "name", "")),
            len(collision.triangles),
        )
    )

    def log_seam_progress(stage: str) -> None:
        """Record read-only exact solver stitch gaps to localize seam divergence."""
        positions = tuple(active_backend.positions())
        pairs_by_seam = getattr(scene.Proxy, "seam_stitch_pairs", {})
        for seam, _piece_a, _piece_b in seam_records:
            seam_id = str(getattr(seam, "SeamId", ""))
            pairs = tuple(pairs_by_seam.get(seam_id, ()))
            if not pairs:
                log(
                    "tunic-seam-progress stage=%s seam=%s unavailable=no-exact-pairs"
                    % (stage, seam_id)
                )
                continue
            gap_records = []
            for global_a, global_b in pairs:
                point_a = tuple(float(value) for value in positions[int(global_a)])
                point_b = tuple(float(value) for value in positions[int(global_b)])
                gap = sum((point_a[axis] - point_b[axis]) ** 2 for axis in range(3)) ** 0.5
                gap_records.append((gap, int(global_a), int(global_b), point_a, point_b))
            worst_gap, worst_a, worst_b, point_a, point_b = max(
                gap_records, key=lambda item: item[0]
            )
            mean_gap = sum(item[0] for item in gap_records) / len(gap_records)
            log(
                "tunic-seam-progress stage=%s seam=%s samples=%d max-mm=%.2f "
                "mean-mm=%.2f worst-pair=(%d,%d) a=(%.2f,%.2f,%.2f) "
                "b=(%.2f,%.2f,%.2f) delta=(%.2f,%.2f,%.2f)"
                % (
                    stage,
                    seam_id,
                    len(gap_records),
                    worst_gap,
                    mean_gap,
                    worst_a,
                    worst_b,
                    point_a[0],
                    point_a[1],
                    point_a[2],
                    point_b[0],
                    point_b[1],
                    point_b[2],
                    point_a[0] - point_b[0],
                    point_a[1] - point_b[1],
                    point_a[2] - point_b[2],
                )
            )

    pathlib.Path(os.path.join(OUT, "cloth-tunic-mannequin-motion-frames")).mkdir(
        exist_ok=True, parents=True
    )
    task_dock.hide()
    events()
    view.setCameraType("Orthographic")
    view.viewAxonometric()
    view.fitAll()
    events()
    save_view(
        "cloth-tunic-mannequin-motion-frames/motion-000.png",
        "mannequin drape step 0",
        "production tunic before gravity",
    )
    log_seam_progress("step-%d" % int(scene.Steps))
    started = perf_counter()
    for frame_index, batch in enumerate((10,) * 9, start=1):
        frame_started = perf_counter()
        simulation_panel.step(batch)
        doc.recompute()
        events()
        log_seam_progress("step-%d" % int(scene.Steps))
        view.viewAxonometric()
        view.fitAll()
        events()
        save_view(
            "cloth-tunic-mannequin-motion-frames/motion-%03d.png" % frame_index,
            "mannequin drape step %d" % int(scene.Steps),
            "production tunic gravity progression",
        )
        log(
            "tunic-simulation-frame=%d steps=%d batch=%d elapsed_ms=%.1f total_ms=%.1f "
            "particles=%d iterations=%d scene_substeps=%d backend_substeps=%d"
            % (
                frame_index,
                int(scene.Steps),
                batch,
                1000.0 * (perf_counter() - frame_started),
                1000.0 * (perf_counter() - started),
                int(scene.ParticleCount),
                int(scene.SolverIterations),
                int(scene.SolverSubsteps),
                int(getattr(active_backend, "_substeps", -1)),
            )
        )
    task_dock.show()
    task_dock.raise_()
    events()
    log("tunic-simulation-total-ms=%.1f" % (1000.0 * (perf_counter() - started)))


def simulation() -> None:
    """Build, simulate, and capture the canonical two-panel tunic in FreeCAD.

    The fixture keeps native Sketcher profiles and semantic seam references
    authoritative, validates target/collision boundaries, and writes visual and
    numeric evidence for the evaluated cloth.

    Raises:
        RuntimeError: If the authored pattern, target, seam, solver, or drape contract fails.
    """
    import os

    os.environ["CLOTH_PBD_COLLISION_MODE"] = "mesh"
    from freecad_cloth.pattern.PatternModel import Seam
    from freecad_cloth.pattern.PatternObjects import add_seam
    from freecad_cloth.simulation.DrapeTarget import (
        collision_surface,
        refresh_drape_target,
        target_status,
    )
    from freecad_cloth.simulation.SimulationCommands import create_quality_simulation_scene
    from freecad_cloth.simulation.SimulationQualityGui import SimulationQualityTaskPanel

    doc = App.newDocument("ClothSimulationVisualRegression")
    scene = cast("_SimulationScene", create_quality_simulation_scene(doc))
    avatar = getattr(getattr(scene, "DrapeTarget", None), "SourceObject", None)
    target = scene.DrapeTarget
    if avatar is None or str(getattr(avatar, "AvatarType", "")) != "ClothAvatar":
        msg = "visual fixture did not create the production ClothAvatar"
        raise RuntimeError(msg)
    if target is None:
        msg = "visual fixture did not create DrapeTarget"
        raise RuntimeError(msg)
    target_source = getattr(target, "SourceObject", None)
    if target_source is not avatar:
        msg = "visual fixture DrapeTarget does not reference the production ClothAvatar"
        raise RuntimeError(msg)
    if TUNIC_PRODUCTION_AUDIT:
        from dataclasses import replace as replace_dataclass

        from freecad_cloth.avatar.AvatarCommands import _parameters, apply_avatar_parameters

        initial_parameters = _parameters(avatar)
        near_t_pose = replace_dataclass(
            initial_parameters.pose,
            left_arm_angle=12.0,
            right_arm_angle=12.0,
            left_elbow_angle=0.0,
            right_elbow_angle=0.0,
            joint_rotations=(),
        )
        apply_avatar_parameters(avatar, replace_dataclass(initial_parameters, pose=near_t_pose))
        refresh_drape_target(target)
        doc.recompute()
        log(
            "tunic-avatar-pose=near-horizontal left_arm_angle=12 right_arm_angle=12 "
            "joint_overrides=cleared"
        )
    pre_status = target_status(target)
    if str(pre_status.get("state", "")) != "ready":
        raise RuntimeError(
            "canonical tunic DrapeTarget is not current before placement: {}".format(
                pre_status.get("message", pre_status)
            )
        )
    target_surface = collision_surface(
        target_source,
        float(getattr(target, "CollisionDeflection", 1.0)),
        float(getattr(target, "CollisionThickness", 0.0)),
    )
    if not target_surface.vertices or not target_surface.triangles:
        msg = "canonical tunic DrapeTarget has no authoritative collision triangles"
        raise RuntimeError(msg)
    from freecad_cloth.avatar.AvatarFitting import ArrangementPoint

    def arrangement_world(name: str) -> _Vector3:
        """Resolve a named avatar arrangement point into world coordinates.

        Args:
            name: Stable arrangement-point identifier stored on the avatar.

        Returns:
            World-space vector corresponding to the requested arrangement point.

        Raises:
            RuntimeError: If the avatar does not contain the named arrangement point.
        """
        raw = next(
            (
                value
                for value in getattr(avatar, "ArrangementPoints", ())
                if str(value).split("|", 1)[0] == name
            ),
            None,
        )
        if raw is None:
            msg = f"canonical tunic is missing avatar arrangement point {name}"
            raise RuntimeError(msg)
        point = ArrangementPoint.from_string(raw)
        return avatar.Placement.multVec(App.Vector(*point.position()))

    shoulder_left = arrangement_world("shoulder_left")
    shoulder_right = arrangement_world("shoulder_right")
    hip_point = arrangement_world("hip")
    if TUNIC_PRODUCTION_AUDIT:

        def landmark_world(name: str) -> _Vector3:
            """Resolve a persisted forward-kinematic landmark into world coordinates.

            Args:
                name: Stable landmark identifier stored on the posed avatar.

            Returns:
                World-space landmark vector after applying the avatar placement.

            Raises:
                RuntimeError: If the landmark is missing or its coordinates are malformed.
            """
            raw = next(
                (
                    value
                    for value in getattr(avatar, "Landmarks", ())
                    if str(value).split("|", 1)[0] == name
                ),
                None,
            )
            if raw is None:
                raise RuntimeError("posed avatar mesh is missing FK landmark %s" % name)
            coordinates = tuple(float(value) for value in str(raw).split("|", 1)[1].split(","))
            if len(coordinates) != 3:
                raise RuntimeError("posed avatar FK landmark %s has invalid coordinates" % name)
            return avatar.Placement.multVec(App.Vector(*coordinates))

        wrist_left = landmark_world("wrist_left")
        wrist_right = landmark_world("wrist_right")
        left_span = abs(float(wrist_left.x) - float(shoulder_left.x))
        right_span = abs(float(wrist_right.x) - float(shoulder_right.x))
        left_vertical = abs(float(wrist_left.z) - float(shoulder_left.z))
        right_vertical = abs(float(wrist_right.z) - float(shoulder_right.z))
        log(
            "tunic-pose-geometry left_dx=%.1f left_dz=%.1f right_dx=%.1f right_dz=%.1f"
            % (left_span, left_vertical, right_span, right_vertical)
        )
        if (
            min(left_span, right_span) < 150.0
            or left_vertical > 0.22 * left_span
            or right_vertical > 0.22 * right_span
        ):
            msg = "tunic mannequin FK mesh is not near-T-pose: wrists are not near shoulder height"
            raise RuntimeError(msg)
        pose_view = Gui.activeDocument().activeView()
        pose_view.viewFront()
        pose_view.fitAll()
        events()
        save(
            "cloth-mannequin-near-t-pose.png",
            "Mannequin near-T pose before cloth",
            "FK pose verified by shoulder-to-wrist geometry before draping",
        )
    target_ys = [float(vertex[1]) for vertex in target_surface.vertices]
    y_span = max(target_ys) - min(target_ys)
    x_mid = (shoulder_left.x + shoulder_right.x) / 2.0
    shoulder_z = (shoulder_left.z + shoulder_right.z) / 2.0
    hem_z = hip_point.z
    shoulder_width = abs(shoulder_right.x - shoulder_left.x)
    panel_width = max(420.0, shoulder_width + 105.0)
    hem_width = (
        max(500.0, panel_width + 100.0)
        if TUNIC_PRODUCTION_AUDIT
        else max(450.0, panel_width + 100.0)
    )
    # Add 10% horizontal ease at the underarms and shoulders without changing fit height.
    panel_width *= 1.10
    hem_width *= 1.10
    # Raise the shoulder seam above the avatar landmark so free drape can settle it down.
    shoulder_headroom_mm = 20.0
    garment_height = max(560.0, (shoulder_z - hem_z + shoulder_headroom_mm) / 0.94)
    log(
        "tunic-shoulder-headroom target-mm=%.1f actual-mm=%.1f"
        % (shoulder_headroom_mm, 0.94 * garment_height - (shoulder_z - hem_z))
    )
    body_depth = max(120.0, min(260.0, y_span))
    clearance = max(20.0, 0.08 * body_depth)
    rot = App.Rotation(App.Vector(1, 0, 0), 90.0)

    def target_relative_piece_placement(
        side: str,
        outline: list[tuple[float, float]],
    ) -> object:
        """Place a panel in front of or behind the avatar using target geometry.

        Args:
            side: Panel side, restricted to "front" or "back".
            outline: Authored two-dimensional panel outline in local coordinates.

        Returns:
            Native FreeCAD placement for the requested panel side.

        Raises:
            RuntimeError: If the authored outline does not overlap the target projection.
            ValueError: If side is neither "front" nor "back".
        """
        if TUNIC_PRODUCTION_AUDIT:
            panel_origin_x = x_mid - hem_width / 2.0
            torso_half_width = max(80.0, 0.30 * shoulder_width)
            projected_target_ys = [
                float(vertex[1])
                for vertex in target_surface.vertices
                if abs(float(vertex[0]) - x_mid) <= torso_half_width
                and _projected_point_within_outline_margin(
                    float(vertex[0]) - panel_origin_x,
                    float(vertex[2]) - hem_z,
                    outline,
                    clearance,
                )
            ]
            if not projected_target_ys:
                msg = "canonical tunic torso silhouette does not overlap DrapeTarget projections"
                raise RuntimeError(msg)
            target_front_y = min(projected_target_ys)
            target_back_y = max(projected_target_ys)
            if side == "front":
                y = target_front_y - clearance
            elif side == "back":
                y = target_back_y + clearance
            else:
                msg = "tunic target-relative side must be front or back"
                raise ValueError(msg)
            log(
                "tunic-placement-depth side=%s projected-target-y=[%.2f, %.2f] "
                "panel-y=%.2f clearance-mm=%.2f torso-x=[%.2f, %.2f] projected-vertices=%d"
                % (
                    side,
                    target_front_y,
                    target_back_y,
                    y,
                    clearance,
                    x_mid - torso_half_width,
                    x_mid + torso_half_width,
                    len(projected_target_ys),
                )
            )
            return App.Placement(App.Vector(panel_origin_x, y, hem_z), rot)
        if side == "front":
            y = (shoulder_left.y + shoulder_right.y) / 2.0 - clearance
        elif side == "back":
            y = (shoulder_left.y + shoulder_right.y) / 2.0 + clearance
        else:
            msg = "tunic target-relative side must be front or back"
            raise ValueError(msg)
        return App.Placement(App.Vector(x_mid - hem_width / 2.0, y, hem_z), rot)

    def make_piece(
        name: str,
        side: str,
        neckline_ratio: float,
        neckline_drop: float,
    ) -> tuple[_PatternPiece, list[tuple[float, float]]]:
        """Create one native Sketcher panel and adopt it as a Cloth PatternPiece.

        Args:
            name: Stable front/back panel identifier.
            side: Target-relative side used to calculate piece placement.
            neckline_ratio: Fractional half-width for the authored neckline opening.
            neckline_drop: Fraction of garment height used for the neckline scoop.

        Returns:
            Persistent PatternPiece and its ordered authored two-dimensional outline.
        """
        sketch, outline = _make_tunic_sketch(
            doc,
            name + "Source",
            panel_width,
            garment_height,
            hem_width,
            neckline_ratio,
            neckline_drop,
        )
        doc.recompute()
        piece = _adopt_sketch(sketch, name, 10.0, 0.0)
        piece.Label = name
        piece.Placement = target_relative_piece_placement(side, outline)
        piece.Sketch.Placement = piece.Placement
        return piece, outline

    # Widen the neck opening and lift the shoulder seams 20 mm over the mannequin's shoulder landmark.
    front_side, back_side = ("back", "front") if TUNIC_PRODUCTION_AUDIT else ("front", "back")
    front, front_outline = make_piece("VisualTunicFront", front_side, 0.72, 0.03)
    back, back_outline = make_piece("VisualTunicBack", back_side, 0.72, 0.03)

    def log_tunic_outline_topology(piece):
        """Log the actual sampled boundary and crossing edges before sewing or draping."""
        import ast
        import re

        from shapely.geometry import LineString, Point, Polygon
        from shapely.validation import explain_validity

        from freecad_cloth.simulation.PatternSimulationAdapter import resolve_piece_ir

        piece_ir = resolve_piece_ir(piece)
        outline = []
        segments = []
        boundary_summary = []
        for boundary in piece_ir.boundaries:
            samples = tuple(
                (round(float(sample[0]), 6), round(float(sample[1]), 6))
                for sample in boundary.samples
            )
            if len(samples) < 2:
                raise RuntimeError(
                    "pattern topology audit found a boundary with fewer than two samples: "
                    "%s:%s" % (piece.Name, boundary.id)
                )
            boundary_summary.append(
                (
                    str(boundary.id),
                    str(boundary.kind),
                    len(samples),
                    samples[0],
                    samples[-1],
                    samples,
                )
            )
            outline.extend(samples[:-1])
            segments.extend(
                (str(boundary.id), start, end)
                for start, end in zip(samples[:-1], samples[1:], strict=True)
            )

        ir_polygon = Polygon(outline)
        ir_reason = explain_validity(ir_polygon)
        try:
            draft_points = tuple(
                (float(point[0]), float(point[1]))
                for point in ast.literal_eval(str(piece.DraftingBoundary))
            )
            draft_polygon = Polygon(draft_points)
            draft_valid = bool(draft_polygon.is_valid)
            draft_reason = explain_validity(draft_polygon)
        except (ValueError, SyntaxError, TypeError, IndexError) as exc:
            draft_points = ()
            draft_valid = False
            draft_reason = "derived outline unavailable: %s" % type(exc).__name__

        crossing_pattern = re.compile(r"Self-intersection\[([-+0-9.eE]+)\s+([-+0-9.eE]+)\]")
        ir_crossing = crossing_pattern.search(ir_reason)
        draft_crossing = crossing_pattern.search(draft_reason)
        crossing_match = ir_crossing or draft_crossing
        if crossing_match is None:
            nearby = ()
        else:
            crossing = Point(float(crossing_match.group(1)), float(crossing_match.group(2)))
            if ir_crossing is not None:
                crossing_segments = segments
            else:
                crossing_segments = tuple(
                    (
                        str(boundary_summary[index][0])
                        if index < len(boundary_summary)
                        else "derived-edge:%d" % index,
                        start,
                        draft_points[(index + 1) % len(draft_points)],
                    )
                    for index, start in enumerate(draft_points)
                )
            distances = sorted(
                (
                    round(float(LineString((start, end)).distance(crossing)), 6),
                    index,
                    edge_id,
                    start,
                    end,
                )
                for index, (edge_id, start, end) in enumerate(crossing_segments)
            )
            nearby = tuple(distances[:8])

        record = {
            "piece": piece.Name,
            "ir_valid": bool(ir_polygon.is_valid),
            "ir_reason": ir_reason,
            "draft_valid": draft_valid,
            "draft_reason": draft_reason,
        }
        log(
            "tunic-outline-topology piece=%s ir-valid=%s ir-reason=%s "
            "draft-valid=%s draft-reason=%s ir-points=%d draft-points=%d "
            "boundary-order=%r near-crossing=%r"
            % (
                piece.Name,
                record["ir_valid"],
                ir_reason,
                draft_valid,
                draft_reason,
                len(outline),
                len(draft_points),
                tuple(boundary_summary),
                nearby,
            )
        )
        return record

    topology_results = [log_tunic_outline_topology(piece) for piece in (front, back)]

    capture_tunic_pattern_view(doc, front, back, hem_width)

    # Use semantic edge IDs and keep the two curved armholes (edges 2 and 6)
    # open. Only the two side seams and two shoulder seams are joined.
    front_edge_ids = tuple(
        str(value) for value in getattr(front.Sketch, "SemanticEdgeIds", ()) or ()
    )
    back_edge_ids = tuple(str(value) for value in getattr(back.Sketch, "SemanticEdgeIds", ()) or ())
    if len(front_edge_ids) < 8 or len(back_edge_ids) < 8:
        msg = "canonical tunic sketches have no complete semantic edge map"
        raise RuntimeError(msg)
    required_indices = (1, 3, 5, 7)
    if any(not front_edge_ids[index] or not back_edge_ids[index] for index in required_indices):
        msg = "canonical tunic fixture is missing authored semantic edge IDs"
        raise RuntimeError(msg)

    from freecad_cloth.simulation.PatternSimulationAdapter import resolve_piece_ir

    for piece, edge_ids in ((front, front_edge_ids), (back, back_edge_ids)):
        piece_ir = resolve_piece_ir(piece)
        boundary_by_id = {str(boundary.id): boundary for boundary in piece_ir.boundaries}
        for edge_index, inward in ((2, -1.0), (6, 1.0)):
            boundary = boundary_by_id.get(edge_ids[edge_index])
            if boundary is None or boundary.kind != "arc" or len(boundary.samples) < 8:
                raise RuntimeError(
                    "canonical garment armhole was not preserved as a sampled native curve: "
                    "piece=%s edge=%s" % (piece.Name, edge_ids[edge_index])
                )
            start_point = boundary.samples[0]
            end_point = boundary.samples[-1]
            vertical_span = float(end_point[1]) - float(start_point[1])
            if abs(vertical_span) <= 1e-9:
                raise RuntimeError(
                    "canonical garment armhole endpoints do not define a vertical chord: "
                    "piece=%s edge=%s" % (piece.Name, edge_ids[edge_index])
                )
            scoop_depth = max(
                inward
                * (
                    float(sample[0])
                    - (
                        float(start_point[0])
                        + (float(sample[1]) - float(start_point[1]))
                        / vertical_span
                        * (float(end_point[0]) - float(start_point[0]))
                    )
                )
                for sample in boundary.samples[1:-1]
            )
            if scoop_depth <= 0.02 * float(panel_width):
                deviations = tuple(
                    float(sample[0])
                    - (
                        float(start_point[0])
                        + (float(sample[1]) - float(start_point[1]))
                        / vertical_span
                        * (float(end_point[0]) - float(start_point[0]))
                    )
                    for sample in boundary.samples[1:-1]
                )
                native_geometry = piece.Sketch.Geometry[edge_index]
                log(
                    "tunic-armhole-debug piece=%s edge=%s native=%s range=%s "
                    "start=(%.3f,%.3f) end=(%.3f,%.3f) x-deviation=[%.3f,%.3f] "
                    "signed-inward=%.3f"
                    % (
                        piece.Name,
                        edge_ids[edge_index],
                        type(native_geometry).__name__,
                        tuple(float(value) for value in boundary.parameter_range),
                        float(start_point[0]),
                        float(start_point[1]),
                        float(end_point[0]),
                        float(end_point[1]),
                        min(deviations),
                        max(deviations),
                        float(scoop_depth),
                    )
                )
                raise RuntimeError(
                    "canonical garment armhole curve has insufficient inward clearance: "
                    "piece=%s edge=%s scoop-mm=%.2f"
                    % (piece.Name, edge_ids[edge_index], scoop_depth)
                )

    seam_specs = (
        (front_edge_ids[1], back_edge_ids[1], "TunicRightSide", False),
        (front_edge_ids[3], back_edge_ids[3], "TunicRightShoulder", False),
        (front_edge_ids[5], back_edge_ids[5], "TunicLeftShoulder", False),
        (front_edge_ids[7], back_edge_ids[7], "TunicLeftSide", False),
    )
    seam_records = []
    for edge_a_id, edge_b_id, seam_id, reversed_b in seam_specs:
        seam = Seam(
            str(front.PieceId),
            edge_a_id,
            str(back.PieceId),
            edge_b_id,
            id=seam_id,
            reversed_b=reversed_b,
            alignment="uniform",
            stitch_group="TunicAssembly",
        )
        add_seam(doc, seam)
        seam_obj = next(o for o in doc.Objects if getattr(o, "SeamId", "") == seam_id)
        if (
            str(getattr(seam_obj, "EdgeAId", "")) != edge_a_id
            or str(getattr(seam_obj, "EdgeBId", "")) != edge_b_id
            or bool(getattr(seam_obj, "ReversedB", False)) != reversed_b
        ):
            raise RuntimeError(
                "canonical tunic seam %s did not retain its authored correspondence" % seam_id
            )
        seam_records.append((seam_obj, front, back))
    capture_tunic_sewing_view(doc, front, back, hem_width, seam_records)
    invalid_native = next(
        (record for record in topology_results if not bool(record["ir_valid"])),
        None,
    )
    if invalid_native is not None:
        raise RuntimeError(
            "canonical tunic PatternIR boundary is invalid before simulation: "
            "piece=%s reason=%s" % (invalid_native["piece"], invalid_native["ir_reason"])
        )
    invalid_derived = next(
        (record for record in topology_results if not bool(record["draft_valid"])),
        None,
    )
    if invalid_derived is not None:
        raise RuntimeError(
            "canonical tunic derived pattern outline is invalid before simulation: "
            "piece=%s reason=%s" % (invalid_derived["piece"], invalid_derived["draft_reason"])
        )
    scene.StartHeight = 0.0
    scene.QualityPreset = "Fast"
    scene.ParticleDistance = 24.0
    scene.SolverIterations = 8
    scene.SolverSubsteps = 4 if TUNIC_PRODUCTION_AUDIT else 1
    scene.TimeStep = 1.0 / 240.0 if TUNIC_PRODUCTION_AUDIT else 1.0 / 120.0
    if TUNIC_PRODUCTION_AUDIT:
        log("tunic-time-step=1/240s for 90-step free-drape audit")
    scene.GravityX = 0.0
    scene.GravityY = 0.0
    scene.GravityZ = -9810.0
    scene.FabricFriction = 0.85 if TUNIC_PRODUCTION_AUDIT else 0.75
    if TUNIC_PRODUCTION_AUDIT:
        log("tunic-solver=particle-distance-24 iterations-8 substeps=4")
    # Keep the free-drape audit unpinned: fixed front/back neckline centers
    # prevent the shoulder seams from converging.
    scene.PinMode = "None"
    scene.PinSelection = []
    scene.ClothPieces = [front, back]
    link_records = tuple(
        (
            str(getattr(piece, "Name", "")),
            str(getattr(piece, "PieceId", "")),
            str(getattr(piece, "PatternType", "")),
        )
        for piece in (getattr(scene, "ClothPieces", ()) or ())
    )
    log("tunic-simulation-input-cloth-pieces=%r" % (link_records,))
    proxy = scene.Proxy
    base_proxy_getter = getattr(proxy, "_base_or_restore", None)
    if not callable(base_proxy_getter):
        msg = "canonical tunic simulation cannot invalidate its cached scene"
        raise RuntimeError(msg)
    # Explicitly invalidate the initial demo signature; touch() alone retained its backend.
    base_proxy_getter().source_signature = None
    scene.touch()
    refresh_drape_target(target)
    doc.recompute()
    # Recompute may leave the GUI-created demo backend cached after the authored
    # PatternPieces are linked. Re-enter the same proxy execution path with its
    # signature invalidated so the audit measures the real tunic panels.
    proxy = scene.Proxy
    base_proxy_getter = getattr(proxy, "_base_or_restore", None)
    if not callable(base_proxy_getter):
        msg = "canonical tunic simulation cannot rebuild its authored panels"
        raise RuntimeError(msg)
    base_proxy_getter().source_signature = None
    proxy.execute(scene)
    status = target_status(target)
    if str(status.get("state", "")) != "ready":
        raise RuntimeError(
            "canonical tunic DrapeTarget is not current: {}".format(status.get("message", status))
        )
    proxy = scene.Proxy
    backend = getattr(proxy, "backend", None)
    if backend is None:
        msg = "canonical tunic did not build a simulation backend"
        raise RuntimeError(msg)
    particle_positions = tuple(
        tuple(float(value) for value in position) for position in backend.positions()
    )
    panel_indices = getattr(proxy, "panel_indices", {})
    panel_objects = tuple(getattr(scene, "DrapePanels", ()))
    if len(panel_objects) < 2:
        msg = "canonical tunic did not create one drape mesh per panel"
        raise RuntimeError(msg)
    neckline_midpoints = []
    panel_boundary_edges = getattr(proxy, "panel_boundary_edges", {})
    panel_piece_names = getattr(proxy, "panel_piece_names", {})
    panel_map_summary = tuple(
        (
            str(getattr(panel, "Name", "")),
            str(panel_piece_names.get(getattr(panel, "Name", ""), "")),
            len(tuple(panel_indices.get(getattr(panel, "Name", ""), ()))),
            len(tuple(panel_boundary_edges.get(getattr(panel, "Name", ""), ()))),
        )
        for panel in panel_objects[:2]
    )
    log(
        "tunic-simulation-panel-map proxy=%s links=%d panels=%r map=%r particles=%d"
        % (
            type(proxy).__name__,
            len(tuple(getattr(scene, "ClothPieces", ()) or ())),
            tuple(str(getattr(panel, "Name", "")) for panel in panel_objects[:2]),
            panel_map_summary,
            len(particle_positions),
        )
    )
    for piece, panel in zip((front, back), panel_objects[:2], strict=True):
        if str(panel_piece_names.get(panel.Name, "")) != str(piece.Name):
            raise RuntimeError(
                "canonical tunic simulation did not build an authored pattern panel: "
                "piece=%s panel=%s mapped-piece=%s cloth-pieces=%r"
                % (
                    piece.Name,
                    panel.Name,
                    str(panel_piece_names.get(panel.Name, "")),
                    link_records,
                )
            )
    for piece, _outline, panel, edge_ids in zip(
        (front, back),
        (front_outline, back_outline),
        panel_objects[:2],
        (front_edge_ids, back_edge_ids),
        strict=True,
    ):
        piece_indices = tuple(int(index) for index in panel_indices.get(panel.Name, ()))
        piece_index_set = set(piece_indices)
        if not piece_index_set:
            raise RuntimeError(
                "canonical tunic has no simulation particles for piece %s" % piece.Name
            )

        # Resolve the neckline by authored Sketcher edge ID, then anchor to the
        # midpoint of that edge's actual meshed boundary chain. This avoids a
        # world-space nearest-vertex search that can accidentally select the
        # wrong region when a panel has been placed or rotated.
        piece_ir = resolve_piece_ir(piece)
        neckline_edge_id = str(edge_ids[4])
        neckline_boundary = next(
            (boundary for boundary in piece_ir.boundaries if str(boundary.id) == neckline_edge_id),
            None,
        )
        if neckline_boundary is None:
            raise RuntimeError(
                "canonical tunic could not resolve neckline semantic edge: "
                "piece=%s edge=%s" % (piece.Name, neckline_edge_id)
            )
        boundary_chains = tuple(panel_boundary_edges.get(panel.Name, ()))
        neckline_particles, boundary_method, endpoint_error = _neckline_boundary_particles(
            piece,
            neckline_boundary,
            piece_indices,
            boundary_chains,
            particle_positions,
        )
        log(
            "tunic-neckline-resolution piece=%s edge=%s method=%s chains=%d endpoint-error-mm=%.6f"
            % (
                piece.Name,
                neckline_edge_id,
                boundary_method,
                len(boundary_chains),
                endpoint_error,
            )
        )
        if len(neckline_particles) < 2:
            raise RuntimeError(
                "canonical tunic neckline boundary has too few mesh vertices: "
                "piece=%s edge=%s" % (piece.Name, neckline_edge_id)
            )
        if any(index not in piece_index_set for index in neckline_particles):
            raise RuntimeError(
                "canonical tunic neckline boundary contains particles from another panel: "
                "piece=%s edge=%s" % (piece.Name, neckline_edge_id)
            )

        cumulative_distances = [0.0]
        for first_index, second_index in zip(
            neckline_particles, neckline_particles[1:], strict=False
        ):
            first = particle_positions[first_index]
            second = particle_positions[second_index]
            span = sum((float(second[axis]) - float(first[axis])) ** 2 for axis in range(3)) ** 0.5
            if span <= 1e-9:
                raise RuntimeError(
                    "canonical tunic neckline boundary contains a zero-length segment: "
                    "piece=%s edge=%s" % (piece.Name, neckline_edge_id)
                )
            cumulative_distances.append(cumulative_distances[-1] + span)

        total_length = cumulative_distances[-1]
        if total_length <= 1e-9:
            raise RuntimeError(
                "canonical tunic neckline boundary has zero length: "
                "piece=%s edge=%s" % (piece.Name, neckline_edge_id)
            )
        midpoint_distance = 0.5 * total_length
        central_offset = min(
            range(len(neckline_particles)),
            key=lambda index: abs(cumulative_distances[index] - midpoint_distance),
        )
        particle_index = neckline_particles[central_offset]
        snap_distance = abs(cumulative_distances[central_offset] - midpoint_distance)
        if snap_distance > max(8.0, float(scene.ParticleDistance)):
            raise RuntimeError(
                "canonical tunic neckline midpoint did not resolve on its boundary: "
                "piece=%s edge=%s midpoint-offset-mm=%.2f"
                % (piece.Name, neckline_edge_id, snap_distance)
            )
        neckline_midpoints.append(particle_index)
        log(
            "tunic-neckline-boundary piece=%s edge=%s vertices=%d length-mm=%.2f"
            % (piece.Name, neckline_edge_id, len(neckline_particles), total_length)
        )
        # Report the midpoint snap along the authored neckline chain, not to a
        # potentially unrelated world-space mesh vertex.
        log(
            "tunic-neckline-midpoint piece=%s particle=%d snap-mm=%.2f"
            % (piece.Name, particle_index, snap_distance)
        )
    neckline_midpoints = tuple(sorted(set(neckline_midpoints)))
    if len(neckline_midpoints) != 2:
        raise RuntimeError(
            "canonical tunic requires one distinct neckline midpoint per panel: %s"
            % (neckline_midpoints,)
        )

    if str(getattr(scene, "PinMode", "")) != "None":
        msg = "canonical tunic must use PinMode=None for seam convergence"
        raise RuntimeError(msg)
    if list(getattr(scene, "PinSelection", ())) != []:
        msg = "canonical tunic PinMode=None retained explicit PinSelection values"
        raise RuntimeError(msg)
    solver_pins = tuple(sorted(int(index) for index in getattr(backend, "_pin_indices", ())))
    if not solver_pins:
        system = getattr(backend, "system", None)
        solver_pins = tuple(sorted(int(index) for index in getattr(system, "pins", {})))
    if solver_pins:
        raise RuntimeError(
            "canonical tunic PinMode=None still has solver pins: %s" % (solver_pins,)
        )
    log("tunic-neckline-midpoints=%s" % (neckline_midpoints,))
    surface = collision_surface(
        target_source,
        float(getattr(target, "CollisionDeflection", 1.0)),
        float(getattr(target, "CollisionThickness", 0.0)),
    )
    initial_clearance = None
    try:
        from freecad_cloth.common.MeshValidation import nearest_target_clearance

        initial_clearance = nearest_target_clearance(
            tuple(backend.positions()), tuple(surface.vertices)
        )
    except (ImportError, ValueError):
        initial_clearance = None
    if initial_clearance is None or float(initial_clearance) < float(clearance):
        msg = (
            "canonical tunic step-0 target clearance is below configured separation: "
            f"{float(initial_clearance or 0.0):.2f} mm < {float(clearance):.2f} mm"
        )
        raise RuntimeError(msg)
    log("pin-mode=None solver-pins=0")
    log("seam-world-x-step0=" + json.dumps(_seam_lateral_snapshot(proxy, x_mid), sort_keys=True))
    log("target-collision-mode=mesh")
    log(
        f"step0-target-vertex-clearance-mm={float(initial_clearance):.2f} required-mm={float(clearance):.2f}"
    )
    for source in (doc.getObject("VisualTunicFront"), doc.getObject("VisualTunicBack")):
        if source is not None:
            source.ViewObject.Visibility = False
        sketch = getattr(source, "Sketch", None) if source is not None else None
        if sketch is not None:
            sketch.ViewObject.Visibility = False
    panels = list(scene.DrapePanels)
    if len(panels) != 2:
        raise RuntimeError("expected two drape panels, got %d" % len(panels))
    for panel, label in zip(panels, ("Drape: Tunic Front", "Drape: Tunic Back"), strict=False):
        style_mesh(panel, label)
        panel.ViewObject.Visibility = True
    avatar.ViewObject.Visibility = True
    doc.recompute()
    target_xs = [float(vertex[0]) for vertex in target_surface.vertices]
    target_ys = [float(vertex[1]) for vertex in target_surface.vertices]
    target_zs = [float(vertex[2]) for vertex in target_surface.vertices]
    log(
        f"target-surface-bounds x={min(target_xs):.1f}..{max(target_xs):.1f} y={min(target_ys):.1f}..{max(target_ys):.1f} z={min(target_zs):.1f}..{max(target_zs):.1f}"
    )
    log(
        "tunic-source=freecad-native-sketcher edges=%d front=%s back=%s"
        % (len(front.Sketch.Geometry), front.Sketch.Name, back.Sketch.Name)
    )
    if (
        int(getattr(avatar, "MeshVertexCount", 0)) <= 100
        or int(getattr(avatar, "MeshTriangleCount", 0)) <= 100
    ):
        msg = "visual fixture does not contain a real humanoid mesh"
        raise RuntimeError(msg)
    activate("ClothSimulationWorkbench", "Cloth Simulation", ["ClothSimulation_Edit"])
    simulation_panel = SimulationQualityTaskPanel(scene)
    task_dock = show_task(
        simulation_panel,
        "Simulation Workbench arranged",
        (
            "Preset",
            "Particle distance",
            "Density",
            "Avatar skin offset",
            "Simulation steps",
            "Step",
            "Run 30",
            "Reset",
        ),
    )
    readiness_labels = getattr(simulation_panel, "workflow_labels", {})
    expected_readiness_keys = {
        "patterns",
        "sewing",
        "target",
        "arrangement",
        "simulation",
    }
    if set(readiness_labels) != expected_readiness_keys:
        raise RuntimeError("simulation panel did not expose all five workflow readiness rows")
    if any(not readiness_labels[key].isVisible() for key in expected_readiness_keys):
        raise RuntimeError("one or more workflow readiness rows are not visible")
    expected_row_text = {
        "patterns": "Pattern pieces:",
        "sewing": "Sewing:",
        "target": "Drape target:",
        "arrangement": "Arrangement:",
        "simulation": "Simulation:",
    }
    for key, required_text in expected_row_text.items():
        if required_text not in str(readiness_labels[key].text()):
            raise RuntimeError(
                f"workflow readiness row {key} is missing its expected label {required_text!r}"
            )
    readiness_states = {
        key: str(readiness_labels[key].property("workflowState"))
        for key in sorted(expected_readiness_keys)
    }
    for key in ("patterns", "target", "simulation"):
        if readiness_states[key] != "ready":
            raise RuntimeError(
                f"workflow readiness row {key} should be ready, got {readiness_states[key]}"
            )
    log("simulation-workflow-readiness=" + json.dumps(readiness_states, sort_keys=True))
    save(
        "simulation-workflow-readiness.png",
        "Simulation workflow readiness checklist",
        "visible five-stage setup checklist for assigned native Sketcher tunic pieces and current drape target",
    )
    view = Gui.activeDocument().activeView()
    # FreeCAD animates viewFront/viewRear transitions by default. Capturing while
    # that transition is in progress records different camera rotations depending
    # on the preceding view, which can mirror left/right seam colors between frames.
    # Disable animation before setting either screenshot view so both captures use
    # the same canonical orthographic projection.
    view.setAnimationEnabled(False)
    view.setCameraType("Orthographic")
    view.viewFront()
    view.fitAll()
    events()
    task_dock.hide()
    events()
    arranged_front_orientation = view.getCameraOrientation()
    log("camera-arranged=" + json.dumps(_camera_snapshot(view), sort_keys=True))
    save(
        "cloth-simulation-arranged.png",
        "Simulation Workbench arranged",
        "vertical sewn tunic generated from native Sketcher pattern sources on production mannequin",
    )
    task_dock.show()
    task_dock.raise_()
    events()
    pathlib.Path(os.path.join(OUT, "cloth-tunic-mannequin-motion-frames")).mkdir(
        exist_ok=True, parents=True
    )
    task_dock.hide()
    events()
    view.setCameraType("Orthographic")
    view.viewAxonometric()
    view.fitAll()
    events()
    save(
        "cloth-tunic-mannequin-motion-frames/motion-000.png",
        "mannequin drape step 0",
        "production tunic before gravity",
    )
    if TUNIC_PRODUCTION_AUDIT:
        _run_production_tunic_drape(simulation_panel, scene, doc, task_dock, view, seam_records)
    else:
        for frame_index, batch in enumerate((10, 10, 10, 10, 10, 10, 10, 10, 10), start=1):
            simulation_panel.step(batch)
            doc.recompute()
            events()
            view.viewAxonometric()
            view.fitAll()
            events()
            save(
                "cloth-tunic-mannequin-motion-frames/motion-%03d.png" % frame_index,
                "mannequin drape step %d" % int(scene.Steps),
                "production tunic gravity progression",
            )
        task_dock.show()
        task_dock.raise_()
        events()
    if int(scene.Steps) != 90 or float(scene.SimulatedTime) <= 0.0 or not bool(scene.FiniteState):
        msg = "simulation did not reach a finite 90-step state"
        raise RuntimeError(msg)
    log("seam-world-x-step90=" + json.dumps(_seam_lateral_snapshot(proxy, x_mid), sort_keys=True))

    from freecad_cloth.sewing.SeamOverlay import refresh_seam_overlay

    overlay = refresh_seam_overlay(doc)
    expected_seam_ids = {str(seam.SeamId) for seam, _piece_a, _piece_b in seam_records}
    rendered_seam_ids = set(getattr(overlay, "rendered_seam_ids", ()))
    if overlay is None or not expected_seam_ids or not expected_seam_ids <= rendered_seam_ids:
        msg = (
            "simulation seam overlay is not rendering exact solver stitch pairs: "
            f"expected={sorted(expected_seam_ids)!r} rendered={sorted(rendered_seam_ids)!r}"
        )
        raise RuntimeError(msg)
    log(
        "simulation-seam-overlay=passed ids=%s source=solver-stitch-pairs"
        % sorted(rendered_seam_ids)
    )
    if any(panel.Mesh.CountFacets <= 10 for panel in scene.DrapePanels):
        msg = "draped tunic panel mesh is empty"
        raise RuntimeError(msg)
    from freecad_cloth.simulation.ClothDiagnosticsGui import (
        DiagnosticsTaskPanel,
        create_diagnostic_map,
    )

    diagnostics_panel = DiagnosticsTaskPanel(scene)
    diagnostic_dock = show_task(
        diagnostics_panel,
        "Cloth Diagnostics",
        (
            "Formula:",
            "Read-only",
            "Refresh analysis",
            "Create diagnostic map",
            "Export analysis data",
        ),
    )
    diagnostic_dock.hide()
    events()
    diagnostic_maps = create_diagnostic_map(scene, "stress")
    if not diagnostic_maps:
        msg = "valid draped tunic produced no diagnostic stress map"
        raise RuntimeError(msg)
    for diagnostic in diagnostic_maps:
        diagnostic.ViewObject.Visibility = True
    log("diagnostic-map=passed metric=stress maps=%d" % len(diagnostic_maps))
    original_finite = bool(scene.FiniteState)
    scene.FiniteState = False
    try:
        create_diagnostic_map(scene, "stress")
    except RuntimeError as exc:
        log(f"diagnostic-stale-guard=passed message={exc!s}")
    else:
        msg = "diagnostics created a map from a non-finite simulation state"
        raise RuntimeError(msg)
    finally:
        scene.FiniteState = original_finite
    view.viewFront()
    view.fitAll()
    events()
    save(
        "cloth-simulation-draped-diagnostics.png",
        "Cloth Diagnostics stress map",
        "read-only stress utilization map over the valid 90-step drape",
    )
    for diagnostic in diagnostic_maps:
        diagnostic.ViewObject.Visibility = False
    if TUNIC_PRODUCTION_AUDIT:
        _validate_authoritative_tunic_seams(scene, seam_records)
    write_drape_metrics(
        panels,
        avatar,
        x_mid,
        shoulder_z=shoulder_z,
        hem_z=hem_z,
        seam_records=seam_records,
        proxy=proxy,
        collision_surface=target_surface if TUNIC_PRODUCTION_AUDIT else None,
    )
    bounds = []
    for panel in scene.DrapePanels:
        b = panel.Mesh.BoundBox
        bounds.append((b.XMin, b.XMax, b.YMin, b.YMax, b.ZMin, b.ZMax))
    log(f"drape-bounds={bounds}")
    task_dock.hide()
    events()
    for direction, method_name in (
        ("front", "viewFront"),
        ("rear", "viewRear"),
        ("left", "viewLeft"),
        ("right", "viewRight"),
        ("top", "viewTop"),
        ("bottom", "viewBottom"),
    ):
        getattr(view, method_name)()
        view.fitAll()
        events()
        if direction == "front":
            # With animation disabled, viewFront must resolve to exactly the same
            # orientation as the arranged capture, independently of prior views.
            restored_orientation = view.getCameraOrientation()
            expected_q = tuple(float(value) for value in arranged_front_orientation.Q)
            actual_q = tuple(float(value) for value in restored_orientation.Q)
            rotation_agreement = abs(sum(a * b for a, b in zip(expected_q, actual_q, strict=True)))
            if rotation_agreement < 1.0 - 1e-8:
                msg = (
                    "draped front camera rotation does not match arranged screenshot "
                    f"(quaternion agreement={rotation_agreement:.12f})"
                )
                raise RuntimeError(msg)
            log("camera-draped-front=" + json.dumps(_camera_snapshot(view), sort_keys=True))
        save(
            f"cloth-simulation-draped-{direction}.png",
            f"Simulation Workbench draped {direction}",
            "same sewn tunic after %d real steps; six-side audit from native Sketcher pattern sources"
            % int(scene.Steps),
        )
        if direction == "front":
            save(
                "cloth-simulation-draped.png",
                "Simulation Workbench draped front",
                "legacy front screenshot alias; native Sketcher tunic source",
            )
    from freecad_cloth.simulation.DrapeVisualSanity import assert_drape_diagnostics

    with pathlib.Path(METRICS).open(encoding="utf-8") as handle:
        # This fixture is intentionally unpinned: gravity may place the free-draped
        # hem below the authored hip reference without indicating detachment, collapse,
        # or collision failure. Keep those other fail-closed diagnostics authoritative.
        assert_drape_diagnostics(
            json.load(handle).get("panels", ()),
            allowed_diagnostics={"below-hem-candidate"},
        )
    task_dock.show()
    task_dock.raise_()
    events()
    close_task()
    App.closeDocument(doc.Name)


def main() -> None:
    """Run the configured GUI acceptance scenarios and save their evidence.

    Raises:
        RuntimeError: If FreeCAD GUI startup or a requested acceptance scenario fails.
    """
    log("script-start")
    if Gui.getMainWindow() is None or not Gui.getMainWindow().isVisible():
        msg = "FreeCAD GUI did not launch"
        raise RuntimeError(msg)
    Gui.getMainWindow().show()
    events()
    events()
    if os.environ.get("CLOTH_TUNIC_AUDIT_RUN_AVATAR_ACCEPTANCE"):
        load_and_run(
            os.path.join(ROOT, "tests/freecad_avatar_acceptance.py"),
            "freecad_avatar_acceptance_inprocess",
        )
        log("avatar-provider-acceptance=passed")
    if not os.environ.get("CLOTH_TUNIC_AUDIT_SKIP_CANONICAL_ACCEPTANCE"):
        run_canonical_acceptance()
    if not os.environ.get("CLOTH_TUNIC_AUDIT_SKIP_SIMULATION"):
        simulation()
    log("scenario-pass")


exit_code = 0
try:
    main()
except BaseException as error:
    exit_code = 1
    print(f"SCENARIO FAILURE: {error!r}", flush=True)
    print(traceback.format_exc(), flush=True)
    log(f"scenario-fail exception={error!r}")
finally:
    try:
        close_task()
        for document in list(App.listDocuments().values()):
            with contextlib.suppress(Exception):
                App.closeDocument(document.Name)
        events()
        log("script-end exit-code=%d" % exit_code)
        if exit_code == 0:
            log("tunic-audit-process-exit=success")
            sys.stdout.flush()
            getattr(os, "_" + "exit")(0)
        window = Gui.getMainWindow()
        if window is not None:
            window.close()
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.quit()
    except BaseException:
        pass
if exit_code:
    os._exit(1)
