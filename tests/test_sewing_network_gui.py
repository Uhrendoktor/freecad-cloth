import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_sewing_network_gui_contract_is_headless_importable():
    import SewingNetworkGui
    assert hasattr(SewingNetworkGui, "SewingNetworkTaskPanel")
    assert hasattr(SewingNetworkGui, "show_sewing_network_task")


def test_network_task_panel_uses_transactional_editor_contract():
    from SewingNetworkGui import SewingNetworkTaskPanel

    assert SewingNetworkTaskPanel._TRANSACTION_NAME == "Edit Sewing Network"
    assert hasattr(SewingNetworkTaskPanel, "_begin_transaction")
    assert hasattr(SewingNetworkTaskPanel, "_commit_transaction")
    assert hasattr(SewingNetworkTaskPanel, "_abort_transaction")
    assert hasattr(SewingNetworkTaskPanel, "_restore_original")


def test_network_task_panel_restores_all_persisted_member_settings():
    from SewingNetworkGui import SewingNetworkTaskPanel

    class Seam:
        def __init__(self):
            self.StartA = 0.2
            self.EndA = 0.8
            self.StartB = 0.1
            self.EndB = 0.9
            self.Alignment = "uniform"
            self.ReversedB = True

    class Doc:
        def recompute(self):
            pass

    seam = Seam()
    panel = SewingNetworkTaskPanel.__new__(SewingNetworkTaskPanel)
    panel.seams = None
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


def test_sewing_network_commands_expose_free_sewing_and_editor():
    import SewingNetworkCommands
    assert "ClothSewing_FreeSewing" in SewingNetworkCommands.COMMANDS
    assert "ClothSewing_EditNetwork" in SewingNetworkCommands.COMMANDS
    assert "ClothSewing_CreateNetwork" in SewingNetworkCommands.COMMANDS


def test_valid_network_has_no_reference_errors():
    from SewingNetworkGui import network_reference_errors, validate_network_for_edit

    class Seam:
        def __init__(self, seam_id, status="Valid"):
            self.SeamId = seam_id
            self.Status = status

    class Network:
        def __init__(self, seams):
            self.Seams = seams

    network = Network([Seam("s1"), Seam("s2")])
    assert network_reference_errors(network) == ()
    assert validate_network_for_edit(network) is True


def test_invalid_reference_is_reported_with_seam_identity():
    from SewingNetworkGui import network_reference_errors, validate_network_for_edit

    class Seam:
        def __init__(self, seam_id, status="Valid"):
            self.SeamId = seam_id
            self.Status = status

    class Network:
        def __init__(self, seams):
            self.Seams = seams

    network = Network([Seam("s1"), Seam("s2", "Changed reference")])
    assert network_reference_errors(network) == (("s2", "Changed reference"),)
    try:
        validate_network_for_edit(network)
    except ValueError as exc:
        assert "s2: Changed reference" in str(exc)
    else:
        raise AssertionError("invalid reference was silently accepted")


def test_missing_reference_is_reported_without_silent_edit():
    from SewingNetworkGui import validate_network_for_edit

    class Seam:
        SeamId = "s-missing"
        Status = "Missing reference"

    class Network:
        Seams = (Seam(),)

    try:
        validate_network_for_edit(Network())
    except ValueError as exc:
        assert "invalid seam references" in str(exc)
        assert "s-missing: Missing reference" in str(exc)
    else:
        raise AssertionError("missing reference was silently accepted")


if __name__ == "__main__":
    test_sewing_network_gui_contract_is_headless_importable()
    test_network_task_panel_uses_transactional_editor_contract()
    test_network_task_panel_restores_all_persisted_member_settings()
    test_sewing_network_commands_expose_free_sewing_and_editor()
    test_valid_network_has_no_reference_errors()
    test_invalid_reference_is_reported_with_seam_identity()
    test_missing_reference_is_reported_without_silent_edit()
    print("sewing network GUI contract tests passed")
