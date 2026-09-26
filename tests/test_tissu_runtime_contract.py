from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pytissu_patch_contract_is_pinned_and_reproducible():
    patch = (ROOT / "tools" / "tissu-mesh-collider-inside.patch").read_text(encoding="utf-8")
    script = (ROOT / "tools" / "build_pytissu_runtime.sh").read_text(encoding="utf-8")
    docs = (ROOT / "docs" / "TISSU_RUNTIME.md").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
        encoding="utf-8"
    )

    commit = "c28a3c7504ddc782bef844ab5bd4cd0bde14b628"
    assert commit in patch
    assert commit in script
    assert "git apply --check" in script
    assert "ctest --test-dir build --output-on-failure" in script
    assert "pytissu-provenance.txt" in script
    assert "pytissu-runtime" in workflow
    assert "freecad-1.1.0-py312-r3" in workflow
    assert "No timeout increases" in docs
