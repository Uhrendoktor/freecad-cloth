from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_contact_control_contract():
    source = (ROOT / "tests" / "freecad_contact_controls.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    assert 'CLOTH_TISSU_COLLISION_MODE" = "mesh"' in source or 'CLOTH_TISSU_COLLISION_MODE"] = "mesh"' in source
    assert 'CLOTH_TISSU_COLLISION_TRIANGLES" = "2048"' in source or 'CLOTH_TISSU_COLLISION_TRIANGLES"] = "2048"' in source
    assert 'rung": "0"' in source
    assert 'rung": "0a"' in source
    assert "inside" in source and "outside" in source
    assert "resolved_outward" in source
    assert "outside_preserved" in source
    assert "run_diagnostics" in workflow
    assert "github.event_name == 'workflow_dispatch' && inputs.run_diagnostics == 'contact'" in workflow
    assert "github.event_name == 'pull_request' && github.head_ref == 'agent/contact-controls-2484-supervisor-20260927'" in workflow
    assert "Temporary supervisor validation" in workflow
    assert "diagnostic-contact-controls" in workflow
    assert "workflow_dispatch" in workflow
    assert "iterations=1" in source
    assert '"iterations": 1' in source
    assert '"case_id": "0-cube-contact"' in source
    assert '"case_id": "0a-avatar-contact"' in source
    assert '"collision_source_triangle_count"' in source
    assert '"solver_collision_triangle_count"' in source
