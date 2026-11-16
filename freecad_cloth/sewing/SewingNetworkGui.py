# Copyright (C) 2026 FreeCAD Cloth contributors
"""FreeCAD task panel for editing semantic sewing-network ranges.

The panel exposes the persisted M:N relationship directly and refuses to
silently edit a network whose canonical seam references are invalid.
"""

from __future__ import annotations

from itertools import starmap
from types import ModuleType
from typing import TYPE_CHECKING, Protocol

from freecad_cloth.common.garment_document import FreeCADDocumentObjectProtocol

if TYPE_CHECKING:
    from collections.abc import Sequence


def _modules():
    """Load the FreeCAD and Qt modules supported by the host runtime.

    Returns:
        Application, GUI, QtCore, and QtWidgets modules in that order.
    """
    import FreeCAD as App
    import FreeCADGui as Gui

    if TYPE_CHECKING:
        from PySide2 import QtCore, QtWidgets
    else:
        try:
            from PySide import QtCore, QtWidgets
        except ImportError:
            from PySide2 import QtCore, QtWidgets
    return App, Gui, QtCore, QtWidgets


class _SeamFeature(FreeCADDocumentObjectProtocol, Protocol):
    """Persisted seam fields read and updated by the sewing-network editor."""

    Status: str
    SeamId: str
    PieceA: str
    PieceB: str
    EdgeA: str
    EdgeB: str
    StartA: float
    EndA: float
    StartB: float
    EndB: float
    Alignment: str
    ReversedB: bool


class _SewingNetworkFeature(FreeCADDocumentObjectProtocol, Protocol):
    """Persistent network identity and its ordered canonical seam members."""

    RelationshipId: str
    Seams: Sequence[_SeamFeature]


class _RangeEditor(Protocol):
    """Numeric Qt control used for one normalized seam-range endpoint."""

    def setRange(self, _minimum: float, _maximum: float) -> None:
        """Limit the editor to a normalized parameter interval."""
        ...

    def setDecimals(self, _decimals: int) -> None:
        """Set the displayed decimal precision."""
        ...

    def setSingleStep(self, _step: float) -> None:
        """Set the keyboard/wheel increment."""
        ...

    def setValue(self, _value: float) -> None:
        """Set the currently displayed endpoint."""
        ...

    def value(self) -> float:
        """Return the current numeric endpoint."""
        ...

    def setEnabled(self, _enabled: bool) -> None:
        """Enable or disable the endpoint editor."""
        ...


def network_reference_errors(network: _SewingNetworkFeature) -> tuple[tuple[str, str], ...]:
    """Collect non-valid statuses from canonical sewing-network members.

    Args:
        network: Persisted sewing-network object whose seam references are checked.

    Returns:
        Tuples pairing each invalid seam identifier with its recorded status.
    """
    errors = []
    for seam in tuple(getattr(network, "Seams", ()) or ()):
        status = str(getattr(seam, "Status", "Valid"))
        if status != "Valid":
            errors.append((str(getattr(seam, "SeamId", "")) or "<unnamed>", status))
    return tuple(errors)


def validate_network_for_edit(network: _SewingNetworkFeature) -> bool:
    """Check whether a persisted network can safely enter the editor.

    Args:
        network: Sewing-network object whose canonical seam references are checked.

    Returns:
        True when every seam reference has a valid status.

    Raises:
        ValueError: If one or more seam references are invalid.
    """
    errors = network_reference_errors(network)
    if errors:
        details = ", ".join(starmap("{}: {}".format, errors))
        raise ValueError("cannot edit sewing network with invalid seam references: " + details)
    return True


class SewingNetworkTaskPanel:
    """Native FreeCAD editor for canonical seam ranges in a sewing network."""

    _TRANSACTION_NAME = "Edit Sewing Network"

    def __init__(self, network: _SewingNetworkFeature) -> None:
        """Initialize the task panel from a persisted sewing network.

        Args:
            network: Network whose seam ranges and alignment will be edited.
        """
        App, Gui, _QtCore, QtWidgets = _modules()
        self.App, self.Gui = App, Gui
        self.network = network
        self.form = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(self.form)
        self.info = QtWidgets.QLabel(
            "Relationship {} — edit normalized edge ranges (0..1). Ranges are local to each referenced edge.".format(
                str(getattr(network, "RelationshipId", ""))
            )
        )
        self.info.setWordWrap(True)
        layout.addWidget(self.info)

        from freecad_cloth.common.UiDesign import configure_form_layout

        controls = QtWidgets.QFormLayout()
        configure_form_layout(controls, QtWidgets)
        self.alignment = QtWidgets.QComboBox()
        self.alignment.addItems(["endpoints", "uniform"])
        alignments = {
            str(getattr(seam, "Alignment", "endpoints"))
            for seam in tuple(getattr(network, "Seams", ()) or ())
        }
        current_alignment = sorted(alignments)[0] if alignments else "uniform"
        index = self.alignment.findText(current_alignment)
        self.alignment.setCurrentIndex(max(0, index))
        controls.addRow("Alignment", self.alignment)

        self.reversed_b = QtWidgets.QCheckBox("Reverse B correspondence")
        seam_values = tuple(getattr(network, "Seams", ()) or ())
        self.reversed_b.setChecked(
            bool(
                seam_values and all(bool(getattr(seam, "ReversedB", False)) for seam in seam_values)
            )
        )
        controls.addRow("Orientation", self.reversed_b)
        layout.addLayout(controls)

        errors = network_reference_errors(network)
        self.warning = QtWidgets.QLabel()
        self.warning.setWordWrap(True)
        self.warning.setObjectName("ClothSewingNetworkReferenceWarning")
        self.warning.setText(
            "Invalid seam references: " + "; ".join(starmap("{} ({})".format, errors))
            if errors
            else ""
        )
        layout.addWidget(self.warning)
        self.correspondence = QtWidgets.QLabel()
        self.correspondence.setWordWrap(True)
        self.correspondence.setObjectName("ClothSewingNetworkCorrespondenceEvidence")
        layout.addWidget(self.correspondence)

        self._seams = seam_values
        self._range_values = [
            (
                float(getattr(seam, "StartA", 0.0)),
                float(getattr(seam, "EndA", 1.0)),
                float(getattr(seam, "StartB", 0.0)),
                float(getattr(seam, "EndB", 1.0)),
            )
            for seam in seam_values
        ]
        self._current_row = -1
        self._loading_range = False

        seam_group = QtWidgets.QGroupBox("Seams")
        seam_layout = QtWidgets.QVBoxLayout(seam_group)
        self.seam_filter = QtWidgets.QLineEdit()
        self.seam_filter.setPlaceholderText("Filter by piece, edge or status…")
        self.seam_filter.setClearButtonEnabled(True)
        self.seam_filter.setToolTip("Search both sides of a seam and its validation status.")
        seam_layout.addWidget(self.seam_filter)
        self.seam_list = QtWidgets.QListWidget()
        self.seam_list.setObjectName("ClothSewingNetworkSeamList")
        self.seam_list.setMinimumHeight(90)
        self.seam_list.setMaximumHeight(170)
        self._seam_items = []
        for seam in seam_values:
            item = QtWidgets.QListWidgetItem(self._seam_caption(seam, network))
            item.setToolTip(self._seam_search_text(seam, network))
            self.seam_list.addItem(item)
            self._seam_items.append(item)
        seam_layout.addWidget(self.seam_list)
        layout.addWidget(seam_group)

        detail = QtWidgets.QGroupBox("Selected seam")
        detail_layout = QtWidgets.QVBoxLayout(detail)
        self.selected_seam_label = QtWidgets.QLabel("Select a seam to edit its ranges.")
        self.selected_seam_label.setWordWrap(True)
        detail_layout.addWidget(self.selected_seam_label)
        range_form = QtWidgets.QFormLayout()
        configure_form_layout(range_form, QtWidgets)
        self.start_a, self.end_a, self.start_b, self.end_b = (
            self._range_spin(QtWidgets) for _ in range(4)
        )
        self._range_fields = (self.start_a, self.end_a, self.start_b, self.end_b)
        for label, field in (
            ("Side A start (0-1)", self.start_a),
            ("Side A end (0-1)", self.end_a),
            ("Side B start (0-1)", self.start_b),
            ("Side B end (0-1)", self.end_b),
        ):
            range_form.addRow(label, field)
        detail_layout.addLayout(range_form)
        layout.addWidget(detail)

        self.seam_filter.textChanged.connect(self._filter_seams)
        self.seam_list.currentRowChanged.connect(self._select_seam_row)
        for field in self._range_fields:
            field.valueChanged.connect(self._selected_range_changed)
        if seam_values:
            self.seam_list.setCurrentRow(0)
        else:
            self._set_range_editor_enabled(False)
            self.selected_seam_label.setText("This network has no seam members.")

        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self._original = {
            "ranges": tuple(
                (
                    float(getattr(seam, "StartA", 0.0)),
                    float(getattr(seam, "EndA", 1.0)),
                    float(getattr(seam, "StartB", 0.0)),
                    float(getattr(seam, "EndB", 1.0)),
                )
                for seam in seam_values
            ),
            "alignment": tuple(
                str(getattr(seam, "Alignment", "endpoints")) for seam in seam_values
            ),
            "reversed_b": tuple(bool(getattr(seam, "ReversedB", False)) for seam in seam_values),
        }
        self._transaction_active = False
        self._begin_transaction()
        self._refresh_status()

        from freecad_cloth.common.UiDesign import apply_panel_style

        apply_panel_style(self.form)

    def _begin_transaction(self):
        """Start one FreeCAD undo transaction for the complete network edit."""
        doc = self.App.ActiveDocument
        opener = getattr(doc, "openTransaction", None) if doc is not None else None
        if callable(opener):
            opener(self._TRANSACTION_NAME)
            self._transaction_active = True

    def _commit_transaction(self) -> None:
        """Commit the active document transaction when the host supports it."""
        if not self._transaction_active:
            return
        doc = self.App.ActiveDocument
        committer = getattr(doc, "commitTransaction", None) if doc is not None else None
        if callable(committer):
            committer()
        self._transaction_active = False

    def _abort_transaction(self) -> bool:
        """Abort an active transaction when possible and clear its local state.

        Returns:
            Whether a document abort operation was available and performed.
        """
        if not self._transaction_active:
            return False
        doc = self.App.ActiveDocument
        aborter = getattr(doc, "abortTransaction", None) if doc is not None else None
        if callable(aborter):
            aborter()
            self._transaction_active = False
            return True
        self._transaction_active = False
        return False

    def _restore_original(self) -> None:
        """Restore the saved seam ranges, alignment, and correspondence direction."""
        if hasattr(self, "_range_values"):
            self._range_values = [tuple(values) for values in self._original["ranges"]]
            current_row = getattr(self, "_current_row", -1)
            if hasattr(self, "_range_fields") and 0 <= current_row < len(self._range_values):
                self._current_row = -1
                self._select_seam_row(current_row)
        for seam, ranges, alignment, reversed_b in zip(
            self._seams,
            self._original["ranges"],
            self._original["alignment"],
            self._original["reversed_b"],
            strict=False,
        ):
            seam.StartA, seam.EndA, seam.StartB, seam.EndB = ranges
            seam.Alignment = alignment
            seam.ReversedB = reversed_b

    @staticmethod
    def _range_spin(qt_widgets: ModuleType) -> _RangeEditor:
        """Create one precise normalized edge-range editor.

        Args:
            qt_widgets: QtWidgets module providing QDoubleSpinBox.

        Returns:
            A native numeric editor constrained to the normalized edge interval.
        """
        field = qt_widgets.QDoubleSpinBox()
        field.setRange(0.0, 1.0)
        field.setDecimals(4)
        field.setSingleStep(0.01)
        return field

    @staticmethod
    def _seam_search_text(seam: _SeamFeature, network: _SewingNetworkFeature) -> str:
        """Build searchable text from both seam sides and validation state.

        Args:
            seam: Seam whose identity and edge references are displayed.
            network: Parent network used as a status fallback.

        Returns:
            Case-folded search content for one seam-list entry.
        """
        return " ".join(
            str(value)
            for value in (
                getattr(seam, "SeamId", ""),
                getattr(seam, "PieceA", ""),
                getattr(seam, "EdgeA", ""),
                getattr(seam, "PieceB", ""),
                getattr(seam, "EdgeB", ""),
                getattr(seam, "Status", getattr(network, "Status", "")),
            )
        ).casefold()

    @staticmethod
    def _seam_caption(seam: _SeamFeature, network: _SewingNetworkFeature) -> str:
        """Create a compact row caption identifying both connected edges.

        Args:
            seam: Seam whose two pattern-edge references are summarized.
            network: Parent network used as a status fallback.

        Returns:
            One readable seam-list caption.
        """
        side_a = "{} / Edge {}".format(
            str(getattr(seam, "PieceA", "—")), str(getattr(seam, "EdgeA", "—"))
        )
        side_b = "{} / Edge {}".format(
            str(getattr(seam, "PieceB", "—")), str(getattr(seam, "EdgeB", "—"))
        )
        status = str(getattr(seam, "Status", getattr(network, "Status", "Unknown")))
        return f"{side_a}  ↔  {side_b}  ·  {status}"

    def _set_range_editor_enabled(self, enabled: bool) -> None:
        """Enable or disable the selected-seam numeric editor as one unit.

        Args:
            enabled: Whether a visible seam row is currently selected.
        """
        for field in getattr(self, "_range_fields", ()):
            field.setEnabled(bool(enabled))

    def _store_selected_range(self) -> None:
        """Copy the current four spin-box values into the staged seam record."""
        row = int(getattr(self, "_current_row", -1))
        ranges = getattr(self, "_range_values", ())
        fields = getattr(self, "_range_fields", ())
        if getattr(self, "_loading_range", False) or not 0 <= row < len(ranges) or len(fields) != 4:
            return
        self._range_values[row] = tuple(float(field.value()) for field in fields)

    def _select_seam_row(self, row: int) -> None:
        """Load a selected seam's staged range values into the detail editor.

        Args:
            row: Current zero-based seam-list row, or -1 when no row is selected.
        """
        self._store_selected_range()
        self._current_row = int(row)
        if not 0 <= self._current_row < len(self._seams):
            self.selected_seam_label.setText("No seams match the current filter.")
            self._set_range_editor_enabled(False)
            return
        seam = self._seams[self._current_row]
        self.selected_seam_label.setText(
            "Seam {} — {}".format(
                str(getattr(seam, "SeamId", self._current_row + 1)),
                str(getattr(seam, "Status", getattr(self.network, "Status", "Unknown"))),
            )
        )
        self._loading_range = True
        for field, value in zip(
            self._range_fields, self._range_values[self._current_row], strict=True
        ):
            field.setValue(float(value))
        self._loading_range = False
        self._set_range_editor_enabled(True)

    def _selected_range_changed(self, _value: float) -> None:
        """Update staged values when an active seam endpoint is edited."""
        if not getattr(self, "_loading_range", False):
            self._store_selected_range()

    def _filter_seams(self, query: str) -> None:
        """Filter seam rows by either piece, either edge, or status.

        Args:
            query: User-entered text used to filter the visible seam list.
        """
        needle = str(query).strip().casefold()
        visible_rows = []
        for row, item in enumerate(self._seam_items):
            hidden = bool(needle) and needle not in self._seam_search_text(
                self._seams[row], self.network
            )
            item.setHidden(hidden)
            if not hidden:
                visible_rows.append(row)
        if self.seam_list.currentRow() not in visible_rows:
            self.seam_list.setCurrentRow(visible_rows[0] if visible_rows else -1)

    def _range(self, row: int, column: int) -> float:
        """Parse and validate one normalized edge-range endpoint.

        Args:
            row: Seam index in the canonical network member sequence.
            column: Legacy endpoint selector (2, 3, 6, or 7).

        Returns:
            Range endpoint constrained to the inclusive interval from zero to one.

        Raises:
            ValueError: If the endpoint is not numeric or is outside the valid range.
        """
        column_index = {2: 0, 3: 1, 6: 2, 7: 3}.get(column)
        if column_index is None:
            msg = "unsupported seam range field"
            raise ValueError(msg)
        self._store_selected_range()
        try:
            ranges = getattr(self, "_range_values", None)
            if ranges is None:
                value = float(self.table.item(row, column).text())
            else:
                value = float(ranges[row][column_index])
        except (AttributeError, IndexError, TypeError, ValueError) as exc:
            msg = "range values must be numeric"
            raise ValueError(msg) from exc
        if not 0.0 <= value <= 1.0:
            msg = "range values must be between 0 and 1"
            raise ValueError(msg)
        return value

    def accept(self):
        """Validate all edits, then apply the complete network atomically.

        Raises:
            ValueError: If seam references or any edited normalized range is invalid.
        """
        validate_network_for_edit(self.network)
        values = []
        for row, seam in enumerate(self._seams):
            start_a, end_a = self._range(row, 2), self._range(row, 3)
            start_b, end_b = self._range(row, 6), self._range(row, 7)
            if start_a >= end_a or start_b >= end_b:
                msg = "seam ranges must have positive extent"
                raise ValueError(msg)
            values.append((seam, start_a, end_a, start_b, end_b))
        alignment = str(self.alignment.currentText())
        reversed_b = bool(self.reversed_b.isChecked())
        for seam, start_a, end_a, start_b, end_b in values:
            seam.StartA, seam.EndA = start_a, end_a
            seam.StartB, seam.EndB = start_b, end_b
            seam.Alignment = alignment
            seam.ReversedB = reversed_b
        self.App.ActiveDocument.recompute()
        if network_reference_errors(self.network):
            self._restore_original()
            self.App.ActiveDocument.recompute()
            self._abort_transaction()
            msg = "sewing network became invalid after edit"
            raise ValueError(msg)
        self._commit_transaction()
        self._refresh_status()
        return True

    def reject(self):
        """Cancel the task and discard the entire edit transaction when possible."""
        if not self._abort_transaction():
            self._restore_original()
        self.App.ActiveDocument.recompute()
        self._refresh_status()
        return True

    def _refresh_status(self):
        """Refresh the task-panel warning and persisted network status display."""
        from freecad_cloth.common.UiDesign import set_status

        errors = network_reference_errors(self.network)
        set_status(
            self.warning,
            "Invalid seam references: " + "; ".join(starmap("{} ({})".format, errors))
            if errors
            else "",
            state="error" if errors else "info",
        )
        network_status = str(getattr(self.network, "Status", ""))
        set_status(
            self.status,
            "%s | segments: %d | Δ %.3f mm%s"
            % (
                network_status,
                int(getattr(self.network, "SegmentCount", 0)),
                float(getattr(self.network, "LengthDifference", 0.0)),
                " | invalid: " + ", ".join(starmap("{} ({})".format, errors)) if errors else "",
            ),
            state=(
                "error" if errors else ("success" if network_status.lower() == "valid" else "info")
            ),
        )
        correspondence_status = str(getattr(self.network, "CorrespondenceStatus", ""))
        set_status(
            self.correspondence,
            "{} — severity {} — {} — recovery: {}".format(
                correspondence_status,
                str(getattr(self.network, "CorrespondenceSeverity", "")),
                str(getattr(self.network, "CorrespondenceMessage", "")),
                str(getattr(self.network, "CorrespondenceRecovery", "")),
            ),
            state=(
                "error"
                if errors or correspondence_status.lower() not in {"valid", "ok"}
                else "success"
            ),
        )

    def update(self):
        """Refresh values shown by the task panel after an external recompute."""
        self._refresh_status()

    def getStandardButtons(self):
        """Return the standard accept and cancel buttons for the task panel.

        Returns:
            Qt button flags for accepting or cancelling the edit transaction.
        """
        _App, _Gui, _QtCore, QtWidgets = _modules()
        return QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel


def show_sewing_network_task(network: _SewingNetworkFeature) -> SewingNetworkTaskPanel:
    """Display a sewing-network editor for the supplied network.

    Args:
        network: Persisted sewing network to edit.

    Returns:
        The task-panel instance shown by FreeCAD.
    """
    _App, Gui, _QtCore, _QtWidgets = _modules()
    panel = SewingNetworkTaskPanel(network)
    Gui.Control.showDialog(panel)
    return panel
