# Copyright (C) 2026 FreeCAD Cloth contributors
"""Contracts for the feedback-paced realtime preview frame clock."""

from math import inf, isclose, nan
from typing import Callable, cast

import pytest

from freecad_cloth.simulation import RealtimePreview
from freecad_cloth.simulation.RealtimePreview import _FrameClock, _sample_p95_ms


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
    assert isclose(snapshot["queue_delay_estimate_ms"], 6.25, abs_tol=1e-9)
    assert isclose(snapshot["worker_wakeup_estimate_ms"], 0.25, abs_tol=1e-9)
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
    assert isclose(clock.snapshot()["queue_delay_estimate_ms"], 10.25, abs_tol=1e-9)
    clock.request_frame(2.0 + 1.0 / 60.0, 2.0 + 1.0 / 60.0 - 0.01025)
    assert len(emitted) == 1
    clock.stop()


def test_queue_delay_estimator_uses_a_high_percentile_not_the_mean() -> None:
    """Use a tail-aware queue-delay lead that covers rare but material GUI stalls."""
    samples = [float(value) for value in range(1, 101)]
    assert _sample_p95_ms(samples) == 95.0


def test_queue_delay_percentile_is_bounded_for_small_sample_windows() -> None:
    """Use the newest sample while the scheduler warms its rolling percentile window."""
    assert _sample_p95_ms([]) == 0.0
    assert _sample_p95_ms([4.25]) == 4.25
    assert _sample_p95_ms([1.0, 3.0, 2.0, 4.0]) == 4.0

def test_dispatcher_posts_a_high_priority_event_to_the_gui_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Post the frame pulse with high priority and dispatch it on the receiver thread."""
    high_priority = 7

    class FakeEvent:
        """Minimal custom Qt event with a registered integer type."""

        _next_type = 1000

        @classmethod
        def registerEventType(cls) -> int:
            cls._next_type += 1
            return cls._next_type

        def __init__(self, event_type: int) -> None:
            self._event_type = event_type

        def type(self) -> int:
            return self._event_type

    class FakeQObject:
        """Minimal QObject base that accepts custom events."""

        def __init__(self) -> None:
            pass

        def event(self, _event: FakeEvent) -> bool:
            return False

    class FakeApplication:
        """Capture worker-thread postEvent calls for the regression assertion."""

        @staticmethod
        def postEvent(receiver: FakeQObject, event: FakeEvent, priority: int) -> None:
            posted.append((receiver, event, priority))

    class FakeQt:
        """Expose the Qt event priority used by the dispatcher."""

        HighEventPriority = high_priority

    class FakeQtCore:
        """Supply only the Qt API surface used to create and post frame events."""

        QEvent = FakeEvent
        QObject = FakeQObject
        QCoreApplication = FakeApplication
        Qt = FakeQt

    posted: list[tuple[FakeQObject, FakeEvent, int]] = []
    callbacks: list[tuple[float, float, float]] = []

    def on_frame(scheduled_at: float, emitted_at: float, dispatched_at: float) -> None:
        callbacks.append((scheduled_at, emitted_at, dispatched_at))

    monkeypatch.setattr(RealtimePreview, "_qt", lambda: FakeQtCore)
    dispatcher = RealtimePreview._make_frame_dispatcher(on_frame)
    dispatcher.start()
    dispatcher.pulse.emit(10.0, 9.5)

    assert len(posted) == 1
    receiver, event, priority = posted[0]
    assert priority == high_priority
    assert receiver is dispatcher
    event_handler = cast("Callable[[FakeEvent], bool]", getattr(dispatcher, "event"))
    assert event_handler(event) is True
    assert len(callbacks) == 1
    assert callbacks[0][0:2] == (10.0, 9.5)
    assert callbacks[0][2] >= 0.0
    assert dispatcher.snapshot() == {
        "dispatch_mode": "QCoreApplication.postEvent(HighEventPriority)",
        "queued_dispatches": 1,
    }

    dispatcher.stop()
    dispatcher.pulse.emit(11.0, 10.5)
    assert len(posted) == 2
    receiver, event, _priority = posted[1]
    assert receiver.event(event) is True
    assert len(callbacks) == 1
