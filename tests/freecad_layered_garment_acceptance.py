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
import traceback
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from freecad_cloth.common.JsonTypes import JsonObject

if TYPE_CHECKING:
    from freecad_cloth.simulation.PositionBasedDynamicsBackend import PositionBasedDynamicsBackend
    from freecad_cloth.simulation.SimulationObjects import SimulationProxy

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from support.freecad_bootstrap import prepare_repository_root
from support.layered_outfit_support import select_top_boundary_supports

ROOT = prepare_repository_root(__file__)

# FreeCAD must be initialized by the bootstrap before these runtime imports.
import FreeCAD as App  # noqa: I001
import FreeCADGui as Gui
import Part
import Sketcher


OUTPUT = Path(os.environ.get("CLOTH_LAYERED_OUTFIT_DIR", "artifacts/layered-outfit"))
os.environ["CLOTH_INTER_CLOTH_DIAGNOSTICS"] = "1"
LOG = OUTPUT / "layered-outfit-progress.log"
IMAGE_WIDTH = 960
IMAGE_HEIGHT = 720
CHECKPOINTS = (0, 1, 15, 60)
SEAM_EDGE_A = 1
SEAM_EDGE_B = 3
SEAM_BOTTOM_EDGE = 0
SEAM_TOP_EDGE = 2
MINIMUM_PIECES = 12
MINIMUM_SEAMS = 16
MINIMUM_CONTACTS = 1
MAXIMUM_RESIDUAL_PENETRATION_MM = 0.5
MINIMUM_BODY_CLEARANCE_MM = 5.0
SKIRT_HEM_FLARE_MM = 65.0
SHIRT_SKIRT_INITIAL_CONTACT_GAP_MM = 6.0


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


def _landmark_world(avatar: App.DocumentObject, name: str) -> App.Vector:
    """Resolve one named arrangement landmark into the shared world frame."""
    from freecad_cloth.avatar.avatar_arrangement import arrangement_point_map

    coordinates = arrangement_point_map(getattr(avatar, "ArrangementPoints", ())).get(name)
    if coordinates is None:
        raise RuntimeError("production mannequin is missing arrangement landmark " + name)
    values = tuple(float(value) for value in coordinates.split(","))
    if len(values) != 3 or not all(math.isfinite(value) for value in values):
        raise RuntimeError("invalid mannequin landmark coordinates for " + name)
    return avatar.Placement.multVec(App.Vector(*values))


def _make_piece(
    doc: App.Document,
    name: str,
    width_mm: float,
    height_mm: float,
    placement: App.Placement,
    grainline_angle: float,
    outline_points: tuple[tuple[float, float], ...] | None = None,
) -> App.DocumentObject:
    """Create one native Sketcher pattern profile and adopt it as the pattern authority."""
    sketch = doc.addObject("Sketcher::SketchObject", name + "Source")
    points = outline_points or (
        (0.0, 0.0),
        (float(width_mm), 0.0),
        (float(width_mm), float(height_mm)),
        (0.0, float(height_mm)),
    )
    if len(points) != 4:
        raise ValueError("layered outfit profile must contain four connected boundary edges")
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
    doc: App.Document,
    garment_id: str,
    radius_x_mm: float,
    radius_y_mm: float,
    bottom_z_mm: float,
    height_mm: float,
    rotation_front: App.Rotation,
    rotation_right: App.Rotation,
    rotation_back: App.Rotation,
    rotation_left: App.Rotation,
    center_x: float,
    center_y: float,
    *,
    hem_flare_mm: float = 0.0,
    top_radius_x_mm: float | None = None,
    top_radius_y_mm: float | None = None,
) -> dict[str, App.DocumentObject]:
    """Create four sewn panels between measured bottom and top radii.

    A positive hem flare widens the lower edge. Optional top radii allow a
    torso-shaped shirt shell to taper independently in X and Y while retaining
    coincident 3D corner seams. Each panel remains a planar Sketcher trapezoid.
    """
    flare = float(hem_flare_mm)
    height = float(height_mm)
    bottom_radius_x = float(radius_x_mm) + flare
    bottom_radius_y = float(radius_y_mm) + flare
    top_radius_x = float(radius_x_mm) if top_radius_x_mm is None else float(top_radius_x_mm)
    top_radius_y = float(radius_y_mm) if top_radius_y_mm is None else float(top_radius_y_mm)
    if not math.isfinite(flare) or flare < 0.0:
        raise ValueError("hem flare must be finite and non-negative")
    if not math.isfinite(height) or height <= 0.0:
        raise ValueError("panel height must be positive and finite")
    radii = (bottom_radius_x, bottom_radius_y, top_radius_x, top_radius_y)
    if not all(math.isfinite(value) and value > 0.0 for value in radii):
        raise ValueError("ring radii must be positive and finite")

    offset_x = bottom_radius_x - top_radius_x
    offset_y = bottom_radius_y - top_radius_y
    front_angle = math.atan2(offset_y, height)
    side_angle = math.atan2(offset_x, height)
    front_local_height = math.hypot(height, offset_y)
    side_local_height = math.hypot(height, offset_x)
    front_tilt = App.Rotation(App.Vector(1.0, 0.0, 0.0), -math.degrees(front_angle))
    side_tilt = App.Rotation(App.Vector(1.0, 0.0, 0.0), -math.degrees(side_angle))

    specifications = (
        (
            "front",
            2.0 * bottom_radius_x,
            offset_x,
            front_local_height,
            App.Placement(
                App.Vector(
                    center_x - bottom_radius_x,
                    center_y - bottom_radius_y,
                    bottom_z_mm,
                ),
                rotation_front.multiply(front_tilt),
            ),
        ),
        (
            "right",
            2.0 * bottom_radius_y,
            offset_y,
            side_local_height,
            App.Placement(
                App.Vector(
                    center_x + bottom_radius_x,
                    center_y - bottom_radius_y,
                    bottom_z_mm,
                ),
                rotation_right.multiply(side_tilt),
            ),
        ),
        (
            "back",
            2.0 * bottom_radius_x,
            offset_x,
            front_local_height,
            App.Placement(
                App.Vector(
                    center_x + bottom_radius_x,
                    center_y + bottom_radius_y,
                    bottom_z_mm,
                ),
                rotation_back.multiply(front_tilt),
            ),
        ),
        (
            "left",
            2.0 * bottom_radius_y,
            offset_y,
            side_local_height,
            App.Placement(
                App.Vector(
                    center_x - bottom_radius_x,
                    center_y + bottom_radius_y,
                    bottom_z_mm,
                ),
                rotation_left.multiply(side_tilt),
            ),
        ),
    )
    pieces = {}
    for side, bottom_width, top_offset, local_height, placement in specifications:
        name = garment_id + "-" + side
        profile = (
            (0.0, 0.0),
            (bottom_width, 0.0),
            (bottom_width - top_offset, local_height),
            (top_offset, local_height),
        )
        pieces[side] = _make_piece(
            doc,
            name,
            bottom_width,
            local_height,
            placement,
            0.0,
            outline_points=profile,
        )
    return pieces


def _edge_id(piece: App.DocumentObject, index: int) -> str:
    """Return one persistent semantic boundary ID from its source Sketcher profile."""
    identifiers = tuple(str(value) for value in piece.Sketch.SemanticEdgeIds)
    edge_id = identifiers[index]
    if not edge_id:
        raise RuntimeError("missing semantic edge " + str(index) + " on " + piece.Name)
    return edge_id


def _add_seam(
    doc: App.Document,
    piece_a: App.DocumentObject,
    edge_a: int,
    piece_b: App.DocumentObject,
    edge_b: int,
    seam_id: str,
    *,
    reversed_b: bool,
    stitch_group: str,
    kind: str = "plain",
) -> App.DocumentObject:
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


def _sew_ring(
    doc: App.Document,
    garment_id: str,
    pieces: Mapping[str, App.DocumentObject],
) -> list[App.DocumentObject]:
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


def _save_png(
    view: Gui.View3DInventorViewer,
    path: Path,
    camera_action: Callable[[], None],
    label: str,
) -> JsonObject:
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
        "file": str(path.relative_to(OUTPUT)),
        "label": label,
        "width": int(metrics["width"]),
        "height": int(metrics["height"]),
        "nonwhite_pixels": int(metrics["nonwhite_pixels"]),
        "distinct_rgb": int(metrics["distinct_rgb"]),
    }


def _seam_measurements(
    backend: PositionBasedDynamicsBackend,
    provenance: Mapping[str, Sequence[tuple[int, int]]],
    seam_objects: Mapping[str, App.DocumentObject],
) -> list[JsonObject]:
    """Measure stitch-pair gaps and join each measurement to its semantic seam record."""
    positions = tuple(backend.positions())
    measurements = []
    for seam_id, pairs in sorted(provenance.items()):
        gaps = [
            float(math.dist(positions[int(left)], positions[int(right)])) for left, right in pairs
        ]
        seam = seam_objects.get(str(seam_id))
        if seam is None:
            raise RuntimeError(
                "solver seam provenance has no matching document seam: " + str(seam_id)
            )
        measurements.append(
            {
                "seam_id": str(seam_id),
                "piece_a_id": str(getattr(seam, "PieceA", "")),
                "piece_b_id": str(getattr(seam, "PieceB", "")),
                "edge_a_id": str(getattr(seam, "EdgeAId", "")),
                "edge_b_id": str(getattr(seam, "EdgeBId", "")),
                "start_a": float(getattr(seam, "StartA", 0.0)),
                "end_a": float(getattr(seam, "EndA", 1.0)),
                "start_b": float(getattr(seam, "StartB", 0.0)),
                "end_b": float(getattr(seam, "EndB", 1.0)),
                "reversed_b": bool(getattr(seam, "ReversedB", False)),
                "alignment": str(getattr(seam, "Alignment", "uniform")),
                "stitch_group": str(getattr(seam, "StitchGroup", "")),
                "kind": str(getattr(seam, "Kind", "plain")),
                "status": str(getattr(seam, "Status", "")),
                "stitch_pair_count": len(gaps),
                "maximum_gap_mm": max(gaps, default=0.0),
                "mean_gap_mm": sum(gaps) / len(gaps) if gaps else 0.0,
            }
        )
    return measurements


def _world_landmarks(avatar: App.DocumentObject) -> list[JsonObject]:
    """Export every persisted mannequin arrangement landmark in document world millimetres."""
    from freecad_cloth.avatar.avatar_arrangement import arrangement_point_map

    coordinates_by_name = arrangement_point_map(getattr(avatar, "ArrangementPoints", ()) or ())
    records = []
    for name, coordinate_text in coordinates_by_name.items():
        local = tuple(float(value) for value in coordinate_text.split(","))
        if len(local) != 3 or not all(math.isfinite(value) for value in local):
            raise RuntimeError("invalid persisted mannequin landmark: " + str(name))
        world = avatar.Placement.multVec(App.Vector(*local))
        records.append(
            {
                "id": name,
                "local_mm": [float(value) for value in local],
                "world_mm": [float(world.x), float(world.y), float(world.z)],
            }
        )
    if not records:
        raise RuntimeError("mannequin did not expose persisted arrangement landmarks")
    return records


def _piece_scene_map(
    pieces: Sequence[App.DocumentObject],
    base: SimulationProxy,
    garment_group_by_piece: Mapping[str, str],
) -> list[JsonObject]:
    """Export exact source boundary, placement and derived solver identities for every piece."""
    from freecad_cloth.simulation.PatternSimulationAdapter import resolve_piece_ir

    panel_for_piece = {
        str(piece_name): str(panel_name)
        for panel_name, piece_name in getattr(base, "panel_piece_names", {}).items()
    }
    result = []
    for piece in pieces:
        piece_id = str(piece.PieceId)
        placement = piece.Placement
        boundaries = resolve_piece_ir(piece).boundaries
        local_points = []
        boundary_records = []
        for boundary in boundaries:
            samples = [
                (float(sample[0]), float(sample[1]), float(sample[2]))
                for sample in boundary.samples
            ]
            local_points.extend(samples)
            boundary_records.append(
                {
                    "id": str(boundary.id),
                    "kind": str(boundary.kind),
                    "length_mm": float(boundary.length),
                    "samples_local_mm": [list(point) for point in samples],
                }
            )
        if not local_points:
            raise RuntimeError("PatternIR source boundary has no samples: " + piece_id)
        world_points = []
        for x, y, z in local_points:
            point = placement.multVec(App.Vector(x, y, z))
            world_points.append((float(point.x), float(point.y), float(point.z)))
        panel_name = panel_for_piece.get(str(piece.Name))
        if panel_name is None:
            raise RuntimeError("solver does not retain a rendered panel for piece " + piece_id)
        panel_indices = tuple(int(value) for value in base.panel_indices.get(panel_name, ()))
        panel_triangles = tuple(base.panel_triangles.get(panel_name, ()))
        if not panel_indices or not panel_triangles:
            raise RuntimeError(
                "solver panel identity has no particle/triangle mapping: " + piece_id
            )
        rotation = placement.Rotation
        quaternion = tuple(float(value) for value in rotation.Q)
        result.append(
            {
                "piece_id": piece_id,
                "name": str(piece.Label),
                "garment_group": str(garment_group_by_piece[piece_id]),
                "solver_panel_id": panel_name,
                "local_to_world": {
                    "translation_mm": [
                        float(placement.Base.x),
                        float(placement.Base.y),
                        float(placement.Base.z),
                    ],
                    "rotation_quaternion_xyzw": list(quaternion),
                },
                "grainline_angle_deg": float(getattr(piece, "GrainlineAngle", 0.0)),
                "seam_allowance_mm": float(getattr(piece, "SeamAllowance", 0.0)),
                "semantic_edge_ids": [
                    str(value) for value in (getattr(piece.Sketch, "SemanticEdgeIds", ()) or ())
                ],
                "boundaries": boundary_records,
                "local_bounds_mm": {
                    "min": [min(point[axis] for point in local_points) for axis in range(3)],
                    "max": [max(point[axis] for point in local_points) for axis in range(3)],
                },
                "world_bounds_mm": {
                    "min": [min(point[axis] for point in world_points) for axis in range(3)],
                    "max": [max(point[axis] for point in world_points) for axis in range(3)],
                },
                "solver_mesh": {
                    "particle_count": len(panel_indices),
                    "triangle_count": len(panel_triangles),
                },
            }
        )
    return result


def _body_clearance(
    scene: App.DocumentObject,
    backend: PositionBasedDynamicsBackend,
) -> dict[str, int | float]:
    """Measure authoritative mannequin clearance and a read-only foot-exit trial."""
    import numpy as np

    from freecad_cloth.simulation.DrapeVisualSanity import points_inside_closed_mesh

    base = scene.Proxy._base_or_restore()
    surface = base.collision_surface
    positions = np.asarray(backend.positions(), dtype=np.float64)
    projector = getattr(backend, "_collision_projector", None)

    containment_started = time.perf_counter()
    _log(
        "body-clearance-containment-start particles=%d target_triangles=%d method=numpy-ray-parity"
        % (len(positions), len(surface.triangles))
    )
    inside = points_inside_closed_mesh(
        tuple(tuple(float(value) for value in point) for point in positions),
        surface.vertices,
        surface.triangles,
        prefer_trimesh=False,
    )
    inside_indices = tuple(index for index, value in enumerate(inside) if value)
    _log(
        "body-clearance-containment-finish inside=%d elapsed_ms=%.1f"
        % (len(inside_indices), 1000.0 * (time.perf_counter() - containment_started))
    )

    panel_for_particle = {
        int(particle_index): str(base.panel_piece_names.get(panel_name, panel_name))
        for panel_name, particle_indices in base.panel_indices.items()
        for particle_index in particle_indices
    }
    sample_records = [
        {
            "particle": int(index),
            "piece": panel_for_particle.get(index, "unknown"),
            "position_mm": [float(value) for value in positions[index]],
        }
        for index in inside_indices
    ]
    if inside_indices:
        _log(
            "body-penetration-diagnostic count=%d particles=%s"
            % (len(inside_indices), json.dumps(sample_records, sort_keys=True))
        )

    if projector is None:
        from freecad_cloth.common.MeshValidation import nearest_surface_clearance

        clearance = nearest_surface_clearance(
            tuple(tuple(float(value) for value in point) for point in positions),
            surface.vertices,
            surface.triangles,
        )
    else:
        # Reuse the projector's exact centroid-tree nearest-face search. This avoids
        # rebuilding a second Trimesh/Rtree for the same immutable mannequin mesh.
        nearest_distances = np.empty(len(positions), dtype=np.float64)
        nearest_started = time.perf_counter()
        for index, point in enumerate(positions):
            nearest_point, _normal = projector._nearest_surface_point(point)
            nearest_distances[index] = float(np.linalg.norm(point - nearest_point))
        clearance = float(nearest_distances.min(initial=float("inf")))
        _log(
            "body-clearance-nearest-surface-finish method=cached-exact-kdtree "
            "minimum_mm=%.4f elapsed_ms=%.1f"
            % (clearance, 1000.0 * (time.perf_counter() - nearest_started))
        )

    if inside_indices and projector is not None:
        inside_points = positions[np.asarray(inside_indices, dtype=np.int64)]
        search_center = projector._vertices.mean(axis=0)
        axis_directions = (
            np.asarray((1.0, 0.0, 0.0), dtype=np.float64),
            np.asarray((-1.0, 0.0, 0.0), dtype=np.float64),
            np.asarray((0.0, 1.0, 0.0), dtype=np.float64),
            np.asarray((0.0, -1.0, 0.0), dtype=np.float64),
            np.asarray((0.0, 0.0, 1.0), dtype=np.float64),
            np.asarray((0.0, 0.0, -1.0), dtype=np.float64),
        )
        distance_samples = np.arange(1.0, 31.0, 1.0, dtype=np.float64)
        exit_records = []

        # The previous exact-head ray search established that these foot particles
        # have valid 6 mm-clearance exits within 17-19 mm. Repeat only a bounded
        # 30 mm search for the particles present in this frame; do not rebuild shell
        # components or run several redundant projector variants.
        for particle_index in inside_indices:
            origin = positions[int(particle_index)]
            nearest_point, face_normal = projector._nearest_surface_point(origin)
            raw_directions = (
                nearest_point - origin,
                face_normal,
                -face_normal,
                origin - search_center,
                *axis_directions,
            )
            directions = []
            for raw_direction in raw_directions:
                length = float(np.linalg.norm(raw_direction))
                if length <= 1e-10:
                    continue
                direction = raw_direction / length
                if any(
                    float(np.dot(direction, existing)) > 1.0 - 1e-9
                    for existing in directions
                ):
                    continue
                directions.append(direction)

            candidates = np.asarray(
                [
                    origin + distance * direction
                    for direction in directions
                    for distance in distance_samples
                ],
                dtype=np.float64,
            )
            candidate_inside = projector._inside_mask(candidates)
            best = None
            for direction_index, direction in enumerate(directions):
                start_offset = direction_index * len(distance_samples)
                stop_offset = start_offset + len(distance_samples)
                outside_offsets = np.flatnonzero(~candidate_inside[start_offset:stop_offset])
                for offset in outside_offsets:
                    candidate = candidates[start_offset + int(offset)]
                    exact_nearest, _normal = projector._nearest_surface_point(candidate)
                    candidate_clearance = float(np.linalg.norm(candidate - exact_nearest))
                    if candidate_clearance < projector.clearance_mm - 0.05:
                        continue
                    record = {
                        "direction": [float(value) for value in direction],
                        "distance_mm": float(distance_samples[int(offset)]),
                        "clearance_mm": candidate_clearance,
                        "position_mm": [float(value) for value in candidate],
                    }
                    if best is None or record["distance_mm"] < best["distance_mm"]:
                        best = record
                    break
            exit_records.append(
                {
                    "particle": int(particle_index),
                    "piece": panel_for_particle.get(int(particle_index), "unknown"),
                    "origin_mm": [float(value) for value in origin],
                    "best_exit": best,
                }
            )

        trial_positions = positions.copy()
        trial_clearances = nearest_distances.copy()
        selected_exit_count = 0
        for record in exit_records:
            best_exit = record["best_exit"]
            if best_exit is None:
                continue
            particle_index = int(record["particle"])
            candidate = np.asarray(best_exit["position_mm"], dtype=np.float64)
            trial_positions[particle_index] = candidate
            nearest_point, _normal = projector._nearest_surface_point(candidate)
            trial_clearances[particle_index] = float(np.linalg.norm(candidate - nearest_point))
            selected_exit_count += 1

        trial_inside = projector._inside_mask(trial_positions)
        trial_clearance = float(trial_clearances.min(initial=float("inf")))
        seam_records = []
        for seam_id, stitch_pairs in base.seam_stitch_pairs.items():
            indices = np.asarray(stitch_pairs, dtype=np.int64).reshape((-1, 2))
            gaps = np.linalg.norm(
                trial_positions[indices[:, 0]] - trial_positions[indices[:, 1]],
                axis=1,
            )
            seam_records.append(
                {
                    "seam_id": str(seam_id),
                    "pair_count": int(len(indices)),
                    "maximum_gap_mm": float(gaps.max(initial=0.0)),
                }
            )

        triangle_records = []
        for panel_name, panel_triangles in base.panel_triangles.items():
            # SimulationProxy.panel_triangles already contains combined global indices.
            triangles = np.asarray(panel_triangles, dtype=np.int64).reshape((-1, 3))
            if triangles.size == 0:
                continue
            before = positions[triangles]
            after = trial_positions[triangles]
            before_edges = np.stack(
                (
                    before[:, 1] - before[:, 0],
                    before[:, 2] - before[:, 1],
                    before[:, 0] - before[:, 2],
                ),
                axis=1,
            )
            after_edges = np.stack(
                (
                    after[:, 1] - after[:, 0],
                    after[:, 2] - after[:, 1],
                    after[:, 0] - after[:, 2],
                ),
                axis=1,
            )
            before_lengths = np.linalg.norm(before_edges, axis=2)
            after_lengths = np.linalg.norm(after_edges, axis=2)
            edge_ratios = np.divide(
                after_lengths,
                before_lengths,
                out=np.ones_like(after_lengths),
                where=before_lengths > 1e-9,
            )
            before_normals = np.cross(before_edges[:, 0], -before_edges[:, 2])
            after_normals = np.cross(after_edges[:, 0], -after_edges[:, 2])
            before_areas = 0.5 * np.linalg.norm(before_normals, axis=1)
            after_areas = 0.5 * np.linalg.norm(after_normals, axis=1)
            area_ratios = np.divide(
                after_areas,
                before_areas,
                out=np.ones_like(after_areas),
                where=before_areas > 1e-9,
            )
            flips = np.einsum("ij,ij->i", before_normals, after_normals) < 0.0
            triangle_records.append(
                {
                    "panel": str(panel_name),
                    "triangle_count": int(len(triangles)),
                    "minimum_edge_ratio": float(edge_ratios.min(initial=1.0)),
                    "maximum_edge_ratio": float(edge_ratios.max(initial=1.0)),
                    "minimum_area_ratio": float(area_ratios.min(initial=1.0)),
                    "maximum_area_ratio": float(area_ratios.max(initial=1.0)),
                    "flipped_triangle_count": int(np.count_nonzero(flips)),
                    "degenerate_after_count": int(np.count_nonzero(after_areas <= 1e-8)),
                }
            )
        copy_trial = {
            "selected_exit_count": selected_exit_count,
            "inside_particle_count": int(np.count_nonzero(trial_inside)),
            "minimum_clearance_mm": trial_clearance,
            "maximum_seam_gap_mm": max(
                (float(item["maximum_gap_mm"]) for item in seam_records),
                default=0.0,
            ),
            "seams": seam_records,
            "panels": triangle_records,
            "exits": exit_records,
        }
        _log("body-projection-copy-trial " + json.dumps(copy_trial, sort_keys=True))
        OUTPUT.mkdir(parents=True, exist_ok=True)
        (OUTPUT / "body-exit-copy-trial.json").write_text(
            json.dumps(copy_trial, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return {
        "inside_particle_count": int(len(inside_indices)),
        "minimum_unsigned_clearance_mm": float(clearance),
    }


def _capture_six_views(
    view: Gui.View3DInventorViewer,
    directory: Path,
    checkpoint: int,
) -> list[JsonObject]:
    """Capture all six principal orthographic views for one solver checkpoint."""
    # FreeCAD animates viewFront/viewRear transitions by default. Disable
    # animation before the six captures so saveImage cannot sample an
    # intermediate blank frame. The mannequin's anatomical front is negative Y;
    # the existing avatar screenshot audit maps that direction to viewRear.
    view.setAnimationEnabled(False)
    actions = (
        ("front", view.viewRear),
        ("rear", view.viewFront),
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
    from freecad_cloth.simulation.SimulationQualityRuntime import (
        QualitySimulationProxy,
        ensure_quality_properties,
    )

    OUTPUT.mkdir(parents=True, exist_ok=True)
    doc = App.newDocument("LayeredOutfitAcceptance")
    _log("document-created")
    try:
        _log("before-avatar-create")
        avatar = create_avatar(attach_collision=False, doc=doc)
        _log("avatar-created")
        avatar.Label = "Layered Outfit Mannequin"
        avatar.ViewObject.Visibility = True

        shoulder_left = _landmark_world(avatar, "shoulder_left")
        shoulder_right = _landmark_world(avatar, "shoulder_right")
        hip = _landmark_world(avatar, "hip")
        _log("mannequin-landmarks-resolved")
        center_x = 0.5 * (float(shoulder_left.x) + float(shoulder_right.x))
        shoulder_width = abs(float(shoulder_right.x) - float(shoulder_left.x))
        if shoulder_width <= 100.0:
            raise RuntimeError("mannequin shoulder landmarks do not define a usable torso width")

        from freecad_cloth.simulation.DrapeTarget import collision_surface

        body_surface = collision_surface(avatar, 1.0, 5.0)
        _log("mannequin-collision-surface-built")
        hip_z = float(hip.z)
        shoulder_z = 0.5 * (float(shoulder_left.z) + float(shoulder_right.z))
        torso_x_limit = 0.60 * shoulder_width
        skirt_bottom_z = hip_z - 520.0
        body_depth_samples = [
            vertex
            for vertex in body_surface.vertices
            if skirt_bottom_z - 30.0 <= float(vertex[2]) <= shoulder_z + 30.0
            and abs(float(vertex[0]) - center_x) <= 0.70 * shoulder_width
        ]
        # The torso-bounded cross-section excludes hands and other appendages that
        # can pass through hip height in the posed mannequin mesh. Derive every
        # skirt/waistband ring dimension from this same local anatomical section.
        hip_slice = [
            vertex
            for vertex in body_surface.vertices
            if hip_z - 60.0 <= float(vertex[2]) <= hip_z + 60.0
            and abs(float(vertex[0]) - center_x) <= torso_x_limit
        ]
        if len(body_depth_samples) < 100 or len(hip_slice) < 50:
            raise RuntimeError(
                "authoritative mannequin surface has insufficient garment-height or hip samples"
            )
        center_y = 0.5 * (
            min(float(vertex[1]) for vertex in hip_slice)
            + max(float(vertex[1]) for vertex in hip_slice)
        )
        radius_x = (
            max(
                0.5 * shoulder_width,
                max(abs(float(vertex[0]) - center_x) for vertex in hip_slice),
            )
            + 28.0
        )
        radius_y = (
            0.5
            * (
                max(float(vertex[1]) for vertex in hip_slice)
                - min(float(vertex[1]) for vertex in hip_slice)
            )
            + 28.0
        )
        radius_x = max(150.0, radius_x)
        radius_y = max(100.0, radius_y)

        hip_x_extreme = max(
            hip_slice,
            key=lambda vertex: abs(float(vertex[0]) - center_x),
        )
        hip_y_minimum = min(hip_slice, key=lambda vertex: float(vertex[1]))
        hip_y_maximum = max(hip_slice, key=lambda vertex: float(vertex[1]))
        placement_base = avatar.Placement.Base
        placement_rotation = avatar.Placement.Rotation.Q
        _log(
            "layered-outfit-source-geometry "
            + json.dumps(
                {
                    "landmarks_world_mm": {
                        "shoulder_left": [
                            float(shoulder_left.x),
                            float(shoulder_left.y),
                            float(shoulder_left.z),
                        ],
                        "shoulder_right": [
                            float(shoulder_right.x),
                            float(shoulder_right.y),
                            float(shoulder_right.z),
                        ],
                        "hip": [float(hip.x), float(hip.y), float(hip.z)],
                    },
                    "avatar_placement_base_mm": [
                        float(placement_base.x),
                        float(placement_base.y),
                        float(placement_base.z),
                    ],
                    "avatar_placement_rotation_xyzw": [
                        float(value) for value in placement_rotation
                    ],
                    "collision_surface_bounds_mm": [
                        [
                            min(float(vertex[axis]) for vertex in body_surface.vertices),
                            max(float(vertex[axis]) for vertex in body_surface.vertices),
                        ]
                        for axis in range(3)
                    ],
                    "body_depth_sample_bounds_mm": [
                        [
                            min(float(vertex[axis]) for vertex in body_depth_samples),
                            max(float(vertex[axis]) for vertex in body_depth_samples),
                        ]
                        for axis in range(3)
                    ],
                    "hip_slice_count": len(hip_slice),
                    "hip_slice_gate_x_mm": torso_x_limit,
                    "hip_slice_bounds_mm": [
                        [
                            min(float(vertex[axis]) for vertex in hip_slice),
                            max(float(vertex[axis]) for vertex in hip_slice),
                        ]
                        for axis in range(3)
                    ],
                    "hip_slice_max_abs_x_point_mm": [float(value) for value in hip_x_extreme],
                    "hip_slice_y_min_point_mm": [float(value) for value in hip_y_minimum],
                    "hip_slice_y_max_point_mm": [float(value) for value in hip_y_maximum],
                    "skirt_radii_mm": [radius_x, radius_y],
                    "skirt_center_y_mm": center_y,
                    "shoulder_width_mm": shoulder_width,
                    "hip_z_mm": hip_z,
                    "shoulder_z_mm": shoulder_z,
                },
                sort_keys=True,
            )
        )

        rotation_front = App.Rotation(App.Vector(1.0, 0.0, 0.0), 90.0)
        rotation_right = App.Rotation(App.Vector(0.0, 0.0, 1.0), 90.0).multiply(rotation_front)
        rotation_back = App.Rotation(App.Vector(0.0, 0.0, 1.0), 180.0).multiply(rotation_front)
        rotation_left = App.Rotation(App.Vector(0.0, 0.0, 1.0), 270.0).multiply(rotation_front)
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
            hem_flare_mm=SKIRT_HEM_FLARE_MM,
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
        waistband_join_seams = [
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
            for side in ("front", "right", "back", "left")
        ]

        # Keep the shell envelope on the torso: a full-height X bound also
        # captures the mannequin's outstretched hands and turns the shirt into a
        # metre-wide box. Measure separate shoulder/chest and hem cross-sections
        # in the same FreeCAD world frame as the collision surface.
        shirt_bottom_z = hip_z - 85.0
        shirt_top_z = shoulder_z + 35.0
        shirt_top_samples = [
            vertex
            for vertex in body_surface.vertices
            if shoulder_z - 55.0 <= float(vertex[2]) <= shoulder_z + 30.0
            and abs(float(vertex[0]) - center_x) <= torso_x_limit
        ]
        shirt_hem_samples = [
            vertex
            for vertex in body_surface.vertices
            if shirt_bottom_z - 35.0 <= float(vertex[2]) <= shirt_bottom_z + 35.0
            and abs(float(vertex[0]) - center_x) <= torso_x_limit
        ]
        if len(shirt_top_samples) < 50 or len(shirt_hem_samples) < 50:
            raise RuntimeError(
                "authoritative torso surface has insufficient shoulder or shirt-hem samples"
            )

        shirt_top_radius_x = (
            max(
                0.5 * shoulder_width,
                max(abs(float(vertex[0]) - center_x) for vertex in shirt_top_samples),
            )
            + 28.0
        )
        measured_shirt_hem_radius_x = (
            max(
                0.5 * shoulder_width,
                max(abs(float(vertex[0]) - center_x) for vertex in shirt_hem_samples),
            )
            + 28.0
        )
        shirt_top_radius_y = (
            0.5
            * (
                max(float(vertex[1]) for vertex in shirt_top_samples)
                - min(float(vertex[1]) for vertex in shirt_top_samples)
            )
            + 28.0
        )
        measured_shirt_hem_radius_y = (
            0.5
            * (
                max(float(vertex[1]) for vertex in shirt_hem_samples)
                - min(float(vertex[1]) for vertex in shirt_hem_samples)
            )
            + 28.0
        )
        shirt_top_center_y = 0.5 * (
            min(float(vertex[1]) for vertex in shirt_top_samples)
            + max(float(vertex[1]) for vertex in shirt_top_samples)
        )
        shirt_hem_center_y = 0.5 * (
            min(float(vertex[1]) for vertex in shirt_hem_samples)
            + max(float(vertex[1]) for vertex in shirt_hem_samples)
        )
        # Keep the source garment shells nested at every shared height. The
        # shirt hem overlaps the upper skirt by 45 mm and the waistband by
        # 100 mm; using only the body-fitted radius made both side panels
        # co-planar at x=+/-248 mm. Start the shirt 6 mm outside the skirt's
        # interpolated envelope so the 8 mm contact projector has a measurable
        # clearance deficit to resolve without opposing coincident surfaces.
        skirt_fraction_at_shirt_hem = (shirt_bottom_z - skirt_bottom_z) / skirt_height
        skirt_hem_radius_x = radius_x + SKIRT_HEM_FLARE_MM * (1.0 - skirt_fraction_at_shirt_hem)
        skirt_hem_radius_y = radius_y + SKIRT_HEM_FLARE_MM * (1.0 - skirt_fraction_at_shirt_hem)
        shirt_hem_radius_x = max(
            measured_shirt_hem_radius_x,
            skirt_hem_radius_x + SHIRT_SKIRT_INITIAL_CONTACT_GAP_MM,
        )
        shirt_hem_radius_y = max(
            measured_shirt_hem_radius_y,
            skirt_hem_radius_y + SHIRT_SKIRT_INITIAL_CONTACT_GAP_MM,
        )
        measured_shirt_center_y = 0.5 * (shirt_top_center_y + shirt_hem_center_y)
        # The shirt's skirt overlap and waistband must share the skirt's measured
        # centre; a body-derived average centre displaced the side boundaries.
        shirt_center_y = center_y
        _log(
            "shirt-torso-envelope x_limit_mm=%.3f top_samples=%d hem_samples=%d "
            "top_radii_mm=(%.3f,%.3f) measured_hem_radii_mm=(%.3f,%.3f) "
            "layered_hem_radii_mm=(%.3f,%.3f) center_y_mm=%.3f measured_body_center_y_mm=%.3f "
            "initial_layer_gap_mm=%.3f"
            % (
                torso_x_limit,
                len(shirt_top_samples),
                len(shirt_hem_samples),
                shirt_top_radius_x,
                shirt_top_radius_y,
                measured_shirt_hem_radius_x,
                measured_shirt_hem_radius_y,
                shirt_hem_radius_x,
                shirt_hem_radius_y,
                shirt_center_y,
                measured_shirt_center_y,
                SHIRT_SKIRT_INITIAL_CONTACT_GAP_MM,
            )
        )
        shirt = _make_ring(
            doc,
            "Shirt",
            shirt_hem_radius_x,
            shirt_hem_radius_y,
            shirt_bottom_z,
            shirt_top_z - shirt_bottom_z,
            *rotations,
            center_x,
            shirt_center_y,
            top_radius_x_mm=shirt_top_radius_x,
            top_radius_y_mm=shirt_top_radius_y,
        )
        shirt_seams = _sew_ring(doc, "Shirt", shirt)
        doc.recompute()

        from freecad_cloth.simulation.DrapeTarget import create_drape_target
        from freecad_cloth.simulation.SimulationObjects import create_simulation_scene

        target = create_drape_target(doc, avatar, "Mannequin", 1.0, 5.0)
        scene = create_simulation_scene(doc, build=False)
        scene.DrapeTarget = target
        ensure_quality_properties(scene)
        scene.Proxy = QualitySimulationProxy()

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
        garment_group_by_piece = {
            entry.split("|", 1)[1]: entry.split("|", 1)[0] for entry in scene.GarmentGroups
        }
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
        _log(
            "pattern-pieces=%d seams=%d"
            % (len(pieces), len(shirt_seams + skirt_seams + waistband_seams + waistband_join_seams))
        )
        if not bool(scene.FiniteState) or int(scene.ParticleCount) <= 0:
            raise RuntimeError("initial twelve-panel solver build did not produce finite particles")

        base = scene.Proxy._base_or_restore()
        backend = base.backend
        if set(getattr(base, "panel_piece_names", {}).values()) != {
            str(piece.Name) for piece in pieces
        }:
            raise RuntimeError(
                "the solver output lost one or more persistent PatternPiece identities"
            )
        if len(base.seam_stitch_pairs) != MINIMUM_SEAMS:
            raise RuntimeError(
                "expected sixteen exact solver seam groups, got %d" % len(base.seam_stitch_pairs)
            )
        if set(base.seam_stitch_pairs) != {
            str(seam.SeamId)
            for seam in (shirt_seams + skirt_seams + waistband_seams + waistband_join_seams)
        }:
            raise RuntimeError("solver stitch provenance does not match the authored sixteen seams")
        # This fixture uses an open-top shirt shell. Support only its authored
        # shoulder/top boundary so the shirt remains worn while the skirt and
        # waistband stay fully dynamic and independently collidable.
        shirt_piece_names = {str(piece.Name) for piece in shirt.values()}
        shirt_top_chains: dict[str, tuple[int, ...]] = {}
        for panel_name, piece_name in base.panel_piece_names.items():
            if piece_name not in shirt_piece_names:
                continue
            boundary_chains = base.panel_boundary_edges.get(panel_name, ())
            if len(boundary_chains) <= SEAM_TOP_EDGE:
                raise RuntimeError("shirt panel has no semantic top boundary: " + panel_name)
            top_chain = tuple(int(index) for index in boundary_chains[SEAM_TOP_EDGE])
            if len(top_chain) < 3:
                raise RuntimeError("shirt panel top boundary has fewer than three particles")
            shirt_top_chains[str(panel_name)] = top_chain

        # A shoulder boundary can overlap the mannequin's upper-arm surface even
        # when its torso-derived ellipse has a positive unsigned distance. Only
        # anchor top-edge particles that are outside the full closed body mesh.
        import numpy as np

        from freecad_cloth.simulation.DrapeVisualSanity import points_inside_closed_mesh

        collision_surface = base.collision_surface
        initial_positions = np.asarray(backend.positions(), dtype=np.float64)
        candidate_indices = tuple(
            dict.fromkeys(index for chain in shirt_top_chains.values() for index in chain)
        )
        candidate_points = tuple(
            tuple(float(value) for value in initial_positions[index])
            for index in candidate_indices
        )
        candidate_inside = points_inside_closed_mesh(
            candidate_points,
            collision_surface.vertices,
            collision_surface.triangles,
            prefer_trimesh=False,
        )
        exterior_by_particle = {
            index: not bool(is_inside)
            for index, is_inside in zip(candidate_indices, candidate_inside, strict=True)
        }
        projector = getattr(backend, "_collision_projector", None)
        if projector is None:
            raise RuntimeError(
                "shirt support selection requires the active body collision projector"
            )
        clearance_by_particle: dict[int, float] = {}
        for index in candidate_indices:
            nearest_point, _normal = projector._nearest_surface_point(initial_positions[index])
            clearance_by_particle[index] = float(
                np.linalg.norm(initial_positions[index] - nearest_point)
            )

        selected_by_panel = select_top_boundary_supports(
            shirt_top_chains,
            exterior_by_particle,
            clearance_by_particle,
            minimum_clearance_mm=MINIMUM_BODY_CLEARANCE_MM,
            samples_per_chain=3,
        )
        support_pin_indices = {
            index for selected in selected_by_panel.values() for index in selected
        }
        if len(support_pin_indices) != 12:
            raise RuntimeError(
                "expected twelve unique exterior shirt-top support particles, got %d"
                % len(support_pin_indices)
            )
        _log(
            "shirt-support-pin-candidate-audit="
            + json.dumps(
                {
                    panel_name: [
                        {
                            "particle": index,
                            "position_mm": [float(value) for value in initial_positions[index]],
                            "inside_mannequin": not exterior_by_particle[index],
                            "nearest_surface_clearance_mm": clearance_by_particle[index],
                            "selected": index in selected_by_panel[panel_name],
                        }
                        for index in chain
                    ]
                    for panel_name, chain in sorted(shirt_top_chains.items())
                },
                sort_keys=True,
            )
        )
        scene.PinMode = "Explicit"
        scene.PinSelection = [str(index) for index in sorted(support_pin_indices)]
        doc.recompute()
        base = scene.Proxy._base_or_restore()
        backend = base.backend
        if backend is None:
            raise RuntimeError("shirt support-pin rebuild did not initialize the solver backend")
        if set(backend._pin_indices) != support_pin_indices:
            raise RuntimeError("native PBD did not register the authored shirt-top support pins")
        initial_positions = backend.positions()
        support_pin_positions = {
            index: tuple(float(value) for value in initial_positions[index])
            for index in support_pin_indices
        }
        top_z_values = [support_pin_positions[index][2] for index in support_pin_indices]
        if max(top_z_values) - min(top_z_values) > 1e-5:
            raise RuntimeError("shirt support pins do not lie on one authored top boundary")
        if max(abs(value - shirt_top_z) for value in top_z_values) > 1e-3:
            raise RuntimeError("shirt support pins are not at the authored shoulder height")
        _log(
            "shirt-support-pins="
            + json.dumps(
                {
                    "mode": str(scene.PinMode),
                    "count": len(support_pin_indices),
                    "particle_indices": sorted(support_pin_indices),
                    "positions_mm": {
                        str(index): list(support_pin_positions[index])
                        for index in sorted(support_pin_indices)
                    },
                },
                sort_keys=True,
            )
        )
        _log(
            "seam-stitch-index-map="
            + json.dumps(
                {
                    seam_id: [[int(left), int(right)] for left, right in pairs]
                    for seam_id, pairs in sorted(base.seam_stitch_pairs.items())
                },
                sort_keys=True,
            )
        )

        seam_objects = {
            str(getattr(obj, "SeamId", "")): obj
            for obj in doc.Objects
            if str(getattr(obj, "SeamId", ""))
        }
        piece_scene_map = _piece_scene_map(pieces, base, garment_group_by_piece)
        mannequin_landmarks = _world_landmarks(avatar)
        collision_surface_record = {
            "source_object": str(avatar.Name),
            "source_revision": int(getattr(avatar, "AvatarRevision", 0)),
            "vertex_count": len(base.collision_surface.vertices),
            "triangle_count": len(base.collision_surface.triangles),
            "collision_thickness_mm": float(target.CollisionThickness),
            "collision_deflection_mm": float(target.CollisionDeflection),
        }

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
        contact_observed_so_far = False
        for step in CHECKPOINTS[1:]:
            scene.Steps = int(step)
            _log("layered-outfit-step-start=%d" % step)
            started = time.perf_counter()
            doc.recompute()
            elapsed_ms = 1000.0 * (time.perf_counter() - started)
            _log("layered-outfit-step-finish=%d elapsed_ms=%.1f" % (step, elapsed_ms))
            _events()
            base = scene.Proxy._base_or_restore()
            backend = base.backend
            before_body_projection = getattr(
                backend,
                "inter_cloth_metrics_before_body_projection",
                None,
            )
            after_body_projection = getattr(backend, "inter_cloth_metrics", None)
            _log(
                "inter-cloth-step=%d before-final-body=%s after-final-body=%s"
                % (
                    step,
                    before_body_projection._asdict()
                    if before_body_projection is not None
                    else None,
                    after_body_projection._asdict() if after_body_projection is not None else None,
                )
            )
            if not bool(scene.FiniteState):
                raise RuntimeError("solver state became non-finite at step %d" % step)
            current_positions = backend.positions()
            maximum_support_pin_drift_mm = max(
                (
                    math.dist(support_pin_positions[index], current_positions[index])
                    for index in support_pin_indices
                ),
                default=0.0,
            )
            _log(
                "shirt-support-pin-drift-step=%d count=%d maximum_mm=%.9f"
                % (step, len(support_pin_indices), maximum_support_pin_drift_mm)
            )
            if maximum_support_pin_drift_mm > 1e-6:
                raise RuntimeError(
                    "shirt support pin drift %.9f mm exceeds 0.000001 mm at step %d"
                    % (maximum_support_pin_drift_mm, step)
                )
            contact_count = int(scene.InterClothContactCount)
            corrected_particle_count = int(scene.InterClothCorrectedParticleCount)
            contact_observed_so_far = contact_observed_so_far or (
                contact_count >= MINIMUM_CONTACTS and corrected_particle_count > 0
            )
            if int(scene.InterClothRemainingContactCount) > 0:
                raise RuntimeError(
                    "residual inter-garment edge/triangle pairs remain below clearance at step %d"
                    % step
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
            seam_metrics = _seam_measurements(backend, base.seam_stitch_pairs, seam_objects)
            _log(
                "seam-metrics-step=%d %s"
                % (step, json.dumps(seam_metrics, sort_keys=True))
            )
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
                _save_png(
                    view,
                    OUTPUT / ("step-%03d-body-penetration.png" % step),
                    view.viewAxonometric,
                    "layered outfit body-penetration diagnostic at step %d" % step,
                )
                _log(
                    "body-clearance-checkpoint=%d metrics=%s"
                    % (step, json.dumps(body_metrics, sort_keys=True))
                )
                raise RuntimeError(
                    "draped garment penetrated the mannequin at step %d: %d particles"
                    % (step, int(body_metrics["inside_particle_count"]))
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
                "contact_count": contact_count,
                "corrected_particle_count": corrected_particle_count,
                "contact_observed_so_far": contact_observed_so_far,
                "support_pin_count": len(support_pin_indices),
                "maximum_support_pin_drift_mm": maximum_support_pin_drift_mm,
                "remaining_contact_count": int(scene.InterClothRemainingContactCount),
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

        if not contact_observed_so_far:
            raise RuntimeError(
                "independent shirt/skirt contact never corrected particles at any checkpoint"
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
        if int(scene.InterClothRemainingContactCount) > 0:
            raise RuntimeError("reloaded solver retained contacts below requested clearance")
        reloaded_base = scene.Proxy._base_or_restore()
        reloaded_backend = reloaded_base.backend
        reloaded_selection = tuple(
            sorted(int(value) for value in getattr(scene, "PinSelection", ()))
        )
        if str(scene.PinMode) != "Explicit":
            raise RuntimeError("explicit shirt support-pin mode did not survive save/reload")
        if reloaded_selection != tuple(sorted(support_pin_indices)):
            raise RuntimeError("shirt support-pin selections changed after save/reload")
        if reloaded_backend is None or set(reloaded_backend._pin_indices) != support_pin_indices:
            raise RuntimeError("native shirt support pins were not rebuilt after save/reload")
        reloaded_positions = reloaded_backend.positions()
        reloaded_pin_drift = max(
            (
                math.dist(support_pin_positions[index], reloaded_positions[index])
                for index in support_pin_indices
            ),
            default=0.0,
        )
        if reloaded_pin_drift > 1e-6:
            raise RuntimeError(
                "shirt support pins moved %.9f mm after save/reload" % reloaded_pin_drift
            )
        _log(
            "shirt-support-pins-save-reload=passed count=%d maximum_drift_mm=%.9f"
            % (len(support_pin_indices), reloaded_pin_drift)
        )
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
                "description": "Longline shirt shell overlapping a flared A-line skirt and separate waistband; twelve panels in two independent groups",
                "piece_count": len(scene.ClothPieces),
                "seam_count": len(reloaded_base.seam_stitch_pairs),
                "garment_group_count": len({entry.split("|", 1)[0] for entry in saved_groups}),
                "piece_ids": list(saved_piece_ids),
                "garment_groups": list(saved_groups),
                "inter_cloth_clearance_mm": float(scene.InterClothClearance),
                "particle_distance_mm": float(scene.ParticleDistance),
                "support_pins": {
                    "mode": str(scene.PinMode),
                    "particle_indices": sorted(support_pin_indices),
                    "count": len(support_pin_indices),
                },
            },
            "scene_map": {
                "coordinate_system": {
                    "units": "mm",
                    "origin": "FreeCAD document world origin",
                    "x_axis": "mannequin left-right",
                    "y_axis": "mannequin front-back",
                    "z_axis": "world up",
                    "front_direction": "negative Y",
                    "placement_quaternion_order": "x,y,z,w",
                },
                "avatar": {
                    "id": str(avatar.Name),
                    "label": str(avatar.Label),
                    "landmarks": mannequin_landmarks,
                    "collision_surface": collision_surface_record,
                },
                "garment_groups": [
                    {
                        "id": "shirt",
                        "piece_ids": [
                            str(shirt[side].PieceId) for side in ("front", "right", "back", "left")
                        ],
                        "independent_of": ["skirt"],
                    },
                    {
                        "id": "skirt",
                        "piece_ids": [
                            str(skirt[side].PieceId) for side in ("front", "right", "back", "left")
                        ]
                        + [
                            str(waistband[side].PieceId)
                            for side in ("front", "right", "back", "left")
                        ],
                        "independent_of": ["shirt"],
                    },
                ],
                "pieces": piece_scene_map,
                "seams": checkpoints[-1]["seams"],
                "camera_views": [
                    {"id": side, "projection": "orthographic", "world_axis_view": side}
                    for side in ("front", "rear", "right", "left", "top", "bottom")
                ],
                "inter_garment_relation": {
                    "garment_group_a": "shirt",
                    "garment_group_b": "skirt",
                    "minimum_requested_clearance_mm": float(scene.InterClothClearance),
                    "measurement_method": "two-sided edge-to-triangle position projection",
                    "metric_semantics": "positive residual value is the requested clearance deficit (requested gap minus closest sampled edge/triangle distance), not signed volumetric intersection depth",
                },
            },
            "checkpoints": checkpoints,
            "images": images,
            "persistence": {
                "fcstd": save_path.name,
                "piece_links_preserved": True,
                "garment_groups_preserved": True,
                "contact_rebuilt_after_reload": True,
                "support_pins_preserved": True,
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
    detail = traceback.format_exc()
    _log("layered-outfit-acceptance=failed error=%r\n%s" % (error, detail))
    App.Console.PrintError("Layered outfit acceptance failed: %s\n%s" % (error, detail))
    os._exit(1)
os._exit(0)
