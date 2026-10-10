"""FreeCAD/Xvfb acceptance and visual evidence for viewport-picked anchors and Arrange."""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import FreeCAD as App
import FreeCADGui as Gui
import Part

from tests.support.freecad_input import UiGifRecorder


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


def _create_demo_avatar(doc):
    target = doc.addObject("Part::Feature", "AnchorAvatarSurface")
    target.Label = "Mannequin / Fitting Target"
    parts = [
        Part.makeSphere(18.0, App.Vector(0.0, 0.0, 48.0)),
        Part.makeSphere(9.0, App.Vector(0.0, 0.0, 72.0)),
        Part.makeSphere(14.0, App.Vector(0.0, 0.0, 25.0)),
        Part.makeCylinder(5.0, 9.0, App.Vector(0.0, 0.0, 59.0)),
        Part.makeCylinder(3.5, 26.0, App.Vector(-12.0, 0.0, 55.0), App.Vector(-1.0, 0.0, 0.0)),
        Part.makeCylinder(3.5, 26.0, App.Vector(12.0, 0.0, 55.0), App.Vector(1.0, 0.0, 0.0)),
        Part.makeCylinder(5.5, 25.0, App.Vector(-7.0, 0.0, 22.0), App.Vector(0.0, 0.0, -1.0)),
        Part.makeCylinder(5.5, 25.0, App.Vector(7.0, 0.0, 22.0), App.Vector(0.0, 0.0, -1.0)),
    ]
    target.Shape = Part.makeCompound(parts)
    target.ViewObject.ShapeColor = (0.76, 0.75, 0.71)
    target.ViewObject.LineColor = (0.28, 0.28, 0.27)
    return target


def _create_demo_piece(doc):
    piece = doc.addObject("Part::Feature", "FrontPatternPiece")
    piece.Label = "Front Pattern Piece"
    piece.addProperty("App::PropertyString", "PatternType", "Pattern")
    piece.PatternType = "PatternPiece"
    piece.addProperty("App::PropertyString", "PieceId", "Pattern")
    piece.PieceId = "front-pattern-piece"
    outline = Part.makePolygon(
        [
            App.Vector(-20.0, 0.0, 0.0),
            App.Vector(0.0, 2.0, 0.0),
            App.Vector(20.0, 0.0, 0.0),
            App.Vector(20.0, 10.0, 0.0),
            App.Vector(14.0, 20.0, 0.0),
            App.Vector(14.0, 60.0, 0.0),
            App.Vector(-14.0, 60.0, 0.0),
            App.Vector(-14.0, 20.0, 0.0),
            App.Vector(-20.0, 10.0, 0.0),
            App.Vector(-20.0, 0.0, 0.0),
        ]
    )
    piece.Shape = Part.Face(outline).extrude(App.Vector(0.0, 0.0, 1.0))
    piece.Placement = App.Placement(
        App.Vector(-60.0, -22.0, 48.0),
        App.Rotation(App.Vector(0.0, 0.0, 1.0), 0.0),
    )
    piece.ViewObject.ShapeColor = (0.82, 0.69, 0.51)
    piece.ViewObject.LineColor = (0.25, 0.20, 0.15)
    return piece


def run():
    from freecad_cloth.avatar.FittingCommands import (
        add_selected_pattern_pieces,
        arrangement_anchor_status,
        create_fitting_scene,
    )
    from freecad_cloth.avatar.FittingGui import FittingTaskPanel

    doc = App.newDocument("InteractiveArrangeAcceptance")
    target = _create_demo_avatar(doc)
    piece = _create_demo_piece(doc)
    scene = create_fitting_scene()
    scene.AvatarProxy = target
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(piece)
    add_selected_pattern_pieces()
    doc.recompute()

    view = Gui.activeDocument().activeView()
    view.setCameraType("Orthographic")
    view.viewAxonometric()
    view.fitAll()
    panel = FittingTaskPanel(scene)
    Gui.Control.showDialog(panel)
    view.fitAll()
    Gui.updateGui()
    controller = panel.controller

    # Capture the creation step independently from the drag-and-snap animation.
    # The selection observer receives the same object/subelement/world-point tuple
    # that FreeCAD emits for a viewport face pick.
    anchor_world = App.Vector(-18.0, 0.0, 48.0)
    anchor_recorder = UiGifRecorder(
        "artifacts/ui-gifs/arrangement-anchor.gif",
        gui=Gui,
        window=Gui.getMainWindow(),
        fps=10,
        scale=0.65,
        max_frames=80,
        show_cursor=False,
    )
    anchor_recorder.start()
    try:
        anchor_recorder.hold(500)
        panel.start_anchor_pick()
        anchor_recorder.hold(700)
        panel.anchor_picker.addSelection(
            doc.Name,
            target.Name,
            "Face1",
            anchor_world.x,
            anchor_world.y,
            anchor_world.z,
        )
        Gui.updateGui()
        anchor_recorder.hold(1100)
    finally:
        if anchor_recorder._started:
            anchor_recorder.stop()

    if len(scene.ArrangementPointObjects) != 1:
        raise RuntimeError("viewport surface pick did not create exactly one arrangement anchor")
    point_obj = doc.getObject(scene.ArrangementPointObjects[0])
    if point_obj is None or point_obj.AnchorTarget is None:
        raise RuntimeError("surface anchor did not persist its target-object reference")
    if point_obj.AnchorTarget.Name != target.Name:
        raise RuntimeError("surface anchor references the wrong target")
    if point_obj.AnchorSubelement != "Face1":
        raise RuntimeError("surface anchor did not persist its selected subelement")
    if arrangement_anchor_status(point_obj) != "valid":
        raise RuntimeError("new surface anchor is not current against its target geometry")
    anchor_records = [json.loads(value) for value in scene.ArrangementAnchorData]
    if len(anchor_records) != 1 or anchor_records[0]["target"] != target.Name:
        raise RuntimeError("surface-anchor metadata was not persisted in the fitting scene")

    viewport_height = float(view.getSize()[1])
    start_top = _screen(view, piece.Placement.Base)
    start = (start_top[0], int(round(viewport_height - start_top[1])))
    snap_screen = controller._screen_position(point_obj)
    # Coin mouse/location events use a bottom-left origin; projected snap points
    # returned by the controller are converted to top-left screen coordinates.
    snap = (snap_screen[0], viewport_height - snap_screen[1])
    recorder = UiGifRecorder(
        "artifacts/ui-gifs/interactive-arrange.gif",
        gui=Gui,
        window=Gui.getMainWindow(),
        fps=12,
        scale=0.65,
        max_frames=100,
        show_cursor=False,
    )
    recorder.start()
    try:
        recorder.hold(500)
        controller._mouse_event(
            {
                "State": "DOWN",
                "Button": "BUTTON1",
                "Position": start,
                "Object": piece.Label,
            }
        )
        recorder.hold(250)
        for index in range(1, 21):
            fraction = index / 20.0
            position = (
                start[0] + (snap[0] - start[0]) * fraction,
                start[1] + (snap[1] - start[1]) * fraction,
            )
            controller._location_event(
                {
                    "State": "MOVE",
                    "Position": (int(round(position[0])), int(round(position[1]))),
                }
            )
            if index % 4 == 0:
                recorder.hold(100)
        if controller.snap_point is None or controller._snap_indicator is None:
            raise RuntimeError(
                "callback-driven viewport drag did not expose snap preview and marker"
            )
        recorder.hold(900)
        _capture_screen("artifacts/interactive-arrange.png")
        controller._mouse_event(
            {
                "State": "UP",
                "Button": "BUTTON1",
                "Position": (int(round(snap[0])), int(round(snap[1]))),
            }
        )
        recorder.hold(700)
    finally:
        if recorder._started:
            recorder.stop()
    doc.recompute()

    base = piece.Placement.Base
    expected = (float(point_obj.X), float(point_obj.Y), float(point_obj.Offset))
    actual = (float(base.x), float(base.y), float(base.z))
    if any(abs(left - right) > 1e-6 for left, right in zip(actual, expected)):
        raise RuntimeError("piece did not snap to the picked surface anchor: " + repr(actual))
    if controller._snap_indicator is not None:
        raise RuntimeError("snap marker remained after placement commit")

    from freecad_cloth.avatar.AvatarFitting import PiecePlacement

    persisted = tuple(PiecePlacement.from_string(value) for value in scene.PiecePlacements)
    matching = [value for value in persisted if value.piece_id == "front-pattern-piece"]
    if len(matching) != 1 or matching[0].position != expected:
        raise RuntimeError("snapped placement was not persisted in the fitting scene")

    # Whole-object transforms must move the anchor with its target, not invalidate it
    # or leave the marker at the old world coordinate.
    original_anchor = (float(point_obj.X), float(point_obj.Y), float(point_obj.Offset))
    target.Placement = App.Placement(
        App.Vector(4.0, -3.0, 6.0), target.Placement.Rotation
    )
    doc.recompute()
    controller._points()
    transformed_world = target.Placement.multVec(point_obj.AnchorLocalPoint)
    transformed_anchor = (
        float(point_obj.X), float(point_obj.Y), float(point_obj.Offset)
    )
    expected_transform = (
        original_anchor[0] + 4.0,
        original_anchor[1] - 3.0,
        original_anchor[2] + 6.0,
    )
    if any(
        abs(actual_value - expected_value) > 1e-6
        for actual_value, expected_value in zip(transformed_anchor, expected_transform)
    ):
        raise RuntimeError(
            "surface anchor did not follow target Placement: "
            + repr((transformed_anchor, expected_transform))
        )
    if any(
        abs(actual_value - expected_value) > 1e-6
        for actual_value, expected_value in zip(
            (transformed_world.x, transformed_world.y, transformed_world.z),
            transformed_anchor,
        )
    ):
        raise RuntimeError("anchor marker is not coincident with the transformed target")

    # Changing local shape geometry without preserving the anchored surface contract
    # must still make the anchor stale and remove it from snap candidates.
    changed_shape = target.Shape.copy()
    changed_shape.translate(App.Vector(0.0, 0.0, 1.0))
    target.Shape = changed_shape
    doc.recompute()
    if arrangement_anchor_status(point_obj) != "stale":
        raise RuntimeError("changing the source geometry did not invalidate its surface anchor")
    if point_obj in controller._points():
        raise RuntimeError("a stale surface anchor remained available for snapping")
    if "Stale anchor:" not in str(point_obj.Label):
        raise RuntimeError("stale surface anchor was not marked visibly in the viewport")

    # Exercise the actual avatar skeleton rebuild path. Select a triangle that
    # moves strongly under a manual joint rotation, then prove the saved barycentric
    # anchor follows that same triangle when the avatar mesh is rebuilt.
    from freecad_cloth.avatar.AvatarCommands import create_avatar, set_avatar_joint
    from freecad_cloth.avatar.FittingCommands import (
        _mesh_anchor_local_position,
        create_arrangement_anchor,
    )

    avatar = create_avatar(attach_collision=False, doc=doc, object_name="PoseAnchorAvatar")
    scene.AvatarProxy = avatar
    doc.recompute()

    def _mesh_snapshot(mesh_target):
        mesh_vertices, mesh_triangles = mesh_target.Mesh.Topology
        return (
            tuple((float(v.x), float(v.y), float(v.z)) for v in mesh_vertices),
            tuple(tuple(int(index) for index in face) for face in mesh_triangles),
        )

    rest_vertices, rest_triangles = _mesh_snapshot(avatar)
    set_avatar_joint("upperarm01.L", y=30.0)
    posed_vertices, posed_triangles = _mesh_snapshot(avatar)
    if posed_triangles != rest_triangles:
        raise RuntimeError("avatar skeleton edit unexpectedly changed mesh triangle connectivity")

    moved_triangle_index = max(
        range(len(rest_triangles)),
        key=lambda index: sum(
            sum(
                (posed_vertices[vertex][axis] - rest_vertices[vertex][axis]) ** 2
                for axis in range(3)
            )
            for vertex in rest_triangles[index]
        ),
    )
    moved_triangle = rest_triangles[moved_triangle_index]
    movement_score = sum(
        sum(
            (posed_vertices[vertex][axis] - rest_vertices[vertex][axis]) ** 2
            for axis in range(3)
        )
        for vertex in moved_triangle
    )
    if movement_score <= 1e-4:
        raise RuntimeError("manual skeleton edit did not deform any avatar surface triangle")

    set_avatar_joint("upperarm01.L", y=0.0)
    reset_vertices, reset_triangles = _mesh_snapshot(avatar)
    if reset_triangles != rest_triangles:
        raise RuntimeError("reset avatar pose changed surface triangle connectivity")
    triangle_weights = (0.2, 0.3, 0.5)
    local_pick = tuple(
        sum(
            reset_vertices[moved_triangle[index]][axis] * triangle_weights[index]
            for index in range(3)
        )
        for axis in range(3)
    )
    world_pick = avatar.Placement.multVec(App.Vector(*local_pick))
    create_arrangement_anchor(
        "SkeletonSurfaceAnchor",
        avatar,
        world_pick,
        subelement="Facet{}".format(moved_triangle_index + 1),
    )
    records = [json.loads(value) for value in scene.ArrangementAnchorData]
    mesh_anchor_record = next(
        value for value in records if value["name"] == "SkeletonSurfaceAnchor"
    )
    if int(mesh_anchor_record.get("triangle_index", -1)) != moved_triangle_index:
        raise RuntimeError("surface picker did not persist the selected avatar triangle")
    mesh_anchor_obj = doc.getObject("ArrangementPoint_SkeletonSurfaceAnchor")
    rest_anchor = (
        float(mesh_anchor_obj.X), float(mesh_anchor_obj.Y), float(mesh_anchor_obj.Offset)
    )

    # This calls the production avatar rebuild and its fitting-anchor refresh hook.
    set_avatar_joint("upperarm01.L", y=30.0)
    if arrangement_anchor_status(mesh_anchor_obj) != "valid":
        raise RuntimeError("skeleton posing incorrectly invalidated a compatible mesh anchor")
    expected_local = _mesh_anchor_local_position(avatar, mesh_anchor_record)
    expected_world = avatar.Placement.multVec(App.Vector(*expected_local))
    posed_anchor = (
        float(mesh_anchor_obj.X), float(mesh_anchor_obj.Y), float(mesh_anchor_obj.Offset)
    )
    expected_pose_point = (
        float(expected_world.x), float(expected_world.y), float(expected_world.z)
    )
    if any(
        abs(actual_value - expected_value) > 1e-5
        for actual_value, expected_value in zip(posed_anchor, expected_pose_point)
    ):
        raise RuntimeError(
            "surface anchor did not follow the deformed avatar triangle: "
            + repr((posed_anchor, expected_pose_point))
        )
    if sum(
        (posed_anchor[index] - rest_anchor[index]) ** 2 for index in range(3)
    ) <= 1e-4:
        raise RuntimeError("avatar skeleton edit left the surface anchor at its old position")
    if mesh_anchor_obj not in controller._points():
        raise RuntimeError("a valid posed-avatar anchor was excluded from snapping")

    panel.reject()
    if controller._mouse_callback is not None or controller._location_callback is not None:
        raise RuntimeError("Interactive Arrange callbacks were not removed")

    Path("artifacts").mkdir(parents=True, exist_ok=True)
    Path("artifacts/interactive-arrange.log").write_text(
        "arrangement-anchor=passed target-linked=true persisted=true placement-follow=true skeleton-follow=true stale-detection=true\n"
        "interactive-arrange=passed snapped=true persisted=true\n"
        "interactive-arrange-cleanup=passed callbacks-removed=true\n",
        encoding="utf-8",
    )
    print("arrangement-anchor=passed target-linked=true persisted=true placement-follow=true skeleton-follow=true stale-detection=true", flush=True)
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
