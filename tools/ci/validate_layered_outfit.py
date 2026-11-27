# Copyright (C) 2026 FreeCAD Cloth contributors
"""Independent artifact validation for the multi-piece layered outfit acceptance."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from freecad_cloth.common.JsonTypes import JsonObject, JsonValue

if TYPE_CHECKING:
    from collections.abc import Mapping

EXPECTED_PIECES = 10
EXPECTED_SEAMS = 16
EXPECTED_GROUPS = frozenset({"shirt", "skirt"})
EXPECTED_CHECKPOINTS = (5, 15, 60)
EXPECTED_VIEWS = frozenset({"front", "rear", "right", "left", "top", "bottom"})
EXPECTED_IMAGE_WIDTH = 960
EXPECTED_IMAGE_HEIGHT = 720
EXPECTED_IMAGE_COUNT = 15
EXPECTED_GROUP_VIEWS = frozenset(
    {
        "shirt-only-front",
        "shirt-only-rear",
        "shirt-only-right",
        "skirt-only-front",
        "skirt-only-rear",
        "skirt-only-right",
    }
)
MAXIMUM_SHIRT_TOP_DROP_MM = 25.0
MAXIMUM_SHIRT_HEM_DRIFT_MM = 25.0
SHIRT_HEM_SUPPORT_ANCHOR_ROLE = "tucked-hem-stabilizer"
SHIRT_SHOULDER_SUPPORT_ANCHOR_ROLE = "shoulder-side-stabilizer"
MAXIMUM_SHIRT_SHOULDER_SUPPORT_TARGET_DEVIATION_MM = 55.0
MINIMUM_ARMHOLE_DROP_BELOW_SHOULDER_MM = 10.0
MAXIMUM_ARMHOLE_DROP_BELOW_SHOULDER_MM = 85.0
MAXIMUM_RESIDUAL_PENETRATION_MM = 0.5
MAXIMUM_SEAM_GAP_MM = 12.0
MAXIMUM_EARLY_SEAM_GAP_MM = 100.0
MINIMUM_BODY_CLEARANCE_MM = 5.0
MAXIMUM_WAISTBAND_SUPPORT_STANDOFF_MM = 45.0
MAXIMUM_SHIRT_SUPPORT_STANDOFF_MM = 45.0
MAXIMUM_SHIRT_SUPPORT_TARGET_DEVIATION_MM = 5.0
MAXIMUM_SHIRT_SUPPORT_CENTERLINE_OFFSET_MM = 80.0
MAXIMUM_SHIRT_SUPPORT_HEIGHT_OFFSET_MM = 35.0
SHIRT_SUPPORT_ANCHOR_ROLE = "torso-centerline-stabilizer"


def _require(condition: bool, message: str) -> None:
    """Raise a user-facing validation error when one artifact invariant fails."""
    if not condition:
        raise ValueError(message)


def _number(record: Mapping[str, JsonValue], key: str) -> float:
    """Read one finite numeric manifest value."""
    value = record.get(key)
    _require(
        isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value),
        "manifest field %r must be a finite number" % key,
    )
    return float(value)


def _image_file(root: Path, record: Mapping[str, JsonValue]) -> Path:
    """Resolve a manifest image path while rejecting paths outside the artifact root."""
    raw_path = record.get("file")
    _require(isinstance(raw_path, str) and bool(raw_path.strip()), "image file path is missing")
    relative = Path(raw_path)
    _require(not relative.is_absolute(), "image path must be relative to the artifact root")
    path = (root / relative).resolve()
    _require(path.is_relative_to(root.resolve()), "image path escapes the artifact root")
    _require(path.is_file() and path.stat().st_size > 0, "image artifact is missing: %s" % raw_path)
    return path


def _finite_vector(value: JsonValue, name: str, size: int) -> list[float]:
    """Validate one finite coordinate vector in the outfit scene map."""
    _require(
        isinstance(value, list) and len(value) == size,
        "%s must contain %d coordinates" % (name, size),
    )
    values = []
    for item in value:
        _require(
            isinstance(item, (int, float)) and not isinstance(item, bool) and math.isfinite(item),
            "%s contains a non-finite coordinate" % name,
        )
        values.append(float(item))
    return values


def _validated_body_clearance_by_group(
    value: JsonValue,
    clearance_mm: float,
    source: str,
) -> dict[str, float]:
    """Validate nested inner/outer mannequin standoffs for the layered outfit."""
    _require(isinstance(value, dict), "%s body-clearance map is missing" % source)
    _require(
        set(value) == set(EXPECTED_GROUPS),
        "%s body-clearance map must classify shirt and skirt" % source,
    )
    result: dict[str, float] = {}
    for group_id in sorted(EXPECTED_GROUPS):
        raw_value = value.get(group_id)
        _require(
            isinstance(raw_value, (int, float))
            and not isinstance(raw_value, bool)
            and math.isfinite(raw_value)
            and raw_value > 0.0,
            "%s %s body clearance must be finite and positive" % (source, group_id),
        )
        result[group_id] = float(raw_value)
    _require(
        result["shirt"] - result["skirt"] >= clearance_mm - 1e-9,
        "%s outer shirt body clearance must exceed the inner skirt clearance "
        "by at least the inter-garment gap" % source,
    )
    return result


def _validated_vertical_layer_interfaces(
    value: JsonValue,
    clearance_mm: float,
    source: str,
) -> dict[str, float]:
    """Validate the skirt-waistband-shirt vertical interface and hem clearance."""
    _require(isinstance(value, dict), "%s vertical layer interface is missing" % source)
    keys = (
        "skirt_top_z_mm",
        "waistband_bottom_z_mm",
        "waistband_top_z_mm",
        "shirt_hem_z_mm",
        "shirt_hem_front_gap_mm",
        "shirt_hem_back_gap_mm",
    )
    values = {key: _number(value, key) for key in keys}
    _require(
        math.isclose(
            values["waistband_bottom_z_mm"],
            values["skirt_top_z_mm"],
            rel_tol=0.0,
            abs_tol=1e-6,
        ),
        "%s waistband bottom must meet the skirt top" % source,
    )
    _require(
        values["waistband_top_z_mm"] > values["waistband_bottom_z_mm"],
        "%s waistband must have positive vertical height" % source,
    )
    _require(
        math.isclose(
            values["shirt_hem_z_mm"],
            values["waistband_top_z_mm"],
            rel_tol=0.0,
            abs_tol=1e-6,
        ),
        "%s shirt hem must meet the waistband top, not overlap the flared skirt body" % source,
    )
    for side in ("front", "back"):
        _require(
            values["shirt_hem_%s_gap_mm" % side] >= clearance_mm - 1e-6,
            "%s shirt hem %s gap is below the requested inter-garment clearance" % (source, side),
        )
    return values


def _validate_scene_map(
    scene_map: JsonValue,
    piece_ids: list[JsonValue],
    group_assignments: list[JsonValue],
    clearance_mm: float,
    body_clearance_by_group: dict[str, float],
    vertical_layer_interfaces: dict[str, float],
) -> dict[str, int]:
    """Validate exact CAD geometry, world transforms, landmarks and semantic seam links."""
    _require(isinstance(scene_map, dict), "CAD scene map is missing")
    coordinate_system = scene_map.get("coordinate_system")
    avatar = scene_map.get("avatar")
    group_records = scene_map.get("garment_groups")
    piece_records = scene_map.get("pieces")
    seam_records = scene_map.get("seams")
    camera_records = scene_map.get("camera_views")
    relation = scene_map.get("inter_garment_relation")
    scene_body_clearances = _validated_body_clearance_by_group(
        scene_map.get("body_clearance_by_group_mm"),
        clearance_mm,
        "scene map",
    )
    _require(
        scene_body_clearances == body_clearance_by_group,
        "scene map body clearances disagree with the persisted outfit configuration",
    )
    scene_vertical_interfaces = _validated_vertical_layer_interfaces(
        scene_map.get("vertical_layer_interfaces"),
        clearance_mm,
        "scene map",
    )
    _require(
        scene_vertical_interfaces == vertical_layer_interfaces,
        "scene map vertical layer interfaces disagree with the persisted outfit configuration",
    )
    _require(isinstance(coordinate_system, dict), "scene map coordinate system is missing")
    _require(coordinate_system.get("units") == "mm", "scene map must use millimetre coordinates")
    _require(
        coordinate_system.get("placement_quaternion_order") == "x,y,z,w",
        "scene map quaternion order is not declared",
    )
    _require(isinstance(avatar, dict), "scene map mannequin node is missing")
    landmarks = avatar.get("landmarks")
    collision = avatar.get("collision_surface")
    _require(
        isinstance(landmarks, list) and len(landmarks) >= 3,
        "scene map needs named mannequin landmarks",
    )
    landmark_ids: set[str] = set()
    for landmark in landmarks:
        _require(isinstance(landmark, dict), "mannequin landmark record must be an object")
        identifier = landmark.get("id")
        _require(isinstance(identifier, str) and identifier, "mannequin landmark ID is empty")
        _require(identifier not in landmark_ids, "duplicate mannequin landmark ID: %s" % identifier)
        landmark_ids.add(identifier)
        _finite_vector(landmark.get("local_mm"), "landmark local position", 3)
        _finite_vector(landmark.get("world_mm"), "landmark world position", 3)
    _require(isinstance(collision, dict), "mannequin collision surface provenance is missing")
    _require(
        isinstance(collision.get("vertex_count"), int)
        and int(collision["vertex_count"]) > 0
        and isinstance(collision.get("triangle_count"), int)
        and int(collision["triangle_count"]) > 0,
        "mannequin collision topology counts must be positive",
    )

    _require(
        isinstance(group_records, list) and len(group_records) == 2,
        "scene map must contain two garment group nodes",
    )
    expected_by_group: dict[str, set[str]] = {}
    for entry in group_assignments:
        _require(isinstance(entry, str) and "|" in entry, "garment assignment is malformed")
        group_id, piece_id = entry.split("|", 1)
        expected_by_group.setdefault(group_id, set()).add(piece_id)
    seen_groups: set[str] = set()
    for group in group_records:
        _require(isinstance(group, dict), "garment group node must be an object")
        group_id = group.get("id")
        _require(
            isinstance(group_id, str) and group_id in EXPECTED_GROUPS, "unknown garment group node"
        )
        _require(group_id not in seen_groups, "duplicate garment group node: %s" % group_id)
        seen_groups.add(group_id)
        group_piece_ids = group.get("piece_ids")
        _require(isinstance(group_piece_ids, list), "garment group piece inventory is missing")
        _require(
            {str(value) for value in group_piece_ids} == expected_by_group.get(group_id, set()),
            "scene map garment group inventory disagrees with persisted assignments",
        )
        independent = group.get("independent_of")
        _require(
            isinstance(independent, list)
            and set(str(value) for value in independent) == EXPECTED_GROUPS - {group_id},
            "garment group must name the other independent group",
        )
    _require(seen_groups == set(EXPECTED_GROUPS), "scene map is missing a garment group")

    _require(
        isinstance(piece_records, list) and len(piece_records) == EXPECTED_PIECES,
        "scene map needs ten panel geometry records",
    )
    pieces_by_id: dict[str, Mapping[str, JsonValue]] = {}
    for piece in piece_records:
        _require(isinstance(piece, dict), "panel geometry record must be an object")
        piece_id = piece.get("piece_id")
        group_id = piece.get("garment_group")
        _require(isinstance(piece_id, str) and piece_id, "panel piece ID is missing")
        _require(piece_id not in pieces_by_id, "duplicate scene map piece ID: %s" % piece_id)
        _require(
            isinstance(group_id, str) and group_id in EXPECTED_GROUPS,
            "panel references an unknown garment group",
        )
        _require(
            piece_id in expected_by_group[group_id],
            "panel garment group disagrees with its persistent assignment",
        )
        semantic_ids = piece.get("semantic_edge_ids")
        boundaries = piece.get("boundaries")
        expected_edges = 8 if group_id == "shirt" else 4
        _require(
            isinstance(semantic_ids, list)
            and len(semantic_ids) == expected_edges
            and all(isinstance(value, str) and value for value in semantic_ids),
            "source panel must retain %d semantic edge IDs" % expected_edges,
        )
        _require(
            len(set(semantic_ids)) == expected_edges,
            "panel semantic edge IDs are duplicated",
        )
        _require(
            isinstance(boundaries, list) and len(boundaries) == expected_edges,
            "panel boundary sample list is incomplete",
        )
        boundary_ids: set[str] = set()
        for boundary in boundaries:
            _require(isinstance(boundary, dict), "panel boundary record must be an object")
            edge_id = boundary.get("id")
            _require(
                isinstance(edge_id, str) and edge_id in semantic_ids,
                "boundary ID is not a source semantic edge",
            )
            _require(edge_id not in boundary_ids, "duplicate panel boundary ID: %s" % edge_id)
            boundary_ids.add(edge_id)
            samples = boundary.get("samples_local_mm")
            _require(
                isinstance(samples, list) and len(samples) >= 2,
                "boundary must have at least two local samples",
            )
            for sample in samples:
                _finite_vector(sample, "boundary sample", 3)
            _number(boundary, "length_mm")
        _require(
            boundary_ids == set(semantic_ids),
            "panel boundary geometry does not cover its semantic edge map",
        )
        transform = piece.get("local_to_world")
        _require(isinstance(transform, dict), "panel local-to-world transform is missing")
        _finite_vector(transform.get("translation_mm"), "panel translation", 3)
        quaternion = _finite_vector(
            transform.get("rotation_quaternion_xyzw"), "panel rotation quaternion", 4
        )
        _require(
            abs(math.sqrt(sum(value * value for value in quaternion)) - 1.0) <= 1e-5,
            "panel rotation quaternion must be normalized",
        )
        for bound_name in ("local_bounds_mm", "world_bounds_mm"):
            bounds = piece.get(bound_name)
            _require(isinstance(bounds, dict), "%s is missing" % bound_name)
            minimum = _finite_vector(bounds.get("min"), bound_name + " minimum", 3)
            maximum = _finite_vector(bounds.get("max"), bound_name + " maximum", 3)
            _require(
                all(minimum[index] <= maximum[index] for index in range(3)),
                "%s bounds are inverted" % bound_name,
            )
        _number(piece, "grainline_angle_deg")
        _number(piece, "seam_allowance_mm")
        mesh = piece.get("solver_mesh")
        _require(isinstance(mesh, dict), "panel solver mesh provenance is missing")
        _require(
            isinstance(mesh.get("particle_count"), int)
            and int(mesh["particle_count"]) >= 3
            and isinstance(mesh.get("triangle_count"), int)
            and int(mesh["triangle_count"]) >= 1,
            "panel solver mesh topology is incomplete",
        )
        pieces_by_id[piece_id] = piece
    _require(
        set(pieces_by_id) == {str(value) for value in piece_ids},
        "scene map piece identities do not match outfit inventory",
    )
    shirt_panels = [
        piece for piece in pieces_by_id.values() if piece.get("garment_group") == "shirt"
    ]
    skirt_panels = [
        piece
        for piece in pieces_by_id.values()
        if piece.get("garment_group") == "skirt"
        and str(piece.get("name", "")).lower().startswith("skirt ")
    ]
    waistband_panels = [
        piece
        for piece in pieces_by_id.values()
        if piece.get("garment_group") == "skirt"
        and str(piece.get("name", "")).lower().startswith("waistband ")
    ]
    _require(
        len(shirt_panels) == 2 and len(skirt_panels) == 4 and len(waistband_panels) == 4,
        "scene map must distinguish two shirt, four skirt and four waistband panels",
    )
    for panel in shirt_panels:
        bounds = panel.get("world_bounds_mm")
        _require(isinstance(bounds, dict), "shirt world bounds are missing")
        minimum = _finite_vector(bounds.get("min"), "shirt world minimum", 3)
        _require(
            math.isclose(
                minimum[2],
                vertical_layer_interfaces["shirt_hem_z_mm"],
                rel_tol=0.0,
                abs_tol=1e-5,
            ),
            "shirt panel world geometry does not terminate at the declared waistband top",
        )
    for panel in waistband_panels:
        bounds = panel.get("world_bounds_mm")
        _require(isinstance(bounds, dict), "waistband world bounds are missing")
        minimum = _finite_vector(bounds.get("min"), "waistband world minimum", 3)
        maximum = _finite_vector(bounds.get("max"), "waistband world maximum", 3)
        _require(
            math.isclose(
                minimum[2],
                vertical_layer_interfaces["waistband_bottom_z_mm"],
                rel_tol=0.0,
                abs_tol=1e-5,
            )
            and math.isclose(
                maximum[2],
                vertical_layer_interfaces["waistband_top_z_mm"],
                rel_tol=0.0,
                abs_tol=1e-5,
            ),
            "waistband panel world geometry disagrees with its declared vertical interface",
        )
    for panel in skirt_panels:
        bounds = panel.get("world_bounds_mm")
        _require(isinstance(bounds, dict), "skirt world bounds are missing")
        maximum = _finite_vector(bounds.get("max"), "skirt world maximum", 3)
        _require(
            math.isclose(
                maximum[2],
                vertical_layer_interfaces["skirt_top_z_mm"],
                rel_tol=0.0,
                abs_tol=1e-5,
            ),
            "skirt panel world geometry disagrees with its declared top edge",
        )

    _require(
        isinstance(seam_records, list) and len(seam_records) == EXPECTED_SEAMS,
        "scene map needs sixteen semantic sewing relations",
    )
    seam_ids: set[str] = set()
    for seam in seam_records:
        _require(isinstance(seam, dict), "semantic sewing relation must be an object")
        seam_id = seam.get("seam_id")
        _require(isinstance(seam_id, str) and seam_id, "semantic seam ID is empty")
        _require(seam_id not in seam_ids, "duplicate semantic seam ID: %s" % seam_id)
        seam_ids.add(seam_id)
        piece_a = seam.get("piece_a_id")
        piece_b = seam.get("piece_b_id")

        _require(
            piece_a in pieces_by_id and piece_b in pieces_by_id,
            "seam references an unknown source panel",
        )
        _require(
            pieces_by_id[str(piece_a)]["garment_group"]
            == pieces_by_id[str(piece_b)]["garment_group"],
            "semantic seam joins two independent garment groups",
        )
        edge_a = seam.get("edge_a_id")
        edge_b = seam.get("edge_b_id")
        _require(
            edge_a in pieces_by_id[str(piece_a)]["semantic_edge_ids"],
            "seam A-edge is absent from source Sketcher geometry",
        )
        _require(
            edge_b in pieces_by_id[str(piece_b)]["semantic_edge_ids"],
            "seam B-edge is absent from source Sketcher geometry",
        )
        _require(seam.get("status") == "Valid", "seam %s was not valid before simulation" % seam_id)
        _require(seam.get("alignment") in {"uniform", "endpoints"}, "seam alignment is unsupported")
        _number(seam, "maximum_gap_mm")
        _number(seam, "mean_gap_mm")
        _require(
            isinstance(seam.get("stitch_pair_count"), int) and int(seam["stitch_pair_count"]) > 0,
            "seam has no exact solver stitch-pair provenance",
        )
    _require(isinstance(camera_records, list), "scene map camera views are missing")
    camera_ids = {
        str(record.get("id", ""))
        for record in camera_records
        if isinstance(record, dict) and record.get("projection") == "orthographic"
    }
    _require(
        camera_ids == set(EXPECTED_VIEWS), "scene map must declare all six fixed orthographic views"
    )
    _require(isinstance(relation, dict), "independent-garment relation record is missing")
    _require(
        relation.get("garment_group_a") == "shirt" and relation.get("garment_group_b") == "skirt",
        "independent-garment relation does not connect shirt and skirt",
    )
    _require(
        abs(_number(relation, "minimum_requested_clearance_mm") - clearance_mm) <= 1e-9,
        "scene map inter-garment clearance disagrees with the simulation setting",
    )
    metric_semantics = relation.get("metric_semantics")
    _require(
        isinstance(metric_semantics, str)
        and "not signed volumetric intersection depth" in metric_semantics,
        "scene map must define the residual value as a clearance deficit, "
        "not signed volume penetration",
    )
    return {
        "landmarks": len(landmarks),
        "pieces": len(piece_records),
        "seams": len(seam_records),
        "camera_views": len(camera_ids),
        "body_clearance_groups": len(scene_body_clearances),
    }


def validate_manifest(manifest_path: Path | str, expected_commit: str | None = None) -> JsonObject:
    """Validate outfit provenance, independent garment groups, metrics and rendered artifacts.

    Args:
        manifest_path: JSON manifest emitted by the FreeCAD layered outfit acceptance.
        expected_commit: Optional exact source commit to require in the provenance block.

    Returns:
        A concise report containing verified piece, seam, checkpoint and image counts.

    Raises:
        ValueError: If the manifest, metric thresholds, image files or persisted document
            do not satisfy the layered-outfit acceptance contract.
    """
    path = Path(manifest_path).resolve()
    _require(path.is_file(), "layered outfit manifest is missing: %s" % path)
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("layered outfit manifest is not valid JSON") from exc
    _require(isinstance(manifest, dict), "layered outfit manifest root must be an object")
    _require(
        manifest.get("schema") == "freecad-cloth.layered-outfit"
        and manifest.get("schema_version") == 4,
        "unsupported layered outfit manifest schema",
    )

    provenance = manifest.get("provenance")
    outfit = manifest.get("outfit")
    persistence = manifest.get("persistence")
    checkpoints = manifest.get("checkpoints")
    images = manifest.get("images")
    _require(isinstance(provenance, dict), "manifest provenance block is missing")
    _require(isinstance(outfit, dict), "manifest outfit block is missing")
    _require(isinstance(persistence, dict), "manifest persistence block is missing")
    _require(isinstance(checkpoints, list), "manifest checkpoint list is missing")
    _require(isinstance(images, list), "manifest image inventory is missing")

    source_sha = provenance.get("commit_sha")
    _require(
        isinstance(source_sha, str) and len(source_sha) == 40, "manifest commit SHA is invalid"
    )
    if expected_commit:
        _require(
            source_sha == expected_commit,
            "manifest commit SHA does not match the validated checkout",
        )
    _require(provenance.get("units") == "mm", "manifest does not declare millimetre coordinates")
    backend = provenance.get("backend")
    _require(backend == "position-based-dynamics", "manifest does not identify the PBD runtime")

    piece_ids = outfit.get("piece_ids")
    group_assignments = outfit.get("garment_groups")
    _require(isinstance(piece_ids, list), "manifest piece ID inventory is missing")
    _require(
        len(piece_ids) == EXPECTED_PIECES
        and len(set(str(value) for value in piece_ids)) == EXPECTED_PIECES,
        "layered outfit must contain ten distinct native pattern pieces",
    )
    _require(outfit.get("piece_count") == EXPECTED_PIECES, "manifest piece count is not ten")
    _require(outfit.get("seam_count") == EXPECTED_SEAMS, "manifest seam count is not sixteen")
    _require(isinstance(group_assignments, list), "garment group assignments are missing")
    _require(
        len(group_assignments) == EXPECTED_PIECES,
        "every pattern piece must be assigned to exactly one garment group",
    )
    assigned_piece_ids: list[str] = []
    group_ids: set[str] = set()
    for entry in group_assignments:
        _require(
            isinstance(entry, str) and "|" in entry, "garment assignment must use group|piece-id"
        )
        group_id, piece_id = entry.split("|", 1)
        _require(
            group_id in EXPECTED_GROUPS and bool(piece_id), "unknown or empty garment assignment"
        )
        group_ids.add(group_id)
        assigned_piece_ids.append(piece_id)
    _require(
        len(set(assigned_piece_ids)) == EXPECTED_PIECES,
        "a pattern piece is assigned more than once",
    )
    _require(
        set(assigned_piece_ids) == {str(value) for value in piece_ids},
        "piece assignments do not match the pattern inventory",
    )
    _require(
        group_ids == set(EXPECTED_GROUPS),
        "shirt and skirt must remain two independent garment groups",
    )
    _require(
        outfit.get("garment_group_count") == len(EXPECTED_GROUPS), "manifest group count is not two"
    )
    clearance = _number(outfit, "inter_cloth_clearance_mm")
    _require(clearance > 0.0, "inter-cloth clearance must be positive")
    body_clearance_by_group = _validated_body_clearance_by_group(
        outfit.get("body_clearance_by_group_mm"),
        clearance,
        "manifest outfit",
    )
    vertical_layer_interfaces = _validated_vertical_layer_interfaces(
        outfit.get("vertical_layer_interfaces"),
        clearance,
        "manifest outfit",
    )
    armhole_endpoints = outfit.get("shirt_armhole_endpoints")
    _require(
        isinstance(armhole_endpoints, list) and len(armhole_endpoints) == 4,
        "shirt must expose all four native world-space armhole endpoints",
    )
    scene_map_evidence = manifest.get("scene_map")
    _require(isinstance(scene_map_evidence, dict), "scene map is missing")
    avatar_evidence = scene_map_evidence.get("avatar")
    _require(isinstance(avatar_evidence, dict), "scene map avatar landmarks are missing")
    landmark_records = avatar_evidence.get("landmarks")
    _require(isinstance(landmark_records, list), "scene map avatar landmark inventory is missing")
    shoulder_landmarks: dict[str, list[float]] = {}
    for landmark in landmark_records:
        _require(isinstance(landmark, dict), "avatar landmark record must be an object")
        landmark_id = landmark.get("id")
        if isinstance(landmark_id, str) and landmark_id in {
            "shoulder_left",
            "shoulder_right",
        }:
            _require(
                isinstance(landmark_id, str) and landmark_id not in shoulder_landmarks,
                "avatar shoulder landmark identities must be unique",
            )
            shoulder_landmarks[landmark_id] = _finite_vector(
                landmark.get("world_mm"),
                "avatar shoulder landmark world position",
                3,
            )
    _require(
        set(shoulder_landmarks) == {"shoulder_left", "shoulder_right"},
        "scene map must expose both world-space shoulder landmarks",
    )
    shoulder_z = sum(point[2] for point in shoulder_landmarks.values()) / 2.0
    armhole_identities: set[tuple[str, str]] = set()
    for endpoint in armhole_endpoints:
        _require(isinstance(endpoint, dict), "shirt armhole endpoint record must be an object")
        panel_id = endpoint.get("panel")
        arm_side = endpoint.get("arm_side")
        _require(
            isinstance(panel_id, str)
            and isinstance(arm_side, str)
            and panel_id in {"front", "back"}
            and arm_side in {"left", "right"},
            "shirt armhole endpoint must identify a front/back panel and left/right side",
        )
        identity = (panel_id, arm_side)
        _require(
            identity not in armhole_identities,
            "shirt armhole endpoint identities must cover front/back and left/right once",
        )
        armhole_identities.add(identity)
        world_point = _finite_vector(
            endpoint.get("world_mm"), "shirt armhole endpoint world position", 3
        )
        nearest_point = _finite_vector(
            endpoint.get("nearest_mannequin_point_mm"),
            "shirt armhole nearest mannequin point",
            3,
        )
        measured_surface_distance = math.dist(world_point, nearest_point)
        recorded_surface_distance = _number(endpoint, "nearest_surface_distance_mm")
        _require(
            measured_surface_distance > 0.0
            and abs(recorded_surface_distance - measured_surface_distance) <= 1e-3,
            "shirt armhole nearest-surface distance disagrees with its world coordinates",
        )
        measured_drop = shoulder_z - world_point[2]
        _require(
            abs(_number(endpoint, "drop_below_shoulder_mm") - measured_drop) <= 1e-3,
            "shirt armhole shoulder-relative drop disagrees with its world coordinates",
        )
        _require(
            MINIMUM_ARMHOLE_DROP_BELOW_SHOULDER_MM
            <= measured_drop
            <= MAXIMUM_ARMHOLE_DROP_BELOW_SHOULDER_MM,
            "shirt armhole endpoint is outside the expected shoulder/underarm height band",
        )
    scene_armholes = scene_map_evidence.get("shirt_armhole_endpoints")
    _require(
        scene_armholes == armhole_endpoints,
        "scene map armhole positions disagree with the outfit pattern evidence",
    )
    support_pins = outfit.get("support_pins")
    _require(isinstance(support_pins, dict), "shirt torso support-pin record is missing")
    _require(
        support_pins.get("mode") == "Explicit",
        "shirt must retain explicit front/back torso-centerline stabilizers",
    )
    support_pin_indices = support_pins.get("particle_indices")
    _require(
        isinstance(support_pin_indices, list)
        and len(support_pin_indices) == 2
        and all(
            isinstance(index, int) and not isinstance(index, bool) and index >= 0
            for index in support_pin_indices
        )
        and len(set(support_pin_indices)) == 2,
        "shirt support-pin inventory must contain two unique particle indices",
    )
    _require(
        support_pins.get("count") == len(support_pin_indices),
        "shirt support-pin count disagrees with its index inventory",
    )
    shirt_supports = outfit.get("shirt_supports")
    _require(
        isinstance(shirt_supports, list) and len(shirt_supports) == 2,
        "shirt must expose two front/back torso-centerline support records",
    )
    shirt_support_panels: set[str] = set()
    shirt_support_particles: set[int] = set()
    for support in shirt_supports:
        _require(isinstance(support, dict), "shirt support record must be an object")
        panel_id = support.get("panel_id")
        particle_index = support.get("particle_index")
        _require(
            isinstance(panel_id, str) and panel_id and panel_id not in shirt_support_panels,
            "shirt support panel identities must be two unique values",
        )
        _require(
            isinstance(particle_index, int)
            and not isinstance(particle_index, bool)
            and particle_index >= 0
            and particle_index not in shirt_support_particles,
            "shirt support particle identities must be two unique indices",
        )
        shirt_support_panels.add(panel_id)
        shirt_support_particles.add(particle_index)
        _require(
            support.get("anchor_role") == SHIRT_SUPPORT_ANCHOR_ROLE,
            "shirt support anchor role must identify a torso-centerline stabilizer",
        )
        target = _finite_vector(support.get("target_mm"), "shirt support target", 3)
        position = _finite_vector(support.get("position_mm"), "shirt support position", 3)
        target_deviation = math.dist(target, position)
        recorded_target_deviation = _number(support, "target_deviation_mm")
        _require(
            abs(recorded_target_deviation - target_deviation) <= 1e-3,
            "shirt support target deviation disagrees with its persisted coordinates",
        )
        _require(
            target_deviation <= MAXIMUM_SHIRT_SUPPORT_TARGET_DEVIATION_MM,
            "shirt support is detached from its persisted PatternIR mesh target",
        )
        centerline_x = _number(support, "centerline_x_mm")
        centerline_offset = _number(support, "centerline_offset_mm")
        measured_centerline_offset = abs(position[0] - centerline_x)
        _require(
            abs(centerline_offset - measured_centerline_offset) <= 1e-3,
            "shirt support centerline offset disagrees with its persisted coordinates",
        )
        _require(
            measured_centerline_offset <= MAXIMUM_SHIRT_SUPPORT_CENTERLINE_OFFSET_MM,
            "shirt torso support is outside the allowed centerline band",
        )
        target_height_z = _number(support, "target_height_z_mm")
        height_offset = _number(support, "height_offset_mm")
        measured_height_offset = abs(position[2] - target_height_z)
        _require(
            abs(height_offset - measured_height_offset) <= 1e-3,
            "shirt support height offset disagrees with its persisted coordinates",
        )
        _require(
            measured_height_offset <= MAXIMUM_SHIRT_SUPPORT_HEIGHT_OFFSET_MM,
            "shirt torso support is outside the allowed height band",
        )
        design_target = _finite_vector(
            support.get("design_target_mm"), "shirt support design target", 3
        )
        design_deviation = math.dist(position, design_target)
        _require(
            abs(_number(support, "design_target_deviation_mm") - design_deviation) <= 1e-3,
            "shirt support design-target deviation disagrees with its persisted coordinates",
        )
        stand_off = _number(support, "clearance_mm")
        _require(
            MINIMUM_BODY_CLEARANCE_MM <= stand_off <= MAXIMUM_SHIRT_SUPPORT_STANDOFF_MM,
            "shirt support stand-off is outside the anatomical support range",
        )
    _require(
        shirt_support_particles == set(support_pin_indices),
        "shirt support geometry does not match its pinned particle inventory",
    )
    shirt_shoulder_support_pins = outfit.get("shirt_shoulder_support_pins")
    _require(
        isinstance(shirt_shoulder_support_pins, dict),
        "shirt shoulder support-pin record is missing",
    )
    _require(
        shirt_shoulder_support_pins.get("mode") == "Explicit",
        "shirt shoulder-side supports must use Explicit pin mode",
    )
    shirt_shoulder_pin_indices = shirt_shoulder_support_pins.get("particle_indices")
    _require(
        isinstance(shirt_shoulder_pin_indices, list)
        and len(shirt_shoulder_pin_indices) == 4
        and all(
            isinstance(index, int) and not isinstance(index, bool) and index >= 0
            for index in shirt_shoulder_pin_indices
        )
        and len(set(shirt_shoulder_pin_indices)) == 4,
        "shirt shoulder support-pin inventory must contain four unique particle indices",
    )
    _require(
        shirt_shoulder_support_pins.get("count") == len(shirt_shoulder_pin_indices),
        "shirt shoulder support-pin count disagrees with its index inventory",
    )
    _require(
        set(support_pin_indices).isdisjoint(shirt_shoulder_pin_indices),
        "torso-centerline and shoulder-side support pins must be disjoint",
    )
    shirt_shoulder_supports = outfit.get("shirt_shoulder_supports")
    _require(
        isinstance(shirt_shoulder_supports, list) and len(shirt_shoulder_supports) == 4,
        "shirt must expose four front/back shoulder-side support records",
    )
    shoulder_support_particles: set[int] = set()
    shoulder_support_ids: set[str] = set()
    shoulder_support_panels: set[str] = set()
    for support in shirt_shoulder_supports:
        _require(isinstance(support, dict), "shirt shoulder support record must be an object")
        panel_id = support.get("panel_id")
        support_id = support.get("support_id")
        particle_index = support.get("particle_index")
        _require(
            isinstance(panel_id, str) and panel_id and panel_id not in shoulder_support_panels,
            "shirt shoulder support panel identities must be unique",
        )
        _require(
            isinstance(support_id, str) and support_id and support_id not in shoulder_support_ids,
            "shirt shoulder support identifiers must be unique",
        )
        _require(
            isinstance(particle_index, int)
            and not isinstance(particle_index, bool)
            and particle_index >= 0
            and particle_index not in shoulder_support_particles,
            "shirt shoulder support particles must be four unique indices",
        )
        shoulder_support_panels.add(panel_id)
        shoulder_support_ids.add(support_id)
        shoulder_support_particles.add(particle_index)
        _require(
            support.get("anchor_role") == SHIRT_SHOULDER_SUPPORT_ANCHOR_ROLE,
            "shirt shoulder support role must identify a shoulder-side stabilizer",
        )
        target = _finite_vector(support.get("target_mm"), "shirt shoulder support target", 3)
        position = _finite_vector(support.get("position_mm"), "shirt shoulder support position", 3)
        deviation = math.dist(target, position)
        _require(
            abs(_number(support, "target_deviation_mm") - deviation) <= 1e-3,
            "shirt shoulder support target deviation disagrees with its persisted coordinates",
        )
        _require(
            deviation <= MAXIMUM_SHIRT_SHOULDER_SUPPORT_TARGET_DEVIATION_MM,
            "shirt shoulder-side support is detached from its anatomical target",
        )
        stand_off = _number(support, "clearance_mm")
        _require(
            MINIMUM_BODY_CLEARANCE_MM <= stand_off <= MAXIMUM_SHIRT_SUPPORT_STANDOFF_MM,
            "shirt shoulder support stand-off is outside the anatomical support range",
        )
    _require(
        shoulder_support_particles == set(shirt_shoulder_pin_indices),
        "shirt shoulder support geometry does not match its pinned particle inventory",
    )
    shirt_hem_support_pins = outfit.get("shirt_hem_support_pins")
    _require(
        isinstance(shirt_hem_support_pins, dict),
        "shirt hem support-pin record is missing",
    )
    _require(
        shirt_hem_support_pins.get("mode") == "Explicit",
        "shirt hem support pins must use Explicit mode",
    )
    shirt_hem_pin_indices = shirt_hem_support_pins.get("particle_indices")
    _require(
        isinstance(shirt_hem_pin_indices, list)
        and len(shirt_hem_pin_indices) == 10
        and all(
            isinstance(index, int) and not isinstance(index, bool) and index >= 0
            for index in shirt_hem_pin_indices
        )
        and len(set(shirt_hem_pin_indices)) == 10,
        "shirt hem support-pin inventory must contain ten unique particle indices",
    )
    _require(
        shirt_hem_support_pins.get("count") == len(shirt_hem_pin_indices),
        "shirt hem support-pin count disagrees with its index inventory",
    )
    _require(
        set(support_pin_indices).isdisjoint(shirt_hem_pin_indices)
        and set(shirt_shoulder_pin_indices).isdisjoint(shirt_hem_pin_indices),
        "torso, shoulder and shirt hem support-pin inventories must be disjoint",
    )
    shirt_hem_supports = outfit.get("shirt_hem_supports")
    _require(
        isinstance(shirt_hem_supports, list) and len(shirt_hem_supports) == 10,
        "shirt must expose ten distributed native hem support records",
    )
    hem_support_particles: set[int] = set()
    hem_support_ids: set[str] = set()
    hem_support_counts: dict[str, int] = {}
    for support in shirt_hem_supports:
        _require(isinstance(support, dict), "shirt hem support record must be an object")
        panel_id = support.get("panel_id")
        support_id = support.get("support_id")
        particle_index = support.get("particle_index")
        _require(
            isinstance(panel_id, str) and panel_id,
            "shirt hem support panel identity is missing",
        )
        _require(
            isinstance(support_id, str) and support_id and support_id not in hem_support_ids,
            "shirt hem support identifiers must be unique",
        )
        _require(
            isinstance(particle_index, int)
            and not isinstance(particle_index, bool)
            and particle_index >= 0
            and particle_index not in hem_support_particles,
            "shirt hem support particles must be ten unique indices",
        )
        hem_support_ids.add(support_id)
        hem_support_particles.add(particle_index)
        hem_support_counts[panel_id] = hem_support_counts.get(panel_id, 0) + 1
        _require(
            support.get("anchor_role") == SHIRT_HEM_SUPPORT_ANCHOR_ROLE,
            "shirt hem support role must identify a tucked-hem stabilizer",
        )
        target = _finite_vector(support.get("target_mm"), "shirt hem support target", 3)
        position = _finite_vector(support.get("position_mm"), "shirt hem support position", 3)
        deviation = math.dist(target, position)
        _require(
            abs(_number(support, "target_deviation_mm") - deviation) <= 1e-3 and deviation <= 1e-3,
            "shirt hem support is detached from its native boundary particle",
        )
        stand_off = _number(support, "clearance_mm")
        _require(
            MINIMUM_BODY_CLEARANCE_MM <= stand_off <= MAXIMUM_SHIRT_SUPPORT_STANDOFF_MM,
            "shirt hem support stand-off is outside the anatomical support range",
        )
    _require(
        hem_support_particles == set(shirt_hem_pin_indices),
        "shirt hem support geometry does not match its pinned particle inventory",
    )
    _require(
        len(hem_support_counts) == 2 and set(hem_support_counts.values()) == {5},
        "shirt hem supports must be distributed five per front/back panel",
    )
    waistband_support_pins = outfit.get("waistband_support_pins")
    _require(
        isinstance(waistband_support_pins, dict),
        "waistband support-pin record is missing",
    )
    _require(
        waistband_support_pins.get("mode") == "Explicit",
        "waistband support pins must use Explicit mode",
    )
    waistband_pin_indices = waistband_support_pins.get("particle_indices")
    _require(
        isinstance(waistband_pin_indices, list)
        and len(waistband_pin_indices) == 4
        and all(
            isinstance(index, int) and not isinstance(index, bool) and index >= 0
            for index in waistband_pin_indices
        )
        and len(set(waistband_pin_indices)) == 4,
        "waistband support-pin inventory must contain four unique particle indices",
    )
    _require(
        waistband_support_pins.get("count") == len(waistband_pin_indices),
        "waistband support-pin count disagrees with its index inventory",
    )
    _require(
        set(support_pin_indices).isdisjoint(waistband_pin_indices)
        and set(shirt_shoulder_pin_indices).isdisjoint(waistband_pin_indices)
        and set(shirt_hem_pin_indices).isdisjoint(waistband_pin_indices),
        "shirt and waistband support-pin inventories must be disjoint",
    )
    waistband_supports = outfit.get("waistband_supports")
    _require(
        isinstance(waistband_supports, list) and len(waistband_supports) == 4,
        "waistband must expose four anatomical support records",
    )
    support_panels: set[str] = set()
    support_particles: set[int] = set()
    for support in waistband_supports:
        _require(isinstance(support, dict), "waistband support record must be an object")
        panel_id = support.get("panel_id")
        particle_index = support.get("particle_index")
        _require(
            isinstance(panel_id, str) and panel_id and panel_id not in support_panels,
            "waistband support panel identities must be four unique values",
        )
        _require(
            isinstance(particle_index, int)
            and not isinstance(particle_index, bool)
            and particle_index >= 0
            and particle_index not in support_particles,
            "waistband support particle identities must be four unique indices",
        )
        support_panels.add(panel_id)
        support_particles.add(particle_index)
        _finite_vector(support.get("target_mm"), "waistband support target", 3)
        _finite_vector(support.get("position_mm"), "waistband support position", 3)
        stand_off = _number(support, "clearance_mm")
        _require(
            MINIMUM_BODY_CLEARANCE_MM <= stand_off <= MAXIMUM_WAISTBAND_SUPPORT_STANDOFF_MM,
            "waistband support stand-off is outside the anatomical support range",
        )
    _require(
        support_particles == set(waistband_pin_indices),
        "waistband support geometry does not match its pinned particle inventory",
    )
    total_support_pin_count = (
        len(support_pin_indices)
        + len(shirt_shoulder_pin_indices)
        + len(shirt_hem_pin_indices)
        + len(waistband_pin_indices)
    )
    scene_map_counts = _validate_scene_map(
        manifest.get("scene_map"),
        piece_ids,
        group_assignments,
        clearance,
        body_clearance_by_group,
        vertical_layer_interfaces,
    )

    checkpoint_map: dict[int, Mapping[str, JsonValue]] = {}
    for raw_checkpoint in checkpoints:
        _require(isinstance(raw_checkpoint, dict), "checkpoint record must be an object")
        raw_step = raw_checkpoint.get("step")
        _require(
            isinstance(raw_step, int) and not isinstance(raw_step, bool),
            "checkpoint step must be an integer",
        )
        step = int(raw_step)
        _require(step not in checkpoint_map, "duplicate solver checkpoint %d" % step)
        checkpoint_map[step] = raw_checkpoint
    _require(
        tuple(sorted(checkpoint_map)) == EXPECTED_CHECKPOINTS,
        "required garment checkpoints are steps 5, 15 and 60",
    )

    scene_map = manifest["scene_map"]
    scene_seam_ids = {str(seam["seam_id"]) for seam in scene_map["seams"] if isinstance(seam, dict)}
    _require(len(scene_seam_ids) == EXPECTED_SEAMS, "scene map has duplicate seam identities")

    group_colors = outfit.get("garment_group_colors")
    _require(
        isinstance(group_colors, dict) and set(group_colors) == set(EXPECTED_GROUPS),
        "outfit garment colour legend must define shirt and skirt",
    )
    normalized_colors = {
        group_id: _finite_vector(group_colors.get(group_id), "%s garment color" % group_id, 3)
        for group_id in sorted(EXPECTED_GROUPS)
    }
    _require(
        normalized_colors["shirt"] != normalized_colors["skirt"],
        "shirt and skirt must use contrasting display colours",
    )
    scene_map_colors = scene_map.get("garment_group_colors")
    _require(
        isinstance(scene_map_colors, dict) and scene_map_colors == group_colors,
        "scene map garment colours disagree with the outfit display legend",
    )

    contact_observed_so_far = False
    for step, checkpoint in checkpoint_map.items():
        _require(checkpoint.get("finite") is True, "non-finite solver state at step %d" % step)
        contact_count = checkpoint.get("contact_count")
        corrected_particle_count = checkpoint.get("corrected_particle_count")
        _require(
            isinstance(contact_count, int)
            and not isinstance(contact_count, bool)
            and contact_count >= 0,
            "contact count must be a non-negative integer at step %d" % step,
        )
        _require(
            isinstance(corrected_particle_count, int)
            and not isinstance(corrected_particle_count, bool)
            and corrected_particle_count >= 0,
            "corrected particle count must be a non-negative integer at step %d" % step,
        )
        contact_observed_so_far = contact_observed_so_far or (
            contact_count > 0 and corrected_particle_count > 0
        )
        _require(
            checkpoint.get("support_pin_count") == total_support_pin_count,
            "checkpoint must retain all four waistband support pins at step %d" % step,
        )
        _require(
            checkpoint.get("shirt_support_pin_count") == len(support_pin_indices),
            "checkpoint must retain both shirt torso-centerline stabilizers at step %d" % step,
        )
        _require(
            checkpoint.get("shirt_shoulder_support_pin_count") == len(shirt_shoulder_pin_indices),
            "checkpoint must retain all four shoulder-side shirt supports at step %d" % step,
        )
        _require(
            checkpoint.get("shirt_hem_support_pin_count") == len(shirt_hem_pin_indices),
            "checkpoint must retain all ten shirt hem supports at step %d" % step,
        )
        _require(
            checkpoint.get("waistband_support_pin_count") == len(waistband_pin_indices),
            "checkpoint must retain all four waistband support pins at step %d" % step,
        )
        _require(
            _number(checkpoint, "maximum_support_pin_drift_mm") <= 1e-6,
            "garment support pin drift exceeds tolerance at step %d" % step,
        )
        _require(
            _number(checkpoint, "maximum_shirt_support_pin_drift_mm") <= 1e-6,
            "shirt support pin drift exceeds tolerance at step %d" % step,
        )
        _require(
            _number(checkpoint, "maximum_shirt_shoulder_support_pin_drift_mm") <= 1e-6,
            "shirt shoulder support pin drift exceeds tolerance at step %d" % step,
        )
        _require(
            _number(checkpoint, "maximum_shirt_hem_support_pin_drift_mm") <= 1e-6,
            "shirt hem support pin drift exceeds tolerance at step %d" % step,
        )
        _require(
            _number(checkpoint, "maximum_waistband_support_pin_drift_mm") <= 1e-6,
            "waistband support pin drift exceeds tolerance at step %d" % step,
        )
        _require(
            checkpoint.get("contact_observed_so_far") is contact_observed_so_far,
            "cumulative contact activation evidence is inconsistent at step %d" % step,
        )
        _require(
            checkpoint.get("remaining_contact_count") == 0,
            "residual edge/triangle contacts remain below requested clearance at step %d" % step,
        )
        _require(
            _number(checkpoint, "residual_penetration_mm") <= MAXIMUM_RESIDUAL_PENETRATION_MM,
            "residual cloth-to-cloth penetration exceeds tolerance at step %d" % step,
        )
        seam_gap_limit = (
            MAXIMUM_SEAM_GAP_MM if step == EXPECTED_CHECKPOINTS[-1] else MAXIMUM_EARLY_SEAM_GAP_MM
        )
        _require(
            _number(checkpoint, "max_seam_gap_mm") <= seam_gap_limit,
            "sewn panel gap exceeds %.3f mm settling limit at step %d" % (seam_gap_limit, step),
        )
        seams = checkpoint.get("seams")
        _require(
            isinstance(seams, list) and len(seams) == EXPECTED_SEAMS,
            "checkpoint does not contain all sixteen seam measurements at step %d" % step,
        )
        seam_ids = [str(record.get("seam_id", "")) for record in seams if isinstance(record, dict)]
        _require(
            len(seam_ids) == EXPECTED_SEAMS and len(set(seam_ids)) == EXPECTED_SEAMS,
            "checkpoint seam measurements are incomplete or duplicated at step %d" % step,
        )
        _require(
            set(seam_ids) == scene_seam_ids,
            "checkpoint seam identities disagree with the native semantic sewing graph at step %d"
            % step,
        )
        body = checkpoint.get("body")
        _require(
            isinstance(body, dict), "body collision measurements are missing at step %d" % step
        )
        _require(
            body.get("inside_particle_count") == 0,
            "garment particles penetrate the mannequin at step %d" % step,
        )
        _require(
            _number(body, "minimum_unsigned_clearance_mm") >= MINIMUM_BODY_CLEARANCE_MM,
            "mannequin clearance is too small at step %d" % step,
        )
        shirt_fit = checkpoint.get("shirt_fit")
        _require(isinstance(shirt_fit, dict), "shirt fit metrics are missing at step %d" % step)
        top_drop = _number(shirt_fit, "top_drop_mm")
        hem_drift = _number(shirt_fit, "hem_drift_mm")
        if step == EXPECTED_CHECKPOINTS[-1]:
            _require(
                top_drop <= MAXIMUM_SHIRT_TOP_DROP_MM,
                "shirt top falls below the shoulder fit band by %.3f mm" % top_drop,
            )
            _require(
                hem_drift <= MAXIMUM_SHIRT_HEM_DRIFT_MM,
                "shirt hem falls below its waistband fit band by %.3f mm" % hem_drift,
            )
        panel_motion = checkpoint.get("panel_motion")
        _require(
            isinstance(panel_motion, list) and len(panel_motion) == EXPECTED_PIECES,
            "checkpoint must report independent movement for all ten pattern panels",
        )
        panel_motion_by_piece: dict[str, Mapping[str, JsonValue]] = {}
        for record in panel_motion:
            _require(isinstance(record, dict), "panel motion record must be an object")
            piece_id = record.get("piece_id")
            _require(
                isinstance(piece_id, str)
                and piece_id in piece_ids
                and piece_id not in panel_motion_by_piece,
                "panel motion records must identify ten unique pattern pieces",
            )
            role = record.get("role")
            expected_group = (
                "shirt"
                if role == "shirt"
                else "skirt"
                if role in {"skirt_body", "waistband"}
                else ""
            )
            _require(
                record.get("garment_group") == expected_group,
                "panel motion garment ownership disagrees with the pattern-piece group",
            )
            particle_count = record.get("particle_count")
            _require(
                isinstance(particle_count, int)
                and not isinstance(particle_count, bool)
                and particle_count > 0,
                "panel motion must include a positive particle count",
            )
            for metric in (
                "maximum_displacement_mm",
                "mean_displacement_mm",
                "rms_displacement_mm",
            ):
                _require(
                    _number(record, metric) >= 0.0,
                    "panel motion displacement must be non-negative",
                )
            for metric in ("moved_particle_count_1mm", "moved_particle_count_5mm"):
                moved_count = record.get(metric)
                _require(
                    isinstance(moved_count, int)
                    and not isinstance(moved_count, bool)
                    and 0 <= moved_count <= particle_count,
                    "panel moved-particle counts must be within the particle inventory",
                )
            panel_motion_by_piece[piece_id] = record
        _require(
            set(panel_motion_by_piece) == set(piece_ids),
            "panel motion evidence is missing one or more pattern pieces",
        )
        role_counts = {
            role: sum(record.get("role") == role for record in panel_motion_by_piece.values())
            for role in ("shirt", "skirt_body", "waistband")
        }
        _require(
            role_counts == {"shirt": 2, "skirt_body": 4, "waistband": 4},
            "panel motion inventory must cover two shirt, four skirt and four waistband panels",
        )
        if step == EXPECTED_CHECKPOINTS[-1]:
            stationary_skirt = [
                str(record.get("piece_name", piece_id))
                for piece_id, record in panel_motion_by_piece.items()
                if record.get("role") == "skirt_body"
                and (
                    _number(record, "maximum_displacement_mm") < 1.0
                    or record.get("moved_particle_count_1mm", 0) < 1
                )
            ]
            _require(
                not stationary_skirt,
                "skirt panel did not move under the PBD simulation: %s" % stationary_skirt,
            )

    from freecad_cloth.common.VisualCaptureValidation import validate_png_capture

    image_paths: dict[str, Path] = {}
    for raw_image in images:
        _require(isinstance(raw_image, dict), "image inventory entry must be an object")
        raw_label = raw_image.get("label")
        _require(isinstance(raw_label, str) and raw_label.strip(), "image label is missing")
        image_path = _image_file(path.parent, raw_image)
        _require(str(raw_label) not in image_paths, "duplicate image label: %s" % raw_label)
        image_paths[str(raw_label)] = image_path
        _require(
            raw_image.get("width") == EXPECTED_IMAGE_WIDTH
            and raw_image.get("height") == EXPECTED_IMAGE_HEIGHT,
            "image record dimensions are incorrect: %s" % raw_label,
        )
        metrics = validate_png_capture(
            image_path,
            expected_width=EXPECTED_IMAGE_WIDTH,
            expected_height=EXPECTED_IMAGE_HEIGHT,
            min_nonwhite_pixels=128,
            min_distinct_rgb=2,
            min_opaque_pixels=EXPECTED_IMAGE_WIDTH * EXPECTED_IMAGE_HEIGHT // 2,
        )
        _require(
            metrics["nonwhite_pixels"] >= 128, "rendered image is visually blank: %s" % raw_label
        )

    _require(
        len(images) == EXPECTED_IMAGE_COUNT,
        "expected fifteen motion, garment and final-view PNG artifacts",
    )
    group_views = {label for label in image_paths if label in EXPECTED_GROUP_VIEWS}
    _require(
        group_views == set(EXPECTED_GROUP_VIEWS),
        "isolated shirt-only and skirt-only view inventory is incomplete",
    )
    for group_label in EXPECTED_GROUP_VIEWS:
        candidates = [
            raw
            for raw in images
            if raw.get("label") == group_label
            and str(raw.get("file", "")).startswith("final-group-view/")
        ]
        _require(len(candidates) == 1, "isolated garment view is missing: %s" % group_label)
    final_views = {label for label in image_paths if label in EXPECTED_VIEWS}
    _require(final_views == set(EXPECTED_VIEWS), "final six-side view inventory is incomplete")
    for view_name in EXPECTED_VIEWS:
        candidates = [
            raw
            for raw in images
            if raw.get("label") == view_name
            and str(raw.get("file", "")).startswith("final-six-view/")
        ]
        _require(len(candidates) == 1, "final %s orthographic image is missing" % view_name)

    document_name = persistence.get("fcstd")
    _require(
        isinstance(document_name, str) and bool(document_name.strip()),
        "saved FreeCAD document name is missing",
    )
    document_path = _image_file(
        path.parent,
        {"file": document_name},
    )
    _require(document_path.suffix.lower() == ".fcstd", "saved artifact is not a FreeCAD document")
    _require(
        persistence.get("piece_links_preserved") is True,
        "pattern links were not verified after reload",
    )
    _require(
        persistence.get("garment_groups_preserved") is True,
        "garment groups were not verified after reload",
    )
    _require(
        persistence.get("body_clearance_by_group_preserved") is True,
        "per-garment mannequin body standoffs were not verified after reload",
    )
    _require(
        persistence.get("contact_rebuilt_after_reload") is True,
        "contact was not rebuilt after reload",
    )
    _require(
        persistence.get("support_pins_preserved") is True,
        "support-pin configuration was not preserved after save/reload",
    )

    _require(
        persistence.get("shirt_supports_preserved_after_reload") is True,
        "shirt torso-centerline supports were not preserved after save/reload",
    )
    _require(
        persistence.get("shirt_shoulder_supports_preserved_after_reload") is True,
        "shirt shoulder-side supports were not preserved after save/reload",
    )
    _require(
        persistence.get("shirt_hem_supports_preserved_after_reload") is True,
        "shirt hem supports were not preserved after save/reload",
    )
    _require(
        persistence.get("waistband_support_pins_preserved") is True,
        "waistband support pins were not preserved after save/reload",
    )
    saved_step_count = persistence.get("saved_step_count")
    restored_step_count = persistence.get("restored_step_count")
    post_reload_step_count = persistence.get("post_reload_step_count")
    _require(
        isinstance(saved_step_count, int)
        and not isinstance(saved_step_count, bool)
        and saved_step_count == EXPECTED_CHECKPOINTS[-1],
        "saved solver step counter does not match the final checkpoint",
    )
    _require(
        isinstance(restored_step_count, int)
        and not isinstance(restored_step_count, bool)
        and restored_step_count == saved_step_count,
        "saved solver step counter was not preserved after reload",
    )
    _require(
        isinstance(post_reload_step_count, int)
        and not isinstance(post_reload_step_count, bool)
        and post_reload_step_count == 1,
        "reloaded solver was not advanced exactly one fresh step",
    )
    _require(
        persistence.get("native_backend_rebuilt") is True
        and persistence.get("transient_solver_state_reinitialized") is True,
        "native solver state was not rebuilt from persisted scene properties",
    )

    _require(
        contact_observed_so_far,
        "no independent shirt/skirt contact ever corrected particles at a checkpoint",
    )

    return {
        "commit_sha": source_sha,
        "pieces": EXPECTED_PIECES,
        "seams": EXPECTED_SEAMS,
        "garment_groups": len(EXPECTED_GROUPS),
        "scene_map": scene_map_counts,
        "checkpoints": len(checkpoint_map),
        "images": len(image_paths),
        "document": document_path.name,
    }


def main() -> int:
    """Validate one layered outfit manifest and return its process status."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--expected-commit", default=None)
    args = parser.parse_args()
    try:
        result = validate_manifest(args.manifest, args.expected_commit)
    except (OSError, ValueError, TypeError) as exc:
        print("layered-outfit-artifacts=failed error=%s" % exc, file=sys.stderr, flush=True)
        return 1
    print("layered-outfit-artifacts=passed %s" % json.dumps(result, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
