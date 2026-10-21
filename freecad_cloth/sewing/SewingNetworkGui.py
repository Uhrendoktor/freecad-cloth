# Copyright (C) 2026 FreeCAD Cloth contributors
"""FreeCAD task panel for editing semantic sewing-network ranges.

The panel exposes the persisted M:N relationship directly and refuses to
silently edit a network whose canonical seam references are invalid.
"""

from itertools import starmap


def _modules():
    """Load the FreeCAD and Qt modules supported by the host runtime.

    Returns:
        Application, GUI, QtCore, and QtWidgets modules in that order.
    """
    import FreeCAD as App
    import FreeCADGui as Gui

    try:
        from PySide import QtCore, QtWidgets
    except ImportError:
        from PySide2 import QtCore, QtWidgets
    return App, Gui, QtCore, QtWidgets


def network_reference_errors(network: object) -> tuple[tuple[str, str], ...]:
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


def validate_network_for_edit(network: object) -> bool:
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

    def __init__(self, network: object) -> None:
        """Initialize the task panel from a persisted sewing network.

        Args:
            network: Network whose seam ranges and alignment will be edited.
        """
        App, Gui, QtCore, QtWidgets = _modules()
        self.App, self.Gui, self.QtCore = App, Gui, QtCore
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

        controls = QtWidgets.QFormLayout()
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

        columns = (
            "A piece",
            "A edge",
            "A start",
            "A end",
            "B piece",
            "B edge",
            "B start",
            "B end",
            "Direction",
            "Status",
        )
        self.table = QtWidgets.QTableWidget(len(seam_values), len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setObjectName("ClothSewingNetworkRangeTable")
        self._seams = seam_values
        for row, seam in enumerate(seam_values):
            values = (
                str(getattr(seam, "PieceA", "")),
                str(getattr(seam, "EdgeA", "")),
                float(getattr(seam, "StartA", 0.0)),
                float(getattr(seam, "EndA", 1.0)),
                str(getattr(seam, "PieceB", "")),
                str(getattr(seam, "EdgeB", "")),
                float(getattr(seam, "StartB", 0.0)),
                float(getattr(seam, "EndB", 1.0)),
                "reversed" if bool(getattr(seam, "ReversedB", False)) else "forward",
                str(getattr(seam, "Status", getattr(network, "Status", ""))),
            )
            for column, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(value))
                if column not in (2, 3, 6, 7):
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                self.table.setItem(row, column, item)
        layout.addWidget(self.table)
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

    def _range(self, row: int, column: int) -> float:
        """Parse and validate one normalized edge range from the table.

        Args:
            row: Table row containing the seam range.
            column: Table column containing its numeric value.

        Returns:
            Range endpoint constrained to the inclusive interval from zero to one.

        Raises:
            ValueError: If the cell is not numeric or its value is out of range.
        """
        try:
            value = float(self.table.item(row, column).text())
        except (TypeError, ValueError) as exc:
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


def show_sewing_network_task(network: object) -> SewingNetworkTaskPanel:
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
