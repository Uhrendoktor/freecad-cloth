"""Human-facing documentation contracts.

Keep these checks close to the docs so command labels, prerequisites, and
repository links do not drift silently from the implementation.
"""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
DOCS = (
    ROOT / "README.md",
    ROOT / "docs" / "README.md",
    ROOT / "docs" / "INSTALLATION.md",
    ROOT / "docs" / "USER_GUIDE.md",
    ROOT / "docs" / "EXAMPLES.md",
    ROOT / "docs" / "WORKBENCH_GUIDE.md",
)


def _markdown_links(text):
    for match in re.finditer(r"!?\[[^\]]*\]\(([^)]+)\)", text):
        yield match.group(1).strip().split("#", 1)[0].split("?", 1)[0]


def _command_source():
    paths = (
        ROOT / "freecad_cloth" / "pattern" / "PatternCommands.py",
        ROOT / "freecad_cloth" / "sewing" / "SewingCommands.py",
        ROOT / "freecad_cloth" / "sewing" / "SewingNetworkCommands.py",
        ROOT / "freecad_cloth" / "avatar" / "FittingCommands.py",
        ROOT / "freecad_cloth" / "simulation" / "SimulationCommands.py",
        ROOT / "freecad_cloth" / "simulation" / "DrapeCommands.py",
    )
    return "\n".join(path.read_text(encoding="utf-8") for path in paths)


def test_human_facing_internal_links_exist():
    failures = []
    for doc in DOCS:
        text = doc.read_text(encoding="utf-8")
        for target in _markdown_links(text):
            if not target or target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            candidate = (doc.parent / target).resolve()
            if not candidate.is_file():
                failures.append(f"{doc.relative_to(ROOT)} -> {target}")
    assert not failures, "broken documentation links: " + ", ".join(failures)


def test_documented_command_ids_exist_in_current_command_surface():
    docs_text = "\n".join(path.read_text(encoding="utf-8") for path in DOCS)
    documented = set(
        re.findall(r"Cloth(?:Pattern|Sewing|Fitting|Simulation|Drape)_[A-Za-z0-9_]+", docs_text)
    )
    source = _command_source()
    missing = sorted(command for command in documented if command not in source)
    assert not missing, "documented commands missing from current command surface: " + ", ".join(missing)


def test_documented_simulation_ui_labels_match_current_panel():
    docs_text = (ROOT / "docs" / "USER_GUIDE.md").read_text(encoding="utf-8") + "\n" + (
        ROOT / "docs" / "WORKBENCH_GUIDE.md"
    ).read_text(encoding="utf-8")
    gui = (ROOT / "freecad_cloth" / "simulation" / "SimulationGui.py").read_text(encoding="utf-8")
    for label in (
        "Cloth pieces",
        "Drape target",
        "Pinned vertices",
        "Seam pairs",
        "Run 30 steps",
        "Reset",
    ):
        assert label in docs_text
        assert label in gui


def test_documented_runtime_prerequisites_match_project_metadata():
    installation = (ROOT / "docs" / "INSTALLATION.md").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    dockerfile = (ROOT / "docker" / "freecad-ci" / "Dockerfile").read_text(encoding="utf-8")

    assert "Python 3.12" in installation
    assert "triangle==20250106" in installation
    assert 'requires-python = ">=3.12"' in pyproject
    assert '"triangle==20250106"' in pyproject
    assert "python=3.12" in dockerfile
    assert "freecad=1.1.0" in dockerfile
    assert "pytissu==1.1.0" in dockerfile
    assert "triangle==20250106" in dockerfile


def test_stable_visual_asset_names_are_documented():
    docs_readme = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    for asset in (
        "cloth-blanket-motion.gif",
        "cloth-simulation-draped-front.png",
        "cloth-simulation-arranged-turntable.gif",
        "cloth-simulation-draped-turntable.gif",
        "cloth-avatar-turntable.gif",
    ):
        assert asset in docs_readme
        assert f"docs/screenshots" in docs_readme


def test_documentation_separates_capability_boundary():
    user_guide = (ROOT / "docs" / "USER_GUIDE.md").read_text(encoding="utf-8")
    gates = (ROOT / "docs" / "RELEASE_GATES.md").read_text(encoding="utf-8")
    for term in ("grading/nesting", "construction hardware", "pressure/fit maps"):
        assert term in user_guide
        assert term in gates
