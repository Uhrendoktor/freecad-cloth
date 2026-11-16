# Copyright (C) 2026 FreeCAD Cloth contributors
"""Independently validate realtime-preview performance metrics produced by FreeCAD CI."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import cast

if __package__:
    from tools.ci.repository_paths import add_repository_root
else:
    from repository_paths import add_repository_root

ROOT = add_repository_root(__file__)

from freecad_cloth.common.JsonTypes import JsonObject, JsonValue

TARGET_FPS = 60.0
FRAME_BUDGET_MS = 1000.0 / TARGET_FPS
MIN_FRAMES = 120
MIN_WARMUP_FRAMES = 30
MIN_PARTICLES = 100
EXPECTED_PANEL_COUNT = 2
MIN_COLLISION_TRIANGLES = 1
FRAME_BUDGET_TOLERANCE_MS = 1e-6
MIN_PARTICLE_DISTANCE_MM = 40.0
FRAME_DISPATCH_SAMPLE_LIMIT = 120


def _number(value: JsonValue) -> float | None:
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


def _integer(value: JsonValue) -> int | None:
    """Return an integer metric without accepting booleans or truncated floats.

    Args:
        value: Candidate metric value to validate.

    Returns:
        Integer value, or None when the value is not an integer.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _validate_artifact_identity(metrics: JsonObject, errors: list[str]) -> None:
    """Check schema identity and the required realtime benchmark fixture.

    Args:
        metrics: Decoded metric fields.
        errors: Mutable list receiving acceptance failures.
    """
    if _integer(metrics.get("schema_version")) != 1:
        errors.append("schema_version must be 1")
    if metrics.get("backend") != "position-based-dynamics":
        errors.append("backend must be position-based-dynamics")
    if metrics.get("fixture") != "two-panel-tunic-pattern":
        errors.append("fixture must be two-panel-tunic-pattern")


def _validate_fixture_size(metrics: JsonObject, errors: list[str]) -> None:
    """Check garment-scale particle and collision-surface counts.

    Args:
        metrics: Decoded metric fields.
        errors: Mutable list receiving acceptance failures.
    """
    particles = _integer(metrics.get("particles"))
    if particles is None or particles < MIN_PARTICLES:
        errors.append(f"particles must be an integer >= {MIN_PARTICLES} for garment-scale coverage")
    if _integer(metrics.get("panel_count")) != EXPECTED_PANEL_COUNT:
        errors.append(f"panel_count must be {EXPECTED_PANEL_COUNT}")
    collision_triangles = _integer(metrics.get("collision_triangles"))
    if collision_triangles is None or collision_triangles < MIN_COLLISION_TRIANGLES:
        errors.append("collision_triangles must be a positive integer")


def _validate_frame_counts(
    metrics: JsonObject,
    errors: list[str],
) -> int | None:
    """Validate requested cadence samples and their matching timer ticks.

    Args:
        metrics: Decoded metric fields.
        errors: Mutable list receiving acceptance failures.

    Returns:
        Parsed number of measured frames, or None when that field is invalid.
    """
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
    return frames


def _validate_finite_state(metrics: JsonObject, errors: list[str]) -> None:
    """Require finite solver and published state and reject timeout artifacts.

    Args:
        metrics: Decoded metric fields.
        errors: Mutable list receiving acceptance failures.
    """
    if metrics.get("timed_out") is not False:
        errors.append("timed_out must be false")
    if metrics.get("backend_finite") is not True:
        errors.append("backend_finite must be true")
    if metrics.get("published_state_finite") is not True:
        errors.append("published_state_finite must be true")


def _validate_timing_metrics(metrics: JsonObject, errors: list[str]) -> None:
    """Check frame-budget and callback timing values without weakening the FPS gate.

    Args:
        metrics: Decoded metric fields.
        errors: Mutable list receiving acceptance failures.
    """
    budget = _number(metrics.get("frame_budget_ms"))
    if budget is None or abs(budget - FRAME_BUDGET_MS) > FRAME_BUDGET_TOLERANCE_MS:
        errors.append("frame_budget_ms must match the 60 FPS budget")

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
        errors.append("mean_frame_interval_ms exceeds the 60 FPS budget")
    if p95_interval is not None and p95_interval > FRAME_BUDGET_MS:
        errors.append("p95_frame_interval_ms exceeds the 60 FPS budget")


def _validate_frame_scheduler(metrics: JsonObject, frames: int | None, errors: list[str]) -> None:
    """Validate the phase-locked worker clock and its single-outstanding-pulse contract.

    Args:
        metrics: Decoded realtime benchmark artifact.
        frames: Parsed measured interval count, or None when invalid.
        errors: Mutable list receiving acceptance failures.
    """
    scheduler_value = metrics.get("frame_scheduler")
    if not isinstance(scheduler_value, dict):
        errors.append("frame_scheduler must be a JSON object")
        return

    scheduler = cast("JsonObject", scheduler_value)
    if scheduler.get("mode") != "threaded-feedback-phase-locked":
        errors.append("frame_scheduler.mode must be threaded-feedback-phase-locked")
    target_fps = _number(scheduler.get("target_fps"))
    if target_fps is None or abs(target_fps - TARGET_FPS) > 1e-9:
        errors.append(f"frame_scheduler.target_fps must equal {TARGET_FPS:g}")
    initial_delay = _number(scheduler.get("initial_queue_delay_ms"))
    if initial_delay is None or abs(initial_delay - 5.0) > 1e-9:
        errors.append("frame_scheduler.initial_queue_delay_ms must equal 5")
    queue_delay = _number(scheduler.get("queue_delay_estimate_ms"))
    if queue_delay is None or queue_delay < 0.0:
        errors.append("frame_scheduler.queue_delay_estimate_ms must be finite and non-negative")

    emitted = _integer(scheduler.get("signals_emitted"))
    if emitted is None or emitted < (frames or MIN_FRAMES):
        errors.append("frame_scheduler.signals_emitted must cover the measured frames")
    for key in ("coalesced_pulses", "missed_deadlines"):
        value = _integer(scheduler.get(key))
        if value is None or value < 0:
            errors.append(f"frame_scheduler.{key} must be a non-negative integer")
    outstanding = _integer(scheduler.get("outstanding_pulses"))
    if outstanding != 0:
        errors.append("frame_scheduler.outstanding_pulses must be zero at benchmark completion")
    dispatch_mode = scheduler.get("dispatch_mode")
    if dispatch_mode != "Qt.QueuedConnection":
        errors.append("frame_scheduler.dispatch_mode must be Qt.QueuedConnection")
    queued_dispatches = _integer(scheduler.get("queued_dispatches"))
    if queued_dispatches is None or queued_dispatches < (frames or MIN_FRAMES):
        errors.append("frame_scheduler.queued_dispatches must cover the measured frames")

    dispatch_value = metrics.get("frame_dispatch_lateness")
    if not isinstance(dispatch_value, dict):
        errors.append("frame_dispatch_lateness must be a JSON object")
        return
    dispatch = cast("JsonObject", dispatch_value)
    samples = _integer(dispatch.get("samples"))
    minimum_samples = min(frames or MIN_FRAMES, FRAME_DISPATCH_SAMPLE_LIMIT)
    if samples is None or samples < minimum_samples:
        errors.append(f"frame_dispatch_lateness.samples must be >= {minimum_samples}")
    for key in ("mean_ms", "p95_ms", "max_ms"):
        value = _number(dispatch.get(key))
        if value is None or value < 0.0:
            errors.append(f"frame_dispatch_lateness.{key} must be finite and non-negative")

    for metric_name in ("worker_wakeup_lateness", "gui_queue_dispatch_lateness"):
        component_value = metrics.get(metric_name)
        if not isinstance(component_value, dict):
            errors.append(f"{metric_name} must be a JSON object")
            continue
        component = cast("JsonObject", component_value)
        component_samples = _integer(component.get("samples"))
        if component_samples is None or component_samples < minimum_samples:
            errors.append(f"{metric_name}.samples must be >= {minimum_samples}")
        for key in ("mean_ms", "p95_ms", "max_ms"):
            value = _number(component.get(key))
            if value is None or value < 0.0:
                errors.append(f"{metric_name}.{key} must be finite and non-negative")


def _validate_stage_timings(
    metrics: JsonObject,
    frames: int | None,
    errors: list[str],
) -> None:
    """Validate sample counts and finite timing values for each required preview stage.

    Args:
        metrics: Decoded metric fields.
        frames: Parsed number of measured frames, or None if malformed.
        errors: Mutable list receiving acceptance failures.
    """
    stage_value = metrics.get("stage_timings")
    publication_mode = metrics.get("publication_mode")
    if publication_mode != "transient-coin3d":
        errors.append("publication_mode must be transient-coin3d")
    required_stages = (
        "advance_preview_frame",
        "solver_step",
        "state_publish",
        "mesh_write",
        "preview_mesh_publish",
        "overlay_schedule",
        "viewport_redraw",
    )
    if not isinstance(stage_value, dict):
        errors.append("stage_timings must be a JSON object")
        return

    stages = cast("JsonObject", stage_value)
    for name in required_stages:
        stage_value_for_name = stages.get(name)
        if not isinstance(stage_value_for_name, dict):
            errors.append(f"stage_timings.{name} must be a JSON object")
            continue
        stage = cast("JsonObject", stage_value_for_name)
        samples = _integer(stage.get("samples"))
        if frames is None:
            minimum_samples = MIN_FRAMES
        elif name == "overlay_schedule":
            minimum_samples = max(1, frames // 2 - 2)
        elif name == "mesh_write":
            minimum_samples = 0
        elif name == "preview_mesh_publish":
            minimum_samples = frames * 2
        else:
            minimum_samples = frames
        if samples is None or samples < minimum_samples:
            errors.append(f"stage_timings.{name}.samples must be >= {minimum_samples}")
        if name == "mesh_write":
            if samples != 0:
                errors.append("stage_timings.mesh_write.samples must equal 0 during preview")
            continue
        for metric_name in ("mean_ms", "p95_ms", "max_ms"):
            value = _number(stage.get(metric_name))
            if value is None or value < 0.0:
                errors.append(
                    f"stage_timings.{name}.{metric_name} must be a finite non-negative number"
                )


def _validate_profile(metrics: JsonObject, errors: list[str]) -> None:
    """Check the quality settings that make benchmark samples comparable.

    Args:
        metrics: Decoded metric fields.
        errors: Mutable list receiving acceptance failures.
    """
    profile_value = metrics.get("profile")
    if not isinstance(profile_value, dict):
        errors.append("profile must be a JSON object")
        return

    profile = cast("JsonObject", profile_value)
    if profile.get("quality_preset") != "Fast":
        errors.append("profile.quality_preset must be Fast")
    spacing = _number(profile.get("particle_distance_mm"))
    if spacing is None or spacing < MIN_PARTICLE_DISTANCE_MM:
        errors.append(f"profile.particle_distance_mm must be >= {MIN_PARTICLE_DISTANCE_MM:g}")
    errors.extend(
        f"profile.{key} must be 1"
        for key in ("solver_iterations", "solver_substeps", "pbd_substeps")
        if _integer(profile.get(key)) != 1
    )


def _validate_runtime(metrics: JsonObject, errors: list[str]) -> None:
    """Require identifying runtime metadata and a valid CPU count.

    Args:
        metrics: Decoded metric fields.
        errors: Mutable list receiving acceptance failures.
    """
    runtime_value = metrics.get("runtime")
    if not isinstance(runtime_value, dict):
        errors.append("runtime must be a JSON object")
        return

    runtime = cast("JsonObject", runtime_value)
    for key in ("platform", "python_version", "freecad_version"):
        value = runtime.get(key)
        if not isinstance(value, str) or not value:
            errors.append(f"runtime.{key} must be a non-empty string")
    cpu_count = _integer(runtime.get("cpu_count"))
    if cpu_count is None or cpu_count < 1:
        errors.append("runtime.cpu_count must be a positive integer")


def validate_metrics(payload: JsonValue) -> list[str]:
    """Return all acceptance failures found in a realtime metric artifact.

    Args:
        payload: Decoded JSON value from the saved metrics artifact.

    Returns:
        Human-readable errors for each unmet metric requirement.
    """
    if not isinstance(payload, dict):
        return ["metrics artifact must contain a JSON object"]
    metrics = cast("JsonObject", payload)
    errors: list[str] = []
    _validate_artifact_identity(metrics, errors)
    _validate_fixture_size(metrics, errors)
    frames = _validate_frame_counts(metrics, errors)
    _validate_finite_state(metrics, errors)
    _validate_timing_metrics(metrics, errors)
    _validate_frame_scheduler(metrics, frames, errors)
    _validate_stage_timings(metrics, frames, errors)
    _validate_profile(metrics, errors)
    _validate_runtime(metrics, errors)
    return errors


def main() -> int:
    """Read and independently validate a saved realtime metric artifact.

    Returns:
        Process status indicating whether the realtime metrics are acceptable.

    Raises:
        SystemExit: Raised when the metrics file cannot be read or decoded.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metrics", type=Path, help="path to metrics.json produced by FreeCAD")
    args = parser.parse_args()
    try:
        payload = json.loads(args.metrics.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        msg = f"realtime-benchmark=failed reason=unreadable-metrics error={exc}"
        raise SystemExit(msg) from exc

    errors = validate_metrics(payload)
    if errors:
        for error in errors:
            sys.stdout.write(f"realtime-benchmark=failed reason={error}\n")
        sys.stdout.flush()
        return 1

    metrics = cast("JsonObject", payload)
    mean_interval = _number(metrics.get("mean_frame_interval_ms"))
    p95_interval = _number(metrics.get("p95_frame_interval_ms"))
    if mean_interval is None or p95_interval is None:
        return 1
    sys.stdout.write(
        "realtime-benchmark=passed "
        f"frames={metrics['measured_intervals']} "
        f"mean_ms={mean_interval:.3f} "
        f"p95_ms={p95_interval:.3f} "
        f"budget_ms={FRAME_BUDGET_MS:.3f}\n"
    )
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
