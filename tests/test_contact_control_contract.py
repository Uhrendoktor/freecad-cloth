from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_contact_control_contract():
    source = (ROOT / "tests" / "freecad_contact_controls.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    assert 'CLOTH_TISSU_COLLISION_MODE" = "mesh"' in source or 'CLOTH_TISSU_COLLISION_MODE"] = "mesh"' in source
    assert 'CLOTH_TISSU_COLLISION_TRIANGLES" = "2048"' in source or 'CLOTH_TISSU_COLLISION_TRIANGLES"] = "2048"' in source
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
    assert "App.exit()" in source
    assert "QApplication.instance()" in source
    assert "iterations=1" in source
    assert '"iterations": 1' in source
    assert '"case_id": "0-cube-contact"' in source
    assert '"case_id": "0a-avatar-contact"' in source
    assert '"collision_source_triangle_count"' in source
    assert '"solver_collision_triangle_count"' in source
    assert "faulthandler.dump_traceback_later(30.0, repeat=True" in source
    assert "contact-controls-progress.log" in source
    assert "_progress(" in source
    assert "Gui.getDocument(doc.Name)" in source
    assert 'saveImage(str(OUT / name), 1200, 900, "Current")' in source
    assert 'saveImage(str(OUT / name), 1200, 900, "Current", 1)' not in source
    assert "_events()" in source
    assert "setsid /opt/freecad/AppRun" in workflow
    assert "contact-controls-supervisor=timeout" in workflow
    assert "artifacts/contact-controls/app-run.log" in workflow
    assert "if: always()" in workflow
    assert "if-no-files-found: warn" in workflow
    assert 'CLOTH_CONTACT_CONTROLS_EXECUTE=1' in workflow
    assert "FreeCAD AppRun may evaluate the script in more than one namespace" in source
    assert '_CLOTH_CONTACT_CONTROLS_RAN' in source
    assert 'CLOTH_CONTACT_CONTROLS_EXECUTE' in source
    assert 'entrypoint __name__=' in source
    assert 'Gui.getDocument(doc.Name)' in source
    assert 'def _save_probe_view(doc, name' in source
    assert "retention-days: 14" in workflow
    assert "faulthandler.dump_traceback_later(30.0, repeat=True" in source
    assert "contact-controls-progress.log" in source
    assert "_progress(" in source
