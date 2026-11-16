# Copyright (C) 2026 FreeCAD Cloth contributors
"""FreeCAD/Xvfb acceptance for a multi-piece, two-layer garment ensemble.

The fixture constructs two independent four-panel garments around the production
mannequin: a shirt and a skirt. A four-panel waistband is sewn into the skirt.
Native Sketcher profiles, semantic seam IDs, persistent garment groups and
solver particle contacts are checked in the same saved FreeCAD document.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from support.freecad_bootstrap import prepare_repository_root

ROOT = prepare_repository_root(__file__)

import FreeCAD as App
import FreeCADGui as Gui
import Part
import Sketcher


OUTPUT = Path(os.environ.get("CLOTH_LAYERED_OUTFIT_DIR", "artifacts/layered-outfit"))
LOG = OUTPUT / "layered-outfit-progress.log"
IMAGE_WIDTH = 960
IMAGE_HEIGHT = 720
CHECKPOINTS = (0, 1, 5, 15)
SEAM_EDGE_A = 1
SEAM_EDGE_B = 3
SEAM_BOTTOM_EDGE = 0
SEAM_TOP_EDGE = 2
MINIMUM_PIECES = 12
MINIMUM_SEAMS = 16
MINIMUM_CONTACTS = 1
MAXIMUM_RESIDUAL_PENETRATION_MM = 0.5
MINIMUM_BODY_CLEARANCE_MM = 5.0


def _log(message: str) -> None:
    """Write one flushed acceptance milestone to the artifact directory."""
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as stream:
        stream.write(str(message) + "\n")
        stream.flush()
    print(str(message), flush=True)


def _events() -> None:
    """Refresh FreeCAD's viewport and process queued Qt events."""
    Gui.updateGui()
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets

    application = QtWidgets.QApplication.instance()
    if application is not None:
        application.processEvents()


def _landmark_world(avatar, name: str):
    """Resolve one named arrangement landmark into the shared world frame."""
    raw = next(
        (
            str(value)
            for value in getattr(avatar, "ArrangementPoints", ())
            if str(value).split("|", 1)[0] == name
        ),
        None,
    )
    if raw is None:
        raise RuntimeError("production mannequin is missing arrangement landmark " + name)
    values = tuple(float(value) for value in raw.split("|", 1)[1].split(","))
    if len(values) != 3 or not all(math.isfinite(value) for value in values):
        raise RuntimeError("invalid mannequin landmark coordinates for " + name)
    return avatar.Placement.multVec(App.Vector(*values))


def _make_piece(
    doc,
    name: str,
    width_mm: float,
    height_mm: float,
    placement,
    grainline_angle: float,
):
    """Create one native Sketcher rectangle and adopt it as the pattern authority."""
    sketch = doc.addObject("Sketcher::SketchObject", name + "Source")
    points = (
        (0.0, 0.0),
        (float(width_mm), 0.0),
        (float(width_mm), float(height_mm)),
        (0.0, float(height_mm)),
    )
    segments = [
        Part.LineSegment(
            App.Vector(points[index][0], points[index][1], 0.0),
            App.Vector(points[(index + 1) % 4][0], points[(index + 1) % 4][1], 0.0),
        )
        for index in range(4)
    ]
    sketch.addGeometry(segments, False)
    sketch.addConstraint([Sketcher.Constraint("Block", index) for index in range(4)])
    doc.recompute()

    from freecad_cloth.pattern.PatternCommands import create_pattern_piece_from_selected_sketch

    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(sketch)
    piece = create_pattern_piece_from_selected_sketch(
        name=name,
        allowance=10.0,
        grainline=grainline_angle,
    )
    if piece.Sketch is not sketch:
        raise RuntimeError("PatternPiece lost its authoritative Sketcher source: " + name)
    if len(tuple(getattr(sketch, "SemanticEdgeIds", ()) or ())) != 4:
        raise RuntimeError("PatternPiece did not retain four semantic edge IDs: " + name)

    piece.Placement = placement
    sketch.Placement = placement
    piece.Label = name.replace("-", " ").title()
    piece.ViewObject.Visibility = False
    sketch.ViewObject.Visibility = False
    doc.recompute()
    return piece


def _make_ring(
    doc,
    garment_id: str,
    radius_x_mm: float,
    radius_y_mm: float,
    bottom_z_mm: float,
    height_mm: float,
    rotation_front,
    rotation_right,
    rotation_back,
    rotation_left,
    center_x: float,
    center_y: float,
):
    """Create four independent rectangular panels arranged as a sewn square shell."""
    specifications = (
        (
            "front",
            2.0 * radius_x_mm,
            App.Placement(
                App.Vector(center_x - radius_x_mm, center_y - radius_y_mm, bottom_z_mm),
                rotation_front,
            ),
        ),
        (
            "right",
            2.0 * radius_y_mm,
            App.Placement(
                App.Vector(center_x + radius_x_mm, center_y - radius_y_mm, bottom_z_mm),
                rotation_right,
            ),
        ),
        (
            "back",
            2.0 * radius_x_mm,
            App.Placement(
                App.Vector(center_x + radius_x_mm, center_y + radius_y_mm, bottom_z_mm),
                rotation_back,
            ),
        ),
        (
            "left",
            2.0 * radius_y_mm,
            App.Placement(
                App.Vector(center_x - radius_x_mm, center_y + radius_y_mm, bottom_z_mm),
                rotation_left,
            ),
        ),
    )
    pieces = {}
    for side, width, placement in specifications:
        name = garment_id + "-" + side
        pieces[side] = _make_piece(
            doc,
            name,
            width,
            height_mm,
            placement,
            0.0,
        )
    return pieces


def _edge_id(piece, index: int) -> str:
    """Return one persistent semantic boundary ID from its source Sketcher profile."""
    identifiers = tuple(str(value) for value in piece.Sketch.SemanticEdgeIds)
    edge_id = identifiers[index]
    if not edge_id:
        raise RuntimeError("missing semantic edge " + str(index) + " on " + piece.Name)
    return edge_id


def _add_seam(
    doc,
    piece_a,
    edge_a: int,
    piece_b,
    edge_b: int,
    seam_id: str,
    *,
    reversed_b: bool,
    stitch_group: str,
    kind: str = "plain",
):
    """Persist and validate one semantic edge-to-edge sewing relationship."""
    from freecad_cloth.pattern.PatternModel import Seam
    from freecad_cloth.pattern.PatternObjects import add_seam

    seam = Seam(
        str(piece_a.PieceId),
        _edge_id(piece_a, edge_a),
        str(piece_b.PieceId),
        _edge_id(piece_b, edge_b),
        id=seam_id,
        reversed_b=reversed_b,
        alignment="uniform",
        stitch_group=stitch_group,
        kind=kind,
    )
    obj = add_seam(doc, seam)
    if str(getattr(obj, "Status", "")) != "Valid":
        raise RuntimeError("semantic seam failed validation before simulation: " + seam_id)
    if str(getattr(obj, "EdgeAId", "")) != _edge_id(piece_a, edge_a):
        raise RuntimeError("seam A-side edge identity changed: " + seam_id)
    if str(getattr(obj, "EdgeBId", "")) != _edge_id(piece_b, edge_b):
        raise RuntimeError("seam B-side edge identity changed: " + seam_id)
    return obj


def _sew_ring(doc, garment_id: str, pieces):
    """Close one four-panel shell using four persistent side-seam relationships."""
    order = ("front", "right", "back", "left")
    seams = []
    for index, side in enumerate(order):
        next_side = order[(index + 1) % len(order)]
        seams.append(
            _add_seam(
                doc,
                pieces[side],
                SEAM_EDGE_A,
                pieces[next_side],
                SEAM_EDGE_B,
                garment_id + "-side-" + side,
                reversed_b=True,
                stitch_group=garment_id,
            )
        )
    return seams


def _save_png(view, path: Path, camera_action, label: str) -> dict[str, object]:
    """Capture a fixed orthographic view and verify its pixels independently."""
    from freecad_cloth.common.VisualCaptureValidation import validate_png_capture

    path.parent.mkdir(parents=True, exist_ok=True)
    view.setCameraType("Orthographic")
    camera_action()
    view.fitAll()
    _events()
    view.redraw()
    _events()
    view.saveImage(str(path), IMAGE_WIDTH, IMAGE_HEIGHT, "White")
    metrics = validate_png_capture(
        path,
        expected_width=IMAGE_WIDTH,
        expected_height=IMAGE_HEIGHT,
        min_nonwhite_pixels=128,
        min_distinct_rgb=2,
        min_opaque_pixels=IMAGE_WIDTH * IMAGE_HEIGHT // 2,
    )
    return {
        "file": path.name,
        "label": label,
        "width": int(metrics["width"]),
        "height": int(metrics["height"]),
        "nonwhite_pixels": int(metrics["nonwhite_pixels"]),
        "distinct_rgb": int(metrics["distinct_rgb"]),
    }


def _seam_measurements(backend, provenance):
    """Measure exact particle-pair gaps for every authored seam."""
    positions = tuple(backend.positions())
    measurements = []
    for seam_id, pairs in sorted(provenance.items()):
        gaps = []
        for left, right in pairs:
            gap = math.dist(positions[int(left)], positions[int(right)])
            gaps.append(float(gap))
        measurements.append(
            {
                "seam_id": str(seam_id),
                "stitch_pair_count": len(gaps),
                "maximum_gap_mm": max(gaps, default=0.0),
                "mean_gap_mm": sum(gaps) / len(gaps) if gaps else 0.0,
            }
        )
    return measurements


def _body_clearance(scene, backend) -> dict[str, object]:
    """Measure sampled clothing clearance to the active authoritative DrapeTarget."""
    from freecad_cloth.common.MeshValidation import nearest_surface_clearance
    from freecad_cloth.simulation.DrapeVisualSanity import points_inside_closed_mesh

    base = scene.Proxy._base_or_restore()
    surface = base.collision_surface
    positions = tuple(backend.positions())
    inside = points_inside_closed_mesh(positions, surface.vertices, surface.triangles)
    clearance = nearest_surface_clearance(positions, surface.vertices, surface.triangles)
    return {
        "inside_particle_count": int(sum(bool(value) for value in inside)),
        "minimum_unsigned_clearance_mm": float(clearance),
    }


def _capture_six_views(view, directory: Path, checkpoint: int):
    """Capture all six principal orthographic views for one solver checkpoint."""
    actions = (
        ("front", view.viewFront),
        ("rear", view.viewRear),
        ("right", view.viewRight),
        ("left", view.viewLeft),
        ("top", view.viewTop),
        ("bottom", view.viewBottom),
    )
    records = []
    for name, action in actions:
        path = directory / ("step-%03d-%s.png" % (checkpoint, name))
        records.append(_save_png(view, path, action, name))
    return records


def run_acceptance() -> None:
    """Build, sew, simulate, save/reload and capture a twelve-piece layered outfit."""
    from freecad_cloth.avatar.AvatarCommands import create_avatar
    from freecad_cloth.simulation.DrapeCommands import set_drape_target_source
    from freecad_cloth.simulation.SimulationObjects import create_simulation_scene
    from freecad_cloth.simulation.SimulationQualityRuntime import (
        QualitySimulationProxy,
        ensure_quality_properties,
    )

    OUTPUT.mkdir(parents=True, exist_ok=True)
    doc = App.newDocument("LayeredOutfitAcceptance")
    _log("document-created")
    try:
        scene = create_simulation_scene(doc, build=False)
        avatar = create_avatar(attach_collision=False, doc=doc)
        avatar.Label = "Layered Outfit Mannequin"
        avatar.ViewObject.Visibility = True
        set_drape_target_source(scene, avatar, thickness=5.0, deflection=1.0)
        target = doc.getObject("DrapeTarget")
        if target is None or scene.DrapeTarget is not target:
            raise RuntimeError("the production DrapeTarget was not attached to the simulation")
        ensure_quality_properties(scene)
        scene.Proxy = QualitySimulationProxy()

        shoulder_left = _landmark_world(avatar, "shoulder_left")
        shoulder_right = _landmark_world(avatar, "shoulder_right")
        hip = _landmark_world(avatar, "hip")
        center_x = 0.5 * (float(shoulder_left.x) + float(shoulder_right.x))
        shoulder_width = abs(float(shoulder_right.x) - float(shoulder_left.x))
        if shoulder_width <= 100.0:
            raise RuntimeError("mannequin shoulder landmarks do not define a usable torso width")

        from freecad_cloth.simulation.DrapeTarget import collision_surface

        body_surface = collision_surface(
            avatar,
            float(target.CollisionDeflection),
            float(target.CollisionThickness),
        )
        hip_z = float(hip.z)
        shoulder_z = 0.5 * (float(shoulder_left.z) + float(shoulder_right.z))
        torso_vertices = [
            vertex
            for vertex in body_surface.vertices
            if hip_z - 50.0 <= float(vertex[2]) <= shoulder_z + 30.0
            and abs(float(vertex[0]) - center_x) <= 0.65 * shoulder_width
        ]
        if len(torso_vertices) < 50:
            raise RuntimeError("authoritative mannequin surface has too few torso-region samples")
        center_y = 0.5 * (
            min(float(vertex[1]) for vertex in torso_vertices)
            + max(float(vertex[1]) for vertex in torso_vertices)
        )
        radius_x = 0.5 * shoulder_width + 28.0
        radius_y = 0.5 * (
            max(float(vertex[1]) for vertex in torso_vertices)
            - min(float(vertex[1]) for vertex in torso_vertices)
        ) + 28.0
        radius_x = max(150.0, radius_x)
        radius_y = max(100.0, radius_y)

        rotation_front = App.Rotation(App.Vector(1.0, 0.0, 0.0), 90.0)
        rotation_right = App.Rotation(App.Vector(0.0, 0.0, 1.0), 90.0).multiply(
            rotation_front
        )
        rotation_back = App.Rotation(App.Vector(0.0, 0.0, 1.0), 180.0).multiply(
            rotation_front
        )
        rotation_left = App.Rotation(App.Vector(0.0, 0.0, 1.0), 270.0).multiply(
            rotation_front
        )
        rotations = (
            rotation_front,
            rotation_right,
            rotation_back,
            rotation_left,
        )

        skirt_bottom_z = hip_z - 520.0
        skirt_top_z = hip_z - 40.0
        skirt_height = skirt_top_z - skirt_bottom_z
        skirt = _make_ring(
            doc,
            "Skirt",
            radius_x,
            radius_y,
            skirt_bottom_z,
            skirt_height,
            *rotations,
            center_x,
            center_y,
        )
        skirt_seams = _sew_ring(doc, "Skirt", skirt)

        waistband_bottom_z = skirt_top_z
        waistband_height = 100.0
        waistband = _make_ring(
            doc,
            "Waistband",
            radius_x,
            radius_y,
            waistband_bottom_z,
            waistband_height,
            *rotations,
            center_x,
            center_y,
        )
        waistband_seams = _sew_ring(doc, "Waistband", waistband)
        waistband_join_seams = []
        for side in ("front", "right", "back", "left"):
            waistband_join_seams.append(
                _add_seam(
                    doc,
                    skirt[side],
                    SEAM_TOP_EDGE,
                    waistband[side],
                    SEAM_BOTTOM_EDGE,
                    "Skirt-Waistband-" + side,
                    reversed_b=True,
                    stitch_group="SkirtAssembly",
                    kind="plain",
                )
            )

        shirt_bottom_z = hip_z - 10.0
        shirt_top_z = shoulder_z + 35.0
        shirt = _make_ring(
            doc,
            "Shirt",
            radius_x + 7.0,
            radius_y + 7.0,
            shirt_bottom_z,
            shirt_top_z - shirt_bottom_z,
            *rotations,
            center_x,
            center_y,
        )
        shirt_seams = _sew_ring(doc, "Shirt", shirt)
        doc.recompute()

        pieces = (
            [shirt[side] for side in ("front", "right", "back", "left")]
            + [skirt[side] for side in ("front", "right", "back", "left")]
            + [waistband[side] for side in ("front", "right", "back", "left")]
        )
        expected_ids = {str(piece.PieceId) for piece in pieces}
        if len(pieces) != MINIMUM_PIECES or len(expected_ids) != MINIMUM_PIECES:
            raise RuntimeError("outfit fixture must contain twelve distinct native PatternPieces")
        scene.ClothPieces = pieces
        scene.GarmentGroups = (
            ["shirt|" + str(shirt[side].PieceId) for side in ("front", "right", "back", "left")]
            + ["skirt|" + str(skirt[side].PieceId) for side in ("front", "right", "back", "left")]
            + [
                "skirt|" + str(waistband[side].PieceId)
                for side in ("front", "right", "back", "left")
            ]
        )
        scene.InterClothClearance = 8.0
        scene.QualityPreset = "Fast"
        scene.ParticleDistance = 24.0
        scene.SolverIterations = 6
        scene.SolverSubsteps = 1
        scene.TimeStep = 1.0 / 120.0
        scene.StartHeight = 0.0
        scene.PinMode = "None"
        scene.PinSelection = []
        scene.GravityX = 0.0
        scene.GravityY = 0.0
        scene.GravityZ = -9810.0
        scene.FabricFriction = 0.55
        scene.FabricTransparency = 0

        for obj in doc.Objects:
            if getattr(obj, "PatternType", "") == "PatternPiece":
                obj.ViewObject.Visibility = False
                obj.Sketch.ViewObject.Visibility = False
        doc.recompute()
        _events()
        _log("pattern-pieces=%d seams=%d" % (len(pieces), len(shirt_seams + skirt_seams + waistband_seams + waistband_join_seams)))
        if not bool(scene.FiniteState) or int(scene.ParticleCount) <= 0:
            raise RuntimeError("initial twelve-panel solver build did not produce finite particles")

        base = scene.Proxy._base_or_restore()
        backend = base.backend
        if set(getattr(base, "panel_piece_names", {}).values()) != {
            str(piece.Name) for piece in pieces
        }:
            raise RuntimeError("the solver output lost one or more persistent PatternPiece identities")
        if len(base.seam_stitch_pairs) != MINIMUM_SEAMS:
            raise RuntimeError(
                "expected sixteen exact solver seam groups, got %d" % len(base.seam_stitch_pairs)
            )
        if set(base.seam_stitch_pairs) != {
            str(seam.SeamId)
            for seam in (shirt_seams + skirt_seams + waistband_seams + waistband_join_seams)
        }:
            raise RuntimeError("solver stitch provenance does not match the authored sixteen seams")

        scene.Steps = 0
        doc.recompute()
        view = Gui.activeDocument().activeView()
        images = []
        motion = _save_png(
            view,
            OUTPUT / "step-000-axonometric.png",
            view.viewAxonometric,
            "initial arranged layered outfit",
        )
        images.append(motion)
        checkpoints = []
        for step in CHECKPOINTS[1:]:
            scene.Steps = int(step)
            started = time.perf_counter()
            doc.recompute()
            elapsed_ms = 1000.0 * (time.perf_counter() - started)
            _events()
            base = scene.Proxy._base_or_restore()
            backend = base.backend
            if not bool(scene.FiniteState):
                raise RuntimeError("solver state became non-finite at step %d" % step)
            if int(scene.InterClothContactCount) < MINIMUM_CONTACTS:
                raise RuntimeError(
                    "independent shirt/skirt contact was not observed at step %d" % step
                )
            if float(scene.InterClothResidualPenetration) > MAXIMUM_RESIDUAL_PENETRATION_MM:
                raise RuntimeError(
                    "inter-cloth residual penetration %.3f mm exceeds %.3f mm at step %d"
                    % (
                        float(scene.InterClothResidualPenetration),
                        MAXIMUM_RESIDUAL_PENETRATION_MM,
                        step,
                    )
                )
            seam_metrics = _seam_measurements(backend, base.seam_stitch_pairs)
            max_seam_gap = max(
                (float(item["maximum_gap_mm"]) for item in seam_metrics),
                default=0.0,
            )
            if max_seam_gap > 12.0:
                raise RuntimeError(
                    "authored multi-panel seams diverged to %.3f mm at step %d"
                    % (max_seam_gap, step)
                )
            body_metrics = _body_clearance(scene, backend)
            if int(body_metrics["inside_particle_count"]) > 0:
                raise RuntimeError(
                    "draped garment penetrated the mannequin at step %d" % step
                )
            if float(body_metrics["minimum_unsigned_clearance_mm"]) < MINIMUM_BODY_CLEARANCE_MM:
                raise RuntimeError(
                    "mannequin clearance %.3f mm is below %.3f mm at step %d"
                    % (
                        float(body_metrics["minimum_unsigned_clearance_mm"]),
                        MINIMUM_BODY_CLEARANCE_MM,
                        step,
                    )
                )
            checkpoint_images = []
            if step == CHECKPOINTS[-1]:
                checkpoint_images = _capture_six_views(
                    view,
                    OUTPUT / "final-six-view",
                    int(step),
                )
                images.extend(checkpoint_images)
            else:
                checkpoint_images = [
                    _save_png(
                        view,
                        OUTPUT / ("step-%03d-axonometric.png" % step),
                        view.viewAxonometric,
                        "layered outfit motion at step %d" % step,
                    )
                ]
                images.extend(checkpoint_images)
            checkpoint = {
                "step": int(step),
                "elapsed_ms": round(elapsed_ms, 3),
                "finite": bool(scene.FiniteState),
                "contact_count": int(scene.InterClothContactCount),
                "corrected_particle_count": int(scene.InterClothCorrectedParticleCount),
                "max_penetration_before_mm": float(scene.InterClothMaxPenetration),
                "residual_penetration_mm": float(scene.InterClothResidualPenetration),
                "max_seam_gap_mm": max_seam_gap,
                "body": body_metrics,
                "seams": seam_metrics,
                "images": checkpoint_images,
            }
            checkpoints.append(checkpoint)
            _log(
                "checkpoint=%d particles=%d contacts=%d corrected=%d residual_mm=%.4f "
                "seam_gap_mm=%.4f body_clearance_mm=%.4f elapsed_ms=%.1f"
                % (
                    step,
                    int(scene.ParticleCount),
                    int(scene.InterClothContactCount),
                    int(scene.InterClothCorrectedParticleCount),
                    float(scene.InterClothResidualPenetration),
                    max_seam_gap,
                    float(body_metrics["minimum_unsigned_clearance_mm"]),
                    elapsed_ms,
                )
            )

        expected_groups = tuple(str(value) for value in scene.GarmentGroups)
        if len(set(expected_groups)) != MINIMUM_PIECES:
            raise RuntimeError("garment group assignment inventory is incomplete or ambiguous")
        garment_group_ids = {entry.split("|", 1)[0] for entry in expected_groups}
        if garment_group_ids != {"shirt", "skirt"}:
            raise RuntimeError("outfit must retain exactly two independently simulated garments")
        save_path = OUTPUT / "layered-outfit.FCStd"
        doc.recompute()
        doc.saveAs(str(save_path))
        _log("saved-document=" + str(save_path))

        saved_piece_ids = tuple(str(piece.PieceId) for piece in scene.ClothPieces)
        saved_groups = tuple(str(value) for value in scene.GarmentGroups)
        App.closeDocument(doc.Name)
        doc = None
        reloaded = App.openDocument(str(save_path))
        _events()
        scene = reloaded.getObject("ClothSimulation")
        if scene is None:
            raise RuntimeError("ClothSimulation was not restored from the saved FCStd")
        if tuple(str(piece.PieceId) for piece in scene.ClothPieces) != saved_piece_ids:
            raise RuntimeError("PatternPiece links or identities changed after save/reload")
        if tuple(str(value) for value in scene.GarmentGroups) != saved_groups:
            raise RuntimeError("independent garment-group assignments did not survive save/reload")
        if abs(float(scene.InterClothClearance) - 8.0) > 1e-9:
            raise RuntimeError("inter-cloth clearance did not survive save/reload")
        reloaded.recompute()
        scene.Steps = int(scene.Steps) + 1
        reloaded.recompute()
        if not bool(scene.FiniteState):
            raise RuntimeError("reloaded multi-piece simulation rebuilt a non-finite solver")
        if int(scene.InterClothContactCount) < MINIMUM_CONTACTS:
            raise RuntimeError("reloaded solver did not retain inter-garment contact activation")
        reloaded_base = scene.Proxy._base_or_restore()
        reloaded_backend = reloaded_base.backend
        _log(
            "save-reload=passed pieces=%d groups=%d contacts=%d"
            % (
                len(scene.ClothPieces),
                len({entry.split("|", 1)[0] for entry in saved_groups}),
                int(scene.InterClothContactCount),
            )
        )

        manifest = {
            "schema": "freecad-cloth.layered-outfit",
            "schema_version": 1,
            "provenance": {
                "commit_sha": os.environ.get("CLOTH_HEAD_SHA", ""),
                "document": save_path.name,
                "backend": str(getattr(reloaded_backend, "name", "")),
                "units": "mm",
                "world_frame": {
                    "origin": "FreeCAD document world origin",
                    "axes": {"x": "mannequin left-right", "y": "front-back", "z": "world up"},
                    "camera_front": "negative Y",
                },
            },
            "outfit": {
                "description": "Twelve-panel shirt, skirt and waistband with two independent garment groups",
                "piece_count": len(scene.ClothPieces),
                "seam_count": len(reloaded_base.seam_stitch_pairs),
                "garment_group_count": len({entry.split("|", 1)[0] for entry in saved_groups}),
                "piece_ids": list(saved_piece_ids),
                "garment_groups": list(saved_groups),
                "inter_cloth_clearance_mm": float(scene.InterClothClearance),
                "particle_distance_mm": float(scene.ParticleDistance),
            },
            "checkpoints": checkpoints,
            "images": images,
            "persistence": {
                "fcstd": save_path.name,
                "piece_links_preserved": True,
                "garment_groups_preserved": True,
                "contact_rebuilt_after_reload": True,
            },
        }
        manifest_path = OUTPUT / "layered-outfit-manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        _log("manifest=" + str(manifest_path))
        _log("layered-outfit-acceptance=passed")
        App.closeDocument(reloaded.Name)
        doc = None
    finally:
        if doc is not None:
            try:
                App.closeDocument(doc.Name)
            except Exception:
                pass


OUTPUT.mkdir(parents=True, exist_ok=True)
try:
    run_acceptance()
except BaseException as error:
    _log("layered-outfit-acceptance=failed error=%r" % (error,))
    App.Console.PrintError("Layered outfit acceptance failed: %s\n" % error)
    os._exit(1)
os._exit(0)
