import os
from types import SimpleNamespace

from freecad_cloth.simulation.TissuBackend import (
    TissuBackend,
    _tissu_stitch_delay_steps,
)


def _fake_backend(delay=15):
    backend = object.__new__(TissuBackend)
    calls = []
    backend._stitch_delay_steps = delay
    backend._step_count = 0
    backend._stitches_active = delay == 0
    backend._stitches = ((2, 5), (8, 11))
    backend._sim = SimpleNamespace(
        solver=SimpleNamespace(
            add_stitch=lambda a, b, compliance: calls.append((a, b, compliance))
        )
    )
    return backend, calls


def test_tissu_stitch_delay_defaults_to_zero(monkeypatch):
    monkeypatch.delenv("CLOTH_TISSU_STITCH_DELAY_STEPS", raising=False)
    assert _tissu_stitch_delay_steps() == 0


def test_tissu_stitch_delay_rejects_negative(monkeypatch):
    monkeypatch.setenv("CLOTH_TISSU_STITCH_DELAY_STEPS", "-1")
    try:
        _tissu_stitch_delay_steps()
    except ValueError as exc:
        assert "must be >= 0" in str(exc)
    else:
        raise AssertionError("negative Tissu stitch delay was accepted")


def test_tissu_stitch_delay_holds_stitches_for_first_fifteen_steps():
    backend, calls = _fake_backend(delay=15)
    for step in range(15):
        backend._step_count = step
        backend._maybe_activate_stitches()
        assert not backend._stitches_active
        assert calls == []
    backend._step_count = 15
    backend._maybe_activate_stitches()
    assert backend._stitches_active
    assert calls == [(2, 5, 0.0), (8, 11, 0.0)]


def test_tissu_stitch_delay_zero_is_active_without_delay():
    backend, calls = _fake_backend(delay=0)
    assert backend._stitches_active
    backend._step_count = 0
    backend._maybe_activate_stitches()
    assert calls == []


def test_tissu_stitch_delay_reset_restores_configured_boundary():
    backend, _calls = _fake_backend(delay=15)
    backend._step_count = 22
    backend._stitches_active = True
    backend._reset_stitch_activation_state()
    assert backend._step_count == 0
    assert backend._stitches_active is False

    backend._stitch_delay_steps = 0
    backend._step_count = 22
    backend._stitches_active = False
    backend._reset_stitch_activation_state()
    assert backend._step_count == 0
    assert backend._stitches_active is True


def test_tissu_stitch_delay_set_stitches_defers_solver_mutation():
    backend, calls = _fake_backend(delay=15)
    backend.set_stitches(((1, 4),), compliance=0.25)
    assert backend._stitches == ((1, 4),)
    assert calls == []

    backend._step_count = 15
    backend._maybe_activate_stitches()
    assert calls == [(1, 4, 0.0)]
