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
    """Write a shaped two-panel shirt and four-panel skirt/waistband artifact."""
    (root / "layered-outfit.FCStd").write_bytes(b"native-freecad-document-fixture")
    image_records = []
    image_inventory = (
        ("step-000-axonometric.png", "initial shaped layered outfit"),
        ("step-005-axonometric.png", "layered outfit motion at step 5"),
        ("step-015-axonometric.png", "layered outfit motion at step 15"),
        *(
            ("final-six-view/step-060-%s.png" % side, side)
            for side in ("front", "rear", "right", "left", "top", "bottom")
        ),
        *(
            ("final-group-view/step-015-shirt-only-%s.png" % side, "shirt-only-" + side)
            for side in ("front", "rear", "right")
        ),
        *(
            ("final-group-view/step-015-skirt-only-%s.png" % side, "skirt-only-" + side)
            for side in ("front", "rear", "right")
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

    piece_ids = ["piece-%02d" % index for index in range(10)]
    panel_names = (
        "Shirt Front",
        "Shirt Back",
        "Skirt Front",
        "Skirt Right",
        "Skirt Back",
        "Skirt Left",
        "Waistband Front",
        "Waistband Right",
        "Waistband Back",
        "Waistband Left",
    )
    assignments = [
        ("shirt" if index < 2 else "skirt") + "|" + piece_id
        for index, piece_id in enumerate(piece_ids)
    ]
    seam_edge_links = (
        (0, 1, 1, 1),
        (0, 3, 1, 3),
        (0, 5, 1, 5),
        (0, 7, 1, 7),
        *((2 + index, 1, 2 + (index + 1) % 4, 3) for index in range(4)),
        *((6 + index, 1, 6 + (index + 1) % 4, 3) for index in range(4)),
        *((2 + index, 2, 6 + index, 0) for index in range(4)),
    )
    seams = []
    for index, (piece_a_index, edge_a, piece_b_index, edge_b) in enumerate(seam_edge_links):
        piece_a_id = piece_ids[piece_a_index]
        piece_b_id = piece_ids[piece_b_index]
        seams.append(
            {
                "seam_id": "seam-%02d" % index,
                "piece_a_id": piece_a_id,
                "piece_b_id": piece_b_id,
                "edge_a_id": piece_a_id + ":e%d" % edge_a,
                "edge_b_id": piece_b_id + ":e%d" % edge_b,
                "start_a": 0.0,
                "end_a": 1.0,
                "start_b": 0.0,
                "end_b": 1.0,
                "reversed_b": index >= 4,
                "alignment": "uniform",
                "stitch_group": "garment-assembly",
                "kind": "plain",
                "status": "Valid",
                "stitch_pair_count": 8,
                "maximum_gap_mm": 0.2,
                "mean_gap_mm": 0.1,
            }
        )
    panel_motion = [
        {
            "panel_name": "DrapePanel%d" % index,
            "piece_id": piece_ids[index],
            "piece_name": panel_names[index],
            "garment_group": "shirt" if index < 2 else "skirt",
            "role": "shirt" if index < 2 else "skirt_body" if index < 6 else "waistband",
            "particle_count": 50,
            "maximum_displacement_mm": 2.0,
            "mean_displacement_mm": 1.5,
            "rms_displacement_mm": 1.6,
            "moved_particle_count_1mm": 20,
            "moved_particle_count_5mm": 0,
        }
        for index in range(10)
    ]
    checkpoints = [
        {
            "step": step,
            "elapsed_ms": 100.0,
            "finite": True,
            "contact_count": 0 if step == 60 else 24,
            "corrected_particle_count": 0 if step == 60 else 32,
            "contact_observed_so_far": True,
            "support_pin_count": 20,
            "shirt_support_pin_count": 2,
            "shirt_shoulder_support_pin_count": 4,
            "shirt_hem_support_pin_count": 10,
            "waistband_support_pin_count": 4,
            "maximum_support_pin_drift_mm": 0.0,
            "maximum_shirt_support_pin_drift_mm": 0.0,
            "maximum_shirt_shoulder_support_pin_drift_mm": 0.0,
            "maximum_shirt_hem_support_pin_drift_mm": 0.0,
            "maximum_waistband_support_pin_drift_mm": 0.0,
            "remaining_contact_count": 0,
            "max_penetration_before_mm": 1.0,
            "residual_penetration_mm": 0.0,
            "max_seam_gap_mm": 0.2,
            "shirt_fit": {
                "top_drop_mm": 0.0,
                "hem_drift_mm": 0.0,
                "bounds_min_mm": [-100.0, -100.0, 980.0],
                "bounds_max_mm": [100.0, 100.0, 1340.0],
                "vertical_span_mm": 360.0,
                "vertical_span_ratio": 0.9,
                "top_above_shoulder_mm": -7.5,
                "bottom_above_hip_mm": 60.0,
                "particle_count": 1426,
            },
            "panel_motion": panel_motion,
            "body": {
                "inside_particle_count": 0,
                "minimum_unsigned_clearance_mm": 18.0,
            },
            "seams": seams,
            "images": [],
        }
        for step in (5, 15, 60)
    ]
    pieces_scene = []
    for index, piece_id in enumerate(piece_ids):
        group_id = "shirt" if index < 2 else "skirt"
        world_min_z, world_max_z = (
            (110.0, 250.0) if index < 2 else (0.0, 10.0) if index < 6 else (10.0, 110.0)
        )
        edge_count = 8 if group_id == "shirt" else 4
        semantic_ids = [piece_id + ":e%d" % edge for edge in range(edge_count)]
        boundaries = [
            {
                "id": semantic_ids[edge],
                "kind": "arc" if group_id == "shirt" and edge in (2, 4, 6) else "line",
                "length_mm": 100.0,
                "samples_local_mm": [[0.0, 0.0, 0.0], [100.0, 0.0, 0.0]],
            }
            for edge in range(edge_count)
        ]
        pieces_scene.append(
            {
                "piece_id": piece_id,
                "name": panel_names[index],
                "garment_group": group_id,
                "solver_panel_id": "DrapePanel%d" % index,
                "local_to_world": {
                    "translation_mm": [float(index), 0.0, world_min_z],
                    "rotation_quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
                },
                "grainline_angle_deg": 0.0,
                "seam_allowance_mm": 10.0,
                "semantic_edge_ids": semantic_ids,
                "boundaries": boundaries,
                "local_bounds_mm": {
                    "min": [0.0, 0.0, 0.0],
                    "max": [100.0, 100.0, world_max_z - world_min_z],
                },
                "world_bounds_mm": {
                    "min": [float(index), 0.0, world_min_z],
                    "max": [float(index) + 100.0, 100.0, world_max_z],
                },
                "solver_mesh": {"particle_count": 50, "triangle_count": 80},
            }
        )
    underarm_endpoints = [
        {
            "panel": panel,
            "arm_side": side,
            "world_mm": [x, y, 130.0],
            "nearest_mannequin_point_mm": [x, y - 14.0, 130.0],
            "nearest_surface_distance_mm": 14.0,
            "drop_below_shoulder_mm": 20.0,
        }
        for panel, y in (("front", -90.0), ("back", 90.0))
        for side, x in (("left", -170.0), ("right", 170.0))
    ]
    scene_map = {
        "coordinate_system": {
            "units": "mm",
            "origin": "FreeCAD document world origin",
            "x_axis": "mannequin left-right",
            "y_axis": "front-back",
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
            {"id": "shirt", "piece_ids": piece_ids[:2], "independent_of": ["skirt"]},
            {"id": "skirt", "piece_ids": piece_ids[2:], "independent_of": ["shirt"]},
        ],
        "body_clearance_by_group_mm": {"shirt": 14.0, "skirt": 6.0},
        "shirt_armhole_endpoints": underarm_endpoints,
        "garment_group_colors": {
            "shirt": [0.10, 0.34, 0.78],
            "skirt": [0.88, 0.34, 0.08],
        },
        "vertical_layer_interfaces": {
            "skirt_top_z_mm": 10.0,
            "waistband_bottom_z_mm": 10.0,
            "waistband_top_z_mm": 110.0,
            "shirt_hem_z_mm": 110.0,
            "shirt_hem_front_gap_mm": 8.0,
            "shirt_hem_back_gap_mm": 8.0,
        },
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
            "metric_semantics": (
                "positive residual value is the requested clearance deficit "
                "(requested gap minus closest sampled edge/triangle distance), "
                "not signed volumetric intersection depth"
            ),
        },
    }
    manifest = {
        "schema": "freecad-cloth.layered-outfit",
        "schema_version": 4,
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
            "piece_count": 10,
            "seam_count": 16,
            "garment_group_count": 2,
            "piece_ids": piece_ids,
            "garment_groups": assignments,
            "inter_cloth_clearance_mm": 8.0,
            "body_clearance_by_group_mm": {"shirt": 14.0, "skirt": 6.0},
            "shirt_armhole_endpoints": underarm_endpoints,
            "garment_group_colors": {
                "shirt": [0.10, 0.34, 0.78],
                "skirt": [0.88, 0.34, 0.08],
            },
            "vertical_layer_interfaces": {
                "skirt_top_z_mm": 10.0,
                "waistband_bottom_z_mm": 10.0,
                "waistband_top_z_mm": 110.0,
                "shirt_hem_z_mm": 110.0,
                "shirt_hem_front_gap_mm": 8.0,
                "shirt_hem_back_gap_mm": 8.0,
            },
            "particle_distance_mm": 24.0,
            "support_pins": {
                "mode": "Explicit",
                "particle_indices": [0, 1],
                "count": 2,
            },
            "shirt_supports": [
                {
                    "panel_id": "shirt-torso-" + side,
                    "anchor_role": "torso-centerline-stabilizer",
                    "particle_index": index,
                    "target_mm": [float(index), 0.0, 150.0],
                    "position_mm": [float(index), 0.0, 150.0],
                    "target_deviation_mm": 0.0,
                    "centerline_x_mm": 0.0,
                    "centerline_offset_mm": float(index),
                    "target_height_z_mm": 150.0,
                    "height_offset_mm": 0.0,
                    "design_target_mm": [0.0, 0.0, 150.0],
                    "design_target_deviation_mm": float(index),
                    "clearance_mm": 25.0,
                }
                for index, side in enumerate(("right", "left"))
            ],
            "shirt_hem_support_pins": {
                "mode": "Explicit",
                "particle_indices": list(range(6, 16)),
                "count": 10,
            },
            "shirt_shoulder_support_pins": {
                "mode": "Explicit",
                "particle_indices": list(range(2, 6)),
                "count": 4,
            },
            "shirt_shoulder_supports": [
                {
                    "panel_id": panel_id,
                    "anchor_role": "shoulder-side-stabilizer",
                    "support_id": panel_id,
                    "particle_index": particle_index,
                    "target_mm": [x, y, 135.0],
                    "position_mm": [x, y, 135.0],
                    "target_deviation_mm": 0.0,
                    "clearance_mm": 25.0,
                }
                for particle_index, panel_id, x, y in (
                    (2, "shirt-front-left-shoulder", -80.0, -95.0),
                    (3, "shirt-front-right-shoulder", 80.0, -95.0),
                    (4, "shirt-back-left-shoulder", -80.0, 95.0),
                    (5, "shirt-back-right-shoulder", 80.0, 95.0),
                )
            ],
            "shirt_hem_supports": [
                {
                    "panel_id": "shirt-hem-" + side,
                    "anchor_role": "tucked-hem-stabilizer",
                    "support_id": "shirt-hem-" + side + "-" + str(ordinal),
                    "particle_index": particle_index,
                    "target_mm": [float(particle_index), 0.0, 110.0],
                    "position_mm": [float(particle_index), 0.0, 110.0],
                    "target_deviation_mm": 0.0,
                    "clearance_mm": 20.0,
                }
                for side, start in (("front", 6), ("back", 11))
                for ordinal, particle_index in enumerate(range(start, start + 5))
            ],
            "waistband_support_pins": {
                "mode": "Explicit",
                "particle_indices": list(range(16, 20)),
                "count": 4,
            },
            "waistband_supports": [
                {
                    "panel_id": "waistband-" + side,
                    "particle_index": index + 16,
                    "target_mm": [float(index), 0.0, 100.0],
                    "position_mm": [float(index), 25.0, 100.0],
                    "clearance_mm": 25.0,
                }
                for index, side in enumerate(("front", "right", "back", "left"))
            ],
        },
        "scene_map": scene_map,
        "checkpoints": checkpoints,
        "images": image_records,
        "persistence": {
            "fcstd": "layered-outfit.FCStd",
            "piece_links_preserved": True,
            "garment_groups_preserved": True,
            "body_clearance_by_group_preserved": True,
            "contact_rebuilt_after_reload": True,
            "support_pins_preserved": True,
            "shirt_supports_preserved_after_reload": True,
            "shirt_shoulder_supports_preserved_after_reload": True,
            "shirt_hem_supports_preserved_after_reload": True,
            "waistband_support_pins_preserved": True,
            "saved_step_count": 60,
            "restored_step_count": 60,
            "post_reload_step_count": 1,
            "native_backend_rebuilt": True,
            "transient_solver_state_reinitialized": True,
        },
    }
    path = root / "layered-outfit-manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_validator_rejects_missing_shirt_hem_anchors(tmp_path: Path) -> None:
    """Ten native hem anchors are required independently of torso/shoulder anchors."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["outfit"]["shirt_hem_supports"] = []
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="ten distributed native hem support records"):
        validate_manifest(manifest_path)

def test_validator_rejects_missing_shirt_shoulder_anchors(tmp_path: Path) -> None:
    """All four shoulder-side panel anchors must be explicitly persisted."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["outfit"]["shirt_shoulder_support_pins"]["particle_indices"] = [2, 3]
    manifest["outfit"]["shirt_shoulder_support_pins"]["count"] = 2
    manifest["outfit"]["shirt_shoulder_supports"] = manifest["outfit"][
        "shirt_shoulder_supports"
    ][:2]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="four unique particle indices"):
        validate_manifest(manifest_path)


def test_validator_rejects_invalid_armhole_world_geometry(tmp_path: Path) -> None:
    """All four underarm endpoints must have finite world-space evidence."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["outfit"]["shirt_armhole_endpoints"][0]["world_mm"][2] = float("nan")
    manifest["scene_map"]["shirt_armhole_endpoints"][0]["world_mm"][2] = float("nan")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="shirt armhole endpoint world position"):
        validate_manifest(manifest_path)

def test_validator_rejects_underarm_surface_distance_mismatch(tmp_path: Path) -> None:
    """The reported nearest-body distance must match the saved world-space points."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for record in (manifest["outfit"], manifest["scene_map"]):
        record["shirt_armhole_endpoints"][0]["nearest_surface_distance_mm"] = 20.0
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="nearest-surface distance disagrees"):
        validate_manifest(manifest_path)

def test_validator_rejects_underarm_shoulder_drop_mismatch(tmp_path: Path) -> None:
    """The reported underarm drop must be derived from saved shoulder and edge positions."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for record in (manifest["outfit"], manifest["scene_map"]):
        record["shirt_armhole_endpoints"][0]["drop_below_shoulder_mm"] = 50.0
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="shoulder-relative drop disagrees"):
        validate_manifest(manifest_path)

def test_validator_rejects_armhole_below_the_underarm_height_band(tmp_path: Path) -> None:
    """An armhole opening must not sit excessively below the mannequin shoulder line."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for record in (manifest["outfit"], manifest["scene_map"]):
        endpoint = record["shirt_armhole_endpoints"][0]
        endpoint["world_mm"][2] = 50.0
        endpoint["nearest_mannequin_point_mm"][2] = 50.0
        endpoint["drop_below_shoulder_mm"] = 100.0
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="expected shoulder/underarm height band"):
        validate_manifest(manifest_path)

def test_validator_rejects_stationary_skirt_panel(tmp_path: Path) -> None:
    """Every skirt body panel must have measurable particle motion at the final checkpoint."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    panel = next(
        record
        for record in manifest["checkpoints"][-1]["panel_motion"]
        if record["role"] == "skirt_body"
    )
    panel["maximum_displacement_mm"] = 0.0
    panel["moved_particle_count_1mm"] = 0
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="skirt panel did not move"):
        validate_manifest(manifest_path)


def test_validator_rejects_missing_group_only_views(tmp_path: Path) -> None:
    """Shirt and skirt renders must be independently visible, not behind the avatar."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["images"] = [
        record for record in manifest["images"] if record["label"] != "skirt-only-front"
    ]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="expected fifteen"):
        validate_manifest(manifest_path)


def test_validator_rejects_shirt_outside_the_shoulder_and_hem_fit_bands(
    tmp_path: Path,
) -> None:
    """The saved shirt must not sit substantially below its shoulder or waist references."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["checkpoints"][-1]["shirt_fit"]["top_drop_mm"] = 26.0
    manifest["checkpoints"][-1]["shirt_fit"]["hem_drift_mm"] = 26.0
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="shirt top falls below"):
        validate_manifest(manifest_path)


def test_validator_accepts_complete_layered_outfit_artifacts(tmp_path: Path) -> None:
    """A full pack must retain early contact activation and zero residual at all checkpoints."""
    manifest = _valid_artifact(tmp_path)

    result = validate_manifest(manifest, expected_commit="a" * 40)

    assert result == {
        "commit_sha": "a" * 40,
        "pieces": 10,
        "seams": 16,
        "garment_groups": 2,
        "scene_map": {
            "landmarks": 3,
            "pieces": 10,
            "seams": 16,
            "camera_views": 6,
            "body_clearance_groups": 2,
        },
        "checkpoints": 3,
        "images": 15,
        "document": "layered-outfit.FCStd",
    }


def test_validator_rejects_shirt_hem_in_the_flared_skirt_body(tmp_path: Path) -> None:
    """The shirt hem must terminate at the waistband top, above the skirt panels."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for record in (manifest["outfit"], manifest["scene_map"]):
        record["vertical_layer_interfaces"]["shirt_hem_z_mm"] = 109.0
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="shirt hem must meet the waistband top"):
        validate_manifest(manifest_path)


def test_multi_garment_shirt_uses_stable_side_lines_and_a_simple_armhole_profile() -> None:
    """Keep shallow sides linear and the shortened shirt's armscyes outside its contour."""
    source_path = (
        Path(__file__).resolve().parents[1] / "tests" / "freecad_layered_garment_acceptance.py"
    )
    source = source_path.read_text(encoding="utf-8")
    panel = source.split("def _make_tunic_piece(", 1)[1].split("\ndef _make_ring(", 1)[0]
    assert "if index == 2:" in panel
    assert "if index == 4:" in panel
    assert "if index == 6:" in panel
    assert "0.84 * panel_width, armhole_mid_z" in panel
    assert "0.16 * panel_width, armhole_mid_z" in panel
    assert "for index in (1, 7)" in panel
    assert 'type(geometry[index]).__name__.lower() != "linesegment"' in panel
    assert "shirt side seams must remain stable native Sketcher lines" in panel
    assert "panel.ViewObject.PointColor" not in source
    assert "0.741 * panel_width" not in panel
    assert "0.259 * panel_width" not in panel
    assert "armhole_z = 0.80 * garment_height" in panel
    assert "armhole_z = 0.62 * garment_height" not in panel
    assert "SHIRT_SUPPORT_TARGET_BELOW_SHOULDER_MM = 30.0" in source
    assert "shirt_support_target_z = shoulder_z - SHIRT_SUPPORT_TARGET_BELOW_SHOULDER_MM" in source
    assert "shirt_panel_width = max(420.0, shoulder_width + 40.0)" in source
    assert "shirt_hem_width = max(480.0, shirt_panel_width + 10.0)" in source
    assert "CHECKPOINTS = (0, 5, 15, 60)" in source
    assert "SHIRT_HEM_SUPPORTS_PER_PANEL = 5" in source
    assert "samples_per_chain=SHIRT_HEM_SUPPORTS_PER_PANEL" in source
    assert "SHIRT_SHOULDER_SUPPORT_ANCHOR_ROLE" in source
    assert 'evaluator = getattr(curve, "valueAt", None)' in source
    assert 'evaluator = getattr(curve, "value", None)' in source


def test_validator_rejects_vertical_layer_scene_map_mismatch(tmp_path: Path) -> None:
    """Persisted outfit profile and the independent scene map must agree."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["scene_map"]["vertical_layer_interfaces"]["shirt_hem_front_gap_mm"] = 9.0
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="vertical layer interfaces disagree"):
        validate_manifest(manifest_path)


def test_validator_rejects_inner_skirt_standoff_too_close_to_outer_shirt(
    tmp_path: Path,
) -> None:
    """Body-shell layers must remain separated by at least the requested 8 mm."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["outfit"]["body_clearance_by_group_mm"]["shirt"] = 13.0
    manifest["scene_map"]["body_clearance_by_group_mm"]["shirt"] = 13.0
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="outer shirt body clearance"):
        validate_manifest(manifest_path)


def test_validator_rejects_scene_map_body_standoff_mismatch(tmp_path: Path) -> None:
    """Scene geometry provenance must match the saved outfit standoff configuration."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["scene_map"]["body_clearance_by_group_mm"]["skirt"] = 5.0
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="scene map body clearances disagree"):
        validate_manifest(manifest_path)


def test_validator_rejects_missing_body_standoff_persistence(tmp_path: Path) -> None:
    """The per-garment shell settings must survive a native FCStd save/reload."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["persistence"]["body_clearance_by_group_preserved"] = False
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="body standoffs were not verified after reload"):
        validate_manifest(manifest_path)


def test_validator_rejects_missing_shirt_torso_supports(tmp_path: Path) -> None:
    """The shaped shirt must retain two bounded front/back torso-centerline stabilizers."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["outfit"]["support_pins"]["particle_indices"] = []
    manifest["outfit"]["support_pins"]["count"] = 0
    manifest["outfit"]["shirt_supports"] = []
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="two unique particle indices"):
        validate_manifest(manifest_path)


def test_validator_rejects_airborne_shirt_torso_support(tmp_path: Path) -> None:
    """A torso-centerline stabilizer far from the mannequin must invalidate the artifact."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["outfit"]["shirt_supports"][0]["clearance_mm"] = 90.0
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="shirt support stand-off is outside"):
        validate_manifest(manifest_path)


def test_validator_rejects_shirt_support_detached_from_authored_target(tmp_path: Path) -> None:
    """The chosen support particle must remain at its persisted PatternIR mesh target."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["outfit"]["shirt_supports"][0]["position_mm"][0] += 20.0
    manifest["outfit"]["shirt_supports"][0]["target_deviation_mm"] = 20.0
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="persisted PatternIR mesh target"):
        validate_manifest(manifest_path)


def test_validator_rejects_shirt_torso_support_outside_centerline_band(tmp_path: Path) -> None:
    """A torso-centerline stabilizer must stay inside its authored panel support band."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    support = manifest["outfit"]["shirt_supports"][0]
    support["position_mm"][0] += 100.0
    support["target_mm"][0] += 100.0
    support["centerline_offset_mm"] = 100.0
    support["design_target_deviation_mm"] = 100.0
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="outside the allowed centerline band"):
        validate_manifest(manifest_path)


def test_validator_rejects_shirt_torso_support_outside_height_band(tmp_path: Path) -> None:
    """A torso-centerline stabilizer must stay within its authored hip-relative height band."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    support = manifest["outfit"]["shirt_supports"][0]
    support["position_mm"][2] += 50.0
    support["target_mm"][2] += 50.0
    support["height_offset_mm"] = 50.0
    support["design_target_deviation_mm"] = 50.0
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="outside the allowed height band"):
        validate_manifest(manifest_path)


def test_validator_rejects_missing_waistband_support_pins(tmp_path: Path) -> None:
    """The waistband must retain four local support pins around the waist."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["outfit"]["waistband_support_pins"]["particle_indices"] = []
    manifest["outfit"]["waistband_support_pins"]["count"] = 0
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="four unique particle indices"):
        validate_manifest(manifest_path)


def test_validator_rejects_airborne_waistband_support(tmp_path: Path) -> None:
    """A waistband pin far from its anatomical target must invalidate the artifact."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["outfit"]["waistband_supports"][0]["clearance_mm"] = 120.0
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="stand-off is outside the anatomical support range"):
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
    manifest["checkpoints"][1]["maximum_shirt_support_pin_drift_mm"] = 0.01
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


def test_validator_rejects_changed_saved_step_counter_after_reload(tmp_path: Path) -> None:
    """The persisted checkpoint counter must survive reopening the native document."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["persistence"]["restored_step_count"] = 59
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="saved solver step counter was not preserved"):
        validate_manifest(manifest_path)


def test_validator_rejects_missing_native_solver_rebuild_evidence(tmp_path: Path) -> None:
    """A reopened document must rebuild transient native solver state."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["persistence"]["native_backend_rebuilt"] = False
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="native solver state was not rebuilt"):
        validate_manifest(manifest_path)


def test_validator_rejects_duplicate_semantic_edge_ids(tmp_path: Path) -> None:
    """Every source panel boundary must map to a distinct persistent edge ID."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    panel = manifest["scene_map"]["pieces"][0]
    panel["semantic_edge_ids"][-1] = panel["semantic_edge_ids"][0]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="panel semantic edge IDs are duplicated"):
        validate_manifest(manifest_path)


def test_validator_allows_transient_shirt_seam_gap_during_settling(tmp_path: Path) -> None:
    """Initial side-seam convergence is diagnostic; final garment seams must close."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["checkpoints"][0]["max_seam_gap_mm"] = 84.8
    manifest["checkpoints"][1]["max_seam_gap_mm"] = 42.0
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = validate_manifest(manifest_path)

    assert result["checkpoints"] == 3


def test_validator_rejects_unclosed_final_shirt_seam(tmp_path: Path) -> None:
    """The final saved garment cannot pass with an open side or shoulder seam."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["checkpoints"][-1]["max_seam_gap_mm"] = 12.01
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="sewn panel gap exceeds 12.000 mm"):
        validate_manifest(manifest_path)


def test_validator_rejects_excessive_transient_shirt_seam_gap(tmp_path: Path) -> None:
    """Transient side-seam mismatch is bounded instead of silently ignored."""
    manifest_path = _valid_artifact(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["checkpoints"][0]["max_seam_gap_mm"] = 100.01
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="sewn panel gap exceeds 100.000 mm"):
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
    manifest["outfit"]["garment_groups"][2] = manifest["outfit"]["garment_groups"][0].replace(
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
    seam["piece_b_id"] = "piece-02"
    seam["edge_b_id"] = "piece-02:e3"
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
