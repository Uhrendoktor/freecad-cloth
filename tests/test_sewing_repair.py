import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_repair_reversed_correspondence_only_changes_orientation():
    from SewingGui import repair_correspondence_settings

    class Seam:
        ReversedB = True

    class Report:
        status = "reversed"

    seam = Seam()
    assert repair_correspondence_settings(seam, Report()) == "reversed correspondence repaired"
    assert seam.ReversedB is False


def test_repair_invalid_range_restores_full_ranges():
    from SewingGui import repair_correspondence_settings

    class Seam:
        StartA, EndA, StartB, EndB = 0.8, 0.2, 0.7, 0.1

    class Report:
        status = "invalid_range"

    seam = Seam()
    assert repair_correspondence_settings(seam, Report()) == "invalid ranges reset to full seam edges"
    assert (seam.StartA, seam.EndA, seam.StartB, seam.EndB) == (0.0, 1.0, 0.0, 1.0)


def test_repair_does_not_hide_physical_length_mismatch():
    from SewingGui import repair_correspondence_settings

    class Seam:
        pass

    class Report:
        status = "length_mismatch"

    try:
        repair_correspondence_settings(Seam(), Report())
    except ValueError as exc:
        assert "length mismatch" in str(exc)
        assert "not hidden" in str(exc)
    else:
        raise AssertionError("length mismatch was silently hidden")


def test_repair_command_is_registered_with_context_activation():
    import SewingCommands
    assert "ClothSewing_RepairSeam" in SewingCommands.COMMANDS
    assert "ClothSewing_RepairSeam" in SewingCommands._COMMAND_HANDLERS
    assert "ClothSewing_RepairSeam" in SewingCommands._ACTIVATION
    assert "Repair Seam" == SewingCommands._MENU_TEXT["ClothSewing_RepairSeam"]


if __name__ == "__main__":
    test_repair_reversed_correspondence_only_changes_orientation()
    test_repair_invalid_range_restores_full_ranges()
    test_repair_does_not_hide_physical_length_mismatch()
    test_repair_command_is_registered_with_context_activation()
    print("sewing repair tests passed")
