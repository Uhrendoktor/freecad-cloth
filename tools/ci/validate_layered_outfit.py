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
