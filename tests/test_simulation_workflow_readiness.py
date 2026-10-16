"""Pure unit tests for the simulation workflow readiness checklist."""

from types import SimpleNamespace

from freecad_cloth.simulation.WorkflowReadiness import build_workflow_checklist


def _piece(name: str) -> SimpleNamespace:
    """Create a minimal PatternPiece-like test object."""
    return SimpleNamespace(Name=name, PatternType="PatternPiece")


def _scene(
    pieces: tuple[object, ...] = (),
    extra_objects: tuple[object, ...] = (),
    *,
    fitting: object | None = None,
) -> SimpleNamespace:
    """Create a minimal simulation and document for checklist tests."""
    objects = (*pieces, *extra_objects)
    if fitting is not None:
        objects = (*objects, fitting)
    document = SimpleNamespace(Objects=objects)
    return SimpleNamespace(
        Document=document,
        ClothPieces=pieces,
        DrapeTarget=object(),
    )


def _target_status(_target: object | None, state: str = "ready") -> dict[str, object]:
    """Return a deterministic target status for tests."""
    return {
        "state": state,
        "message": "Drape target is current" if state == "ready" else "Drape target needs refresh",
    }


def _by_key(scene: object | None, state: str = "ready") -> dict[str, object]:
    """Index checklist rows by stable key for readable assertions."""
    return {
        step.key: step
        for step in build_workflow_checklist(
            scene,
            target_status_fn=lambda target: _target_status(target, state),
        )
    }


def test_missing_scene_explains_first_steps_and_blocks_simulation() -> None:
    """A missing scene must produce actionable setup guidance."""
    rows = {step.key: step for step in build_workflow_checklist(None)}
    assert rows["patterns"].state == "next"
    assert rows["target"].state == "blocked"
    assert rows["simulation"].state == "blocked"
    assert "Cloth Pattern" in rows["patterns"].message


def test_unassigned_document_pieces_are_distinguished_from_missing_pieces() -> None:
    """The checklist must tell users when pieces exist but are not assigned."""
    piece = _piece("Front")
    scene = _scene((), (piece,))
    rows = _by_key(scene, "stale")
    assert rows["patterns"].state == "next"
    assert "exist in the document" in rows["patterns"].message
    assert rows["target"].state == "blocked"
    assert rows["simulation"].state == "blocked"


def test_unsewn_multi_piece_setup_is_reviewable_not_hard_blocked() -> None:
    """Unsewn panels should prompt review without blocking valid single-panel tests."""
    scene = _scene((_piece("Front"), _piece("Back")))
    rows = _by_key(scene)
    assert rows["patterns"].state == "ready"
    assert rows["sewing"].state == "review"
    assert rows["target"].state == "ready"
    assert rows["simulation"].state == "ready"
    assert "unsewn tests remain valid" in rows["sewing"].message


def test_sewn_and_fully_placed_garment_reports_ready_arrangement() -> None:
    """A multi-piece scene with seams and persistent placements reports full readiness."""
    front = _piece("Front")
    back = _piece("Back")
    seam = SimpleNamespace(
        SewingType="Seam",
        SeamId="seam-front-back",
        PieceA=front,
        PieceB=back,
    )
    fitting = SimpleNamespace(
        FittingType="FittingScene",
        PatternPieces=(front, back),
        PiecePlacements=(object(), object()),
    )
    scene = _scene((front, back), (seam,), fitting=fitting)
    rows = _by_key(scene)
    assert rows["sewing"].state == "ready"
    assert rows["arrangement"].state == "ready"
    assert "2 saved placement(s)" in rows["arrangement"].message


def test_target_inspection_failure_fails_closed() -> None:
    """Unexpected target-status failures must not advertise simulation readiness."""
    def fail(_target: object | None) -> dict[str, object]:
        raise RuntimeError("stale collision cache")

    rows = {
        step.key: step
        for step in build_workflow_checklist(_scene((_piece("Panel"),)), target_status_fn=fail)
    }
    assert rows["target"].state == "blocked"
    assert rows["simulation"].state == "blocked"
    assert "stale collision cache" in rows["target"].message
