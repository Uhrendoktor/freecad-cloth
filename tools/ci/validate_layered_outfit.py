# Copyright (C) 2026 FreeCAD Cloth contributors
"""Independent artifact validation for the multi-piece layered outfit acceptance."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

EXPECTED_PIECES = 12
EXPECTED_SEAMS = 16
EXPECTED_GROUPS = frozenset({"shirt", "skirt"})
EXPECTED_CHECKPOINTS = (1, 5, 15)
EXPECTED_VIEWS = frozenset({"front", "rear", "right", "left", "top", "bottom"})
EXPECTED_IMAGE_WIDTH = 960
EXPECTED_IMAGE_HEIGHT = 720
EXPECTED_IMAGE_COUNT = 9
MAXIMUM_RESIDUAL_PENETRATION_MM = 0.5
MAXIMUM_SEAM_GAP_MM = 12.0
MINIMUM_BODY_CLEARANCE_MM = 5.0


def _require(condition: bool, message: str) -> None:
    """Raise a user-facing validation error when one artifact invariant fails."""
    if not condition:
        raise ValueError(message)


def _number(record: Mapping[str, object], key: str) -> float:
    """Read one finite numeric manifest value."""
    value = record.get(key)
    _require(
        isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value),
        "manifest field %r must be a finite number" % key,
    )
    return float(value)


def _image_file(root: Path, record: Mapping[str, object]) -> Path:
    """Resolve a manifest image path while rejecting paths outside the artifact root."""
    raw_path = record.get("file")
    _require(isinstance(raw_path, str) and bool(raw_path.strip()), "image file path is missing")
    relative = Path(raw_path)
    _require(not relative.is_absolute(), "image path must be relative to the artifact root")
    path = (root / relative).resolve()
    _require(path.is_relative_to(root.resolve()), "image path escapes the artifact root")
    _require(path.is_file() and path.stat().st_size > 0, "image artifact is missing: %s" % raw_path)
    return path



def _finite_vector(value: object, name: str, size: int) -> list[float]:
    """Validate one finite coordinate vector in the outfit scene map."""
    _require(isinstance(value, list) and len(value) == size, "%s must contain %d coordinates" % (name, size))
    values = []
    for item in value:
        _require(
            isinstance(item, (int, float))
            and not isinstance(item, bool)
            and math.isfinite(item),
            "%s contains a non-finite coordinate" % name,
        )
        values.append(float(item))
    return values


def _validate_scene_map(
    scene_map: object,
    piece_ids: list[object],
    group_assignments: list[object],
    clearance_mm: float,
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
    _require(isinstance(coordinate_system, dict), "scene map coordinate system is missing")
    _require(coordinate_system.get("units") == "mm", "scene map must use millimetre coordinates")
    _require(coordinate_system.get("placement_quaternion_order") == "x,y,z,w", "scene map quaternion order is not declared")
    _require(isinstance(avatar, dict), "scene map mannequin node is missing")
    landmarks = avatar.get("landmarks")
    collision = avatar.get("collision_surface")
    _require(isinstance(landmarks, list) and len(landmarks) >= 3, "scene map needs named mannequin landmarks")
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
        isinstance(collision.get("vertex_count"), int) and int(collision["vertex_count"]) > 0
        and isinstance(collision.get("triangle_count"), int) and int(collision["triangle_count"]) > 0,
        "mannequin collision topology counts must be positive",
    )

    _require(isinstance(group_records, list) and len(group_records) == 2, "scene map must contain two garment group nodes")
    expected_by_group: dict[str, set[str]] = {}
    for entry in group_assignments:
        _require(isinstance(entry, str) and "|" in entry, "garment assignment is malformed")
        group_id, piece_id = entry.split("|", 1)
        expected_by_group.setdefault(group_id, set()).add(piece_id)
    seen_groups: set[str] = set()
    for group in group_records:
        _require(isinstance(group, dict), "garment group node must be an object")
        group_id = group.get("id")
        _require(isinstance(group_id, str) and group_id in EXPECTED_GROUPS, "unknown garment group node")
        _require(group_id not in seen_groups, "duplicate garment group node: %s" % group_id)
        seen_groups.add(group_id)
        group_piece_ids = group.get("piece_ids")
        _require(isinstance(group_piece_ids, list), "garment group piece inventory is missing")
        _require({str(value) for value in group_piece_ids} == expected_by_group.get(group_id, set()), "scene map garment group inventory disagrees with persisted assignments")
        independent = group.get("independent_of")
        _require(
            isinstance(independent, list) and set(str(value) for value in independent) == EXPECTED_GROUPS - {group_id},
            "garment group must name the other independent group",
        )
    _require(seen_groups == set(EXPECTED_GROUPS), "scene map is missing a garment group")

    _require(isinstance(piece_records, list) and len(piece_records) == EXPECTED_PIECES, "scene map needs twelve panel geometry records")
    pieces_by_id: dict[str, Mapping[str, object]] = {}
    for piece in piece_records:
        _require(isinstance(piece, dict), "panel geometry record must be an object")
        piece_id = piece.get("piece_id")
        group_id = piece.get("garment_group")
        _require(isinstance(piece_id, str) and piece_id, "panel piece ID is missing")
        _require(piece_id not in pieces_by_id, "duplicate scene map piece ID: %s" % piece_id)
        _require(isinstance(group_id, str) and group_id in EXPECTED_GROUPS, "panel references an unknown garment group")
        _require(piece_id in expected_by_group[group_id], "panel garment group disagrees with its persistent assignment")
        semantic_ids = piece.get("semantic_edge_ids")
        boundaries = piece.get("boundaries")
        _require(
            isinstance(semantic_ids, list) and len(semantic_ids) == 4
            and all(isinstance(value, str) and value for value in semantic_ids),
            "each rectangular source panel must retain four semantic edge IDs",
        )
        _require(len(set(semantic_ids)) == 4, "panel semantic edge IDs are duplicated")
        _require(isinstance(boundaries, list) and len(boundaries) == 4, "panel boundary sample list is incomplete")
        boundary_ids: set[str] = set()
        for boundary in boundaries:
            _require(isinstance(boundary, dict), "panel boundary record must be an object")
            edge_id = boundary.get("id")
            _require(isinstance(edge_id, str) and edge_id in semantic_ids, "boundary ID is not a source semantic edge")
            _require(edge_id not in boundary_ids, "duplicate panel boundary ID: %s" % edge_id)
            boundary_ids.add(edge_id)
            samples = boundary.get("samples_local_mm")
            _require(isinstance(samples, list) and len(samples) >= 2, "boundary must have at least two local samples")
            for sample in samples:
                _finite_vector(sample, "boundary sample", 3)
            _number(boundary, "length_mm")
        _require(boundary_ids == set(semantic_ids), "panel boundary geometry does not cover its semantic edge map")
        transform = piece.get("local_to_world")
        _require(isinstance(transform, dict), "panel local-to-world transform is missing")
        _finite_vector(transform.get("translation_mm"), "panel translation", 3)
        quaternion = _finite_vector(transform.get("rotation_quaternion_xyzw"), "panel rotation quaternion", 4)
        _require(abs(math.sqrt(sum(value * value for value in quaternion)) - 1.0) <= 1e-5, "panel rotation quaternion must be normalized")
        for bound_name in ("local_bounds_mm", "world_bounds_mm"):
            bounds = piece.get(bound_name)
            _require(isinstance(bounds, dict), "%s is missing" % bound_name)
            minimum = _finite_vector(bounds.get("min"), bound_name + " minimum", 3)
            maximum = _finite_vector(bounds.get("max"), bound_name + " maximum", 3)
            _require(all(minimum[index] <= maximum[index] for index in range(3)), "%s bounds are inverted" % bound_name)
        _number(piece, "grainline_angle_deg")
        _number(piece, "seam_allowance_mm")
        mesh = piece.get("solver_mesh")
        _require(isinstance(mesh, dict), "panel solver mesh provenance is missing")
        _require(
            isinstance(mesh.get("particle_count"), int) and int(mesh["particle_count"]) >= 3
            and isinstance(mesh.get("triangle_count"), int) and int(mesh["triangle_count"]) >= 1,
            "panel solver mesh topology is incomplete",
        )
        pieces_by_id[piece_id] = piece
    _require(set(pieces_by_id) == {str(value) for value in piece_ids}, "scene map piece identities do not match outfit inventory")

    _require(isinstance(seam_records, list) and len(seam_records) == EXPECTED_SEAMS, "scene map needs sixteen semantic sewing relations")
    seam_ids: set[str] = set()
    for seam in seam_records:
        _require(isinstance(seam, dict), "semantic sewing relation must be an object")
        seam_id = seam.get("seam_id")
        _require(isinstance(seam_id, str) and seam_id, "semantic seam ID is empty")
        _require(seam_id not in seam_ids, "duplicate semantic seam ID: %s" % seam_id)
        seam_ids.add(seam_id)
        piece_a = seam.get("piece_a_id")
        piece_b = seam.get("piece_b_id")
        _require(piece_a in pieces_by_id and piece_b in pieces_by_id, "seam references an unknown source panel")
        _require(
            pieces_by_id[str(piece_a)]["garment_group"] == pieces_by_id[str(piece_b)]["garment_group"],
            "semantic seam joins two independent garment groups",
        )
        edge_a = seam.get("edge_a_id")
        edge_b = seam.get("edge_b_id")
        _require(edge_a in pieces_by_id[str(piece_a)]["semantic_edge_ids"], "seam A-edge is absent from source Sketcher geometry")
        _require(edge_b in pieces_by_id[str(piece_b)]["semantic_edge_ids"], "seam B-edge is absent from source Sketcher geometry")
        _require(seam.get("status") == "Valid", "seam %s was not valid before simulation" % seam_id)
        _require(seam.get("alignment") in {"uniform", "endpoints"}, "seam alignment is unsupported")
        _number(seam, "maximum_gap_mm")
        _number(seam, "mean_gap_mm")
        _require(isinstance(seam.get("stitch_pair_count"), int) and int(seam["stitch_pair_count"]) > 0, "seam has no exact solver stitch-pair provenance")
    _require(isinstance(camera_records, list), "scene map camera views are missing")
    camera_ids = {
        str(record.get("id", ""))
        for record in camera_records
        if isinstance(record, dict) and record.get("projection") == "orthographic"
    }
    _require(camera_ids == set(EXPECTED_VIEWS), "scene map must declare all six fixed orthographic views")
    _require(isinstance(relation, dict), "independent-garment relation record is missing")
    _require(
        relation.get("garment_group_a") == "shirt" and relation.get("garment_group_b") == "skirt",
        "independent-garment relation does not connect shirt and skirt",
    )
    _require(
        abs(_number(relation, "minimum_requested_clearance_mm") - clearance_mm) <= 1e-9,
        "scene map inter-garment clearance disagrees with the simulation setting",
    )
    return {
        "landmarks": len(landmarks),
        "pieces": len(piece_records),
        "seams": len(seam_records),
        "camera_views": len(camera_ids),
    }


def validate_manifest(manifest_path: Path | str, expected_commit: str | None = None) -> dict[str, object]:
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
        and manifest.get("schema_version") == 1,
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
    _require(isinstance(source_sha, str) and len(source_sha) == 40, "manifest commit SHA is invalid")
    if expected_commit:
        _require(source_sha == expected_commit, "manifest commit SHA does not match the validated checkout")
    _require(provenance.get("units") == "mm", "manifest does not declare millimetre coordinates")
    backend = provenance.get("backend")
    _require(backend == "position-based-dynamics", "manifest does not identify the PBD runtime")

    piece_ids = outfit.get("piece_ids")
    group_assignments = outfit.get("garment_groups")
    _require(isinstance(piece_ids, list), "manifest piece ID inventory is missing")
    _require(
        len(piece_ids) == EXPECTED_PIECES
        and len(set(str(value) for value in piece_ids)) == EXPECTED_PIECES,
        "layered outfit must contain twelve distinct native pattern pieces",
    )
    _require(outfit.get("piece_count") == EXPECTED_PIECES, "manifest piece count is not twelve")
    _require(outfit.get("seam_count") == EXPECTED_SEAMS, "manifest seam count is not sixteen")
    _require(isinstance(group_assignments, list), "garment group assignments are missing")
    _require(
        len(group_assignments) == EXPECTED_PIECES,
        "every pattern piece must be assigned to exactly one garment group",
    )
    assigned_piece_ids: list[str] = []
    group_ids: set[str] = set()
    for entry in group_assignments:
        _require(isinstance(entry, str) and "|" in entry, "garment assignment must use group|piece-id")
        group_id, piece_id = entry.split("|", 1)
        _require(group_id in EXPECTED_GROUPS and bool(piece_id), "unknown or empty garment assignment")
        group_ids.add(group_id)
        assigned_piece_ids.append(piece_id)
    _require(len(set(assigned_piece_ids)) == EXPECTED_PIECES, "a pattern piece is assigned more than once")
    _require(set(assigned_piece_ids) == {str(value) for value in piece_ids}, "piece assignments do not match the pattern inventory")
    _require(group_ids == set(EXPECTED_GROUPS), "shirt and skirt must remain two independent garment groups")
    _require(outfit.get("garment_group_count") == len(EXPECTED_GROUPS), "manifest group count is not two")
    clearance = _number(outfit, "inter_cloth_clearance_mm")
    _require(clearance > 0.0, "inter-cloth clearance must be positive")
    scene_map_counts = _validate_scene_map(manifest.get("scene_map"), piece_ids, group_assignments, clearance)

    checkpoint_map: dict[int, Mapping[str, object]] = {}
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
        "required garment checkpoints are steps 1, 5 and 15",
    )

    scene_map = manifest["scene_map"]
    scene_seam_ids = {
        str(seam["seam_id"]) for seam in scene_map["seams"] if isinstance(seam, dict)
    }
    _require(len(scene_seam_ids) == EXPECTED_SEAMS, "scene map has duplicate seam identities")

    for step, checkpoint in checkpoint_map.items():
        _require(checkpoint.get("finite") is True, "non-finite solver state at step %d" % step)
        _require(
            isinstance(checkpoint.get("contact_count"), int)
            and int(checkpoint["contact_count"]) > 0,
            "no independent garment contact was measured at step %d" % step,
        )
        _require(
            isinstance(checkpoint.get("corrected_particle_count"), int)
            and int(checkpoint["corrected_particle_count"]) > 0,
            "no cloth particles were corrected by inter-garment contact at step %d" % step,
        )
        _require(
            _number(checkpoint, "residual_penetration_mm") <= MAXIMUM_RESIDUAL_PENETRATION_MM,
            "residual cloth-to-cloth penetration exceeds tolerance at step %d" % step,
        )
        _require(
            _number(checkpoint, "max_seam_gap_mm") <= MAXIMUM_SEAM_GAP_MM,
            "sewn panel gap exceeds tolerance at step %d" % step,
        )
        seams = checkpoint.get("seams")
        _require(isinstance(seams, list) and len(seams) == EXPECTED_SEAMS,
            "checkpoint does not contain all sixteen seam measurements at step %d" % step)
        seam_ids = [
            str(record.get("seam_id", ""))
            for record in seams
            if isinstance(record, dict)
        ]
        _require(
            len(seam_ids) == EXPECTED_SEAMS and len(set(seam_ids)) == EXPECTED_SEAMS,
            "checkpoint seam measurements are incomplete or duplicated at step %d" % step,
        )
        _require(
            set(seam_ids) == scene_seam_ids,
            "checkpoint seam identities disagree with the native semantic sewing graph at step %d" % step,
        )
        body = checkpoint.get("body")
        _require(isinstance(body, dict), "body collision measurements are missing at step %d" % step)
        _require(
            body.get("inside_particle_count") == 0,
            "garment particles penetrate the mannequin at step %d" % step,
        )
        _require(
            _number(body, "minimum_unsigned_clearance_mm") >= MINIMUM_BODY_CLEARANCE_MM,
            "mannequin clearance is too small at step %d" % step,
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
        _require(metrics["nonwhite_pixels"] >= 128, "rendered image is visually blank: %s" % raw_label)

    _require(len(images) == EXPECTED_IMAGE_COUNT, "expected nine motion and final-view PNG artifacts")
    final_views = {
        label
        for label in image_paths
        if label in EXPECTED_VIEWS
    }
    _require(final_views == set(EXPECTED_VIEWS), "final six-side view inventory is incomplete")
    for view_name in EXPECTED_VIEWS:
        candidates = [
            raw for raw in images
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
    _require(persistence.get("piece_links_preserved") is True, "pattern links were not verified after reload")
    _require(persistence.get("garment_groups_preserved") is True, "garment groups were not verified after reload")
    _require(persistence.get("contact_rebuilt_after_reload") is True, "contact was not rebuilt after reload")

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
