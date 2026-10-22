# Copyright (C) 2026 FreeCAD Cloth contributors
"""Contract tests for the diagnostic contact controls.

These checks protect diagnostic scope and the shared manifest contract without
making the diagnostic artifact a release gate.
"""

from pathlib import Path
from types import SimpleNamespace

from tests.support.assertions import require, require_contains
from tests.support.pbd_contact_helpers import checkpoint_record, connected_components, seam_geometry

_ROOT = Path(__file__).resolve().parents[1]
_SOURCE = (_ROOT / "tests" / "freecad_pbd_contact_diagnostics.py").read_text(encoding="utf-8")
_HELPERS = (_ROOT / "tests" / "support" / "pbd_contact_helpers.py").read_text(encoding="utf-8")
_WORKFLOW = (_ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(
    encoding="utf-8"
)


def _require_fragments(*, source: str, fragments: tuple[str, ...], contract: str) -> None:
    """Require each source fragment that makes up a named repository contract.

    Args:
        source: Source text inspected by the contract test.
        fragments: Exact source fragments that must remain present.
        contract: Short name used to explain a failed fragment check.
    """
    for fragment in fragments:
        require_contains(
            source=source,
            fragment=fragment,
            message=f"Missing {contract} fragment: {fragment!r}",
        )


def test_diagnostic_controls_are_static_and_one_step() -> None:
    """Verify contact diagnostic controls remain static, one-step, and outside release gates."""
    _require_fragments(
        source=_SOURCE,
        fragments=(
            '"control-0-cube"',
            '"control-0a-avatar"',
            "scene.Steps = 1",
            '"diagnostic-only-contact-controls"',
            '"release_gate_effect": "none"',
            "scene.GravityZ = 0.0",
        ),
        contract="diagnostic control",
    )


def test_diagnostic_manifest_contains_shared_schema_fields() -> None:
    """Verify the diagnostic manifest preserves all required shared schema fields."""
    _require_fragments(
        source=_SOURCE,
        fragments=(
            '"schema": 1',
            '"cases"',
            '"case_id"',
            '"predecessor_case_id"',
            '"case":',
            '"rung"',
            '"solver"',
            '"collision"',
            '"source_triangles"',
            '"solver_triangles"',
            '"pre_step"',
            '"piece_bounds"',
            '"checkpoints"',
            '"contact_state"',
            '"first_contact_step"',
            '"control"',
            '"release_gate_effect"',
        ),
        contract="diagnostic manifest",
    )


def test_canonical_workflow_uses_single_opt_in_dispatch_job() -> None:
    """Verify contact diagnostics run only through the single explicit opt-in dispatch job."""
    _require_fragments(
        source=_WORKFLOW,
        fragments=(
            "diagnostic_controls:",
            "diagnostic-pbd-contact:",
            "github.event_name == 'workflow_dispatch' && inputs.diagnostic_controls",
            "needs: [agent-quality, local_runner_readiness, pbd_validation_image]",
        ),
        contract="workflow dispatch",
    )
    require(
        condition="needs: [diagnostic-pbd-contact]" not in _WORKFLOW,
        message="The diagnostic-only job must not gate the normal simulation ladder.",
    )


def test_diagnostic_entrypoint_and_failure_evidence_are_explicit() -> None:
    """Verify the diagnostic entrypoint and its failure evidence remain explicit."""
    source_contracts = (
        (_WORKFLOW, "CLOTH_CONTACT_DIAGNOSTICS_EXECUTE=1"),
        (_SOURCE, 'os.environ.get("CLOTH_CONTACT_DIAGNOSTICS_EXECUTE") == "1"'),
        (_SOURCE, "CLOTH_CONTACT_DIAGNOSTICS_SCHEDULED"),
        (_SOURCE, "schedule_freecad_main(_scheduled_main)"),
        (_HELPERS, "QtCore.QTimer.singleShot(0, callback)"),
        (_SOURCE, "os._exit(status)"),
        (_SOURCE, "Gui.activeDocument().activeView()"),
        (_SOURCE, "solver_collision_surface"),
        (_HELPERS, "point_inside_closed_mesh"),
        (
            _HELPERS,
            "from freecad_cloth.simulation.DrapeVisualSanity import point_inside_closed_mesh",
        ),
        (_SOURCE, "make_shutdown_gui(_progress)"),
        (_HELPERS, "app.quit()"),
        (_HELPERS, "gui-shutdown-requested"),
        (_SOURCE, "faulthandler.dump_traceback_later(30.0, repeat=True"),
        (_SOURCE, "diagnostic contact controls start"),
        (_WORKFLOW, "test-script: tests/freecad_pbd_contact_diagnostics.py"),
        (_SOURCE, "ArrangementPoint.from_string"),
        (_SOURCE, "state = _inside_outside("),
        (_SOURCE, "float(candidate.x)"),
        (_SOURCE, "float(candidate.y)"),
        (_SOURCE, "float(candidate.z)"),
        (_SOURCE, "interior_seed_source"),
        (_SOURCE, "float(center.y) + 120.0"),
        (_SOURCE, "width=72.0"),
        (_HELPERS, 'mesh_is_inside = getattr(mesh, "isInside", None)'),
        (_SOURCE, "did not create a true interior pre-step state"),
        (_SOURCE, "pbd-env: collision_mode="),
        (_WORKFLOW, "diagnostic-pbd-contact:"),
        (_WORKFLOW, "artifacts/pbd-contact-diagnostics/app-run.log"),
    )
    for source, fragment in source_contracts:
        require_contains(
            source=source,
            fragment=fragment,
            message=f"Missing diagnostic entrypoint/evidence contract: {fragment!r}",
        )
    require(
        condition="App.exit()" not in _SOURCE,
        message="The diagnostic shutdown contract must not call App.exit().",
    )
    diagnostic_job = _WORKFLOW.split("  diagnostic-pbd-contact:", 1)[1].split(
        "  simulation-ladder:", 1
    )[0]
    _require_fragments(
        source=diagnostic_job,
        fragments=(
            "artifact-name: pbd-contact-diagnostics",
            "artifact-path: artifacts/pbd-contact-diagnostics/**",
        ),
        contract="diagnostic artifact",
    )


def test_workflow_validator_matches_shared_manifest() -> None:
    """Verify the canonical workflow invokes the shared manifest contract validator."""
    _require_fragments(
        source=_WORKFLOW,
        fragments=(
            "tools/ci/validate_manifests.py",
            "simulation-ladder",
            "artifact",
            "test-script: tests/freecad_pbd_contact_diagnostics.py",
            "validate_manifests.py",
        ),
        contract="workflow validator",
    )


def test_cube_ladder_diagnostic_job_has_scoped_branch_trigger() -> None:
    """Verify the cube collision ladder keeps its scoped branch trigger."""
    _require_fragments(
        source=_WORKFLOW,
        fragments=("contains(github.event.pull_request.head.ref, 'cube-ladder-2481')",),
        contract="cube-ladder trigger",
    )


def test_cube_ladder_caches_collision_proximity_mesh() -> None:
    """Verify the cube ladder reuses its collision proximity mesh during checkpoints."""
    source = (_ROOT / "tests" / "freecad_pbd_cube_ladder.py").read_text(encoding="utf-8")
    _require_fragments(
        source=source,
        fragments=(
            "proximity_mesh = trimesh.Trimesh(",
            "proximity_mesh.nearest.on_surface",
            "_surface_signed_clearance(",
            "source_shape,",
            "collision_surface,",
            "proximity_mesh,",
            "for step in CHECKPOINTS:",
            "scene.Steps = int(step)",
        ),
        contract="cube-ladder mesh cache",
    )


def test_cube_ladder_bootstrap_faulthandler_is_freecad_safe() -> None:
    """Verify FreeCAD-safe startup and traceback handling in the cube ladder."""
    source = (_ROOT / "tests" / "freecad_pbd_cube_ladder.py").read_text(encoding="utf-8")
    _require_fragments(
        source=source,
        fragments=(
            "runpy.run_path(",
            "from pbd_contact_helpers import",
            '_HELPER_DIR = Path(__file__).resolve().parent / "support"',
            "sys.path.insert(0, str(_HELPER_DIR))",
            "before-support-helper-import",
            "_TRACE_HANDLE = _BOOT_LOG.open(",
            "faulthandler.enable(file=_TRACE_HANDLE, all_threads=True)",
            "faulthandler.dump_traceback_later(30.0, repeat=True, file=_TRACE_HANDLE)",
            '_boot("script-start")',
            "_freecad_entrypoint_name = Path(__file__).stem",
            '_freecad_gui_hosted = bool(getattr(App, "GuiUp", False))',
            "def _schedule_freecad_main():",
            "schedule_freecad_main(_run_and_shutdown)",
            "QtCore.QTimer.singleShot(0, callback)",
            '_boot("freecad-hosted-entrypoint")',
            "__name__ == _freecad_entrypoint_name",
            '_boot("direct-entrypoint")',
        ),
        contract="cube-ladder startup",
    )
    require(
        condition="file=sys.stderr" not in source,
        message="The cube ladder must not redirect its traceback to stderr.",
    )


def test_progressive_collision_ladder_is_a_normal_gate() -> None:
    """Verify the progressive collision ladder remains a normal full-validation gate."""
    block = _WORKFLOW.split("  simulation-ladder:", 1)[1]
    _require_fragments(
        source=_WORKFLOW,
        fragments=(
            "simulation-ladder:",
            "CLOTH_PBD_SUBSTEPS: 8",
            "CLOTH_PBD_COLLISION_TOLERANCE_MM: 2",
            "artifact-name: simulation-collision-ladder",
        ),
        contract="simulation ladder",
    )
    _require_fragments(
        source=block,
        fragments=(
            "if: ${{ inputs.execution_mode == 'full' && github.event_name != 'schedule' }}",
            "test-script: tests/freecad_pbd_cube_ladder.py",
            "validate_manifests.py simulation",
            "artifact-name: simulation-collision-ladder",
            "artifact-path: artifacts/simulation-ladder/**",
        ),
        contract="simulation ladder gate",
    )


def test_shared_pbd_helpers_are_import_safe_and_keep_ladder_contracts_explicit() -> None:
    """Verify PBD support helpers remain import-safe and ladder contracts are explicit."""
    cube = (_ROOT / "tests" / "freecad_pbd_cube_ladder.py").read_text(encoding="utf-8")
    avatar = (_ROOT / "tests" / "freecad_pbd_avatar_ladder.py").read_text(encoding="utf-8")
    for source, fragments, contract in (
        (
            cube + avatar,
            ("runpy.run_path(",),
            "no runpy bootstrap",
        ),
        (
            cube,
            (
                "from pbd_contact_helpers import",
                '_HELPER_DIR = Path(__file__).resolve().parent / "support"',
                "_REPO_ROOT = Path(__file__).resolve().parents[1]",
                "sys.path.insert(0, str(_REPO_ROOT))",
                "sys.path.insert(0, str(_HELPER_DIR))",
            ),
            "cube-ladder helper",
        ),
        (
            avatar,
            (
                "from pbd_contact_helpers import",
                '_HELPER_DIR = Path(__file__).resolve().parent / "support"',
                "_REPO_ROOT = Path(__file__).resolve().parents[1]",
                "sys.path.insert(0, str(_REPO_ROOT))",
                "sys.path.insert(0, str(_HELPER_DIR))",
            ),
            "avatar-ladder helper",
        ),
        (
            _HELPERS,
            (
                "def build_scene(",
                "def checkpoint_record(",
            ),
            "shared PBD helper",
        ),
    ):
        if fragments == ("runpy.run_path(",):
            require(
                condition=fragments[0] not in source,
                message="PBD ladder scripts must not execute helpers via runpy.",
            )
        else:
            _require_fragments(source=source, fragments=fragments, contract=contract)
    require(
        condition='if __name__ == "__main__"' not in _HELPERS,
        message="The shared PBD helper module must remain import-safe.",
    )


def test_shared_checkpoint_builder_preserves_case_specific_contact_labels() -> None:
    """Verify checkpoint records retain case-specific contact labels."""
    backend = SimpleNamespace(positions=lambda: ((0.0, 0.0, 0.0), (0.0, 0.0, 2.0)))
    base = SimpleNamespace(backend=backend, seam_stitch_pairs={"side": ((0, 1),)})
    geometry = seam_geometry(backend, base.seam_stitch_pairs)
    require(
        condition=geometry[0]["max_span_mm"] == 2.0,
        message="The side seam span must match the two-millimeter diagnostic fixture.",
    )
    record = checkpoint_record(
        1,
        "step-001.png",
        backend.positions(),
        ((0, 1, 1),),
        2.0,
        2.0,
        base,
        connected_components,
        "diagnostic-only-cube",
    )
    require(
        condition=record["contact_state"] == "diagnostic-only-cube",
        message="The cube checkpoint must retain its diagnostic-only contact label.",
    )
    require(
        condition=record["components"] == 1,
        message="The cube checkpoint must preserve the single connected component.",
    )
    require(
        condition=record["penetration_mm"] == 0.0,
        message="The cube contact-control checkpoint must show zero penetration.",
    )
    require(
        condition=record["seam_world_spans_mm"] == geometry,
        message="Checkpoint seam measurements must match the reference geometry.",
    )
