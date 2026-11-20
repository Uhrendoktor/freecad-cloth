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
        ("step-015-axonometric.png", "layered outfit motion at step 15"),
        *(
            ("final-six-view/step-060-%s.png" % side, side)
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
    seams = []
    seam_links = (
        *((index, (index + 1) % 4) for index in range(4)),
        *((4 + index, 4 + (index + 1) % 4) for index in range(4)),
        *((8 + index, 8 + (index + 1) % 4) for index in range(4)),
        *((4 + index, 8 + index) for index in range(4)),
    )
    for index, (piece_a_index, piece_b_index) in enumerate(seam_links):
        piece_a_id = piece_ids[piece_a_index]
        piece_b_id = piece_ids[piece_b_index]
        seams.append(
            {
                "seam_id": "seam-%02d" % index,
                "piece_a_id": piece_a_id,
                "piece_b_id": piece_b_id,
                "edge_a_id": piece_a_id + ":e1",
                "edge_b_id": piece_b_id + ":e3",
                "start_a": 0.0,
                "end_a": 1.0,
                "start_b": 0.0,
                "end_b": 1.0,
                "reversed_b": True,
                "alignment": "uniform",
                "stitch_group": "garment-assembly",
                "kind": "plain",
                "status": "Valid",
                "stitch_pair_count": 8,
                "maximum_gap_mm": 0.2,
                "mean_gap_mm": 0.1,
            }
        )
    checkpoints = [
        {
            "step": step,
            "elapsed_ms": 100.0,
            "finite": True,
            "contact_count": 0 if step == 60 else 24,
            "corrected_particle_count": 0 if step == 60 else 32,
            "contact_observed_so_far": True,
            "support_pin_count": 24,
            "shirt_support_pin_count": 12,
            "waistband_support_pin_count": 12,
            "maximum_support_pin_drift_mm": 0.0,
            "maximum_shirt_support_pin_drift_mm": 0.0,
            "maximum_waistband_support_pin_drift_mm": 0.0,
            "remaining_contact_count": 0,
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
        for step in (1, 15, 60)
    ]
    pieces_scene = []
    for index, piece_id in enumerate(piece_ids):
        group_id = "shirt" if index < 4 else "skirt"
        semantic_ids = [piece_id + ":e%d" % edge for edge in range(4)]
        boundaries = [
            {
                "id": semantic_ids[edge],
                "kind": "line",
                "length_mm": 100.0,
                "samples_local_mm": [[0.0, 0.0, 0.0], [100.0, 0.0, 0.0]],
            }
            for edge in range(4)
        ]
        pieces_scene.append(
            {
                "piece_id": piece_id,
                "name": "Panel " + piece_id,
                "garment_group": group_id,
                "solver_panel_id": "DrapePanel%d" % index,
                "local_to_world": {
                    "translation_mm": [float(index), 0.0, 0.0],
                    "rotation_quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
                },
                "grainline_angle_deg": 0.0,
                "seam_allowance_mm": 10.0,
                "semantic_edge_ids": semantic_ids,
                "boundaries": boundaries,
                "local_bounds_mm": {"min": [0.0, 0.0, 0.0], "max": [100.0, 100.0, 0.0]},
                "world_bounds_mm": {
                    "min": [float(index), 0.0, 0.0],
                    "max": [float(index) + 100.0, 100.0, 0.0],
                },
                "solver_mesh": {"particle_count": 50, "triangle_count": 80},
            }
        )
    scene_map = {
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
            "id": "ClothAvatar",
            "label": "Mannequin",
            "landmarks": [
                {
                    "id": "shoulder_left",
                    "local_mm": [-100.0, 0.0, 150.0],
                    "world_mm": [-100.0, 0.0, 150.0],
                },
                {
                    "id": "shoulder_right",
                    "local_mm": [100.0, 0.0, 150.0],
                    "world_mm": [100.0, 0.0, 150.0],
                },
                {"id": "hip", "local_mm": [0.0, 0.0, 0.0], "world_mm": [0.0, 0.0, 0.0]},
            ],
            "collision_surface": {
                "source_object": "ClothAvatar",
                "source_revision": 1,
                "vertex_count": 1000,
                "triangle_count": 2000,
                "collision_thickness_mm": 5.0,
                "collision_deflection_mm": 1.0,
            },
        },
        "garment_groups": [
            {"id": "shirt", "piece_ids": piece_ids[:4], "independent_of": ["skirt"]},
            {"id": "skirt", "piece_ids": piece_ids[4:], "independent_of": ["shirt"]},
        ],
        "pieces": pieces_scene,
        "seams": seams,
        "camera_views": [
            {"id": side, "projection": "orthographic", "world_axis_view": side}
            for side in ("front", "rear", "right", "left", "top", "bottom")
        ],
        "inter_garment_relation": {
            "garment_group_a": "shirt",
            "garment_group_b": "skirt",
            "minimum_requested_clearance_mm": 8.0,
            "measurement_method": "two-sided edge-to-triangle position projection",
            "metric_semantics": "positive residual value is the requested clearance deficit (requested gap minus closest sampled edge/triangle distance), not signed volumetric intersection depth",
        },
    }
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
            "support_pins": {
                "mode": "Explicit",
                "particle_indices": list(range(12)),
                "count": 12,
            },
            "waistband_support_pins": {
                "mode": "Explicit",
                "particle_indices": list(range(12, 24)),
                "count": 12,
            },
        },
        "scene_map": scene_map,
        "checkpoints": checkpoints,
        "images": image_records,
        "persistence": {
            "fcstd": "layered-outfit.FCStd",
            "piece_links_preserved": True,
            "garment_groups_preserved": True,
            "contact_rebuilt_after_reload": True,
            "support_pins_preserved": True,
            "waistband_support_pins_preserved": True,
        },
    }
    path = root / "layered-outfit-manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_validator_accepts_complete_layered_outfit_artifacts(tmp_path: Path) -> None:
    """A full pack must retain early contact activation and zero residual at all checkpoints."""
    manifest = _valid_artifact(tmp_path)

    result = validate_manifest(manifest, expected_commit="a" * 40)

    assert result == {
        "commit_sha": "a" * 40,
        "pieces": 12,
        "seams": 16,
        "garment_groups": 2,
        "scene_map": {"landmarks": 3, "pieces": 12, "seams": 16, "camera_views": 6},
        "checkpoints": 3,
        "images": 9,
        "document": "layered-outfit.FCStd",
    }


def test_validator_rejects_missing_shirt_support_pins(tmp_path: Path) -> None:
    """The shirt must retain its twelve authored top-boundary support pins."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["outfit"]["support_pins"]["particle_indices"] = []
    manifest["outfit"]["support_pins"]["count"] = 0
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="twelve unique particle indices"):
        validate_manifest(manifest_path)


def test_validator_rejects_missing_waistband_support_pins(tmp_path: Path) -> None:
    """The waistband must retain twelve authored top-boundary support pins."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["outfit"]["waistband_support_pins"]["particle_indices"] = []
    manifest["outfit"]["waistband_support_pins"]["count"] = 0
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="twelve unique particle indices"):
        validate_manifest(manifest_path)


def test_validator_rejects_waistband_support_pin_drift(tmp_path: Path) -> None:
    """Waistband top anchors must remain fixed throughout all native checkpoints."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["checkpoints"][1]["maximum_waistband_support_pin_drift_mm"] = 0.01
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="waistband support pin drift"):
        validate_manifest(manifest_path)


def test_validator_rejects_shirt_support_pin_drift(tmp_path: Path) -> None:
    """Support anchors must remain fixed throughout all native solver checkpoints."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["checkpoints"][1]["maximum_support_pin_drift_mm"] = 0.01
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="shirt support pin drift"):
        validate_manifest(manifest_path)


def test_validator_rejects_no_contact_activation_during_the_run(tmp_path: Path) -> None:
    """At least one checkpoint must show real contact-driven particle correction."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for checkpoint in manifest["checkpoints"]:
        checkpoint["contact_count"] = 0
        checkpoint["corrected_particle_count"] = 0
        checkpoint["contact_observed_so_far"] = False
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="no independent shirt/skirt contact ever"):
        validate_manifest(manifest_path)


def test_validator_rejects_inconsistent_cumulative_contact_activation(tmp_path: Path) -> None:
    """The stored cumulative contact flag must match the checkpoint measurements."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["checkpoints"][-1]["contact_observed_so_far"] = False
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="cumulative contact activation"):
        validate_manifest(manifest_path)


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
    blank_path = tmp_path / "final-six-view" / "step-060-left.png"
    _write_png(blank_path, blank=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="blank"):
        validate_manifest(manifest_path)


def test_validator_rejects_a_seam_that_connects_two_independent_garments(tmp_path: Path) -> None:
    """Cross-garment sewing is not a valid substitute for inter-cloth contact."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    seam = manifest["scene_map"]["seams"][0]
    seam["piece_b_id"] = "piece-04"
    seam["edge_b_id"] = "piece-04:e3"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="joins two independent garment groups"):
        validate_manifest(manifest_path)


def test_validator_rejects_remaining_edge_triangle_contact_after_projection(tmp_path: Path) -> None:
    """The artifact cannot pass while any garment pair remains below requested clearance."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["checkpoints"][1]["remaining_contact_count"] = 2
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="residual edge/triangle contacts"):
        validate_manifest(manifest_path)


def test_validator_requires_clearance_deficit_semantics(tmp_path: Path) -> None:
    """A metric named penetration must not be silently interpreted as signed volume."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    del manifest["scene_map"]["inter_garment_relation"]["metric_semantics"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="clearance deficit"):
        validate_manifest(manifest_path)
