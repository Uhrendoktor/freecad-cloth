"""Headless contract tests for public DrapeTarget/Simulation commands."""
import sys
from types import SimpleNamespace

from DrapeCommands import COMMANDS as DRAPE_COMMANDS, _attach_to_simulation
from SimulationCommands import COMMANDS as SIMULATION_COMMANDS


def test_refresh_commands_are_public():
    assert "ClothDrape_RefreshTarget" in DRAPE_COMMANDS
    assert "ClothSimulation_RefreshDrapeTarget" in SIMULATION_COMMANDS


def test_drape_attachment_links_authoritative_target_not_avatar_proxy():
    target = SimpleNamespace(Name="DrapeTarget")
    scene = SimpleNamespace(Type="ClothSimulation", DrapeTarget=None)
    doc = SimpleNamespace(Objects=[scene], recompute=lambda: None)
    _attach_to_simulation(doc, target)
    assert scene.DrapeTarget is target
    assert not hasattr(scene, "AvatarProxy") or scene.AvatarProxy is not target


def test_simulation_target_preflight_requires_ready_lifecycle(monkeypatch):
    import SimulationCommands
    target = SimpleNamespace(LifecycleState="STALE")
    doc = SimpleNamespace(Objects=[SimpleNamespace(TypeId="App::FeaturePython", Type="ClothSimulation", DrapeTarget=target)])
    app = SimpleNamespace(ActiveDocument=doc)
    monkeypatch.setitem(sys.modules, "FreeCAD", app)
    try:
        SimulationCommands._require_simulation_target_ready(doc)
    except RuntimeError as exc:
        assert "blocks simulation" in str(exc)
    else:
        raise AssertionError("stale DrapeTarget must block simulation")
