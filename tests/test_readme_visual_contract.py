"""Contracts for the published README/wiki visual validation path."""

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
    avatar_screenshot = (ROOT / "tests" / "freecad_avatar_screenshot.py").read_text(
        encoding="utf-8"
    )
    publisher = (ROOT / "tools" / "ci" / "publish_visual_evidence.py").read_text(
        encoding="utf-8"
    )

    for asset in (
        "cloth-pattern-design.png",
        "cloth-sewing.png",
        "cloth-blanket-motion.gif",
        "cloth-tunic-mannequin-motion.gif",
        "cloth-simulation-arranged-turntable.gif",
        "cloth-simulation-draped-turntable.gif",
        "cloth-simulation-arranged.png",
        "cloth-simulation-draped.png",
        "avatar-pose-mode.png",
        "interactive-arrange.png",
    ):
        assert asset in readme
    assert "Simulation ladder" in readme
    assert "penetration" in readme.lower()
    assert "cloth-tunic-mannequin-motion-frames" in screenshot_source
    assert "simulation-ladder:" in workflow
    assert "artifact: avatar-pose-ui" in workflow
    assert "artifact: interactive-arrange" in workflow
    assert "frame_count=TURNTABLE_FRAMES" in avatar_screenshot
    assert "expected = documented_assets(source_root)" in publisher
    assert "for asset in sorted(expected):" in publisher
    assert "find_asset(asset)" in publisher


def test_pose_visual_audit_exposes_all_avatar_renders():
    pose = (ROOT / "docs" / "wiki" / "04-pose.md").read_text(encoding="utf-8")
    publisher = (ROOT / "tools" / "ci" / "publish_visual_evidence.py").read_text(
        encoding="utf-8"
    )

    for asset in (
        "cloth-avatar-front.png",
        "cloth-avatar-rear.png",
        "cloth-avatar-left.png",
        "cloth-avatar-right.png",
        "cloth-avatar-top.png",
        "cloth-avatar-bottom.png",
        "cloth-avatar-turntable.gif",
    ):
        assert asset in pose
    assert "find_asset(asset)" in publisher


def test_visual_publisher_runs_as_a_module_for_relative_imports():
    publisher = (ROOT / "tools" / "ci" / "publish_visual_evidence.py").read_text(
        encoding="utf-8"
    )
    action = (ROOT / ".github" / "actions" / "publish-visual-evidence" / "action.yml").read_text(
        encoding="utf-8"
    )

    assert "from .visual_evidence import documented_assets, verify, write_provenance" in publisher
    assert "python3 -m tools.ci.publish_visual_evidence" in action


print("GUI visual contract checks passed")
