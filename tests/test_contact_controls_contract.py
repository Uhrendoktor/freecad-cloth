from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_contact_controls_are_diagnostic_only_and_schema_locked():
    source = (ROOT / "tests" / "freecad_contact_controls.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    assert 'SCHEMA = 1' in source
    assert '"static-surface-probe"' in source
    assert '"avatar-shallow-penetration"' in source
    assert 'TissuBackend(system, ((0, 1, 2),), collision_surface=surface, collision_mode="mesh")' in source
    assert 'gravity=(0.0, 0.0, 0.0)' in source
    assert 'inputs.diagnostic_controls == true' in workflow
    assert 'name: Diagnostic contact controls 0/0a' in workflow
    assert 'gui-tunic-visual' not in workflow[workflow.index("  contact_controls:"):workflow.index("\n  python:", workflow.index("  contact_controls:"))]
