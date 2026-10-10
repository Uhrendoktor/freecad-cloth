import re
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_collection_plugin_accepts_all_expected_modules(monkeypatch):
    from tools.ci.check_test_collection import pytest_collection_modifyitems

    monkeypatch.setenv(
        "CLOTH_EXPECTED_TEST_MODULES",
        "tests/test_core.py\ntests/test_mesh.py",
    )
    pytest_collection_modifyitems(
        [
            SimpleNamespace(path=ROOT / "tests" / "test_core.py"),
            SimpleNamespace(path=ROOT / "tests" / "test_mesh.py"),
        ]
    )


def test_collection_plugin_fails_when_a_module_collects_no_items(monkeypatch):
    from tools.ci.check_test_collection import pytest_collection_modifyitems

    monkeypatch.setenv(
        "CLOTH_EXPECTED_TEST_MODULES",
        "tests/test_core.py\ntests/test_mesh.py",
    )
    with pytest.raises(pytest.UsageError, match="tests/test_mesh.py"):
        pytest_collection_modifyitems([SimpleNamespace(path=ROOT / "tests" / "test_core.py")])


def test_canonical_python_job_executes_pytest_contract_modules():
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    start = workflow.index("  python:")
    match = re.search(r"\n  [A-Za-z0-9_-]+:\n", workflow[start + 3 :])
    end = start + 3 + match.start() if match else len(workflow)
    block = workflow[start:end]
    assert "group: [core, pattern, sewing, gui, pytest]" in block
    assert "python_validation.py" in block
    runner = (ROOT / "tools" / "ci" / "python_validation.py").read_text(encoding="utf-8")
    assert '"-p", "tools.ci.check_test_collection"' in runner
    assert "CLOTH_EXPECTED_TEST_MODULES" in runner
    assert "check_test_collection.py" not in runner
    assert "matrix.group != 'gui'" in block
    assert "test-args: gui" in block


def test_gui_acceptance_validator_uses_visual_artifacts_only():
    from tools.ci import validate_acceptance

    assert set(validate_acceptance.CASES) == {"avatar-pose", "fitting"}
    assert all(path.suffix == ".png" for path in validate_acceptance.CASES.values())


def test_simulation_evidence_publisher_uses_authenticated_checked_out_head():
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    start = workflow.index("  publish-pr-simulation-evidence:")
    match = re.search(r"\n  [A-Za-z0-9_-]+:\n", workflow[start + 3 :])
    end = start + 3 + match.start() if match else len(workflow)
    publisher = workflow[start:end]
    assert "publish-visual-evidence@" in publisher
    assert "evidence-head:" in publisher
    assert "source-sha:" in publisher
    assert "mode: pr" in publisher


# Exact-head validation recut marker; behavior unchanged.
# Final exact-head cube diagnostic trigger marker; behavior unchanged.
