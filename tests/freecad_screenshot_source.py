

def style_mesh(obj, label):
    obj.Label = label
    try:
        obj.ViewObject.DisplayMode = "Flat Lines"; obj.ViewObject.ShapeColor = (0.86, 0.20, 0.10); obj.ViewObject.LineColor = (0.20, 0.02, 0.01); obj.ViewObject.LineWidth = 1.5
    except (AttributeError, TypeError, ValueError):
        pass


def simulation():
    import os
    os.environ["CLOTH_TISSU_COLLISION_MODE"] = "mesh"
    from freecad_cloth.simulation.SimulationQualityRuntimeV2 import create_quality_simulation_scene
    from freecad_cloth.simulation.SimulationQualityGui import SimulationQualityTaskPanel
    from freecad_cloth.simulation.DrapeTarget import collision_surface, refresh_drape_target, target_status
    from freecad_cloth.pattern.PatternModel import Seam
    from freecad_cloth.pattern.PatternObjects import add_seam
    doc = App.newDocument("ClothSimulationVisualRegression"); scene = create_quality_simulation_scene(doc); avatar = getattr(scene.AvatarProxy, "SourceObject", None); target = scene.DrapeTarget
    if avatar is None or str(getattr(avatar, "AvatarType", "")) != "ClothAvatar":
        raise RuntimeError("visual fixture did not create the production ClothAvatar")
    if target is None:
        raise RuntimeError("visual fixture did not create DrapeTarget")
    target_source = getattr(target, "SourceObject", None)
    if target_source is not avatar:
        raise RuntimeError("visual fixture DrapeTarget does not reference the production ClothAvatar")
    pre_status = target_status(target)
    if str(pre_status.get("state", "")) != "ready":
        raise RuntimeError("canonical tunic DrapeTarget is not current before placement: %s" % pre_status.get("message", pre_status))
    target_surface = collision_surface(
        target_source,
        float(getattr(target, "CollisionDeflection", 1.0)),
        float(getattr(target, "CollisionThickness", 0.0)),
    )
    if not target_surface.vertices or not target_surface.triangles:
        raise RuntimeError("canonical tunic DrapeTarget has no authoritative collision triangles")
    from freecad_cloth.avatar.AvatarFitting import ArrangementPoint
    def arrangement_world(name):
        raw = next((value for value in getattr(avatar, "ArrangementPoints", ()) if str(value).split("|", 1)[0] == name), None)
        if raw is None:
            raise RuntimeError("canonical tunic is missing avatar arrangement point %s" % name)
        point = ArrangementPoint.from_string(raw)
        return avatar.Placement.multVec(App.Vector(*point.position()))
    shoulder_left = arrangement_world("shoulder_left")
    shoulder_right = arrangement_world("shoulder_right")
    hip_point = arrangement_world("hip")
    target_ys = [float(vertex[1]) for vertex in target_surface.vertices]
    y_span = max(target_ys) - min(target_ys)
    x_mid = (shoulder_left.x + shoulder_right.x) / 2.0
    shoulder_z = (shoulder_left.z + shoulder_right.z) / 2.0
    hem_z = hip_point.z
    shoulder_width = abs(shoulder_right.x - shoulder_left.x)
    panel_width = max(420.0, shoulder_width + 100.0)
    hem_width = max(450.0, panel_width + 80.0)
    garment_height = max(560.0, shoulder_z - hem_z)
    body_depth = max(120.0, min(260.0, y_span))
    clearance = max(20.0, 0.08 * body_depth)
    rot = App.Rotation(App.Vector(1,0,0), 90.0)
    def target_relative_piece_placement(side):
        if side == "front":
            y = (shoulder_left.y + shoulder_right.y) / 2.0 - clearance
        elif side == "back":
            y = (shoulder_left.y + shoulder_right.y) / 2.0 + clearance
        else:
            raise ValueError("tunic target-relative side must be front or back")
        return App.Placement(App.Vector(x_mid - hem_width / 2.0, y, hem_z + 120.0), rot)
    def make_piece(name, side, neckline_ratio, neckline_drop):
        sketch, outline = _make_tunic_sketch(doc, name + "Source", panel_width, garment_height, hem_width, neckline_ratio, neckline_drop); doc.recompute(); piece = _adopt_sketch(sketch, name, 10.0, 0.0); piece.Label = name; piece.Placement = target_relative_piece_placement(side); piece.Sketch.Placement = piece.Placement; return piece, outline
    front, front_outline = make_piece("VisualTunicFront", "front", 0.64, 0.10); back, back_outline = make_piece("VisualTunicBack", "back", 0.64, 0.07)
    # Same-side side seams and authored shoulder seams; the neckline remains open.
    seam_records = []
    for edge_a, edge_b, seam_id in ((2,2,"TunicRightShoulder"),(5,5,"TunicLeftShoulder")):
        seam = Seam(str(front.PieceId), edge_a, str(back.PieceId), edge_b, id=seam_id, alignment="uniform", stitch_group="TunicAssembly")
        add_seam(doc, seam)
        seam_obj = next(o for o in doc.Objects if getattr(o, "SeamId", "") == seam_id)
        seam_records.append((seam_obj, front, back))
    scene.StartHeight = 0.0; scene.QualityPreset = "Fast"; scene.ParticleDistance = 24.0; scene.SolverIterations = 8; scene.SolverSubsteps = 1; scene.TimeStep = 1.0 / 120.0; scene.GravityX = 0.0; scene.GravityY = 0.0; scene.GravityZ = -9810.0; scene.FabricFriction = 0.75; scene.PinMode = "None"; scene.PinSelection = []; scene.ClothPieces = [front, back]; refresh_drape_target(target); doc.recompute()
    status = target_status(target)
    if str(status.get("state", "")) != "ready":
        raise RuntimeError("canonical tunic DrapeTarget is not current: %s" % status.get("message", status))
    proxy = scene.Proxy
    backend = getattr(proxy, "backend", None)
    if backend is None:
        raise RuntimeError("canonical tunic did not build a simulation backend")
    if list(getattr(scene, "PinSelection", ())) != []:
        raise RuntimeError("canonical tunic PinMode=None retained explicit PinSelection values")
    solver_pins = tuple(int(i) for i in getattr(backend, "_pin_indices", ()))
    if not solver_pins:
        system = getattr(backend, "system", None)
        solver_pins = tuple(sorted(int(i) for i in getattr(system, "pins", {}).keys()))
    if str(getattr(scene, "PinMode", "")) != "None":
        raise RuntimeError("canonical tunic must use PinMode=None")
    if solver_pins:
        raise RuntimeError("canonical tunic PinMode=None still has solver pins: %s" % (solver_pins,))
    surface = collision_surface(
        target_source,
        float(getattr(target, "CollisionDeflection", 1.0)),
        float(getattr(target, "CollisionThickness", 0.0)),
    )
    initial_clearance = None
    try: