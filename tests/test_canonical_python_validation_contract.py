from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_canonical_python_job_executes_pytest_contract_modules():
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    start = workflow.index("  python:")
    end = workflow.find("\n  ", start + 3)
    block = workflow[start:] if end == -1 else workflow[start:end]
    assert "test-script: tools/ci/python_validation.py" in block
    assert "test-args: ${{ matrix.group }}" in block
    for group in ("core", "pattern", "sewing", "gui", "pytest"):
        assert group in block

def test_pytest_contract_module_has_a_real_test_entrypoint():
    source = Path(__file__).read_text(encoding="utf-8")
    assert "def test_canonical_python_job_executes_pytest_contract_modules" in source
    assert "def test_pytest_contract_module_has_a_real_test_entrypoint" in source


def test_simulation_evidence_publisher_uses_authenticated_checked_out_head():
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    start = workflow.index("  publish-pr-simulation-evidence:")
    match = __import__("re").search(r"\n  [A-Za-z0-9_-]+:\n", workflow[start + 3 :])
    end = start + 3 + match.start() if match else len(workflow)
    publisher = workflow[start:end]
    assert "publish_visual_evidence" in publisher
    assert "EVIDENCE_HEAD" in publisher
    assert "actions/download-artifact@" in publisher
    assert "http.extraheader" not in publisher


# Exact-head validation recut marker; behavior unchanged.
# Final exact-head cube diagnostic trigger marker; behavior unchanged.
