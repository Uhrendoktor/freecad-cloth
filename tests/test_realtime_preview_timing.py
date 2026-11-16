# Copyright (C) 2026 FreeCAD Cloth contributors
"""Contracts for the realtime preview's frame-budget timer scheduling."""

from math import inf, nan

from freecad_cloth.simulation.RealtimePreview import (
    _next_timer_interval_ms,
    _schedule_next_frame,
)


def test_next_timer_interval_complements_callback_cost_to_a_60fps_budget() -> None:
    """Schedule only the remaining frame time after the previous callback completes."""
    assert _next_timer_interval_ms(0.0) == 16
    assert _next_timer_interval_ms(10.0) == 6
    assert _next_timer_interval_ms(13.9) == 2
    assert _next_timer_interval_ms(15.5) == 1


def test_next_timer_interval_uses_a_safe_minimum_for_over_budget_or_invalid_costs() -> None:
    """Avoid zero-delay event-loop starvation and handle invalid timing measurements."""
    assert _next_timer_interval_ms(20.0) == 1
    assert _next_timer_interval_ms(inf) == 1
    assert _next_timer_interval_ms(nan) == 1
    assert _next_timer_interval_ms(-1.0) == 16


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

    _schedule_next_frame(timer, 10.0)

    assert timer.interval_ms == 6, "The next delay must complement the callback's frame cost."
    assert timer.start_count == 1, (
        "A single-shot timer must be explicitly restarted after each tick."
    )
