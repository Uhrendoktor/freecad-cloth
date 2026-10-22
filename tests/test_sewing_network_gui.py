# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression tests for sewing-network GUI validation and transaction behavior."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class _TaskPanelLabel:
    """Capture the label API used by sewing task panels without a GUI."""

    text: str
    properties: dict[str, str]

    def __init__(self) -> None:
        """Initialize empty label text and dynamic properties."""
        self.text = ""
        self.properties = {}

    def setText(self, text: str) -> None:
        """Store the text displayed by the simulated label.

        Args:
            text: Text the task panel requests the label to display.
        """
        self.text = text

    def setWordWrap(self, _value: bool) -> None:
        """Accept the task panel's word-wrapping request.

        Args:
            _value: Whether text wrapping should be enabled.
        """
        del _value

    def setProperty(self, name: str, value: str) -> None:
        """Store a dynamic Qt-style property for the test double.

        Args:
            name: Name of the dynamic property.
            value: Property value to store.
        """
        self.properties[name] = value

    def style(self) -> None:
        """Accept style inspection without providing a GUI style object."""

    def update(self) -> None:
        """Accept a repaint request without opening a graphical interface."""


class _ReferenceSeam:
    """Model the identity and validation status of one network seam."""

    def __init__(self, seam_id: object, status: object = "Valid") -> None:
        """Initialize the seam identity and reference status.

        Args:
            seam_id: Stable identifier used in validation diagnostics.
            status: Reference status reported by the seam fixture.
        """
        self.SeamId = seam_id
        self.Status = status


class _ReferenceNetwork:
    """Provide the seam collection consumed by sewing-network validators."""

    def __init__(self, seams: object) -> None:
        """Initialize a network with the supplied seam collection.

        Args:
            seams: Seam fixture collection exposed to validation helpers.
        """
        self.Seams = seams


def test_sewing_network_gui_contract_is_headless_importable() -> None:
    """Verify the sewing-network GUI imports without a graphical session."""
    from freecad_cloth.sewing import SewingNetworkGui

    assert hasattr(SewingNetworkGui, "SewingNetworkTaskPanel")
    assert hasattr(SewingNetworkGui, "show_sewing_network_task")


def test_network_task_panel_uses_transactional_editor_contract() -> None:
    """Verify the task panel exposes its transactional edit lifecycle."""
    from freecad_cloth.sewing.SewingNetworkGui import SewingNetworkTaskPanel

    assert SewingNetworkTaskPanel._TRANSACTION_NAME == "Edit Sewing Network"
    assert hasattr(SewingNetworkTaskPanel, "_begin_transaction")
    assert hasattr(SewingNetworkTaskPanel, "_commit_transaction")
    assert hasattr(SewingNetworkTaskPanel, "_abort_transaction")
    assert hasattr(SewingNetworkTaskPanel, "_restore_original")


def test_network_task_panel_restores_all_persisted_member_settings() -> None:
    """Verify restoration returns saved seam ranges and correspondence settings."""
    from freecad_cloth.sewing.SewingNetworkGui import SewingNetworkTaskPanel

    class Seam:
        """Represent seam parameters and identity used by a panel test."""

        def __init__(self) -> None:
            """Initialize deterministic seam parameter and correspondence state."""
            self.StartA = 0.2
            self.EndA = 0.8
            self.StartB = 0.1
            self.EndB = 0.9
            self.Alignment = "uniform"
            self.ReversedB = True

    seam = Seam()
    panel = SewingNetworkTaskPanel.__new__(SewingNetworkTaskPanel)
    panel._seams = (seam,)
    panel._original = {
        "ranges": ((0.0, 1.0, 0.0, 1.0),),
        "alignment": ("endpoints",),
        "reversed_b": (False,),
    }
    panel._restore_original()
    assert (seam.StartA, seam.EndA, seam.StartB, seam.EndB) == (0.0, 1.0, 0.0, 1.0)
    assert seam.Alignment == "endpoints"
    assert seam.ReversedB is False


def test_network_task_panel_commit_is_one_document_transaction() -> None:
    """Verify acceptance commits editor changes in one document transaction."""
    from freecad_cloth.sewing.SewingNetworkGui import SewingNetworkTaskPanel

    class Doc:
        """Capture document transactions and recomputation requested by the panel."""

        def __init__(self) -> None:
            """Start an empty log of document operations."""
            self.calls = []

        def openTransaction(self, name: str) -> None:
            """Record the name of a newly opened document transaction.

            Args:
                name: The document transaction name to record.
            """
            self.calls.append(("open", name))

        def commitTransaction(self) -> None:
            """Record that the current document transaction was committed."""
            self.calls.append(("commit",))

        def abortTransaction(self) -> None:
            """Record that the current document transaction was aborted."""
            self.calls.append(("abort",))

    class App:
        """Expose the simulated active document to the task panel."""

        ActiveDocument = Doc()

    panel = SewingNetworkTaskPanel.__new__(SewingNetworkTaskPanel)
    panel.App = App
    panel._transaction_active = False
    panel._begin_transaction()
    panel._commit_transaction()
    assert App.ActiveDocument.calls == [("open", "Edit Sewing Network"), ("commit",)]


def test_network_task_panel_cancel_aborts_transaction_and_refreshes_warning() -> None:
    """Verify cancel aborts edits and refreshes warning state."""
    from freecad_cloth.sewing.SewingNetworkGui import SewingNetworkTaskPanel

    class Doc:
        """Capture document transactions and recomputation requested by the panel."""

        def __init__(self) -> None:
            """Start an empty log of document operations."""
            self.calls = []

        def abortTransaction(self) -> None:
            """Record that the current document transaction was aborted."""
            self.calls.append(("abort",))

        def recompute(self) -> None:
            """Record a document recomputation request."""
            self.calls.append(("recompute",))

    class App:
        """Expose the simulated active document to the task panel."""

        ActiveDocument = Doc()

    class Network:
        """Represent sewing-network status and seam membership for validation."""

        Status = "Invalid"
        SegmentCount = 0
        LengthDifference = 0.0
        Seams = ()

    panel = SewingNetworkTaskPanel.__new__(SewingNetworkTaskPanel)
    panel.App = App
    panel.network = Network()
    panel.warning = _TaskPanelLabel()
    panel.status = _TaskPanelLabel()
    panel.correspondence = _TaskPanelLabel()
    panel._transaction_active = True
    panel.reject()
    assert App.ActiveDocument.calls == [("abort",), ("recompute",)]
    assert panel._transaction_active is False
    assert panel.warning.text == ""


def test_network_task_panel_invalid_recompute_restores_and_aborts() -> None:
    """Verify invalid recomputation restores values and aborts the transaction.

    Raises:
        AssertionError: If restoration or transaction-abort expectations are not met.
        ValueError: If invalid recomputation escapes without restoring prior values.
    """
    from freecad_cloth.sewing.SewingNetworkGui import SewingNetworkTaskPanel

    class Seam:
        """Represent seam parameters and identity used by a panel test."""

        SeamId = "s1"
        Status = "Valid"
        StartA = 0.2
        EndA = 0.8
        StartB = 0.1
        EndB = 0.9
        Alignment = "uniform"
        ReversedB = True

    class Network:
        """Represent sewing-network status and seam membership for validation."""

        Seams = (Seam(),)
        Status = "Valid"
        SegmentCount = 1
        LengthDifference = 0.0

    class Doc:
        """Capture document transactions and recomputation requested by the panel."""

        def __init__(self, network: object) -> None:
            """Start an empty log of document operations.

            Args:
                network: The network used by this test fixture.
            """
            self.network = network
            self.calls = []

        def recompute(self) -> None:
            """Record a document recomputation request."""
            self.calls.append("recompute")
            self.network.Seams[0].Status = "Missing reference"

        def abortTransaction(self) -> None:
            """Record that the current document transaction was aborted."""
            self.calls.append("abort")

    class App:
        """Expose the simulated active document to the task panel."""

    class Item:
        """Represent the display text for one network table item."""

        def __init__(self, value: object) -> None:
            """Store the display text supplied for this item.

            Args:
                value: The value represented by this simulated control.
            """
            self.value = value

        def text(self) -> object:
            """Return the text stored by this table item.

            Returns:
                The display text stored by the item.
            """
            return str(self.value)

    class Table:
        """Provide row-indexed items through the network table interface."""

        def __init__(self) -> None:
            """Initialize the simulated table's row-item mapping."""
            self.values = {(0, 2): 0.3, (0, 3): 0.7, (0, 6): 0.2, (0, 7): 0.8}

        def item(self, row: int, column: object) -> object:
            """Return the table item mapped to the requested row.

            Args:
                row: The zero-based row index to retrieve.
                column: The column used by this test fixture.

            Returns:
                The table item for the requested row.
            """
            return Item(self.values[row, column])

    class Combo:
        """Provide the selected alignment option for the editor."""

        def currentText(self) -> str:
            """Return the alignment option selected by this test fixture.

            Returns:
                The selected alignment option.
            """
            return "endpoints"

    class Check:
        """Provide a deterministic checkbox state for the editor."""

        def isChecked(self) -> bool:
            """Return the configured checkbox state.

            Returns:
                The configured checkbox state.
            """
            return False

    App.ActiveDocument = Doc(Network())
    panel = SewingNetworkTaskPanel.__new__(SewingNetworkTaskPanel)
    panel.App = App
    panel.network = App.ActiveDocument.network
    panel._seams = panel.network.Seams
    panel._original = {
        "ranges": ((0.2, 0.8, 0.1, 0.9),),
        "alignment": ("uniform",),
        "reversed_b": (True,),
    }
    panel.table = Table()
    panel.alignment = Combo()
    panel.reversed_b = Check()
    panel.warning = type("Label", (), {"setText": lambda self, text: None})()
    panel.status = type("Label", (), {"setText": lambda self, text: None})()
    panel.correspondence = type("Label", (), {"setText": lambda self, text: None})()
    panel._transaction_active = True
    try:
        panel.accept()
    except ValueError as exc:
        assert "became invalid after edit" in str(exc)
    else:
        msg = "invalid recompute was silently accepted"
        raise AssertionError(msg)
    seam = panel._seams[0]
    assert (seam.StartA, seam.EndA, seam.StartB, seam.EndB) == (0.2, 0.8, 0.1, 0.9)
    assert seam.Alignment == "uniform"
    assert seam.ReversedB is True
    assert App.ActiveDocument.calls == ["recompute", "recompute", "abort"]
    assert panel._transaction_active is False


def test_network_task_panel_update_refreshes_invalid_reference_warning() -> None:
    """Verify refresh reports invalid seam references in the task panel."""
    from freecad_cloth.sewing.SewingNetworkGui import SewingNetworkTaskPanel

    class Seam:
        """Represent seam parameters and identity used by a panel test."""

        SeamId = "s2"
        Status = "Missing reference"

    class Network:
        """Represent sewing-network status and seam membership for validation."""

        Seams = (Seam(),)
        Status = "Invalid"
        SegmentCount = 0
        LengthDifference = 0.0

    panel = SewingNetworkTaskPanel.__new__(SewingNetworkTaskPanel)
    panel.network = Network()
    panel.warning = _TaskPanelLabel()
    panel.status = _TaskPanelLabel()
    panel.correspondence = _TaskPanelLabel()
    panel.update()
    assert "s2 (Missing reference)" in panel.warning.text


def test_sewing_network_commands_expose_free_sewing_and_editor() -> None:
    """Verify public commands expose free sewing and network editing."""
    from freecad_cloth.sewing import SewingNetworkCommands

    assert "ClothSewing_FreeSewing" in SewingNetworkCommands.COMMANDS
    assert "ClothSewing_EditNetwork" in SewingNetworkCommands.COMMANDS
    assert "ClothSewing_CreateNetwork" in SewingNetworkCommands.COMMANDS


def test_valid_network_has_no_reference_errors() -> None:
    """Verify a fully referenced sewing network passes validation."""
    from freecad_cloth.sewing.SewingNetworkGui import (
        network_reference_errors,
        validate_network_for_edit,
    )

    network = _ReferenceNetwork([_ReferenceSeam("s1"), _ReferenceSeam("s2")])
    assert network_reference_errors(network) == ()
    assert validate_network_for_edit(network) is True


def test_invalid_reference_is_reported_with_seam_identity() -> None:
    """Verify validation identifies seams with invalid references.

    Raises:
        AssertionError: Raised when the invalid seam identity is omitted.
    """
    from freecad_cloth.sewing.SewingNetworkGui import (
        network_reference_errors,
        validate_network_for_edit,
    )

    network = _ReferenceNetwork(
        [
            _ReferenceSeam("s1"),
            _ReferenceSeam("s2", "Changed reference"),
        ]
    )
    assert network_reference_errors(network) == (("s2", "Changed reference"),)
    try:
        validate_network_for_edit(network)
    except ValueError as exc:
        assert "s2: Changed reference" in str(exc)
    else:
        msg = "invalid reference was silently accepted"
        raise AssertionError(msg)


def test_missing_reference_is_reported_without_silent_edit() -> None:
    """Verify a missing seam reference fails validation without silent editing.

    Raises:
        AssertionError: Raised when a missing reference is silently accepted.
    """
    from freecad_cloth.sewing.SewingNetworkGui import validate_network_for_edit

    class Seam:
        """Represent seam parameters and identity used by a panel test."""

        SeamId = "s-missing"
        Status = "Missing reference"

    class Network:
        """Represent sewing-network status and seam membership for validation."""

        Seams = (Seam(),)

    try:
        validate_network_for_edit(Network())
    except ValueError as exc:
        assert "invalid seam references" in str(exc)
        assert "s-missing: Missing reference" in str(exc)
    else:
        msg = "missing reference was silently accepted"
        raise AssertionError(msg)


def test_curved_correspondence_reports_reversal_and_mismatch() -> None:
    """Verify curved correspondence reports reversed direction and length mismatch."""
    from freecad_cloth.sewing.SewingGui import correspondence_report

    class Seam:
        """Represent seam parameters and identity used by a panel test."""

        StartA = 0.0
        EndA = 1.0
        StartB = 0.0
        EndB = 1.0
        ReversedB = True

    report = correspondence_report(Seam(), 120.0, 121.0, 0.05)
    assert report.status == "reversed"
    assert report.valid
    assert report.reversed_b
    Seam.ReversedB = False
    mismatch = correspondence_report(Seam(), 100.0, 120.0, 0.05)
    assert mismatch.status == "length_mismatch"
    assert not mismatch.valid


def test_curved_correspondence_rejects_invalid_range() -> None:
    """Verify correspondence validation rejects inverted parameter ranges."""
    from freecad_cloth.sewing.SewingGui import correspondence_report

    class Seam:
        """Represent seam parameters and identity used by a panel test."""

        StartA = 0.8
        EndA = 0.2
        StartB = 0.0
        EndB = 1.0
        ReversedB = False

    report = correspondence_report(Seam(), 100.0, 100.0, 0.05)
    assert report.status == "invalid_range"
    assert not report.valid


def test_sewing_task_panel_accept_cannot_broaden_mismatch_with_legacy_tolerance() -> None:
    """Verify legacy tolerance cannot override relative-length mismatch.

    Raises:
        AssertionError: If the relative-length mismatch failure is not descriptive.
        ValueError: If accepting the edit does not reject the relative-length mismatch.
    """
    from types import SimpleNamespace

    from freecad_cloth.sewing.SewingGui import SewingTaskPanel

    class Seam:
        """Represent seam parameters and identity used by a panel test."""

        SeamId = "s1"
        Status = "Valid"
        StartA = 0.0
        EndA = 1.0
        StartB = 0.0
        EndB = 1.0
        ReversedB = False

    class Widget:
        """Represent a test input with a configurable value."""

        def __init__(self, value: object) -> None:
            """Store the configured value for this simulated control.

            Args:
                value: The value represented by this simulated control.
            """
            self.value_ = value

        def value(self) -> object:
            """Return the value stored by the simulated input control.

            Returns:
                The value stored by the input control.
            """
            return self.value_

    class Document:
        """Capture recomputation requests made by the panel."""

        def recompute(self) -> None:
            """Record a document recomputation request."""

    class App:
        """Expose the simulated active document to the task panel."""

        ActiveDocument = Document()

    obj = SimpleNamespace(
        Seam=Seam(),
        Tolerance=0.5,
        RelativeTolerance=0.05,
        Stitches=8,
        LengthA=100.0,
        LengthB=106.0,
        LengthDifference=6.0,
    )
    panel = SewingTaskPanel.__new__(SewingTaskPanel)
    panel.App = App
    panel.obj = obj
    panel.seam = obj.Seam
    panel.tolerance = Widget(5.0)
    panel.stitches = Widget(8)
    panel._apply_seam_settings = lambda: None
    panel._commit_transaction = lambda: None

    try:
        panel.accept()
    except ValueError as exc:
        assert "6.00%" in str(exc)
    else:
        msg = "accept() broadened mismatch validation using legacy Tolerance"
        raise AssertionError(msg)


def test_sewing_task_panel_reject_preserves_persisted_relative_tolerance() -> None:
    """Verify rejecting an edit preserves the stored relative tolerance."""
    from types import SimpleNamespace

    from freecad_cloth.sewing.SewingGui import SewingTaskPanel

    class Seam:
        """Represent seam parameters and identity used by a panel test."""

        Alignment = "endpoints"
        ReversedB = False
        StartA = 0.0
        EndA = 1.0
        StartB = 0.0
        EndB = 1.0

    class Document:
        """Capture recomputation requests made by the panel."""

        def recompute(self) -> None:
            """Record a document recomputation request."""

    class App:
        """Expose the simulated active document to the task panel."""

        ActiveDocument = Document()

    obj = SimpleNamespace(
        Tolerance=50.0,
        RelativeTolerance=0.05,
        Stitches=12,
    )
    panel = SewingTaskPanel.__new__(SewingTaskPanel)
    panel.App = App
    panel.obj = obj
    panel.seam = Seam()
    panel._transaction_active = False
    panel._original = {
        "Tolerance": 0.5,
        "RelativeTolerance": 0.05,
        "Stitches": 8,
        "Alignment": "endpoints",
        "ReversedB": False,
        "StartA": 0.0,
        "EndA": 1.0,
        "StartB": 0.0,
        "EndB": 1.0,
    }
    panel._refresh = lambda: None

    panel.reject()

    assert obj.Tolerance == 0.5
    assert obj.Stitches == 8
    assert obj.RelativeTolerance == 0.05


def test_sewing_task_panel_accept_persists_relative_tolerance() -> None:
    """Verify accepting an edit persists the relative tolerance and seam settings."""
    from freecad_cloth.sewing.SewingGui import SewingTaskPanel

    class Seam:
        """Represent seam parameters and identity used by a panel test."""

        Status = "Valid"
        StartA = 0.0
        EndA = 1.0
        StartB = 0.0
        EndB = 1.0
        Alignment = "uniform"
        ReversedB = False

    class Obj:
        """Represent the stored seam correspondence and tolerance properties."""

        Status = "Valid"
        LengthA = 100.0
        LengthB = 102.0
        LengthDifference = 2.0
        Tolerance = 0.5
        RelativeTolerance = 0.05
        Stitches = 8

    class Doc:
        """Capture document transactions and recomputation requested by the panel."""

        def __init__(self) -> None:
            """Start an empty log of document operations."""
            self.calls = []

        def recompute(self) -> None:
            """Record a document recomputation request."""
            self.calls.append("recompute")

        def commitTransaction(self) -> None:
            """Record that the current document transaction was committed."""
            self.calls.append("commit")

    class App:
        """Expose the simulated active document to the task panel."""

    class Spin:
        """Represent a numeric input control with a configurable value."""

        def __init__(self, value: object) -> None:
            """Store the configured numeric value for this control.

            Args:
                value: The value represented by this simulated control.
            """
            self._value = value

        def value(self) -> object:
            """Return the value stored by the simulated input control.

            Returns:
                The value stored by the input control.
            """
            return self._value

    class Combo:
        """Provide the selected alignment option for the editor."""

        def currentText(self) -> str:
            """Return the alignment option selected by this test fixture.

            Returns:
                The selected alignment option.
            """
            return "uniform"

    class Check:
        """Provide a deterministic checkbox state for the editor."""

        def isChecked(self) -> bool:
            """Return the configured checkbox state.

            Returns:
                The configured checkbox state.
            """
            return False

    class Button:
        """Capture the text and enabled state of a task-panel button."""

        def setText(self, text: str) -> None:
            """Store the text displayed by the simulated label.

            Args:
                text: The text to display in the label.
            """
            self.text = text

        def setEnabled(self, enabled: bool) -> None:
            """Store whether the simulated button should be enabled.

            Args:
                enabled: Whether the simulated button is enabled.
            """
            self.enabled = enabled

    app_doc = Doc()
    App.ActiveDocument = app_doc
    obj = Obj()
    obj.Seam = Seam()
    panel = SewingTaskPanel.__new__(SewingTaskPanel)
    panel.App = App
    panel.obj = obj
    panel.seam = obj.Seam
    panel.alignment = Combo()
    panel.reversed_b = Check()
    panel.start_a = Spin(0.0)
    panel.end_a = Spin(1.0)
    panel.start_b = Spin(0.0)
    panel.end_b = Spin(1.0)
    panel.tolerance = Spin(12.5)
    panel.stitches = Spin(12)
    panel.status = _TaskPanelLabel()
    panel.lengths = _TaskPanelLabel()
    panel.correspondence = _TaskPanelLabel()
    panel.reverse_button = Button()
    panel.reset_ranges_button = Button()
    panel._transaction_active = True

    assert panel.accept() is True
    assert obj.RelativeTolerance == 0.125
    assert obj.Tolerance == 0.5
    assert obj.Stitches == 12
    assert app_doc.calls == ["recompute", "commit"]


if __name__ == "__main__":
    test_sewing_task_panel_accept_cannot_broaden_mismatch_with_legacy_tolerance()
    test_sewing_task_panel_reject_preserves_persisted_relative_tolerance()
    print("sewing GUI relative-tolerance regression passed")
