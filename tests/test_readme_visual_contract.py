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

    assert "set_drape_target_source" in source
    assert "create_drape_target" in objects
    assert "assign_drape_target" in objects


def test_readme_turntable_builds_real_motion():
    source = (ROOT / "tests" / "freecad_simulation_turntable.py").read_text(encoding="utf-8")

    assert "BLANKET_PARTICLE_DISTANCE" in source
    assert "simulation-pass" in source
    assert "draped-render-pass" in source


def test_simulation_visual_presentation_is_shaded_and_axonometric():
    runtime = (ROOT / "freecad_cloth" / "simulation" / "SimulationQualityRuntime.py").read_text(
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
    publisher = (ROOT / "tools" / "ci" / "publish_visual_evidence.py").read_text(encoding="utf-8")

    for asset in (
        "cloth-pattern-design.png",
        "cloth-sewing.png",
        "interactive-arrange.png",
        "avatar-pose-mode.png",
        "cloth-simulation-arranged.png",
        "cloth-simulation-draped.png",
    ):
        assert asset in readme
    assert "cloth-tunic-mannequin-motion-frames" in screenshot_source
    assert "simulation-ladder:" in workflow
    assert "artifact: avatar-pose-ui" in workflow
    assert "artifact: interactive-arrange" in workflow
    assert "frame_count=TURNTABLE_FRAMES" in avatar_screenshot
    assert (
        'TURNTABLE_FRAMES = max(12, min(72, int(os.environ.get("CLOTH_TURNTABLE_FRAMES", "72"))))'
        in avatar_screenshot
    )
    assert "expected = documented_assets(source_root)" in publisher
    assert "for asset in sorted(expected):" in publisher
    assert "find_asset(asset)" in publisher


def test_turntable_job_has_no_orphaned_or_legacy_tunic_screenshot_step():
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    block = workflow.split("  gui-turntables:", 1)[1].split("  gui-visual-examples:", 1)[0]
    action = "      - uses: Uhrendoktor/freecad-cloth/.github/actions/freecad-test@9ebd3adbca798a46363904d1ba94c9b267cf52d9"
    assert "tests/freecad_screenshot_source.py" not in block
    assert action + "\n" + action not in block


def test_readme_pattern_and_3d_views_share_the_same_sketch_profiles():
    import json

    screenshot_source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(
        encoding="utf-8"
    )
    publisher = (ROOT / "tools" / "ci" / "publish_visual_evidence.py").read_text(encoding="utf-8")
    manifest = json.loads(
        (ROOT / "tools" / "ci" / "visual_asset_sources.json").read_text(encoding="utf-8")
    )["assets"]

    assert "capture_tunic_pattern_view(doc, front, back, hem_width)" in screenshot_source
    assert "same native Sketcher profiles used by the canonical 3D tunic audit" in screenshot_source
    capture = screenshot_source.split("def capture_tunic_pattern_view(", 1)[1].split(
        "\ndef simulation():", 1
    )[0]
    assert capture.index("close_task()") < capture.index('"cloth-pattern-design.png"')
    assert screenshot_source.rindex(
        "capture_tunic_pattern_view(doc, front, back, hem_width)"
    ) > screenshot_source.index("front, front_outline = make_piece")
    assert (
        "capture_tunic_sewing_view(doc, front, back, hem_width, seam_records)" in screenshot_source
    )
    assert (
        "flat display copies of canonical Sketcher profiles with persistent source sketches "
        "and seam references unchanged"
    ) in screenshot_source
    sewing_capture = screenshot_source.split("def capture_tunic_sewing_view(", 1)[1].split(
        "\ndef simulation()", 1
    )[0]
    assert "VisualTunicFrontSewingPreviewSketch" in sewing_capture
    assert "VisualTunicBackSewingPreviewSketch" in sewing_capture
    assert "front.Sketch.Placement = front_placement" not in sewing_capture
    assert "back.Sketch.Placement = back_placement" not in sewing_capture
    assert "def pattern_and_sewing(" not in screenshot_source
    for name in (
        "cloth-pattern-design.png",
        "cloth-sewing.png",
        "cloth-simulation-arranged.png",
    ):
        assert manifest[name]["artifact"] == "tunic-visual-audit"
        assert manifest[name]["producers"] == ["tests/freecad_tunic_audit_production.py"]
    assert publisher.index('Path("tunic")') < publisher.index('Path("turntables")')


def test_hosted_fallback_visual_publication_is_a_release_gate():
    contract = (ROOT / "tools" / "ci" / "check_visual_asset_contract.py").read_text(
        encoding="utf-8"
    )
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )

    assert "VISUAL_PUBLISH_REQUIRED" in workflow
    assert 'os.environ.get("VISUAL_PUBLISH_REQUIRED"' in contract


def test_pose_visual_audit_exposes_all_avatar_renders():
    pose = (ROOT / "docs" / "wiki" / "04-pose.md").read_text(encoding="utf-8")
    publisher = (ROOT / "tools" / "ci" / "publish_visual_evidence.py").read_text(encoding="utf-8")

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


def test_visual_publisher_removes_stale_public_images_before_publish():
    publisher = (ROOT / "tools" / "ci" / "publish_visual_evidence.py").read_text(encoding="utf-8")

    assert "path.suffix.lower() in IMAGE_SUFFIXES" in publisher
    assert "path.unlink()" in publisher
    assert "for asset in sorted(expected):" in publisher
    assert "write_provenance(" in publisher
    assert "errors = verify(source_root, published, provenance, args.source_sha)" in publisher


def test_visual_publisher_preserves_script_local_import_invocation():
    publisher = (ROOT / "tools" / "ci" / "publish_visual_evidence.py").read_text(encoding="utf-8")
    action = (ROOT / ".github" / "actions" / "publish-visual-evidence" / "action.yml").read_text(
        encoding="utf-8"
    )

    assert "from visual_evidence import documented_assets, verify, write_provenance" in publisher
    assert "python3 tools/ci/publish_visual_evidence.py" in action


print("GUI visual contract checks passed")


def test_pull_request_turntable_validation_skips_wiki_only_avatar_renders() -> None:
    avatar_screenshot = (ROOT / "tests" / "freecad_avatar_screenshot.py").read_text(
        encoding="utf-8"
    )
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )

    assert (
        'if mode in ("all", "turntable", "turntable-validation", "documentation-turntable"):'
        in avatar_screenshot
    )
    validation_capture = avatar_screenshot.split(
        'if mode in ("all", "turntable", "turntable-validation", "documentation-turntable"):', 1
    )[1].split('if mode in ("all", "gallery", "documentation"):', 1)[0]
    assert '"cloth-avatar-turntable-frames"' in validation_capture
    assert "render_turntable(" in validation_capture

    validation_job = workflow.split("  gui-turntables:", 1)[1].split("  gui-visual-examples:", 1)[0]
    assert "CLOTH_AVATAR_SCREENSHOT_MODE=turntable-validation" in validation_job
    assert "Generate wiki-only avatar body-shape gallery" not in validation_job
    assert "build_visual_gifs.py" not in validation_job
    assert "cloth-avatar-turntable-frames/**" not in validation_job

    documentation_job = workflow.split("  gui-documentation-assets:", 1)[1].split(
        "  publish-readme-turntables:", 1
    )[0]
    assert "CLOTH_AVATAR_SCREENSHOT_MODE=documentation" in documentation_job
    assert "CLOTH_AVATAR_SCREENSHOT_MODE=documentation-turntable" in documentation_job
    assert "CLOTH_DOCUMENTATION_CAPTURE_ONLY=true" in documentation_job
    assert "CLOTH_TURNTABLE_FRAMES=${{ env.CLOTH_TURNTABLE_FRAMES }}" in documentation_job


def test_wiki_visual_generation_is_publication_only() -> None:
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )

    assert "CLOTH_WIKI_VISUALS_REQUIRED" not in workflow
    for setting in (
        "CLOTH_TURNTABLE_FRAMES:",
        "CLOTH_BLANKET_STEPS:",
        "CLOTH_TURNTABLE_PBD_SUBSTEPS:",
        "CLOTH_DOC_AVATAR_FIT_STEPS:",
    ):
        assert setting in workflow
    validation_jobs = workflow.split("  gui-turntables:", 1)[1].split(
        "  publish-pr-simulation-evidence:", 1
    )[0]
    assert "ImageMagick for main GIF publication" not in validation_jobs
    assert "build_visual_gifs.py" not in validation_jobs
    documentation_job = workflow.split("  gui-documentation-assets:", 1)[1].split(
        "  publish-readme-turntables:", 1
    )[0]
    assert "if: ${{ inputs.execution_mode == 'publication'" in documentation_job


def test_documentation_turntable_capture_does_not_run_simulation_release_gates() -> None:
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    simulation = (ROOT / "tests" / "freecad_simulation_turntable.py").read_text(encoding="utf-8")
    assert "CLOTH_DOCUMENTATION_CAPTURE_ONLY=true" in workflow
    assert "if documentation_capture_only:" in simulation
    assert "stage=documentation-capture-only" in simulation


def test_ci_workflow_entry_points_keep_triggers_and_configuration_centralized() -> None:
    workflows = ROOT / ".github" / "workflows"
    shared = (workflows / "canonical-execution.yml").read_text(encoding="utf-8")
    commits = (workflows / "commit-validation.yml").read_text(encoding="utf-8")
    publication = (workflows / "main-publication.yml").read_text(encoding="utf-8")
    trigger_header = shared.split("\nenv:", 1)[0]

    assert "workflow_call:" in trigger_header
    assert "\nconcurrency:\n" not in shared.split("\njobs:\n", 1)[0]
    assert "  push:" not in trigger_header
    assert "  pull_request:" not in trigger_header
    assert "  merge_group:" not in trigger_header
    assert "pull_request:" in commits
    assert "merge_group:" in commits
    assert "execution_mode: fast" in commits
    assert "execution_mode: full" in commits
    full_job = commits.split("  full-validation:", 1)[1].split("  scheduled-validation:", 1)[0]
    assert "github.event_name == 'merge_group'" in full_job
    assert "github.event.pull_request" not in full_job
    gate_job = commits.split("  required-pre-merge-validation:", 1)[1]
    assert "github.event.pull_request.draft == false" in gate_job
    assert "name: Required pre-merge validation" in commits
    assert "  push:" not in commits
    assert "  pull_request:" not in publication
    assert "  merge_group:" not in publication
    assert "workflow_dispatch:" not in shared
    assert "push:" in publication
    assert "branches: [main]" in publication
    assert "execution_mode: publication" in publication
    assert "workflow_run:" not in commits
    assert "workflow_run:" not in publication
    assert "\nenv:\n" not in commits
    assert "\nenv:\n" not in publication
    assert "CLOTH_SIMULATION_BACKEND: position-based-dynamics" in shared
    assert "Required validation gate" in shared
    watchdog = shared.split("  runner_watchdog:", 1)[1].split("  pbd_validation_image:", 1)[0]
    watchdog_source = (ROOT / "tools" / "ci" / "runner_watchdog.py").read_text(encoding="utf-8")
    assert "inputs.runner_mode != 'hosted'" in watchdog
    assert 'os.environ.get("FALLBACK_WORKFLOW", "commit-validation.yml")' in watchdog_source


def test_main_publication_requires_artifacts_from_a_matching_full_validation_tree() -> None:
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    publisher = (ROOT / "tools" / "ci" / "publish_visual_evidence.py").read_text(encoding="utf-8")
    assert "source_tree" in workflow
    assert "--event merge_group --status success" in workflow
    assert "Required pre-merge validation" in workflow
    assert "No successful merge-group full-validation run" in workflow
    doc_assets = workflow.split("  gui-documentation-assets:", 1)[1].split(
        "  publish-readme-turntables:", 1
    )[0]
    assert (
        "needs: [find-validation-artifacts, local_runner_readiness, pbd_validation_image]"
        in doc_assets
    )
    assert 'build_visual_gif_set("turntables", Path("turntable-doc-assets"))' in publisher
    assert 'build_visual_gif_set("blanket", Path("blanket"))' in publisher
