# Copyright (C) 2026 FreeCAD Cloth contributors
"""Contracts for the realtime preview's frame-budget timer scheduling."""

from math import inf, nan

from freecad_cloth.simulation.RealtimePreview import (
    _next_timer_interval_ms,
    _schedule_next_frame,
    _timer_wakeup_compensation_ms,
)


def test_timer_wakeup_compensation_uses_the_recent_upper_tail() -> None:
    """Use a stable upper percentile and ignore invalid or negative timing samples."""
    assert _timer_wakeup_compensation_ms([]) == 0.0
    assert _timer_wakeup_compensation_ms([1.0, 2.0, 3.0, 4.0, 5.0]) == 5.0
    assert _timer_wakeup_compensation_ms([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]) == 9.0
    assert _timer_wakeup_compensation_ms([nan, inf, -1.0, 3.5]) == 3.5


def test_next_timer_interval_complements_callback_and_measured_wakeup_cost() -> None:
    """Subtract measured callback and Qt wakeup latency from the 60 FPS frame budget."""
    assert _next_timer_interval_ms(0.0) == 16
    assert _next_timer_interval_ms(0.0, 4.0) == 12
    assert _next_timer_interval_ms(10.0) == 6
    assert _next_timer_interval_ms(10.0, 4.0) == 2
    assert _next_timer_interval_ms(13.9, 4.0) == 1
    assert _next_timer_interval_ms(15.5) == 1


def test_next_timer_interval_uses_a_safe_minimum_for_over_budget_or_invalid_costs() -> None:
    """Avoid zero-delay event-loop starvation and handle invalid timing measurements."""
    assert _next_timer_interval_ms(20.0) == 1
    assert _next_timer_interval_ms(inf) == 1
    assert _next_timer_interval_ms(nan) == 1
    assert _next_timer_interval_ms(0.0, inf) == 1
    assert _next_timer_interval_ms(-1.0, -1.0) == 16


def test_next_frame_schedule_restarts_the_inactive_single_shot_timer() -> None:
    """Restart an inactive one-shot timer using the remaining 60 FPS frame budget."""

    class Timer:
        """Record interval updates and starts without requiring a Qt event loop."""

        def __init__(self) -> None:
            """Initialize the fake timer's interval and start log."""
            self.interval_ms = 16
            self.start_count = 0

        def setInterval(self, interval: int) -> None:
            """Store the delay selected for the next callback."""
            self.interval_ms = interval

        def start(self) -> None:
            """Record that the single-shot timer is armed again."""
            self.start_count += 1

    timer = Timer()

    interval_ms = _schedule_next_frame(timer, 10.0, 4.0)

    assert interval_ms == 2, "The requested delay must include measured timer lateness."
    assert timer.interval_ms == 2, "The timer must receive the compensated interval."
    assert timer.start_count == 1, (
        "A single-shot timer must be explicitly restarted after each tick."
    )
