"""Real FreeCAD/Xvfb acceptance for direct fitting manipulation.

The test drives the same viewport callback surface used by the task panel and
verifies that a drag near an arrangement point becomes a persistent placement.
"""

import sys

import FreeCAD as App
import FreeCADGui as Gui
import Part


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
    controller = panel.controller

    start = _screen(view, App.Vector(0.0, 0.0, 0.0))
    snap = controller._screen_position(
        doc.getObject(scene.ArrangementPointObjects[0])
    )

    controller._mouse_event(
        {
            "State": "DOWN",
            "Button": "BUTTON1",
            "Position": start,
            "Object": piece.Label,
        }
    )
    controller._location_event(
        {
            "State": "MOVE",
            "Position": (int(round(snap[0])), int(round(snap[1]))),
        }
    )

    if controller.snap_point is None:
        raise RuntimeError("drag did not expose an arrangement-point snap preview")

    controller._mouse_event(
        {
            "State": "UP",
            "Button": "BUTTON1",
            "Position": (int(round(snap[0])), int(round(snap[1]))),
        }
    )
    doc.recompute()

    base = piece.Placement.Base
    if abs(float(base.x) - 120.0) > 1e-6:
        raise RuntimeError("piece did not snap to arrangement-point X")
    if abs(float(base.y) - 80.0) > 1e-6:
        raise RuntimeError("piece did not snap to arrangement-point Y")
    if abs(float(base.z) - 3.0) > 1e-6:
        raise RuntimeError("piece did not adopt arrangement-point offset")

    persisted = tuple(str(value) for value in scene.PiecePlacements)
    if not any("120.0,80.0,3.0" in value for value in persisted):
        raise RuntimeError("snapped placement was not persisted in PiecePlacements")

    panel.reject()
    if controller._mouse_callback is not None or controller._location_callback is not None:
        raise RuntimeError("Interactive Arrange callbacks were not removed")

    print("interactive-arrange=passed snapped=true persisted=true")
    print("interactive-arrange-cleanup=passed callbacks-removed=true")
    doc.close()


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print("interactive-arrange=failed", exc)
        App.Console.PrintError("Interactive Arrange acceptance failed: %s\n" % exc)
        sys.exit(1)
