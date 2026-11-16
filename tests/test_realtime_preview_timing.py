# Copyright (C) 2026 FreeCAD Cloth contributors
"""Contracts for the realtime preview's coalescing monotonic frame clock."""

from math import inf, nan

from freecad_cloth.simulation.RealtimePreview import (
    _FrameClock,
    _append_pending_deadline,
    _deadline_timer_interval_ms,
)


def test_frame_clock_coalesces_repeated_pulses_until_gui_dispatch_consumes_one() -> None:
    """Keep at most one queued Qt callback while the GUI thread is busy."""
    emitted: list[float] = []

    class Pulse:
        """Record queued signal emissions without requiring a Qt application."""

        def emit(
            self, scheduled_at: float, _emitted_at: float
        ) -> None:
            emitted.append(scheduled_at)

    clock = _FrameClock(Pulse(), 60.0)

    assert clock.request_frame(10.0, 10.0 - 0.015) is True
    assert clock.request_frame(10.0 + 1.0 / 60.0, 10.0 + 1.0 / 60.0 - 0.015) is False
    assert clock.request_frame(10.0 + 2.0 / 60.0, 10.0 + 2.0 / 60.0 - 0.015) is False
    assert emitted == [10.0]
    assert clock.snapshot() == {
        "mode": "threaded-queued-deadline",
        "target_fps": 60.0,
        "lead_ms": 15.0,
        "signals_emitted": 1,
        "coalesced_pulses": 2,
        "missed_deadlines": 0,
    }

    clock.consume_frame()
    assert (
        clock.request_frame(10.0 + 3.0 / 60.0, 10.0 + 3.0 / 60.0 - 0.015) is True
    )
    assert emitted == [10.0, 10.0 + 3.0 / 60.0]
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
        """Provide a no-op signal for clock lifecycle coverage."""

        def emit(self, _scheduled_at: float) -> None:
            pass

    clock = _FrameClock(Pulse(), 60.0)
    clock.stop()
    clock.stop()
    assert clock.snapshot()["signals_emitted"] == 0



def test_deadline_timer_interval_never_fires_early() -> None:
    """Round positive waits up to the next whole millisecond for precise Qt timers."""
    assert _deadline_timer_interval_ms(2.0, 1.9991) == 1
    assert _deadline_timer_interval_ms(2.0, 1.9989) == 2
    assert _deadline_timer_interval_ms(1.0, 1.0) == 0
    assert _deadline_timer_interval_ms(0.5, 1.0) == 0


def test_deadline_timer_rejects_nonfinite_clock_values() -> None:
    """Reject invalid monotonic clock inputs before arming Qt timers."""
    for deadline, now in ((inf, 0.0), (1.0, nan), (nan, inf)):
        try:
            _deadline_timer_interval_ms(deadline, now)
        except ValueError as exc:
            assert "must be finite" in str(exc)
        else:
            raise AssertionError("Non-finite frame deadline was accepted.")


def test_gui_deadline_queue_is_bounded_and_preserves_earliest_frames() -> None:
    """Retain only two future deadlines and drop later pulses rather than grow a backlog."""
    pending: list[float] = []
    assert _append_pending_deadline(pending, 2.0) is True
    assert _append_pending_deadline(pending, 3.0) is True
    assert _append_pending_deadline(pending, 4.0) is False
    assert pending == [2.0, 3.0]


def test_gui_deadline_queue_accepts_a_new_deadline_after_consumption() -> None:
    """Allow the bounded queue to resume after the GUI timer consumes an entry."""
    pending = [2.0, 3.0]
    pending.pop(0)
    assert _append_pending_deadline(pending, 4.0) is True
    assert pending == [3.0, 4.0]
