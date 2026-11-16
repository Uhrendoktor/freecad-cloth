# Copyright (C) 2026 FreeCAD Cloth contributors
"""FreeCAD task panel for explicit semantic-edge topology repair."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from freecad_cloth.common.garment_document import FreeCADDocumentObjectProtocol

if TYPE_CHECKING:
    from types import ModuleType

    from PySide2 import QtWidgets as _QT_TYPE_QtWidgets


def _gui_modules() -> tuple[ModuleType, ModuleType]:
    import FreeCADGui as Gui

    if TYPE_CHECKING:
        QtWidgets = _QT_TYPE_QtWidgets
    else:
        try:
            from PySide import QtWidgets
        except ImportError:
            from PySide2 import QtWidgets
    return Gui, QtWidgets


class _TopologyRepairViewportPicker:
    """Resolve one viewport edge pick for one explicit seam-side repair row."""

    def __init__(
        self,
        panel: PatternTopologyRepairTaskPanel,
        seam: FreeCADDocumentObjectProtocol,
        side: str,
        combo: _QT_TYPE_QtWidgets.QComboBox,
    ) -> None:
        """Register a one-shot selection observer scoped to one seam side.

        Args:
            panel: Topology-repair task panel owning this picker.
            seam: Seam whose current edge reference is being repaired.
            side: Side A or B that the replacement edge must belong to.
            combo: Existing row selector that receives the stable semantic edge ID.
        """
        self.panel = panel
        self.seam = seam
        self.side = str(side).upper()
        self.combo = combo
        self.expected_piece = getattr(seam, "Pattern" + self.side, None)
        if self.expected_piece is None:
            raise ValueError(f"seam side {self.side} has no source PatternPiece")
        if str(getattr(self.expected_piece, "GeometryAuthority", "")) != "Sketcher":
            raise ValueError("viewport picking requires the native Sketcher authority")
        self.expected_sketch = getattr(self.expected_piece, "Sketch", None)
        if self.expected_sketch is None:
            raise ValueError("the selected seam side has no linked native Sketch")
        sketch_document = getattr(self.expected_sketch, "Document", None)
        panel_document_name = str(getattr(panel.doc, "Name", ""))
        sketch_document_name = str(getattr(sketch_document, "Name", ""))
        if (
            sketch_document is not None
            and panel_document_name
            and sketch_document_name
            and sketch_document_name != panel_document_name
        ):
            raise ValueError("the linked native Sketch belongs to another document")
        self.piece_view = getattr(self.expected_piece, "ViewObject", None)
        self.sketch_view = getattr(self.expected_sketch, "ViewObject", None)
        if self.piece_view is None or self.sketch_view is None:
            raise ValueError("the source Sketch and PatternPiece must expose native view objects")
        self._piece_was_visible = bool(getattr(self.piece_view, "Visibility", True))
        self._sketch_was_visible = bool(getattr(self.sketch_view, "Visibility", True))
        self.Gui = panel.Gui
        self.armed = True
        try:
            self.Gui.Selection.addObserver(self)
            # The rendered PatternPiece may include seam-allowance offsets. Show the
            # authoritative Sketch itself so EdgeN identifies native Sketcher geometry.
            self.piece_view.Visibility = False
            self.sketch_view.Visibility = True
            update_gui = getattr(self.Gui, "updateGui", None)
            if callable(update_gui):
                update_gui()
        except Exception:
            self.dispose()
            raise

    def addSelection(
        self,
        document_name: str,
        object_name: str,
        subelement_name: str,
        *_position: float,
    ) -> None:
        """Accept only the selected seam side's current native Sketcher edge.

        Args:
            document_name: Internal document name reported by FreeCAD.
            object_name: Internal name of the temporarily shown native Sketcher object.
            subelement_name: Native Sketch edge selector such as Edge3.
            *_position: Optional picked world coordinates supplied by FreeCAD.
        """
        if not self.armed:
            return
        expected_document = str(getattr(self.panel.doc, "Name", ""))
        if document_name and expected_document and str(document_name) != expected_document:
            self.panel._set_status(
                "Pick an edge from the active document.",
                state="warning",
            )
            return
        expected_name = str(getattr(self.expected_sketch, "Name", ""))
        selected_name = str(object_name or "")
        if selected_name != expected_name:
            self.panel._set_status(
                f"Pick an edge on the temporarily shown native Sketch linked "
                f"to seam side {self.side}.",
                state="warning",
            )
            return
        match = re.fullmatch(r"Edge\s*(\d+)", str(subelement_name or ""), flags=re.IGNORECASE)
        if match is None or int(match.group(1)) < 1:
            self.panel._set_status(
                "Pick a current outline edge, not a face or empty viewport space.",
                state="warning",
            )
            return
        try:
            from freecad_cloth.pattern.PatternTopologyRepair import (
                current_edge_candidate_for_sketch_index,
            )

            record = current_edge_candidate_for_sketch_index(
                self.seam,
                self.side,
                int(match.group(1)) - 1,
            )
            edge_id = str(record["id"])
        except (AttributeError, KeyError, RuntimeError, TypeError, ValueError) as exc:
            self.panel._set_status(
                f"That viewport edge is not a current semantic boundary — {exc}.",
                state="warning",
            )
            return
        index = self.combo.findData(edge_id)
        if index < 0:
            self.panel._set_status(
                "The picked edge is not available in this seam-side repair row.",
                state="warning",
            )
            return
        self.combo.setCurrentIndex(index)
        label = str(getattr(self.expected_piece, "Label", ""))
        if not label:
            label = str(getattr(self.expected_piece, "Name", "PatternPiece"))
        sketch_label = str(getattr(self.expected_sketch, "Label", expected_name))
        self.dispose()
        self.panel._set_status(
            "Mapped seam {} side {} to native Sketch {} / {} ({}).".format(
                str(getattr(self.seam, "SeamId", "")),
                self.side,
                sketch_label,
                subelement_name,
                label,
            ),
            state="success",
        )

    def dispose(self) -> None:
        """Unregister the observer and return the panel to normal repair mode."""
        if not self.armed:
            return
        self.armed = False
        try:
            self.Gui.Selection.removeObserver(self)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            pass
        try:
            self.piece_view.Visibility = self._piece_was_visible
            self.sketch_view.Visibility = self._sketch_was_visible
            update_gui = getattr(self.Gui, "updateGui", None)
            if callable(update_gui):
                update_gui()
        except (AttributeError, RuntimeError, TypeError, ValueError):
            pass
        if self.panel._active_picker is self:
            self.panel._active_picker = None
        self.panel.cancel_pick_button.setVisible(False)


class PatternTopologyRepairTaskPanel:
    """Show invalid seam sides and require an explicit current-edge mapping."""

    def __init__(self, doc):
        Gui, QtWidgets = _gui_modules()
        from freecad_cloth.pattern.PatternTopologyRepair import (
            current_edge_candidates,
            invalid_seam_sides,
        )

        self.Gui = Gui
        self.doc = doc
        self._active_picker = None
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle("Cloth Pattern — Repair topology")
        outer = QtWidgets.QVBoxLayout(self.form)
        outer.addWidget(
            QtWidgets.QLabel(
                "Sketch topology changed. Select the intended current edge for each invalid "
                "seam side. Nothing is remapped automatically."
            )
        )
        self.rows = []
        grid_content = QtWidgets.QWidget()
        grid = QtWidgets.QVBoxLayout(grid_content)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(6)
        for seam, side, reason in invalid_seam_sides(doc):
            seam_label = str(getattr(seam, "Label", getattr(seam, "Name", "Seam")))
            row_group = QtWidgets.QGroupBox(f"{seam_label} — Side {side}")
            row_layout = QtWidgets.QVBoxLayout(row_group)
            reason_label = QtWidgets.QLabel(f"Reference status: {reason}")
            reason_label.setWordWrap(True)
            row_layout.addWidget(reason_label)
            edge_controls = QtWidgets.QHBoxLayout()
            combo = QtWidgets.QComboBox()
            combo.addItem("Leave unresolved", "")
            for record in current_edge_candidates(seam, side):
                combo.addItem(str(record["id"]), str(record["id"]))
            edge_controls.addWidget(combo, 1)
            pick_button = QtWidgets.QPushButton("Pick in 3D")
            pick_button.setToolTip(
                "Temporarily show the linked native Sketch and pick its exact boundary edge."
            )
            linked_piece = getattr(seam, "Pattern" + str(side).upper(), None)
            linked_sketch = getattr(linked_piece, "Sketch", None)
            pick_button.setEnabled(
                combo.count() > 1
                and linked_sketch is not None
                and str(getattr(linked_piece, "GeometryAuthority", "")) == "Sketcher"
            )
            pick_button.clicked.connect(
                lambda _checked=False, target=seam, target_side=side, selector=combo: (
                    self._begin_viewport_pick(target, target_side, selector)
                )
            )
            edge_controls.addWidget(pick_button)
            row_layout.addLayout(edge_controls)
            grid.addWidget(row_group)
            self.rows.append((seam, side, combo, pick_button))
        grid.addStretch(1)
        from freecad_cloth.common.UiDesign import make_scroll_area

        outer.addWidget(make_scroll_area(grid_content, QtWidgets), 1)
        self.cancel_pick_button = QtWidgets.QPushButton("Cancel viewport pick")
        self.cancel_pick_button.setVisible(False)
        self.cancel_pick_button.clicked.connect(self._cancel_viewport_pick)
        outer.addWidget(self.cancel_pick_button)
        self.status = QtWidgets.QLabel(
            "%d invalid seam side(s) require an explicit mapping." % len(self.rows)
        )
        outer.addWidget(self.status)

        from freecad_cloth.common.UiDesign import apply_panel_style, mark_button, set_status

        set_status(
            self.status,
            self.status.text(),
            state="warning" if self.rows else "info",
        )
        for _seam, _side, _combo, pick_button in self.rows:
            mark_button(pick_button, "secondary")
        mark_button(self.cancel_pick_button, "secondary")
        apply_panel_style(self.form)

    def _begin_viewport_pick(
        self,
        seam: FreeCADDocumentObjectProtocol,
        side: str,
        combo: _QT_TYPE_QtWidgets.QComboBox,
    ) -> None:
        """Arm a one-shot viewport picker for one explicitly selected repair row.

        Args:
            seam: Seam feature containing the invalid side.
            side: A or B side whose linked Sketcher edge must be picked.
            combo: Row combo box receiving the selected semantic edge ID.
        """
        if self._active_picker is not None:
            self._cancel_viewport_pick()
        try:
            self._active_picker = _TopologyRepairViewportPicker(self, seam, side, combo)
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            self._active_picker = None
            self._set_status(
                f"Viewport picking is unavailable — {exc}. Use the edge selector instead.",
                state="warning",
            )
            return
        self.cancel_pick_button.setVisible(True)
        piece = getattr(seam, "Pattern" + str(side).upper(), None)
        sketch = getattr(piece, "Sketch", None)
        sketch_label = str(getattr(sketch, "Label", "the native Sketch"))
        piece_label = str(getattr(piece, "Label", "PatternPiece"))
        self._set_status(
            f"The linked Sketch '{sketch_label}' is shown temporarily; pick its current boundary edge "
            f"for seam side {side} ({piece_label}).",
            state="info",
        )

    def _cancel_viewport_pick(self) -> None:
        """Stop the active viewport selection observer without modifying seam data."""
        picker = self._active_picker
        if picker is None:
            return
        picker.dispose()
        self._set_status(
            "Viewport edge pick cancelled; no topology references were changed.",
            state="info",
        )

    def _set_status(self, message: str, *, state: str = "info") -> None:
        """Display semantic feedback using the shared task-panel status vocabulary.

        Args:
            message: User-facing repair or viewport-picking state.
            state: Information, warning, error, or success presentation role.
        """
        from freecad_cloth.common.UiDesign import set_status

        set_status(self.status, message, state=state)

    def accept(self):
        from freecad_cloth.pattern.PatternTopologyRepair import apply_repair_plan

        if self._active_picker is not None:
            self._cancel_viewport_pick()
        repairs = [
            (seam, side, combo.currentData())
            for seam, side, combo, _pick_button in self.rows
            if combo.currentData()
        ]
        if not repairs:
            from freecad_cloth.common.UiDesign import set_status

            set_status(
                self.status,
                "Select at least one replacement edge before applying repair.",
                state="warning",
            )
            return False
        try:
            plan = apply_repair_plan(self.doc, repairs)
        except Exception as exc:
            from freecad_cloth.common.UiDesign import set_status

            set_status(self.status, f"Repair failed: {exc}", state="error")
            return False
        from freecad_cloth.common.UiDesign import set_status

        set_status(self.status, "Repaired %d seam side(s)." % len(plan), state="success")
        self.Gui.Control.closeDialog()
        return True

    def reject(self):
        if self._active_picker is not None:
            self._cancel_viewport_pick()
        self.Gui.Control.closeDialog()
        return True

    def getStandardButtons(self):
        return 0x00000400 | 0x00800000


def show_topology_repair_task(doc):
    Gui, _QtWidgets = _gui_modules()
    panel = PatternTopologyRepairTaskPanel(doc)
    Gui.Control.showDialog(panel)
    return panel
