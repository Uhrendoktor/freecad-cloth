# Copyright (C) 2026 FreeCAD Cloth contributors
"""Contract tests for staged sewing creation and preview error feedback."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from freecad_cloth.sewing.SewingCreationGui import SewingCreationSession, SewingCreationTaskPanel
from tests.support.assertions import require

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


@dataclass(slots=True)
class _SewingObject:
    """Minimal persisted sewing object returned by the creation callback."""

    Name: str
    SeamId: str
    Status: str


class _Selection:
    """In-memory selection adapter exposing the FreeCAD callback names."""

    def __init__(self, selected: Sequence[object] = ()) -> None:
        """Initialize selection state and bind its host-facing callback aliases.

        Args:
            selected: Objects selected before the staged operation begins.
        """
        self.selected = list(selected)
        self.getSelection = self.get_selection
        self.clearSelection = self.clear_selection
        self.addSelection = self.add_selection

    def get_selection(self) -> list[object]:
        """Return the currently selected objects.

        Returns:
            A copy of the selected-object sequence.
        """
        return list(self.selected)

    def clear_selection(self) -> None:
        """Remove every selected object."""
        self.selected = []

    def add_selection(self, obj: object) -> None:
        """Append one object to the current selection.

        Args:
            obj: Object selected by the staged creation session.
        """
        self.selected.append(obj)


class _Gui:
    """Minimal GUI boundary consumed by the staged creation session."""

    Selection: _Selection

    def __init__(self, selection: _Selection) -> None:
        """Bind the selection adapter.

        Args:
            selection: Selection state used to verify commit and cancellation.
        """
        self.Selection = selection


class _Document:
    """In-memory document implementing the transaction callbacks used by the session."""

    Objects: list[_SewingObject]
    calls: list[tuple[str, ...]]
    _snapshot: list[_SewingObject] | None

    def __init__(self) -> None:
        """Start with an empty object inventory and no active transaction."""
        self.Objects = []
        self.calls = []
        self._snapshot = None
        self.openTransaction = self.open_transaction
        self.commitTransaction = self.commit_transaction
        self.abortTransaction = self.abort_transaction
        self.recompute = self.recompute_document

    def open_transaction(self, name: str) -> None:
        """Record a transaction start and snapshot the current objects.

        Args:
            name: Human-readable transaction name supplied by the task panel.
        """
        self.calls.append(("open", name))
        self._snapshot = list(self.Objects)

    def commit_transaction(self) -> None:
        """Record transaction commit and discard the rollback snapshot."""
        self.calls.append(("commit",))
        self._snapshot = None

    def abort_transaction(self) -> None:
        """Restore the object inventory captured at transaction start."""
        self.calls.append(("abort",))
        if self._snapshot is not None:
            self.Objects = list(self._snapshot)
        self._snapshot = None

    def recompute_document(self) -> None:
        """Record document recomputation requests."""
        self.calls.append(("recompute",))


def _builder(
    doc: _Document,
    name: str = "Seam",
    status: str = "Valid",
) -> Callable[[], None]:
    """Create the callback that adds one sewing object to the fake document.

    Args:
        doc: Document that receives the created object.
        name: Object name exposed through the FreeCAD document inventory.
        status: Validation status inspected by the preview transaction.

    Returns:
        Callback that appends one sewing object when the session previews.
    """

    def build() -> None:
        """Append the configured sewing object to the document."""
        doc.Objects.append(_SewingObject(Name=name, SeamId="s1", Status=status))

    return build


def test_preview_commit_cancel_and_failed_preview_share_one_transaction_contract() -> None:
    """Preserve the single-transaction contract through commit, cancel, and rejection."""
    doc = _Document()
    anchor = SimpleNamespace(Name="PatternPiece")
    gui = _Gui(_Selection([anchor]))

    session = SewingCreationSession(doc, gui, "Create Seam", _builder(doc))
    preview = session.preview()
    require(condition=len(preview) == 1, message="Preview must stage exactly one sewing object.")
    require(
        condition=doc.Objects[0].Status == "Valid",
        message="A valid sewing object must remain staged before commit.",
    )
    require(
        condition=tuple(gui.Selection.selected) == preview,
        message="Preview must select the objects created by the transaction.",
    )
    session.commit()
    require(
        condition=[call[0] for call in doc.calls] == ["open", "recompute", "recompute", "commit"],
        message="Commit must recompute and close the original preview transaction.",
    )
    require(
        condition=len(doc.Objects) == 1,
        message="Commit must persist the staged sewing object.",
    )
    with pytest.raises(ValueError, match="already been committed"):
        session.commit()

    doc_cancel = _Document()
    gui_cancel = _Gui(_Selection([anchor]))
    session_cancel = SewingCreationSession(
        doc_cancel, gui_cancel, "Create Seam", _builder(doc_cancel)
    )
    session_cancel.preview()
    require(
        condition=len(doc_cancel.Objects) == 1,
        message="Preview must stage the sewing object before cancellation.",
    )
    session_cancel.cancel()
    require(
        condition=doc_cancel.Objects == [],
        message="Cancel must restore the document's pre-preview object inventory.",
    )
    require(
        condition=gui_cancel.Selection.selected == [anchor],
        message="Cancel must restore the selection that existed before preview.",
    )
    require(
        condition=("abort",) in doc_cancel.calls,
        message="Cancel must abort the active document transaction.",
    )

    doc_invalid = _Document()
    gui_invalid = _Gui(_Selection([anchor]))
    invalid = SewingCreationSession(
        doc_invalid,
        gui_invalid,
        "Create M:N Sewing",
        _builder(doc_invalid, name="SewingNetwork1", status="Length mismatch"),
    )
    with pytest.raises(ValueError, match=r"Preview validation failed.*Length mismatch"):
        invalid.preview()
    require(
        condition=doc_invalid.Objects == [],
        message="A rejected preview must roll back its newly created sewing object.",
    )
    require(
        condition=invalid.previewed is False,
        message="A rejected preview must not mark the session as successfully previewed.",
    )
    invalid.cancel()


class _FailedSession:
    """Session double that rejects preview before any object can be committed."""

    @staticmethod
    def preview() -> None:
        """Raise the validation error consumed by the public task-panel preview action.

        Raises:
            ValueError: Always, to model the rejection of an invalid edge selection.
        """
        msg = "select exactly two edges on pattern pieces"
        raise ValueError(msg)


class _ErrorFeedbackPanel(SewingCreationTaskPanel):
    """Task-panel fixture with only the collaborators used by its public preview action."""

    feedback: Mock
    commit_button: Mock
    session: _FailedSession

    def _stop_viewport_picking(self) -> None:
        """Skip viewport cleanup because the headless fixture has no active view."""

    def _refresh_selection(self) -> None:
        """Skip selection rendering because the headless fixture has no Qt widgets."""


def test_preview_error_feedback_is_actionable_and_disables_commit() -> None:
    """Show a useful validation message and keep Commit disabled after preview rejection."""
    panel = _ErrorFeedbackPanel.__new__(_ErrorFeedbackPanel)
    feedback = Mock(spec_set=("setText", "setWordWrap", "setProperty", "style", "update"))
    commit_button = Mock(spec_set=("setEnabled",))
    panel.feedback = feedback
    panel.commit_button = commit_button
    panel.session = _FailedSession()

    previewed = panel.preview()

    require(
        condition=previewed is False,
        message="A rejected staged preview must return false to the task-panel caller.",
    )
    feedback.setText.assert_called_once()
    message = str(feedback.setText.call_args.args[0])
    require(
        condition="Preview rejected" in message,
        message="The feedback label must identify that preview validation rejected the input.",
    )
    require(
        condition="Adjust the selection" in message,
        message="The feedback label must explain how the user can recover from the rejection.",
    )
    feedback.setProperty.assert_any_call("clothState", "error")
    commit_button.setEnabled.assert_called_once()
    require(
        condition=commit_button.setEnabled.call_args.args == (False,),
        message="Commit must be disabled after a preview validation error.",
    )
