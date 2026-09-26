import pytest

def test_rigid_solution_is_bounded_and_deterministic():
    from freecad_cloth.avatar.TargetAwarePlacement import solve_rigid_z
    args=(
        ((-50.0,0.0,0.0),(50.0,0.0,0.0)),
        ((-40.0,10.0,0.0),(40.0,10.0,0.0)),
    )
    assert solve_rigid_z(*args,max_translation=50.0,max_rotation=45.0)==solve_rigid_z(*args,max_translation=50.0,max_rotation=45.0)

def test_rigid_solution_rejects_translation_bound():
    from freecad_cloth.avatar.TargetAwarePlacement import TargetPlacementError, solve_rigid_z
    with pytest.raises(TargetPlacementError):
        solve_rigid_z(((100.0,0.0,0.0),),((0.0,0.0,0.0),),max_translation=50.0,max_rotation=45.0)

def test_piece_placement_round_trip_preserves_rotation_axis():
    from freecad_cloth.avatar.AvatarFitting import PiecePlacement
    value=PiecePlacement("piece",(1.0,2.0,3.0),90.0,(1.0,0.0,0.0))
    assert PiecePlacement.from_string(value.to_string())==value
    assert PiecePlacement.from_string("piece|1,2,3|90").rotation_axis==(0.0,0.0,1.0)

def test_public_target_aware_command_contract():
    from pathlib import Path
    commands=(Path(__file__).resolve().parents[1]/"freecad_cloth"/"avatar"/"FittingCommands.py").read_text(encoding="utf-8")
    assert "def _default_garment_anchors" in commands
    assert "def snap_pattern_pieces_to_target" in commands
    assert "def snap_pieces_to_target" in commands
    assert "ClothFitting_TargetAwareArrange" in commands

def test_target_aware_placement_rolls_back_piece_sketch_and_fit_state_on_forced_post_transform_failure():
    try:
        import FreeCAD as App
        import Part
    except ModuleNotFoundError:
        pytest.skip("FreeCAD Python module is unavailable in the non-GUI test runner")
    from unittest.mock import patch
    from freecad_cloth.avatar.AvatarFitting import GarmentAnchor, PiecePlacement
    from freecad_cloth.avatar.FittingCommands import create_fitting_scene, target_aware_place_piece
    from freecad_cloth.simulation.DrapeTarget import create_drape_target
    from freecad_cloth.avatar.TargetAwarePlacement import TargetPlacementError
    doc=App.newDocument("TargetAwareRollback")
    try:
        source=doc.addObject("Part::Feature","TargetSource"); source.Shape=Part.makeBox(100.0,100.0,100.0)
        piece=doc.addObject("Part::Feature","PatternPiece")
        piece.addProperty("App::PropertyString","PatternType","Cloth").PatternType="PatternPiece"
        piece.addProperty("App::PropertyString","PieceId","Cloth").PieceId="rollback-piece"
        piece.Shape=Part.makeBox(12.0,12.0,1.0)
        sketch=doc.addObject("Part::Feature","NativeSketch"); piece.addProperty("App::PropertyLink","Sketch","Pattern"); piece.Sketch=sketch
        piece.Placement=App.Placement(App.Vector(0.0,15.0,25.0),App.Rotation(App.Vector(1,0,0),90.0))
        sketch.Placement=App.Placement(App.Vector(7.0,18.0,30.0),App.Rotation(App.Vector(0,1,0),25.0))
        target=create_drape_target(doc,source,"FreeCAD Geometry",0.5,0.0)
        fitting=create_fitting_scene(); fitting.DrapeTarget=target; fitting.PatternPieces=[piece]
        home=PiecePlacement("rollback-piece",(0.0,15.0,25.0),90.0,(1.0,0.0,0.0))
        fitting.HomePlacements=[home.to_string()]; fitting.PiecePlacements=[home.to_string()]; fitting.FitStatus="Before transaction"
        anchors=(GarmentAnchor("rollback-piece","front_anchor",(6.0,6.0,0.0),"front"),)
        doc.recompute(); before_piece=piece.Placement; before_sketch=sketch.Placement; before_placements=list(fitting.PiecePlacements); before_status=fitting.FitStatus
        with patch("freecad_cloth.avatar.TargetAwarePlacement.assert_minimum_surface_clearance",side_effect=TargetPlacementError("forced post-transform")):
            with pytest.raises(TargetPlacementError,match="forced post-transform"):
                target_aware_place_piece(piece,target,anchors,clearance=8.0,max_translation=600.0,max_rotation=45.0)
        assert piece.Placement==before_piece
        assert sketch.Placement==before_sketch
        assert list(fitting.PiecePlacements)==before_placements
        assert fitting.FitStatus==before_status
    finally:
        if doc.Name in App.listDocuments(): App.closeDocument(doc.Name)

def test_create_simulation_from_fitting_propagates_target_and_source_signature_changes():
    try:
        import FreeCAD as App
        import Part
    except ModuleNotFoundError:
        pytest.skip("FreeCAD Python module is unavailable in the non-GUI test runner")
    from types import SimpleNamespace
    from unittest.mock import patch
    from freecad_cloth.avatar.FittingCommands import create_fitting_scene, create_simulation_from_fitting
    from freecad_cloth.simulation.DrapeTarget import create_drape_target
    from freecad_cloth.simulation.SimulationObjects import _simulation_source_signature
    doc=App.newDocument("TargetHandoff")
    try:
        source=doc.addObject("Part::Feature","TargetSource"); source.Shape=Part.makeBox(100.0,100.0,100.0)
        piece=doc.addObject("App::FeaturePython","PatternPiece"); piece.addProperty("App::PropertyString","PatternType","Cloth").PatternType="PatternPiece"; piece.addProperty("App::PropertyString","PieceId","Cloth").PieceId="handoff-piece"
        target=create_drape_target(doc,source,"FreeCAD Geometry",0.5,0.0)
        fitting=create_fitting_scene(); fitting.DrapeTarget=target; fitting.PatternPieces=[piece]; doc.recompute()
        simulated=SimpleNamespace()
        with patch("freecad_cloth.simulation.SimulationObjects.create_simulation_scene",return_value=simulated):
            result=create_simulation_from_fitting()
        assert result is simulated and result.DrapeTarget is target
        first=_simulation_source_signature(SimpleNamespace(Document=doc,DrapeTarget=target,PinMode="None",PinSelection=[],StitchSamples=8),())
        source.Placement.Base=App.Vector(5.0,0.0,0.0)
        second=_simulation_source_signature(SimpleNamespace(Document=doc,DrapeTarget=target,PinMode="None",PinSelection=[],StitchSamples=8),())
        assert first!=second
    finally:
        if doc.Name in App.listDocuments(): App.closeDocument(doc.Name)
