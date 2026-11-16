# Copyright (C) 2026 FreeCAD Cloth contributors
"""Contracts for the feedback-paced realtime preview frame clock."""

from math import inf, isclose, nan

from freecad_cloth.simulation.RealtimePreview import _FrameClock


def test_frame_clock_allows_only_one_outstanding_gui_pulse() -> None:
    """Coalesce pulses until the GUI acknowledges the current frame start."""
    emitted: list[tuple[float, float]] = []

    class Pulse:
        """Record queued signal emissions without requiring a Qt application."""

        def emit(self, scheduled_at: float, emitted_at: float) -> None:
            emitted.append((scheduled_at, emitted_at))

    clock = _FrameClock(Pulse(), 60.0)
    assert clock.request_frame(10.0, 9.995) is True
    assert clock.request_frame(10.0 + 1.0 / 60.0, 10.0) is False
    assert emitted == [(10.0, 9.995)]
    snapshot = clock.snapshot()
    assert snapshot["mode"] == "threaded-feedback-phase-locked"
    assert snapshot["signals_emitted"] == 1
    assert snapshot["coalesced_pulses"] == 1
    assert snapshot["outstanding_pulses"] == 1

    clock.frame_started(10.001, 9.995)
    snapshot = clock.snapshot()
    assert snapshot["outstanding_pulses"] == 0
    assert isclose(snapshot["queue_delay_estimate_ms"], 5.35, abs_tol=1e-9)
    assert clock.request_frame(10.0 + 2.0 / 60.0, 10.0 + 2.0 / 60.0 - 0.00535) is True
    assert len(emitted) == 2
    clock.stop()


def test_frame_clock_rejects_invalid_target_rates() -> None:
    """Reject invalid cadence values rather than start a zero-division worker."""

    class Pulse:
        """Provide a no-op signal for construction validation."""

        def emit(self, _scheduled_at: float, _emitted_at: float) -> None:
            pass

    for target_fps in (0.0, -1.0, inf, nan):
        try:
            _FrameClock(Pulse(), target_fps)
        except ValueError as exc:
            assert "positive and finite" in str(exc)
        else:
            raise AssertionError("Invalid preview frame-clock rate was accepted.")


def test_frame_clock_stop_is_safe_before_start_and_idempotent() -> None:
    """Allow normal cleanup after startup failures and repeated Stop commands."""

    class Pulse:
        """Provide a no-op signal for lifecycle coverage."""

        def emit(self, _scheduled_at: float, _emitted_at: float) -> None:
            pass

    clock = _FrameClock(Pulse(), 60.0)
    clock.stop()
    clock.stop()
    snapshot = clock.snapshot()
    assert snapshot["signals_emitted"] == 0
    assert snapshot["outstanding_pulses"] == 0


def test_frame_clock_smooths_observed_gui_queue_delay() -> None:
    """Use a weighted estimate so the next frame is emitted before its target."""
    emitted: list[tuple[float, float]] = []

    class Pulse:
        """Collect frame pulses for deterministic feedback tests."""

        def emit(self, scheduled_at: float, emitted_at: float) -> None:
            emitted.append((scheduled_at, emitted_at))

    clock = _FrameClock(Pulse(), 60.0)
    initial = clock.snapshot()["queue_delay_estimate_ms"]
    assert initial == 5.0
    clock.frame_started(2.010, 2.000)
    assert isclose(clock.snapshot()["queue_delay_estimate_ms"], 6.75, abs_tol=1e-9)
    clock.request_frame(2.0 + 1.0 / 60.0, 2.0 + 1.0 / 60.0 - 0.00675)
    assert len(emitted) == 1
    clock.stop()
