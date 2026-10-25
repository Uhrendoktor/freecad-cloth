# Copyright (C) 2026 FreeCAD Cloth contributors
"""Behavioral tests for standalone PBD ladder startup and dispatch."""

from pathlib import Path
from types import SimpleNamespace

from tests.freecad_pbd_ladder_bootstrap import dispatch_ladder_entrypoint


def test_dispatch_runs_main_script_directly() -> None:
    """Run a normal Python entrypoint directly without scheduling it."""
    trace: list[str] = []
    calls: list[str] = []

    def run_ladder() -> None:
        """Record direct invocation of the ladder."""
        calls.append("run")

    def schedule(callback: object) -> None:
        """Record a forbidden scheduled invocation."""
        calls.append("scheduled")

    dispatch_ladder_entrypoint(
        Path("/repo/tests/freecad_pbd_avatar_ladder.py"),
        "__main__",
        run_ladder,
        trace.append,
        SimpleNamespace(GuiUp=True),
        schedule,
    )

    assert calls == ["run"]
    assert trace[0] == "entrypoint-name='__main__'"
    assert trace[1].startswith("entrypoint-argv0=")
    assert trace[2] == "direct-entrypoint"


def test_dispatch_schedules_a_freecad_hosted_module() -> None:
    """Schedule a host-named ladder module through the FreeCAD event loop."""
    trace: list[str] = []
    scheduled: list[object] = []
    calls: list[str] = []

    def run_ladder() -> None:
        """Record the scheduled callback execution."""
        calls.append("run")

    def schedule(callback: object) -> None:
        """Keep the callback for explicit test execution."""
        scheduled.append(callback)

    dispatch_ladder_entrypoint(
        Path("/repo/tests/freecad_pbd_avatar_ladder.py"),
        "freecad_pbd_avatar_ladder",
        run_ladder,
        trace.append,
        SimpleNamespace(GuiUp=False),
        schedule,
    )

    assert calls == []
    assert trace[-2:] == ["freecad-hosted-entrypoint", "entrypoint:schedule-main"]
    assert len(scheduled) == 1
    scheduled[0]()  # type: ignore[operator]
    assert calls == ["run"]


def test_dispatch_does_not_schedule_an_unhosted_import() -> None:
    """Keep an ordinary library import inert when FreeCAD GUI is unavailable."""
    trace: list[str] = []
    scheduled: list[object] = []
    calls: list[str] = []

    def run_ladder() -> None:
        """Record any unexpected ladder invocation."""
        calls.append("run")

    def schedule(callback: object) -> None:
        """Record any unexpected event-loop scheduling."""
        scheduled.append(callback)

    dispatch_ladder_entrypoint(
        Path("/repo/tests/freecad_pbd_avatar_ladder.py"),
        "tests.freecad_pbd_avatar_ladder",
        run_ladder,
        trace.append,
        SimpleNamespace(GuiUp=False),
        schedule,
    )

    assert calls == []
    assert scheduled == []
    assert trace[0] == "entrypoint-name='tests.freecad_pbd_avatar_ladder'"
