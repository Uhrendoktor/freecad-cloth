# Copyright (C) 2026 FreeCAD Cloth contributors
"""Contracts for aligned per-frame realtime preview timing evidence."""

from freecad_cloth.common.JsonTypes import JsonObject
from tools.ci.validate_realtime_benchmark import _validate_frame_timing_trace


def _frame_row() -> JsonObject:
    """Return one valid measured frame with mutually aligned monotonic timestamps."""
    return {
        "frame_index": 1,
        "tick_index": 31,
        "callback_start_offset_ms": 20.0,
        "previous_callback_start_offset_ms": 3.0,
        "scheduled_deadline_offset_ms": 19.0,
        "worker_emit_offset_ms": 14.0,
        "gui_dispatch_offset_ms": 18.0,
        "interval_ms": 17.0,
        "queue_delay_ms": 6.0,
        "gui_event_dispatch_delay_ms": 4.0,
        "gui_callback_after_dispatch_ms": 2.0,
        "deadline_lateness_ms": 1.0,
        "worker_wakeup_lateness_ms": 0.5,
        "worker_schedule_debt_ms": 0.0,
        "worker_missed_deadlines": 0,
        "worker_coalesced_pulses": 0,
        "worker_signals_emitted": 31,
        "worker_pulse_pending": 1,
        "callback_duration_ms": 7.0,
        "stage_timings_ms": {"advance_preview_frame": 6.0, "state_publish": 2.0},
    }


def test_frame_trace_validator_accepts_aligned_samples() -> None:
    """Accept one-to-one frame rows whose timestamp differences reconcile."""
    metrics: JsonObject = {
        "warmup_frames_requested": 30,
        "frame_timing_samples": [_frame_row()],
    }
    errors: list[str] = []
    _validate_frame_timing_trace(metrics, 1, errors)
    assert errors == []


def test_frame_trace_validator_rejects_misaligned_intervals() -> None:
    """Reject trace rows whose recorded interval differs from callback timestamps."""
    row = _frame_row()
    row["interval_ms"] = 16.0
    metrics: JsonObject = {
        "warmup_frames_requested": 30,
        "frame_timing_samples": [row],
    }
    errors: list[str] = []
    _validate_frame_timing_trace(metrics, 1, errors)
    assert any("interval_ms is not aligned" in error for error in errors)
