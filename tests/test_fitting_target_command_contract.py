from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")


def test_target_snap_public_command_has_icon_and_selection_guard():
    icon = ROOT / "resources" / "icons" / "ClothFitting_SnapPiecesToTarget.svg"
    assert icon.is_file() and icon.read_text(encoding="utf-8").startswith("<svg")
    assert '"ClothFitting_SnapPiecesToTarget"' in SOURCE
    assert '"ClothFitting_SnapPiecesToTarget": _snap_selected_to_target' in SOURCE
    assert 'select exactly one DrapeTarget and one or more PatternPiece objects' in SOURCE
    assert 'status = target_status(target)' in SOURCE
    assert 'if status["state"] != "ready":' in SOURCE


def test_target_snap_is_transactional_and_preserves_home_state():
    assert 'old_sketch_placements = {' in SOURCE
    assert 'old_pattern_pieces = tuple(scene.PatternPieces)' in SOURCE
    assert 'old_fit_status = str(getattr(scene, "FitStatus", ""))' in SOURCE
    assert 'scene.PatternPieces = list(old_pattern_pieces)' in SOURCE
    assert 'scene.FitStatus = old_fit_status' in SOURCE
    assert 'scene.HomePlacements = [homes[key].to_string() for key in sorted(homes)]' in SOURCE


def test_fitting_simulation_propagates_authoritative_target():
    assert 'simulation.DrapeTarget = scene.DrapeTarget' in SOURCE
    assert 'obj.addProperty("App::PropertyLinkGlobal", "DrapeTarget", "Fitting")' in SOURCE


def test_piece_placement_persists_non_z_rotation_axis():
    source = (ROOT / "freecad_cloth" / "avatar" / "AvatarFitting.py").read_text(encoding="utf-8")
    assert 'rotation_axis: Tuple[float, float, float]' in source
    assert 'axis = tuple(float(v) for v in axis_value.split(","))' in source
    assert 'App.Rotation(axis, placement.rotation_z)' in (ROOT / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
