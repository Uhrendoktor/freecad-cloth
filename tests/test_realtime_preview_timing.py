# Copyright (C) 2026 FreeCAD Cloth contributors
"""Contracts for the realtime preview's frame-budget timer scheduling."""

from math import inf, nan

from freecad_cloth.simulation.RealtimePreview import _next_timer_interval_ms


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
