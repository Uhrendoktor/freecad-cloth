import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def test_sewing_network_gui_contract_is_headless_importable():
    import SewingNetworkGui
    assert hasattr(SewingNetworkGui, "SewingNetworkTaskPanel")
    assert hasattr(SewingNetworkGui, "show_sewing_network_task")

def test_network_task_panel_uses_transactional_editor_contract():
    from freecad_cloth.sewing.SewingNetworkGui import SewingNetworkTaskPanel
    assert SewingNetworkTaskPanel._TRANSACTION_NAME == "Edit Sewing Network"
    assert hasattr(SewingNetworkTaskPanel, "_begin_transaction")
    assert hasattr(SewingNetworkTaskPanel, "_commit_transaction")
    assert hasattr(SewingNetworkTaskPanel, "_abort_transaction")
    assert hasattr(SewingNetworkTaskPanel, "_restore_original")

def test_network_task_panel_restores_all_persisted_member_settings():
    from freecad_cloth.sewing.SewingNetworkGui import SewingNetworkTaskPanel
    class Seam:
        def __init__(self):
            self.StartA = 0.2; self.EndA = 0.8; self.StartB = 0.1; self.EndB = 0.9
            self.Alignment = "uniform"; self.ReversedB = True
    seam = Seam()
    panel = SewingNetworkTaskPanel.__new__(SewingNetworkTaskPanel)
    panel._seams = (seam,)
    panel._original = {"ranges": ((0.0, 1.0, 0.0, 1.0),), "alignment": ("endpoints",), "reversed_b": (False,)}
    panel._restore_original()
    assert (seam.StartA, seam.EndA, seam.StartB, seam.EndB) == (0.0, 1.0, 0.0, 1.0)
    assert seam.Alignment == "endpoints"
    assert seam.ReversedB is False

def test_network_task_panel_commit_is_one_document_transaction():
    from freecad_cloth.sewing.SewingNetworkGui import SewingNetworkTaskPanel
    class Doc:
        def __init__(self): self.calls = []
        def openTransaction(self, name): self.calls.append(("open", name))
        def commitTransaction(self): self.calls.append(("commit",))
        def abortTransaction(self): self.calls.append(("abort",))
    class App: ActiveDocument = Doc()
    panel = SewingNetworkTaskPanel.__new__(SewingNetworkTaskPanel)
    panel.App = App; panel._transaction_active = False
    panel._begin_transaction(); panel._commit_transaction()
    assert App.ActiveDocument.calls == [("open", "Edit Sewing Network"), ("commit",)]

def test_network_task_panel_cancel_aborts_transaction_and_refreshes_warning():
    from freecad_cloth.sewing.SewingNetworkGui import SewingNetworkTaskPanel
    class Doc:
        def __init__(self): self.calls = []
        def abortTransaction(self): self.calls.append(("abort",))
        def recompute(self): self.calls.append(("recompute",))
    class App: ActiveDocument = Doc()
    class Label:
        def __init__(self): self.text = None
        def setText(self, text): self.text = text
    class Network:
        Status = "Invalid"; SegmentCount = 0; LengthDifference = 0.0; Seams = ()
    panel = SewingNetworkTaskPanel.__new__(SewingNetworkTaskPanel)
    panel.App = App; panel.network = Network(); panel.warning = Label(); panel.status = Label(); panel._transaction_active = True
    panel.reject()
    assert App.ActiveDocument.calls == [("abort",), ("recompute",)]
    assert panel._transaction_active is False
    assert panel.warning.text == ""

def test_network_task_panel_invalid_recompute_restores_and_aborts():
    from freecad_cloth.sewing.SewingNetworkGui import SewingNetworkTaskPanel
    class Seam:
        SeamId = "s1"; Status = "Valid"; StartA = 0.2; EndA = 0.8; StartB = 0.1; EndB = 0.9; Alignment = "uniform"; ReversedB = True
    class Network:
        Seams = (Seam(),); Status = "Valid"; SegmentCount = 1; LengthDifference = 0.0
    class Doc:
        def __init__(self, network): self.network = network; self.calls = []
        def recompute(self): self.calls.append("recompute"); self.network.Seams[0].Status = "Missing reference"
        def abortTransaction(self): self.calls.append("abort")
    class App: pass
    class Item:
        def __init__(self, value): self.value = value
        def text(self): return str(self.value)
    class Table:
        def __init__(self): self.values = {(0, 2): 0.3, (0, 3): 0.7, (0, 6): 0.2, (0, 7): 0.8}
        def item(self, row, column): return Item(self.values[(row, column)])
    class Combo:
        def currentText(self): return "endpoints"
    class Check:
        def isChecked(self): return False
    App.ActiveDocument = Doc(Network())
    panel = SewingNetworkTaskPanel.__new__(SewingNetworkTaskPanel)
    panel.App = App; panel.network = App.ActiveDocument.network; panel._seams = panel.network.Seams
    panel._original = {"ranges": ((0.2, 0.8, 0.1, 0.9),), "alignment": ("uniform",), "reversed_b": (True,)}
    panel.table = Table(); panel.alignment = Combo(); panel.reversed_b = Check()
    panel.warning = type("Label", (), {"setText": lambda self, text: None})(); panel.status = type("Label", (), {"setText": lambda self, text: None})()
    panel._transaction_active = True
    try: panel.accept()
    except ValueError as exc: assert "became invalid after edit" in str(exc)
    else: raise AssertionError("invalid recompute was silently accepted")
    seam = panel._seams[0]
    assert (seam.StartA, seam.EndA, seam.StartB, seam.EndB) == (0.2, 0.8, 0.1, 0.9)
    assert seam.Alignment == "uniform" and seam.ReversedB is True
    assert App.ActiveDocument.calls == ["recompute", "recompute", "abort"]
    assert panel._transaction_active is False

def test_network_task_panel_update_refreshes_invalid_reference_warning():
    from freecad_cloth.sewing.SewingNetworkGui import SewingNetworkTaskPanel
    class Seam: SeamId = "s2"; Status = "Missing reference"
    class Network:
        Seams = (Seam(),); Status = "Invalid"; SegmentCount = 0; LengthDifference = 0.0
    class Label:
        def __init__(self): self.text = ""
        def setText(self, text): self.text = text
    panel = SewingNetworkTaskPanel.__new__(SewingNetworkTaskPanel)
    panel.network = Network(); panel.warning = Label(); panel.status = Label(); panel.update()
    assert "s2 (Missing reference)" in panel.warning.text

def test_sewing_network_commands_expose_free_sewing_and_editor():
    import SewingNetworkCommands
    assert "ClothSewing_FreeSewing" in SewingNetworkCommands.COMMANDS
    assert "ClothSewing_EditNetwork" in SewingNetworkCommands.COMMANDS
    assert "ClothSewing_CreateNetwork" in SewingNetworkCommands.COMMANDS

def test_valid_network_has_no_reference_errors():
    from freecad_cloth.sewing.SewingNetworkGui import network_reference_errors, validate_network_for_edit
    class Seam:
        def __init__(self, seam_id, status="Valid"): self.SeamId=seam_id; self.Status=status
    class Network:
        def __init__(self, seams): self.Seams=seams
    network=Network([Seam("s1"),Seam("s2")]); assert network_reference_errors(network)==(); assert validate_network_for_edit(network) is True

def test_invalid_reference_is_reported_with_seam_identity():
    from freecad_cloth.sewing.SewingNetworkGui import network_reference_errors, validate_network_for_edit
    class Seam:
        def __init__(self, seam_id, status="Valid"): self.SeamId=seam_id; self.Status=status
    class Network:
        def __init__(self, seams): self.Seams=seams
    network=Network([Seam("s1"),Seam("s2","Changed reference")]); assert network_reference_errors(network)==(("s2","Changed reference"),)
    try: validate_network_for_edit(network)
    except ValueError as exc: assert "s2: Changed reference" in str(exc)
    else: raise AssertionError("invalid reference was silently accepted")

def test_missing_reference_is_reported_without_silent_edit():
    from freecad_cloth.sewing.SewingNetworkGui import validate_network_for_edit
    class Seam: SeamId="s-missing"; Status="Missing reference"
    class Network: Seams=(Seam(),)
    try: validate_network_for_edit(Network())
    except ValueError as exc: assert "invalid seam references" in str(exc) and "s-missing: Missing reference" in str(exc)
    else: raise AssertionError("missing reference was silently accepted")

def test_curved_correspondence_reports_reversal_and_mismatch():
    from freecad_cloth.sewing.SewingGui import correspondence_report
    class Seam:
        StartA=0.0; EndA=1.0; StartB=0.0; EndB=1.0; ReversedB=True
    report=correspondence_report(Seam(),120.0,121.0,0.05)
    assert report.status=="reversed" and report.valid and report.reversed_b
    Seam.ReversedB=False
    mismatch=correspondence_report(Seam(),100.0,120.0,0.05)
    assert mismatch.status=="length_mismatch" and not mismatch.valid

def test_curved_correspondence_rejects_invalid_range():
    from freecad_cloth.sewing.SewingGui import correspondence_report
    class Seam:
        StartA=0.8; EndA=0.2; StartB=0.0; EndB=1.0; ReversedB=False
    report=correspondence_report(Seam(),100.0,100.0,0.05)
    assert report.status=="invalid_range" and not report.valid

if __name__ == "__main__":
    test_sewing_network_gui_contract_is_headless_importable(); test_network_task_panel_uses_transactional_editor_contract(); test_network_task_panel_restores_all_persisted_member_settings(); test_network_task_panel_commit_is_one_document_transaction(); test_network_task_panel_cancel_aborts_transaction_and_refreshes_warning(); test_network_task_panel_invalid_recompute_restores_and_aborts(); test_network_task_panel_update_refreshes_invalid_reference_warning(); test_sewing_network_commands_expose_free_sewing_and_editor(); test_valid_network_has_no_reference_errors(); test_invalid_reference_is_reported_with_seam_identity(); test_missing_reference_is_reported_without_silent_edit(); test_curved_correspondence_reports_reversal_and_mismatch(); test_curved_correspondence_rejects_invalid_range(); print("sewing network GUI contract tests passed")
