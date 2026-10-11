"""Native FreeCAD Surface Pen acceptance, screenshot, and staged-workflow capture."""

import contextlib
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import FreeCAD as App
import FreeCADGui as Gui
import Part

try:
    from PySide import QtWidgets
except ImportError:
    from PySide2 import QtWidgets

from freecad_cloth.common.VisualCaptureValidation import validate_png_capture
from freecad_cloth.pattern.SurfacePen import (
    SurfaceAnchor,
    SurfacePenController,
    SurfacePenTaskPanel,
    create_surface_pen_object,
    extract_surface_draft_to_pattern,
)

ARTIFACTS = Path("artifacts")
ARTIFACTS.mkdir(parents=True, exist_ok=True)


def _events() -> None:
    """Paint FreeCAD's main window before recording a visual state."""
    application = QtWidgets.QApplication.instance()
    Gui.updateGui()
    if application is not None:
        application.processEvents()
    Gui.updateGui()
    if application is not None:
        application.processEvents()


def _capture(name: str) -> Path:
    """Capture and validate a 1280x720 real FreeCAD main-window screenshot."""
    application = QtWidgets.QApplication.instance()
    screen = None if application is None else application.primaryScreen()
    window = Gui.getMainWindow()
    if application is None or screen is None or window is None:
        raise RuntimeError("FreeCAD main window/screen is unavailable for Surface Pen capture")
    geometry = screen.availableGeometry()
    if geometry.width() < 1280 or geometry.height() < 720:
        raise RuntimeError(
            "Surface Pen capture requires a 1280x720-capable screen, got %dx%d"
            % (geometry.width(), geometry.height())
        )
    window.showNormal()
    window.resize(1280, 720)
    window.show()
    window.raise_()
    window.activateWindow()
    _events()
    document = Gui.activeDocument()
    view = document.activeView() if document is not None else None
    if view is None:
        raise RuntimeError("FreeCAD active view is unavailable for Surface Pen capture")
    view.redraw()
    time.sleep(0.10)
    _events()
    image = screen.grabWindow(int(window.winId()))
    if image.isNull() or (int(image.width()), int(image.height())) != (1280, 720):
        raise RuntimeError(f"invalid FreeCAD Surface Pen screenshot: {name}")
    path = ARTIFACTS / name
    if not image.save(str(path)):
        raise RuntimeError(f"failed to save FreeCAD Surface Pen screenshot: {path}")
    metrics = validate_png_capture(
        path,
        expected_width=1280,
        expected_height=720,
        min_nonwhite_pixels=500,
        min_distinct_rgb=16,
        min_opaque_pixels=500,
    )
    print(
        "surface-pen-capture=%s opaque=%d nonwhite=%d colors=%d"
        % (name, metrics["opaque_pixels"], metrics["nonwhite_pixels"], metrics["distinct_rgb"]),
        flush=True,
    )
    return path


def _mouse(state: str, position: tuple[int, int]) -> dict[str, object]:
    """Return the FreeCAD callback mapping for a left-button stroke event."""
    return {"State": state, "Button": "BUTTON1", "Position": position}


def _record_frame(index: int) -> None:
    """Capture one state in the Surface Pen workflow animation."""
    _capture(f"surface-pen-frame-{index:02d}.png")


def main() -> None:
    """Exercise controller input, native Sketcher extraction, and target invalidation."""
    doc = App.newDocument("SurfacePenSmoke")
    controller = None
    panel = None
    draft = None
    try:
        target = doc.addObject("Part::Feature", "SurfacePenTarget")
        target.Label = "Surface Pen target"
        target.Shape = Part.makeBox(140.0, 100.0, 20.0)
        target.ViewObject.ShapeColor = (0.78, 0.82, 0.88)
        doc.recompute()

        view = Gui.activeDocument().activeView()
        view.viewAxonometric()
        view.fitAll()
        _events()

        controller = SurfacePenController(target, target)
        panel = SurfacePenTaskPanel(controller)
        # Keep this acceptance path on the original drag-based interaction.
        # Point placement and curve-point extraction are exercised below as well.
        panel.input_mode_combo.setCurrentText("Freehand trace")
        controller.activate()
        Gui.Control.showDialog(panel)
        _events()
        _record_frame(1)

        # Route scripted picks through the real mouse/location event handlers. The
        # deterministic screen-to-anchor map avoids depending on camera pixel picks
        # while exercising stroke continuation, closure feedback, and overlay updates.
        pick_map = {
            (100, 120): SurfaceAnchor((10.0, 10.0, 20.0), (0.0, 0.0, 1.0)),
            (180, 120): SurfaceAnchor((110.0, 10.0, 20.0), (0.0, 0.0, 1.0)),
            (180, 190): SurfaceAnchor((110.0, 70.0, 20.0), (0.0, 0.0, 1.0)),
            (100, 190): SurfaceAnchor((10.0, 70.0, 20.0), (0.0, 0.0, 1.0)),
            (102, 121): SurfaceAnchor((10.5, 10.2, 20.0), (0.0, 0.0, 1.0)),
        }
        controller._pick = lambda position: pick_map.get((int(position[0]), int(position[1])))

        controller._mouse_event(_mouse("DOWN", (100, 120)))
        controller._location_event({"Position": (180, 120)})
        controller._location_event({"Position": (180, 190)})
        controller._mouse_event(_mouse("UP", (180, 190)))
        assert len(controller.anchors) == 3
        assert not controller.can_finish
        assert not panel.finish_button.isEnabled()
        _events()
        _record_frame(2)

        # Lift the pen, start the next segment, and return to within the documented
        # closure tolerance. The controller should preview the closing edge and
        # enable Finish only when the boundary can actually be closed.
        controller._mouse_event(_mouse("DOWN", (100, 190)))
        controller._location_event({"Position": (102, 121)})
        controller._mouse_event(_mouse("UP", (102, 121)))
        assert len(controller.anchors) == 5
        assert controller.can_finish
        assert panel.finish_button.isEnabled()
        assert controller._overlay is not None
        assert "Boundary closed" in panel.status.text()
        _events()
        _record_frame(3)
        _capture("surface-pen.png")

        if not panel.finish():
            raise AssertionError(f"Surface Pen extraction failed: {panel.status.text()}")
        pieces = [obj for obj in doc.Objects if getattr(obj, "PatternType", "") == "PatternPiece"]
        assert len(pieces) == 1
        piece = pieces[0]
        draft = piece.SurfaceDraft
        assert str(piece.GeometryAuthority) == "Sketcher"
        assert piece.Sketch is not None
        assert piece.Sketch.TypeId == "Sketcher::SketchObject"
        assert str(draft.Status) == "Extracted"
        assert len(tuple(piece.Sketch.Geometry)) == 4

        # Capture the actual extracted Sketcher result, not a hand-drawn illustration.
        target.ViewObject.Visibility = False
        view.viewTop()
        view.fitAll()
        _events()
        _capture("surface-pen-pattern.png")
        _record_frame(4)

        # A curve point between two corners must survive extraction as native
        # Sketcher B-spline geometry rather than being reduced to a line chain.
        curve_anchors = (
            SurfaceAnchor((10.0, 10.0, 20.0), (0.0, 0.0, 1.0), "corner"),
            SurfaceAnchor((60.0, 0.0, 20.0), (0.0, 0.0, 1.0), "curve"),
            SurfaceAnchor((110.0, 10.0, 20.0), (0.0, 0.0, 1.0), "corner"),
            SurfaceAnchor((110.0, 70.0, 20.0), (0.0, 0.0, 1.0), "corner"),
            SurfaceAnchor((10.0, 70.0, 20.0), (0.0, 0.0, 1.0), "corner"),
            SurfaceAnchor((10.5, 10.2, 20.0), (0.0, 0.0, 1.0), "corner"),
        )
        curve_draft = create_surface_pen_object(doc, target, curve_anchors)
        curve_piece = extract_surface_draft_to_pattern(curve_draft)
        curve_geometry = tuple(curve_piece.Sketch.Geometry)
        assert len(curve_geometry) == 4
        assert any("bsplinecurve" in type(geometry).__name__.lower() for geometry in curve_geometry)
        assert str(curve_piece.GeometryAuthority) == "Sketcher"

        # Changing the source geometry must invalidate the persisted draft rather
        # than silently reusing coordinates sampled from an older target.
        target.Shape = Part.makeBox(141.0, 100.0, 20.0)
        doc.recompute()
        try:
            extract_surface_draft_to_pattern(draft, tolerance_mm=0.5)
        except ValueError as exc:
            assert "target changed" in str(exc)
        else:
            raise AssertionError("changed target was accepted by a stale Surface Pen draft")
        assert str(draft.Status) == "Stale surface target"

        (ARTIFACTS / "surface-pen.log").write_text(
            "surface-pen-controller=passed\n"
            "surface-pen-native-sketcher-extraction=passed\n"
            "surface-pen-stale-target-guard=passed\n"
            "surface-pen-ui-captures=passed\n",
            encoding="utf-8",
        )
        print("surface-pen-native-smoke=passed", flush=True)
    finally:
        if controller is not None:
            with contextlib.suppress(AttributeError, RuntimeError):
                controller.deactivate()
        with contextlib.suppress(AttributeError, RuntimeError):
            if Gui.Control.activeDialog() is not None:
                Gui.Control.closeDialog()
        if doc.Name in App.listDocuments():
            App.closeDocument(doc.Name)


try:
    main()
    os._exit(0)
except BaseException as exc:
    (ARTIFACTS / "surface-pen.log").write_text(
        "surface-pen-native-smoke=failed\n" + repr(exc) + "\n" + traceback.format_exc(),
        encoding="utf-8",
    )
    print("surface-pen-native-smoke=failed", repr(exc), flush=True)
    print(traceback.format_exc(), flush=True)
    os._exit(1)
