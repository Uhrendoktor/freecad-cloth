# Copyright (C) 2026 FreeCAD Cloth contributors
"""Contract tests for the diagnostic avatar complexity ladder."""

from pathlib import Path

from tests.support.assertions import require_contains

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "tests" / "freecad_pbd_avatar_ladder.py").read_text(encoding="utf-8")
HELPERS = (ROOT / "tests" / "support" / "pbd_contact_helpers.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")


def test_avatar_ladder_contract_is_diagnostic_only_and_frozen() -> None:
    """Keep diagnostic ladder rungs, evidence fields, and workflow wiring frozen."""
    case_ids = (
        "rung-6-avatar-pinned",
        "rung-7-avatar-unpinned",
        "rung-8-avatar-two-piece-no-seam",
        "rung-9-avatar-two-piece-small-seam",
        "rung-10-avatar-two-piece-large-seam",
    )
    for case_id in case_ids:
        require_contains(
            source=SOURCE,
            fragment=case_id,
            message=f"Avatar ladder source is missing case identifier {case_id!r}.",
        )

    expected_source_fragments = (
        'target="avatar"',
        '"AvatarType", ""',
        '"ClothAvatar"',
        '"DrapeTarget"',
        '"ArrangementPoints"',
        '"shoulder_left"',
        '"hip"',
        "solver_collision_surface",
        '"placement_offsets_mm"',
        "dispatch_ladder_entrypoint(",
        "_ladder.schedule_freecad_main",
        "_ladder.capture_ladder_checkpoints(",
        "_ladder.build_ladder_case_record(",
        "_ladder.write_ladder_manifest(",
    )
    for fragment in expected_source_fragments:
        require_contains(
            source=SOURCE,
            fragment=fragment,
            message=f"Avatar ladder source is missing required fragment {fragment!r}.",
        )

    expected_shared_fragments = (
        "LADDER_CHECKPOINTS = (0, 1, 5, 15, 45, 90)",
        '"simulation-avatar-ladder"',
        '"release_gate_effect": "gate"',
        '"source_triangles"',
        '"solver_triangles"',
        '"seam_world_spans_mm"',
        "first_failing_rung",
    )
    for fragment in expected_shared_fragments:
        require_contains(
            source=HELPERS,
            fragment=fragment,
            message=f"Shared ladder helper is missing required fragment {fragment!r}.",
        )

    require_contains(
        source=WORKFLOW,
        fragment="test-script: tests/freecad_pbd_avatar_ladder.py",
        message="Canonical workflow must execute the avatar ladder script.",
    )
    require_contains(
        source=WORKFLOW,
        fragment="artifact",
        message="Canonical workflow must retain artifact handling for ladder evidence.",
    )
    require_contains(
        source=WORKFLOW,
        fragment="avatar-ladder-2482",
        message="Canonical workflow is missing the avatar ladder artifact identity.",
    )


def test_avatar_ladder_seam_controls_encode_near_zero_and_production_scale_pairs() -> None:
    """Keep the avatar ladder's near-zero and production-scale seam controls explicit."""
    expected_source_fragments = (
        "reversed_b=True",
        '"right_offset": 0.5',
        '"right_offset": 80.0',
        "max_span_mm",
        "min_span_mm",
    )
    for fragment in expected_source_fragments:
        require_contains(
            source=SOURCE,
            fragment=fragment,
            message=f"Avatar seam-control fixture is missing {fragment!r}.",
        )


def test_avatar_ladder_screenshot_path_is_fail_closed() -> None:
    """Keep screenshot capture validation and retry diagnostics fail-closed."""
    expected_source_fragments = (
        "def _avatar_png_has_visible_content(path, minimum_pixels=128):",
        "from freecad_cloth.common.VisualCaptureValidation import png_has_visible_content",
        "png_has_visible_content(path, minimum_pixels=int(minimum_pixels))",
        "def _avatar_screenshot(view, path):",
        "view.redraw()",
        "time.sleep(0.05)",
        "png-capture=retry",
        "PNG capture contains no visible rendered content",
    )
    for fragment in expected_source_fragments:
        require_contains(
            source=SOURCE,
            fragment=fragment,
            message=f"Avatar screenshot contract is missing {fragment!r}.",
        )
