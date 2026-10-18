# Copyright (C) 2026 FreeCAD Cloth contributors
"""Independently validate realtime-preview performance metrics produced by FreeCAD CI."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import cast

TARGET_FPS = 30.0
FRAME_BUDGET_MS = 1000.0 / TARGET_FPS
MIN_FRAMES = 120
MIN_WARMUP_FRAMES = 30


def _number(value: object) -> float | None:
    """Return a finite real number; reject booleans and malformed metrics.

    Args:
        value: Candidate metric value to validate.

    Returns:
        Finite numeric value, or None when the value is invalid.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _integer(value: object) -> int | None:
    """Return an integer metric without accepting booleans or truncated floats.

    Args:
        value: Candidate metric value to validate.

    Returns:
        Integer value, or None when the value is not an integer.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def validate_metrics(payload: object) -> list[str]:
    """Return all acceptance failures found in a realtime metric artifact.

    Args:
        payload: Decoded JSON value from the saved metrics artifact.

    Returns:
        Human-readable errors for each unmet metric requirement.
    """
    if not isinstance(payload, dict):
        return ["metrics artifact must contain a JSON object"]
    metrics = cast("dict[str, object]", payload)
    errors: list[str] = []

    if _integer(metrics.get("schema_version")) != 1:
        errors.append("schema_version must be 1")
    if metrics.get("backend") != "position-based-dynamics":
        errors.append("backend must be position-based-dynamics")

    if metrics.get("fixture") != "two-panel-tunic-pattern":
        errors.append("fixture must be two-panel-tunic-pattern")
    particles = _integer(metrics.get("particles"))
    if particles is None or particles < 100:
        errors.append("particles must be an integer >= 100 for garment-scale coverage")
    if _integer(metrics.get("panel_count")) != 2:
        errors.append("panel_count must be 2")
    collision_triangles = _integer(metrics.get("collision_triangles"))
    if collision_triangles is None or collision_triangles < 1:
        errors.append("collision_triangles must be a positive integer")

    frames = _integer(metrics.get("frames_requested"))
    warmup = _integer(metrics.get("warmup_frames_requested"))
    intervals = _integer(metrics.get("measured_intervals"))
    observed_ticks = _integer(metrics.get("observed_ticks"))
    expected_ticks = _integer(metrics.get("expected_ticks"))
    frames_advanced = _integer(metrics.get("frames_advanced"))

    if frames is None or frames < MIN_FRAMES:
        errors.append(f"frames_requested must be an integer >= {MIN_FRAMES}")
    if warmup is None or warmup < MIN_WARMUP_FRAMES:
        errors.append(f"warmup_frames_requested must be an integer >= {MIN_WARMUP_FRAMES}")
    if frames is not None and intervals != frames:
        errors.append("measured_intervals must equal frames_requested")
    if frames is not None and warmup is not None:
        exact_ticks = frames + warmup
        if expected_ticks != exact_ticks:
            errors.append("expected_ticks must equal warm-up ticks plus measured intervals")
        if observed_ticks != exact_ticks:
            errors.append("observed_ticks must equal warm-up ticks plus measured intervals")
        if frames_advanced != exact_ticks:
            errors.append("frames_advanced must equal observed timer ticks")

    if metrics.get("timed_out") is not False:
        errors.append("timed_out must be false")
    if metrics.get("backend_finite") is not True:
        errors.append("backend_finite must be true")
    if metrics.get("published_state_finite") is not True:
        errors.append("published_state_finite must be true")

    budget = _number(metrics.get("frame_budget_ms"))
    if budget is None or abs(budget - FRAME_BUDGET_MS) > 1e-6:
        errors.append("frame_budget_ms must match the 30 FPS budget")

    numeric_keys = (
        "mean_frame_interval_ms",
        "p95_frame_interval_ms",
        "mean_callback_ms",
        "p95_callback_ms",
    )
    for key in numeric_keys:
        value = _number(metrics.get(key))
        if value is None or value < 0.0:
            errors.append(f"{key} must be a finite non-negative number")

    mean_interval = _number(metrics.get("mean_frame_interval_ms"))
    p95_interval = _number(metrics.get("p95_frame_interval_ms"))
    if mean_interval is not None and mean_interval > FRAME_BUDGET_MS:
        errors.append("mean_frame_interval_ms exceeds the 30 FPS budget")
    if p95_interval is not None and p95_interval > FRAME_BUDGET_MS:
        errors.append("p95_frame_interval_ms exceeds the 30 FPS budget")

    stage_value = metrics.get("stage_timings")
    required_stages = (
        "advance_preview_frame",
        "solver_step",
        "state_publish",
        "mesh_write",
        "overlay_schedule",
        "viewport_redraw",
    )
    if not isinstance(stage_value, dict):
        errors.append("stage_timings must be a JSON object")
    else:
        stages = cast("dict[str, object]", stage_value)
        for name in required_stages:
            stage_value_for_name = stages.get(name)
            if not isinstance(stage_value_for_name, dict):
                errors.append(f"stage_timings.{name} must be a JSON object")
                continue
            stage = cast("dict[str, object]", stage_value_for_name)
            samples = _integer(stage.get("samples"))
            if frames is None:
                minimum_samples = MIN_FRAMES
            elif name == "overlay_schedule":
                minimum_samples = max(1, frames // 2 - 2)
            elif name == "mesh_write":
                minimum_samples = frames * 2
            else:
                minimum_samples = frames
            if samples is None or samples < minimum_samples:
                errors.append(f"stage_timings.{name}.samples must be >= {minimum_samples}")
            for metric_name in ("mean_ms", "p95_ms", "max_ms"):
                value = _number(stage.get(metric_name))
                if value is None or value < 0.0:
                    errors.append(
                        f"stage_timings.{name}.{metric_name} must be a finite non-negative number"
                    )

    profile_value = metrics.get("profile")
    if not isinstance(profile_value, dict):
        errors.append("profile must be a JSON object")
    else:
        profile = cast("dict[str, object]", profile_value)
        if profile.get("quality_preset") != "Fast":
            errors.append("profile.quality_preset must be Fast")
        spacing = _number(profile.get("particle_distance_mm"))
        if spacing is None or spacing < 40.0:
            errors.append("profile.particle_distance_mm must be >= 40")
        errors.extend(
            f"profile.{key} must be 1"
            for key in ("solver_iterations", "solver_substeps", "pbd_substeps")
            if _integer(profile.get(key)) != 1
        )

    runtime_value = metrics.get("runtime")
    if not isinstance(runtime_value, dict):
        errors.append("runtime must be a JSON object")
    else:
        runtime = cast("dict[str, object]", runtime_value)
        for key in ("platform", "python_version", "freecad_version"):
            value = runtime.get(key)
            if not isinstance(value, str) or not value:
                errors.append(f"runtime.{key} must be a non-empty string")
        cpu_count = _integer(runtime.get("cpu_count"))
        if cpu_count is None or cpu_count < 1:
            errors.append("runtime.cpu_count must be a positive integer")

    return errors


def main() -> int:
    """Read and independently validate a saved realtime metric artifact.

    Raises:
        SystemExit: Raised when the metrics file cannot be read or decoded.

    Returns:
        Process status indicating whether the realtime metrics are acceptable.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metrics", type=Path, help="path to metrics.json produced by FreeCAD")
    args = parser.parse_args()
    try:
        payload = json.loads(args.metrics.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        msg = f"realtime-benchmark=failed reason=unreadable-metrics error={exc}"
        raise SystemExit(
            msg
        ) from exc

    errors = validate_metrics(payload)
    if errors:
        for error in errors:
            print(f"realtime-benchmark=failed reason={error}", flush=True)
        return 1

    metrics = cast("dict[str, object]", payload)
    mean_interval = _number(metrics.get("mean_frame_interval_ms"))
    p95_interval = _number(metrics.get("p95_frame_interval_ms"))
    if mean_interval is None or p95_interval is None:
        return 1
    print(
        "realtime-benchmark=passed "
        f"frames={metrics['measured_intervals']} "
        f"mean_ms={mean_interval:.3f} "
        f"p95_ms={p95_interval:.3f} "
        f"budget_ms={FRAME_BUDGET_MS:.3f}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
