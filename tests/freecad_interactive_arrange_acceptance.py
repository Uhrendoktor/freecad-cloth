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
    """Create the same production mannequin used by fitting and simulation."""
    from freecad_cloth.avatar.AvatarCommands import create_avatar

    target = create_avatar(attach_collision=False, doc=doc, object_name="TunicArrangeMannequin")
    target.Label = "Mannequin / Tunic Fitting Target"
    target.ViewObject.Visibility = True
    doc.recompute()
    return target


def _mesh_surface_pick(target, x_fraction, z_fraction, side):
    """Return a real triangle centroid on the mannequin's front or back torso."""
    if side not in {"front", "back"}:
        raise ValueError("side must be 'front' or 'back'")
    vertices, triangles = target.Mesh.Topology
    if not vertices or not triangles:
        raise RuntimeError("the mannequin has no mesh triangles for a surface snap")

    bounds = target.Mesh.BoundBox
    width = float(bounds.XMax - bounds.XMin)
    height = float(bounds.ZMax - bounds.ZMin)
    depth = float(bounds.YMax - bounds.YMin)
    if min(width, height, depth) <= 0.0:
        raise RuntimeError("the mannequin mesh has invalid bounds")

    center_x = float(bounds.XMin) + float(x_fraction) * width
    center_z = float(bounds.ZMin) + float(z_fraction) * height
    band_x = max(45.0, width * 0.12)
    band_z = max(70.0, height * 0.075)
    candidates = []
    for index, triangle in enumerate(triangles):
        points = [vertices[int(vertex)] for vertex in triangle]
        x = sum(float(point.x) for point in points) / 3.0
        y = sum(float(point.y) for point in points) / 3.0
        z = sum(float(point.z) for point in points) / 3.0
        if abs(x - center_x) > band_x or abs(z - center_z) > band_z:
            continue
        candidates.append((index, x, y, z))
    if not candidates:
        raise RuntimeError(
            "no mannequin surface triangle near x/z fractions "
            + repr((float(x_fraction), float(z_fraction), side))
        )

    side_y = (
        min(row[2] for row in candidates) if side == "front" else max(row[2] for row in candidates)
    )
    chosen = min(
        candidates,
        key=lambda row: (
            ((row[1] - center_x) / band_x) ** 2
            + ((row[3] - center_z) / band_z) ** 2
            + 0.35 * ((row[2] - side_y) / max(depth, 1.0)) ** 2
        ),
    )
    triangle_index, x, y, z = chosen
    world = target.Placement.multVec(App.Vector(x, y, z))
    return world, "Facet{}".format(int(triangle_index) + 1)


def _create_demo_tunic_piece(
    doc,
    object_name,
    label,
    piece_id,
    placement,
    color,
    panel_width,
    panel_height,
    extrusion_sign=-1,
):
    """Create a recognizable tunic panel oriented vertically against the mannequin."""
    half_width = 0.5 * float(panel_width)
    half_height = 0.5 * float(panel_height)
    outline_points = [
        (-half_width, 0.0, -half_height),
        (half_width, 0.0, -half_height),
        (half_width, 0.0, half_height * 0.35),
        (half_width * 0.80, 0.0, half_height * 0.91),
        (half_width * 0.30, 0.0, half_height * 0.86),
        (half_width * 0.17, 0.0, half_height * 0.62),
        (-half_width * 0.17, 0.0, half_height * 0.62),
        (-half_width * 0.30, 0.0, half_height * 0.86),
        (-half_width * 0.80, 0.0, half_height * 0.91),
        (-half_width, 0.0, half_height * 0.35),
    ]
    wire = Part.makePolygon(
        [App.Vector(*point) for point in outline_points] + [App.Vector(*outline_points[0])]
    )
    shape = Part.Face(wire).extrude(App.Vector(0.0, float(extrusion_sign) * 3.0, 0.0))
    piece = doc.addObject("Part::Feature", object_name)
    piece.Label = label
    piece.Shape = shape
    piece.addProperty("App::PropertyString", "PatternType", "Pattern")
    piece.PatternType = "PatternPiece"
    piece.addProperty("App::PropertyString", "PieceId", "Pattern")
    piece.PieceId = piece_id
    piece.Placement = App.Placement(
        App.Vector(float(placement[0]), float(placement[1]), float(placement[2])),
        App.Rotation(),
    )
    piece.ViewObject.DisplayMode = "Flat Lines"
    piece.ViewObject.ShapeColor = color
    piece.ViewObject.LineColor = (0.18, 0.16, 0.14)
    piece.ViewObject.LineWidth = 1.4
    piece.ViewObject.Visibility = True
    return piece


def run():
    from freecad_cloth.avatar.FittingCommands import (
        _target_signature,
        add_selected_pattern_pieces,
        arrangement_anchor_status,
        create_fitting_scene,
    )
    from freecad_cloth.avatar.FittingGui import FittingTaskPanel

    doc = App.newDocument("InteractiveArrangeAcceptance")
    target = _create_demo_avatar(doc)
    bounds = target.Mesh.BoundBox
    body_width = float(bounds.XMax - bounds.XMin)
    body_height = float(bounds.ZMax - bounds.ZMin)
    center_x = 0.5 * (float(bounds.XMin) + float(bounds.XMax))
    front_pick, front_subelement = _mesh_surface_pick(
        target, x_fraction=0.43, z_fraction=0.67, side="front"
    )
    back_pick, back_subelement = _mesh_surface_pick(
        target, x_fraction=0.57, z_fraction=0.67, side="back"
    )
    panel_height = max(560.0, min(700.0, 0.40 * body_height))
    panel_width = max(360.0, min(440.0, 0.58 * body_width))
    panel_offset = panel_width + 0.16 * body_width + 50.0
    front_piece = _create_demo_tunic_piece(
        doc,
        "TunicFrontPanel",
        "Tunic Front Panel",
        "tunic-front-panel",
        (center_x - panel_offset, float(front_pick.y) - 35.0, float(front_pick.z)),
        (0.82, 0.57, 0.31),
        panel_width,
        panel_height,
    )
    back_piece = _create_demo_tunic_piece(
        doc,
        "TunicBackPanel",
        "Tunic Back Panel",
        "tunic-back-panel",
        (center_x + panel_offset, float(back_pick.y) + 35.0, float(back_pick.z)),
        (0.33, 0.56, 0.78),
        panel_width,
        panel_height,
    )
    scene = create_fitting_scene()
    scene.AvatarProxy = target
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(front_piece)
    Gui.Selection.addSelection(back_piece)
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

    # Capture the real surface-pick workflow twice so readers see named anchors
    # being created on the front and back of a production mannequin.
    pick_specs = (
        ("TunicFrontAnchor", "front", front_pick, front_subelement),
        ("TunicBackAnchor", "back", back_pick, back_subelement),
    )
    anchor_recorder = UiGifRecorder(
        "artifacts/ui-gifs/arrangement-anchor.gif",
        gui=Gui,
        window=Gui.getMainWindow(),
        fps=10,
        scale=0.65,
        max_frames=120,
        show_cursor=False,
    )
    anchor_recorder.start()
    try:
        anchor_recorder.hold(700)
        for name, wrap, world, subelement in pick_specs:
            panel.anchor_name.setText(name)
            panel.wrap_direction.setCurrentIndex(("front", "back", "left", "right").index(wrap))
            panel.start_anchor_pick()
            Gui.updateGui()
            anchor_recorder.hold(650)
            panel.anchor_picker.addSelection(
                doc.Name,
                target.Name,
                subelement,
                world.x,
                world.y,
                world.z,
            )
            Gui.updateGui()
            anchor_recorder.hold(850)
    finally:
        if anchor_recorder._started:
            anchor_recorder.stop()

    if len(scene.ArrangementPointObjects) != 2:
        raise RuntimeError("surface picking did not create exactly two tunic snap anchors")
    anchor_objects = {}
    for name, wrap, _world, subelement in pick_specs:
        point_obj = next(
            (
                doc.getObject(str(obj_name))
                for obj_name in scene.ArrangementPointObjects
                if getattr(doc.getObject(str(obj_name)), "PointName", "") == name
            ),
            None,
        )
        if point_obj is None or point_obj.AnchorTarget is None:
            raise RuntimeError("surface anchor did not persist target for " + name)
        if point_obj.AnchorTarget.Name != target.Name:
            raise RuntimeError("surface anchor references the wrong mannequin: " + name)
        if point_obj.AnchorSubelement != subelement or not subelement.startswith("Facet"):
            raise RuntimeError(
                "surface anchor did not store its picked mannequin triangle: " + name
            )
        if arrangement_anchor_status(point_obj) != "valid":
            raise RuntimeError("new surface anchor is not current against the mannequin: " + name)
        if str(point_obj.WrapDirection) != wrap:
            raise RuntimeError("surface anchor did not persist wrap direction: " + name)
        anchor_objects[name] = point_obj

    overlay = controller._anchor_overlay
    if overlay is None:
        raise RuntimeError("Interactive Arrange did not create an attachment-point overlay")
    if overlay.getNumChildren() != len(anchor_objects) + 1:
        raise RuntimeError(
            "attachment-point overlay does not contain every marker: "
            + repr((overlay.getNumChildren(), len(anchor_objects)))
        )
    depth_state = overlay.getChild(0)
    if bool(depth_state.test.getValue()) or bool(depth_state.write.getValue()):
        raise RuntimeError("attachment-point overlay is still depth-tested or writes depth")
    for index, point_obj in enumerate(anchor_objects.values(), start=1):
        marker = overlay.getChild(index)
        if marker.getNumChildren() < 2 or not hasattr(marker.getChild(1), "axisOfRotation"):
            raise RuntimeError(
                "attachment-point marker is not camera-facing: " + str(point_obj.PointName)
            )
        if bool(point_obj.ViewObject.Visibility):
            raise RuntimeError(
                "depth-tested document marker remained visible alongside its overlay: "
                + str(point_obj.PointName)
            )

    anchor_records = [json.loads(value) for value in scene.ArrangementAnchorData]
    by_anchor_name = {str(record.get("name", "")): record for record in anchor_records}
    for name, _wrap, _world, _subelement in pick_specs:
        record = by_anchor_name.get(name)
        if record is None or record.get("target") != target.Name:
            raise RuntimeError("surface-anchor metadata was not persisted for " + name)

    viewport_height = float(view.getSize()[1])
    from freecad_cloth.avatar.AvatarFitting import PiecePlacement

    def drag_piece_to_anchor(piece, point_obj, recorder):
        start_top = _screen(view, piece.Placement.Base)
        start = (
            start_top[0],
            int(round(viewport_height - start_top[1])),
        )
        snap_screen = controller._screen_position(point_obj)
        # Coin mouse/location events use a bottom-left origin, unlike the projected
        # coordinates exposed by the controller.
        snap = (snap_screen[0], viewport_height - snap_screen[1])
        recorder.hold(450)
        controller._mouse_event(
            {
                "State": "DOWN",
                "Button": "BUTTON1",
                "Position": start,
                "Object": piece.Label,
            }
        )
        recorder.hold(300)
        for index in range(1, 25):
            fraction = index / 24.0
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
        if controller.snap_point is not point_obj or controller._snap_indicator is None:
            raise RuntimeError(
                "tunic panel did not preview the intended surface anchor: "
                + str(getattr(point_obj, "PointName", point_obj.Label))
            )
        recorder.hold(650)
        controller._mouse_event(
            {
                "State": "UP",
                "Button": "BUTTON1",
                "Position": (int(round(snap[0])), int(round(snap[1]))),
            }
        )
        recorder.hold(650)
        doc.recompute()
        base = piece.Placement.Base
        expected = (float(point_obj.X), float(point_obj.Y), float(point_obj.Offset))
        actual = (float(base.x), float(base.y), float(base.z))
        if any(abs(left - right) > 1e-6 for left, right in zip(actual, expected, strict=True)):
            raise RuntimeError(
                piece.Label + " did not snap to its mannequin anchor: " + repr(actual)
            )
        if controller._snap_indicator is not None:
            raise RuntimeError("snap marker remained after placement commit")
        saved = tuple(PiecePlacement.from_string(value) for value in scene.PiecePlacements)
        matching = [value for value in saved if value.piece_id == str(piece.PieceId)]
        if len(matching) != 1 or matching[0].position != expected:
            raise RuntimeError(piece.Label + " placement was not persisted by the fitting scene")

    recorder = UiGifRecorder(
        "artifacts/ui-gifs/interactive-arrange.gif",
        gui=Gui,
        window=Gui.getMainWindow(),
        fps=12,
        scale=0.65,
        max_frames=160,
        show_cursor=False,
    )
    recorder.start()
    try:
        recorder.hold(700)
        drag_piece_to_anchor(front_piece, anchor_objects["TunicFrontAnchor"], recorder)
        drag_piece_to_anchor(back_piece, anchor_objects["TunicBackAnchor"], recorder)
        _capture_screen("artifacts/interactive-arrange.png")
        recorder.hold(700)
    finally:
        if recorder._started:
            recorder.stop()

    if len(tuple(PiecePlacement.from_string(value) for value in scene.PiecePlacements)) != 2:
        raise RuntimeError("fitting scene did not persist both tunic panel placements")
    point_obj = anchor_objects["TunicFrontAnchor"]

    # Whole-object transforms must move the anchor with its target, not invalidate it
    # or leave the marker at the old world coordinate.
    original_anchor = (float(point_obj.X), float(point_obj.Y), float(point_obj.Offset))
    target.Placement = App.Placement(App.Vector(4.0, -3.0, 6.0), target.Placement.Rotation)
    doc.recompute()
    controller._points()
    transformed_world = target.Placement.multVec(point_obj.AnchorLocalPoint)
    transformed_anchor = (float(point_obj.X), float(point_obj.Y), float(point_obj.Offset))
    expected_transform = (
        original_anchor[0] + 4.0,
        original_anchor[1] - 3.0,
        original_anchor[2] + 6.0,
    )
    if any(
        abs(actual_value - expected_value) > 1e-6
        for actual_value, expected_value in zip(transformed_anchor, expected_transform, strict=True)
    ):
        raise RuntimeError(
            "surface anchor did not follow target Placement: "
            + repr(
                {
                    "actual": transformed_anchor,
                    "expected": expected_transform,
                    "status": arrangement_anchor_status(point_obj),
                    "stored_signature": str(point_obj.AnchorGeometrySignature),
                    "current_signature": _target_signature(target),
                    "local_point": tuple(float(value) for value in point_obj.AnchorLocalPoint),
                    "target_placement": repr(target.Placement),
                }
            )
        )
    if any(
        abs(actual_value - expected_value) > 1e-6
        for actual_value, expected_value in zip(
            (transformed_world.x, transformed_world.y, transformed_world.z),
            transformed_anchor,
            strict=True,
        )
    ):
        raise RuntimeError("anchor marker is not coincident with the transformed target")

    # Keep geometry-invalidation coverage on a separate B-rep target; the public
    # demonstration above deliberately uses the real mesh mannequin.
    shape_probe = doc.addObject("Part::Feature", "ShapeAnchorStaleProbe")
    shape_probe.Label = "Hidden shape-anchor validation target"
    shape_probe.Shape = Part.makeSphere(20.0, App.Vector(0.0, 0.0, 0.0))
    shape_probe.Placement = App.Placement(
        App.Vector(5000.0, 0.0, 900.0),
        App.Rotation(),
    )
    shape_probe.ViewObject.Visibility = False
    scene.AvatarProxy = shape_probe
    doc.recompute()
    from freecad_cloth.avatar.FittingCommands import create_arrangement_anchor

    probe_world = shape_probe.Placement.multVec(App.Vector(20.0, 0.0, 0.0))
    create_arrangement_anchor(
        "ShapeGeometryProbe",
        shape_probe,
        probe_world,
        subelement="Face1",
    )
    probe_obj = next(
        (
            doc.getObject(str(obj_name))
            for obj_name in scene.ArrangementPointObjects
            if getattr(doc.getObject(str(obj_name)), "PointName", "") == "ShapeGeometryProbe"
        ),
        None,
    )
    if probe_obj is None or arrangement_anchor_status(probe_obj) != "valid":
        raise RuntimeError("B-rep geometry-staleness probe could not establish a valid anchor")
    changed_shape = Part.makeCompound(
        [shape_probe.Shape.copy(), Part.makeSphere(2.0, App.Vector(100.0, 0.0, 0.0))]
    )
    shape_probe.Shape = changed_shape
    doc.recompute()
    changed_signature = _target_signature(shape_probe)
    if arrangement_anchor_status(probe_obj) != "stale":
        raise RuntimeError(
            "changing the B-rep source geometry did not invalidate its surface anchor: "
            + repr(
                {
                    "status": arrangement_anchor_status(probe_obj),
                    "stored_signature": str(probe_obj.AnchorGeometrySignature),
                    "current_signature": changed_signature,
                }
            )
        )
    if probe_obj in controller._points():
        raise RuntimeError("a stale B-rep surface anchor remained available for snapping")
    if "Stale anchor:" not in str(probe_obj.Label):
        raise RuntimeError("stale B-rep anchor was not marked visibly in the viewport")
    scene.AvatarProxy = target
    doc.recompute()
    controller._points()

    # Exercise the actual avatar skeleton rebuild path. Select a triangle that
    # moves strongly under a manual joint rotation, then prove the saved barycentric
    # anchor follows that same triangle when the avatar mesh is rebuilt.
    from freecad_cloth.avatar.AvatarCommands import set_avatar_joint
    from freecad_cloth.avatar.FittingCommands import _mesh_anchor_local_position

    avatar = target
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
        sum((posed_vertices[vertex][axis] - rest_vertices[vertex][axis]) ** 2 for axis in range(3))
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
        float(mesh_anchor_obj.X),
        float(mesh_anchor_obj.Y),
        float(mesh_anchor_obj.Offset),
    )

    # This calls the production avatar rebuild and its fitting-anchor refresh hook.
    set_avatar_joint("upperarm01.L", y=30.0)
    if arrangement_anchor_status(mesh_anchor_obj) != "valid":
        raise RuntimeError("skeleton posing incorrectly invalidated a compatible mesh anchor")
    expected_local = _mesh_anchor_local_position(avatar, mesh_anchor_record)
    expected_world = avatar.Placement.multVec(App.Vector(*expected_local))
    posed_anchor = (
        float(mesh_anchor_obj.X),
        float(mesh_anchor_obj.Y),
        float(mesh_anchor_obj.Offset),
    )
    expected_pose_point = (
        float(expected_world.x),
        float(expected_world.y),
        float(expected_world.z),
    )
    if any(
        abs(actual_value - expected_value) > 1e-5
        for actual_value, expected_value in zip(posed_anchor, expected_pose_point, strict=True)
    ):
        raise RuntimeError(
            "surface anchor did not follow the deformed avatar triangle: "
            + repr((posed_anchor, expected_pose_point))
        )
    if sum((posed_anchor[index] - rest_anchor[index]) ** 2 for index in range(3)) <= 1e-4:
        raise RuntimeError("avatar skeleton edit left the surface anchor at its old position")
    if mesh_anchor_obj not in controller._points():
        raise RuntimeError("a valid posed-avatar anchor was excluded from snapping")

    panel.reject()
    if controller._mouse_callback is not None or controller._location_callback is not None:
        raise RuntimeError("Interactive Arrange callbacks were not removed")
    if controller._anchor_overlay is not None or controller._anchor_visibility:
        raise RuntimeError("Interactive Arrange did not remove/restore its anchor overlay state")
    if any(not bool(obj.ViewObject.Visibility) for obj in anchor_objects.values()):
        raise RuntimeError("persistent anchor marker visibility was not restored after Arrange")

    Path("artifacts").mkdir(parents=True, exist_ok=True)
    Path("artifacts/interactive-arrange.log").write_text(
        "arrangement-anchor=passed target-linked=true persisted=true placement-follow=true skeleton-follow=true stale-detection=true\n"
        "interactive-arrange=passed snapped=true persisted=true\n"
        "interactive-arrange-cleanup=passed callbacks-removed=true\n",
        encoding="utf-8",
    )
    print(
        "arrangement-anchor=passed target-linked=true persisted=true placement-follow=true skeleton-follow=true stale-detection=true",
        flush=True,
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
