"""Contracts for the published README visual validation path."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_readme_turntable_uses_pbd_backend():
    source = (ROOT / "tests" / "freecad_simulation_turntable.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )

    assert "backend=pbd" in source
    assert "CLOTH_SIMULATION_BACKEND: position-based-dynamics" in workflow


def test_blanket_visual_fixture_has_no_runtime_backend_selector():
    source = (ROOT / "tests" / "freecad_visual_examples.py").read_text(encoding="utf-8")

    assert "CLOTH_SIMULATION_BACKEND" not in source


def test_turntable_still_uses_persistent_drape_target():
    source = (ROOT / "tests" / "freecad_simulation_turntable.py").read_text(encoding="utf-8")
    objects = (ROOT / "freecad_cloth" / "simulation" / "SimulationObjects.py").read_text(
        encoding="utf-8"
    )

    assert "set_avatar_collision_source" in source
    assert "create_drape_target" in objects
    assert "assign_drape_target" in objects


def test_readme_turntable_builds_real_motion():
    source = (ROOT / "tests" / "freecad_simulation_turntable.py").read_text(encoding="utf-8")

    assert "BLANKET_PARTICLE_DISTANCE" in source
    assert "simulation-pass" in source
    assert "draped-render-pass" in source


def test_simulation_visual_presentation_is_shaded_and_axonometric():
    runtime = (ROOT / "freecad_cloth" / "simulation" / "SimulationQualityRuntimeV2.py").read_text(
        encoding="utf-8"
    )
    turntable = (ROOT / "tests" / "freecad_simulation_turntable.py").read_text(encoding="utf-8")
    visual = (ROOT / "tests" / "freecad_visual_examples.py").read_text(encoding="utf-8")

    assert 'view.DisplayMode = "Shaded"' in runtime
    assert "view.viewAxonometric()" in turntable
    assert 'panel.ViewObject.DisplayMode = "Shaded"' in visual
    assert "mode=Shaded" in visual


def test_human_visual_validation_gallery_covers_the_full_flow():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    screenshot_source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(
        encoding="utf-8"
    )

    for asset in (
        "cloth-pattern-design.png",
        "cloth-sewing.png",
        "cloth-blanket-motion.gif",
        "cloth-tunic-mannequin-motion.gif",
        "cloth-simulation-arranged-turntable.gif",
        "cloth-simulation-draped-turntable.gif",
        "cloth-simulation-diagnostics.png",
        "cloth-avatar-turntable.gif",
    ):
        assert asset in readme
    assert "Simulation ladder" in readme
    assert "penetration" in readme.lower()
    assert "cloth-tunic-mannequin-motion-frames" in screenshot_source
    assert "simulation-ladder:" in workflow
    assert "cloth-tunic-mannequin-motion.gif" in workflow

