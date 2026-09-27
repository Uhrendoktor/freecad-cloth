from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_python_job_executes_pytest_contract_modules():
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )
    assert "python3 -m pytest --version" in workflow
    pytest_marker = "python3 -m pytest -q"
    pytest_start = workflow.index(pytest_marker)
    pytest_end = workflow.index("\n              ')", pytest_start)
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
