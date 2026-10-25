# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression tests for MakeHuman-derived arm fitting and pose inputs."""

import json
import tempfile
from pathlib import Path

import pytest

from freecad_cloth.avatar.HumanoidMesh import (
    _arm_pose_weight,
    load_makehuman_arm_weights,
)
from tests.support.assertions import require


def test_geometric_fallback_covers_lower_arm_envelope_without_source_weights() -> None:
    """Keep both arm envelopes controllable when source weights are absent."""
    height = 1750.0
    require(
        condition=_arm_pose_weight(260.0, height * 0.50, 170.0, height) == pytest.approx(1.0)
        and _arm_pose_weight(-260.0, height * 0.50, -170.0, height) == pytest.approx(1.0),
        message="the geometric fallback must cover both arm envelopes.",
    )


def test_source_weight_is_authoritative_for_arm_influence() -> None:
    """Honor authored arm weights rather than inferring extra influence."""
    height = 1750.0
    require(
        condition=_arm_pose_weight(260.0, height * 0.72, 170.0, height, 0.0)
        == pytest.approx(0.0),
        message="zero source weight must suppress geometric fallback.",
    )
    require(
        condition=(
            _arm_pose_weight(10.0, height * 0.50, 170.0, height, 1.0)
            == pytest.approx(1.0)
            and _arm_pose_weight(10.0, height * 0.50, 170.0, height, 0.35)
            == pytest.approx(0.35)
        ),
        message="source weights must retain their authoritative influence.",
    )


def test_makehuman_arm_weights_sum_only_arm_chain_bones() -> None:
    """Accumulate only named arm-chain weights for each side."""
    payload = {
        "weights": {
            "upperarm01.L": [[1, 0.25]],
            "lowerarm01.L": [[1, 0.50]],
            "wrist.L": [[1, 0.20]],
            "finger2-1.L": [[1, 0.10]],
            "shoulder.L": [[1, 0.90]],
            "spine03": [[1, 1.0]],
            "upperarm01.R": [[2, 0.60]],
        }
    }
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "weights.mhw"
        path.write_text(json.dumps(payload), encoding="utf-8")
        left, right = load_makehuman_arm_weights(4, str(path))

    require(
        condition=left[1] == pytest.approx(1.0) and right[2] == pytest.approx(0.60),
        message="only left and right arm-chain weights should be accumulated.",
    )
    require(
        condition=left[0] == pytest.approx(0.0) and right[1] == pytest.approx(0.0),
        message="vertices outside authored arm chains must not gain influence.",
    )
