from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_python_job_executes_pytest_contract_modules():
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    assert "python3 -m pytest --version" in workflow
    pytest_marker = "python3 -m pytest -q"
    pytest_start = workflow.index(pytest_marker)
    pytest_end = workflow.index("\n            '", pytest_start)
    pytest_list = workflow[pytest_start:pytest_end]
    assert "tests/test_tunic_audit_contract.py" in pytest_list
    assert "tests/test_readme_visual_contract.py" in pytest_list
    assert "tests/test_cloth_diagnostics.py" in pytest_list
    assert "python3 -m pytest -q" in pytest_list
    assert 'python3 "$test"' in workflow


def test_pytest_contract_module_has_a_real_test_entrypoint():
    source = Path(__file__).read_text(encoding="utf-8")
    assert "def test_canonical_python_job_executes_pytest_contract_modules" in source
    assert "def test_pytest_contract_module_has_a_real_test_entrypoint" in source


def test_visual_review_is_mandatory_and_exports_intermediate_states():
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    development = (ROOT / "docs" / "DEVELOPMENT.md").read_text(encoding="utf-8")
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    audit = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert "Mandatory visual review and human intervention" in development
    assert "Human inspection is mandatory before acceptance/merge." in workflow
    assert "retention-days: 14" in workflow
    assert "cloth-simulation-draped-step-*.png" in workflow
    assert "cloth-simulation-draped-turntable-frames/frame-*.png" in workflow
    assert "for batch in (15,15,15,15,15,15):" in source
    assert "visual_checkpoints = (15,30,45,60,75,90)" in audit
    assert 'cloth-simulation-draped-step-%03d.png' in audit


def test_tunic_audit_replaces_hard_exit_and_writes_failure_diagnostics():
    audit = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    assert "source = source.replace('os._exit(1)', 'raise SystemExit(1)')" in audit
    assert 'source = source.replace(\'getattr(os, "_" + "exit")(0)\', \'raise SystemExit(0)\')' in audit
    assert "tunic-audit-diagnostics-path=" in audit
    assert "traceback.format_exc()" in audit
    assert "tunic-audit-gui-log-tail-begin" in audit
    assert "docs/images/generated/tunic-audit-diagnostics.txt" in workflow


def test_turntable_exports_post_simulation_state_before_validation():
    source = (ROOT / "tests" / "freecad_simulation_turntable.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    render = source.index('render_turntable(view, [cube, panel], os.path.join(OUT, "cloth-simulation-post-simulation-turntable-frames"))')
    validation = source.index('validation_started = time.monotonic()')
    assert render < validation
    assert "blanket-world-diagnostics centroid_xy_offset_mm=" in source
    assert "projected_overlap_ratio=" in source
    assert "top_support_vertex_fraction=" in source
    assert "low_cube_support" in source
    assert "cloth-simulation-post-simulation-turntable-frames/frame-*.png" in workflow or "*turntable-frames/frame-*.png" in workflow
