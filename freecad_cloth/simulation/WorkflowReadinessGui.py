"""Derive an advisory setup checklist for the native cloth simulation workflow.

This module reads persistent FreeCAD document state but owns no document data. The
checklist is advisory: only the existing simulation runtime decides whether a
solver step is allowed.
"""

from collections.abc import Callable, Mapping
from pydantic.dataclasses import dataclass
from typing import Literal

WorkflowState = Literal["ready", "next", "review", "blocked", "info"]


@dataclass(frozen=True)
class WorkflowStep:
    """One human-readable status in the garment simulation setup checklist."""

    key: str
    label: str
    state: WorkflowState
    message: str


def build_workflow_checklist(
    scene: object | None,
    *,
    target_status_fn: Callable[[object | None], Mapping[str, object]] | None = None,
) -> tuple[WorkflowStep, ...]:
    """Derive setup guidance from the current scene and its document objects.

    Args:
        scene: Persistent simulation document object, or None when no simulation is selected.
        target_status_fn: Optional target-state provider, injectable for deterministic tests.

    Returns:
        Ordered checklist rows for pattern pieces, sewing, target, arrangement and simulation.

    Notes:
        The checklist is explanatory and never changes whether the runtime accepts a simulation.
        Missing sewing is a review prompt, not a hard blocker, because single or unsewn cloth
        tests are valid workflows.
    """
    if scene is None:
        return (
            WorkflowStep(
                "patterns",
                "Pattern pieces",
                "next",
                "Create pieces in Cloth Pattern, then assign them to a simulation.",
            ),
            WorkflowStep(
                "sewing",
                "Sewing",
                "info",
                "Define semantic sewing relationships when multiple pieces form one garment.",
            ),
            WorkflowStep(
                "target",
                "Drape target",
                "blocked",
                "Create or select a simulation with a current mannequin or FreeCAD geometry target.",
            ),
            WorkflowStep(
                "arrangement",
                "Arrangement",
                "info",
                "Use Arrange / Fit to place pieces and review their starting positions.",
            ),
            WorkflowStep(
                "simulation",
                "Simulation",
                "blocked",
                "Select or create a simulation scene before running a preview.",
            ),
        )

    document = getattr(scene, "Document", None)
    objects = tuple(getattr(document, "Objects", ()) or ())
    document_pieces = tuple(
        obj for obj in objects if str(getattr(obj, "PatternType", "")) == "PatternPiece"
    )
    assigned_pieces = tuple(
        obj
        for obj in (getattr(scene, "ClothPieces", ()) or ())
        if str(getattr(obj, "PatternType", "")) == "PatternPiece"
    )

    if assigned_pieces:
        pattern_step = WorkflowStep(
            "patterns",
            "Pattern pieces",
            "ready",
            f"{len(assigned_pieces)} pattern piece(s) assigned to this simulation.",
        )
    elif document_pieces:
        pattern_step = WorkflowStep(
            "patterns",
            "Pattern pieces",
            "next",
            f"{len(document_pieces)} piece(s) exist in the document, but none are assigned to this simulation.",
        )
    else:
        pattern_step = WorkflowStep(
            "patterns",
            "Pattern pieces",
            "next",
            "No PatternPiece found. Create editable pieces in Cloth Pattern, then assign them here.",
        )

    seam_count = sum(
        1
        for obj in objects
        if str(getattr(obj, "SewingType", "")) in {"Seam", "SewingOperation"}
        or str(getattr(obj, "GarmentRole", "")) in {"Seam", "SewingOperation"}
        or (
            bool(str(getattr(obj, "SeamId", "")))
            and getattr(obj, "PieceA", None) is not None
            and getattr(obj, "PieceB", None) is not None
        )
    )
    if len(assigned_pieces) < 2:
        sewing_step = WorkflowStep(
            "sewing",
            "Sewing",
            "info",
            "Sewing relationships are relevant when two or more pieces form one garment.",
        )
    elif seam_count:
        sewing_step = WorkflowStep(
            "sewing",
            "Sewing",
            "ready",
            f"{seam_count} semantic sewing relationship(s) found in the document; review intended pairings.",
        )
    else:
        sewing_step = WorkflowStep(
            "sewing",
            "Sewing",
            "review",
            "No semantic sewing relationship was found. Use Cloth Sewing if these pieces should be joined; unsewn tests remain valid.",
        )

    if target_status_fn is None:
        from freecad_cloth.simulation.DrapeTarget import target_status

        target_status_fn = target_status
    try:
        target_info = target_status_fn(getattr(scene, "DrapeTarget", None))
        target_state = str(target_info.get("state", "invalid"))
        target_message = str(target_info.get("message", "Target status is unavailable."))
    except (ImportError, AttributeError, RuntimeError, TypeError, ValueError) as exc:
        target_state = "invalid"
        target_message = f"Could not inspect the drape target: {exc}"
    target_ready = target_state == "ready"
    target_step = WorkflowStep(
        "target",
        "Drape target",
        "ready" if target_ready else "blocked",
        target_message,
    )

    fitting_scene = next(
        (obj for obj in objects if str(getattr(obj, "FittingType", "")) == "FittingScene"),
        None,
    )
    if fitting_scene is None:
        arrangement_step = WorkflowStep(
            "arrangement",
            "Arrangement",
            "info",
            "No saved Arrange / Fit scene found. Use Arrange / Fit to inspect placements or apply target snapping when needed.",
        )
    else:
        fitting_pieces = tuple(getattr(fitting_scene, "PatternPieces", ()) or ())
        placements = tuple(getattr(fitting_scene, "PiecePlacements", ()) or ())
        if (
            assigned_pieces
            and len(fitting_pieces) >= len(assigned_pieces)
            and len(placements) >= len(assigned_pieces)
        ):
            arrangement_step = WorkflowStep(
                "arrangement",
                "Arrangement",
                "ready",
                f"{len(placements)} saved placement(s) for {len(fitting_pieces)} fitting piece(s).",
            )
        else:
            arrangement_step = WorkflowStep(
                "arrangement",
                "Arrangement",
                "review",
                f"Fitting scene contains {len(fitting_pieces)} piece(s) and {len(placements)} saved placement(s). Review coverage in Arrange / Fit.",
            )

    simulation_ready = bool(assigned_pieces) and target_ready
    simulation_step = WorkflowStep(
        "simulation",
        "Simulation",
        "ready" if simulation_ready else "blocked",
        (
            "Minimum inputs are present. Review any sewing/arrangement notes, then run a short preview."
            if simulation_ready
            else "Assign at least one pattern piece and resolve the drape-target blocker before running."
        ),
    )
    return (
        pattern_step,
        sewing_step,
        target_step,
        arrangement_step,
        simulation_step,
    )
