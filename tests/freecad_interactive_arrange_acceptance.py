"""Real mouse-driven FreeCAD/Xvfb acceptance for direct fitting manipulation."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import FreeCAD as App
import FreeCADGui as Gui
import Part

from tests.support.freecad_input import (
    UiGifRecorder,
    focus_main_window,
    mouse_move,
    mouse_press,
    mouse_release,
    viewport_widget,
)


def _capture_screen(path):
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    app = QtWidgets.QApplication.instance()
    if app is None or app.primaryScreen() is None:
        raise RuntimeError("Qt primary screen is unavailable for Interactive Arrange screenshot")
    if not app.primaryScreen().grabWindow(0).save(path):
        raise RuntimeError("failed to save Interactive Arrange UI screenshot")


def _screen(view, vector):
    point = view.getPointOnScreen(vector)
    size = view.getSize()
    return int(round(float(point[0]))), int(round(float(size[1] - point[1])))


def run():
    from freecad_cloth.avatar.FittingCommands import (
        add_selected_pattern_pieces,
        create_arrangement_point,
        create_fitting_scene,
    )
    from freecad_cloth.avatar.FittingGui import FittingTaskPanel

    doc = App.newDocument("InteractiveArrangeAcceptance")
    piece = doc.addObject("Part::Feature", "AcceptancePiece")
    piece.Label = "Acceptance Piece"
    piece.addProperty("App::PropertyString", "PatternType", "Pattern")
    piece.PatternType = "PatternPiece"
    piece.addProperty("App::PropertyString", "PieceId", "Pattern")
    piece.PieceId = "acceptance-piece"
    piece.Shape = Part.makeBox(50.0, 30.0, 1.0)

    scene = create_fitting_scene()
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(piece)
    add_selected_pattern_pieces()

    point = create_arrangement_point(
        "acceptance_snap",
        120.0,
        80.0,
        offset=3.0,
        wrap_direction="front",
    )
    doc.recompute()

    view = Gui.activeDocument().activeView()
    view.setCameraType("Orthographic")
    view.viewTop()
    view.fitAll()

    panel = FittingTaskPanel(scene)
    Gui.Control.showDialog(panel)
    view.fitAll()
    Gui.updateGui()
    controller = panel.controller

    window = focus_main_window(Gui, size=(1280, 720))
    view.fitAll()
    viewport = viewport_widget(Gui, view)
    start = _screen(view, App.Vector(25.0, 15.0, 1.0))
    snap = controller._screen_position(
        doc.getObject(scene.ArrangementPointObjects[0])
    )
    recorder = UiGifRecorder(
        "artifacts/ui-gifs/interactive-arrange.gif",
        gui=Gui,
        window=window,
        fps=7,
        scale=0.5,
        max_frames=100,
    )
    recorder.start()
    recorder.hold(500)
    mouse_press(viewport, start)
    recorder.hold(250)
    for index in range(1, 21):
        fraction = index / 20.0
        position = (
            start[0] + (snap[0] - start[0]) * fraction,
            start[1] + (snap[1] - start[1]) * fraction,
        )
        mouse_move(viewport, position, delay_ms=25)
    if controller.snap_point is None or controller._snap_indicator is None:
        mouse_release(viewport, snap)
        recorder.stop()
        raise RuntimeError(
            "real viewport drag did not expose an arrangement-point snap preview and marker"
        )
    recorder.hold(900)
    _capture_screen("artifacts/interactive-arrange.png")
    mouse_release(viewport, snap)
    recorder.hold(700)
    recorder.stop()
    doc.recompute()

    base = piece.Placement.Base
    if abs(float(base.x) - 120.0) > 1e-6:
        raise RuntimeError("piece did not snap to arrangement-point X")
    if abs(float(base.y) - 80.0) > 1e-6:
        raise RuntimeError("piece did not snap to arrangement-point Y")
    if abs(float(base.z) - 3.0) > 1e-6:
        raise RuntimeError("piece did not adopt arrangement-point offset")
    if controller._snap_indicator is not None:
        raise RuntimeError("snap marker remained after placement commit")

    from freecad_cloth.avatar.AvatarFitting import PiecePlacement

    persisted = tuple(PiecePlacement.from_string(value) for value in scene.PiecePlacements)
    matching = [value for value in persisted if value.piece_id == "acceptance-piece"]
    if len(matching) != 1:
        raise RuntimeError("snapped placement was not persisted for the acceptance piece")
    if matching[0].position != (120.0, 80.0, 3.0):
        raise RuntimeError(
            "persisted placement does not match the snapped arrangement-point position: "
            + str(matching[0].position)
        )

    panel.reject()
    if controller._mouse_callback is not None or controller._location_callback is not None:
        raise RuntimeError("Interactive Arrange callbacks were not removed")

    Path("artifacts").mkdir(parents=True, exist_ok=True)
    Path("artifacts/interactive-arrange.log").write_text(
        "interactive-arrange=passed snapped=true persisted=true\n"
        "interactive-arrange-cleanup=passed callbacks-removed=true\n",
        encoding="utf-8",
    )
    print("interactive-arrange=passed snapped=true persisted=true", flush=True)
    print("interactive-arrange-cleanup=passed callbacks-removed=true", flush=True)
    App.closeDocument(doc.Name)


try:
    run()
except BaseException as exc:
    print("interactive-arrange=failed", exc, flush=True)
    App.Console.PrintError("Interactive Arrange acceptance failed: %s\n" % exc)
    os._exit(1)
os._exit(0)
