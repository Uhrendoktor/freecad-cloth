# Copyright (C) 2026 FreeCAD Cloth contributors
"""Independent regression tests for layered outfit artifact validation."""

import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from tools.ci.validate_layered_outfit import validate_manifest

IMAGE_WIDTH = 960
IMAGE_HEIGHT = 720


def _write_png(path: Path, *, blank: bool = False) -> None:
    """Create a valid deterministic image for validator infrastructure tests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), "white")
    if not blank:
        draw = ImageDraw.Draw(image)
        draw.rectangle((120, 100, 840, 620), outline=(30, 60, 90), width=10)
        draw.line((120, 360, 840, 360), fill=(160, 30, 80), width=12)
        draw.line((480, 100, 480, 620), fill=(20, 130, 70), width=12)
    image.save(path, format="PNG")


def _valid_artifact(root: Path) -> Path:
    """Write a complete manifest and its referenced document/PNG artifacts."""
    (root / "layered-outfit.FCStd").write_bytes(b"native-freecad-document-fixture")
    image_records = []
    image_inventory = (
        ("step-000-axonometric.png", "initial arranged layered outfit"),
        ("step-001-axonometric.png", "layered outfit motion at step 1"),
        ("step-005-axonometric.png", "layered outfit motion at step 5"),
        *(
            ("final-six-view/step-015-%s.png" % side, side)
            for side in ("front", "rear", "right", "left", "top", "bottom")
        ),
    )
    for relative_path, label in image_inventory:
        image_path = root / relative_path
        _write_png(image_path)
        image_records.append(
            {
                "file": relative_path,
                "label": label,
                "width": IMAGE_WIDTH,
                "height": IMAGE_HEIGHT,
                "nonwhite_pixels": 20000,
                "distinct_rgb": 4,
            }
        )

    piece_ids = ["piece-%02d" % index for index in range(12)]
    assignments = [
        ("shirt" if index < 4 else "skirt") + "|" + piece_id
        for index, piece_id in enumerate(piece_ids)
    ]
    seams = [
        {
            "seam_id": "seam-%02d" % index,
            "stitch_pair_count": 8,
            "maximum_gap_mm": 0.2,
            "mean_gap_mm": 0.1,
        }
        for index in range(16)
    ]
    checkpoints = []
    for step in (1, 5, 15):
        checkpoints.append(
            {
                "step": step,
                "elapsed_ms": 100.0,
                "finite": True,
                "contact_count": 24,
                "corrected_particle_count": 32,
                "max_penetration_before_mm": 1.0,
                "residual_penetration_mm": 0.0,
                "max_seam_gap_mm": 0.2,
                "body": {
                    "inside_particle_count": 0,
                    "minimum_unsigned_clearance_mm": 18.0,
                },
                "seams": seams,
                "images": [],
            }
        )
    manifest = {
        "schema": "freecad-cloth.layered-outfit",
        "schema_version": 1,
        "provenance": {
            "commit_sha": "a" * 40,
            "document": "layered-outfit.FCStd",
            "backend": "position-based-dynamics",
            "units": "mm",
            "world_frame": {
                "origin": "FreeCAD document world origin",
                "axes": {"x": "left-right", "y": "front-back", "z": "world up"},
                "camera_front": "negative Y",
            },
        },
        "outfit": {
            "piece_count": 12,
            "seam_count": 16,
            "garment_group_count": 2,
            "piece_ids": piece_ids,
            "garment_groups": assignments,
            "inter_cloth_clearance_mm": 8.0,
            "particle_distance_mm": 24.0,
        },
        "checkpoints": checkpoints,
        "images": image_records,
        "persistence": {
            "fcstd": "layered-outfit.FCStd",
            "piece_links_preserved": True,
            "garment_groups_preserved": True,
            "contact_rebuilt_after_reload": True,
        },
    }
    path = root / "layered-outfit-manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_validator_accepts_complete_layered_outfit_artifacts(tmp_path: Path) -> None:
    """A full artifact pack must prove two groups, contact, seams, six views and reload."""
    manifest = _valid_artifact(tmp_path)

    result = validate_manifest(manifest, expected_commit="a" * 40)

    assert result == {
        "commit_sha": "a" * 40,
        "pieces": 12,
        "seams": 16,
        "garment_groups": 2,
        "checkpoints": 3,
        "images": 9,
        "document": "layered-outfit.FCStd",
    }


def test_validator_rejects_residual_inter_cloth_penetration(tmp_path: Path) -> None:
    """A drape cannot pass while two independent fabric groups still penetrate."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["checkpoints"][1]["residual_penetration_mm"] = 1.25
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="residual cloth-to-cloth penetration"):
        validate_manifest(manifest_path)


def test_validator_rejects_duplicate_piece_assignment(tmp_path: Path) -> None:
    """A piece cannot silently be assigned to both the shirt and skirt."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["outfit"]["garment_groups"][4] = manifest["outfit"]["garment_groups"][0].replace(
        "shirt|", "skirt|"
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="assigned more than once"):
        validate_manifest(manifest_path)


def test_validator_rejects_blank_rendered_view(tmp_path: Path) -> None:
    """A present but visually blank PNG must not satisfy the six-view contract."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    blank_path = tmp_path / "final-six-view" / "step-015-left.png"
    _write_png(blank_path, blank=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="blank"):
        validate_manifest(manifest_path)
