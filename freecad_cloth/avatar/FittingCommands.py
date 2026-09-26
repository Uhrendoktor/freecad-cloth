"""FreeCAD-facing body measurement, avatar fitting, and arrangement commands."""


def _scene(doc):
    return next((o for o in doc.Objects if getattr(o, "FittingType", "") == "FittingScene"), None)


def _safe_name(value):
    return "".join(ch if ch.isalnum() else "_" for ch in str(value)) or "Item"


def _sync_visuals(scene):
    """Synchronize visible FreeCAD point/volume adapters from canonical strings."""
    import FreeCAD as App
    import Part
    from freecad_cloth.avatar.AvatarFitting import ArrangementPoint, BoundingVolume

    points = tuple(ArrangementPoint.from_string(v) for v in scene.ArrangementPoints)
    volumes = tuple(BoundingVolume.from_string(v) for v in scene.BoundingVolumes)
    point_objects = []
    volume_objects = []
    existing = {o.Name: o for o in scene.Document.Objects}
    for point in points:
        name = "ArrangementPoint_" + _safe_name(point.name)
        obj = existing.get(name) or scene.Document.addObject("Part::Feature", name)
        obj.Label = "Arrangement: " + point.name
        if not hasattr(obj, "FittingType"):
            obj.addProperty("App::PropertyString", "FittingType", "Fitting").FittingType = "ArrangementPoint"
        for prop, value in (("PointName", point.name), ("WrapDirection", point.wrap_direction), ("SymmetryGroup", point.symmetry_group)):
            if not hasattr(obj, prop):
                obj.addProperty("App::PropertyString", prop, "Fitting")
            setattr(obj, prop, value)
        if not hasattr(obj, "X"):
            obj.addProperty("App::PropertyDistance", "X", "Arrangement")
            obj.addProperty("App::PropertyDistance", "Y", "Arrangement")
            obj.addProperty("App::PropertyDistance", "Offset", "Arrangement")
            obj.addProperty("App::PropertyAngle", "RotationZ", "Arrangement")
        obj.X, obj.Y, obj.Offset, obj.RotationZ = point.x, point.y, point.offset, point.rotation_z
        obj.Shape = Part.makeSphere(4.0, App.Vector(point.x, point.y, point.offset))
        point_objects.append(obj)
    for volume in volumes:
        name = "BoundingVolume_" + _safe_name(volume.name)
        obj = existing.get(name) or scene.Document.addObject("Part::Feature", name)
        obj.Label = "Bounding Volume: " + volume.name
        if not hasattr(obj, "FittingType"):
            obj.addProperty("App::PropertyString", "FittingType", "Fitting").FittingType = "BoundingVolume"
        if not hasattr(obj, "VolumeName"):
            obj.addProperty("App::PropertyString", "VolumeName", "Fitting")
            obj.addProperty("App::PropertyVector", "Center", "Volume")
            obj.addProperty("App::PropertyVector", "Size", "Volume")
        obj.VolumeName = volume.name
        obj.Center = App.Vector(*volume.center)
        obj.Size = App.Vector(*volume.size)
        corner = App.Vector(
            volume.center[0] - volume.size[0] / 2.0,
            volume.center[1] - volume.size[1] / 2.0,
            volume.center[2] - volume.size[2] / 2.0,
        )
        obj.Shape = Part.makeBox(volume.size[0], volume.size[1], volume.size[2], corner)
        volume_objects.append(obj)
    scene.ArrangementPointObjects = [obj.Name for obj in point_objects]
    scene.BoundingVolumeObjects = [obj.Name for obj in volume_objects]
    for obj in point_objects + volume_objects:
        obj.ViewObject.Visibility = True



def _migrate_visual_output_references(scene):
    """Convert legacy visual-object links to persisted object-name outputs.

    ArrangementPointObjects and BoundingVolumeObjects are derived visual outputs,
    not dependency inputs. Persisting them as links makes the FittingScene proxy
    depend on objects that the proxy itself mutates during execution, which is a
    reverse dependency that FreeCAD reports as an object still touched after
    recompute. Existing documents keep the property names but migrate their
    values to non-dependency string outputs before proxy execution.
    """
    for name in ("ArrangementPointObjects", "BoundingVolumeObjects"):
        if name not in getattr(scene, "PropertiesList", ()):
            scene.addProperty("App::PropertyStringList", name, "Arrangement")
            setattr(scene, name, [])
            continue
        try:
            type_id = scene.getTypeIdOfProperty(name)
        except (AttributeError, RuntimeError):
            type_id = ""
        if str(type_id) == "App::PropertyStringList":
            continue
        legacy = tuple(getattr(scene, name, ()) or ())
        names = [getattr(item, "Name", "") for item in legacy if getattr(item, "Name", "")]
        scene.removeProperty(name)
        scene.addProperty("App::PropertyStringList", name, "Arrangement")
        setattr(scene, name, names)

def create_fitting_scene():
    import FreeCAD as App
    from freecad_cloth.avatar.AvatarFitting import BodyMeasurements, FittingScene

    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    if _scene(doc) is not None:
        return _scene(doc)
    obj = doc.addObject("App::FeaturePython", "FittingScene")
    obj.Label = "Avatar Fitting Scene"
    obj.addProperty("App::PropertyString", "FittingType", "Fitting").FittingType = "FittingScene"
    obj.addProperty("App::PropertyString", "MeasurementData", "Measurements").MeasurementData = BodyMeasurements().to_json()
    obj.addProperty("App::PropertyString", "MeasurementUnit", "Measurements").MeasurementUnit = "mm"
    obj.addProperty("App::PropertyLink", "AvatarProxy", "Fitting")
    obj.addProperty("App::PropertyLinkGlobal", "DrapeTarget", "Fitting")
    obj.addProperty("App::PropertyLinkListGlobal", "PatternPieces", "Fitting")
    obj.addProperty("App::PropertyStringList", "PiecePlacements", "Fitting").PiecePlacements = []
    obj.addProperty("App::PropertyStringList", "HomePlacements", "Fitting").HomePlacements = []
    obj.addProperty("App::PropertyStringList", "ArrangementPoints", "Arrangement").ArrangementPoints = []
    obj.addProperty("App::PropertyStringList", "BoundingVolumes", "Arrangement").BoundingVolumes = []
    obj.addProperty("App::PropertyStringList", "GarmentAnchors", "Arrangement").GarmentAnchors = []
    obj.addProperty("App::PropertyStringList", "ArrangementPointObjects", "Arrangement").ArrangementPointObjects = []
    obj.addProperty("App::PropertyStringList", "BoundingVolumeObjects", "Arrangement").BoundingVolumeObjects = []
    obj.addProperty("App::PropertyBool", "SymmetryEnabled", "Arrangement").SymmetryEnabled = True
    obj.addProperty("App::PropertyString", "FitStatus", "Fitting").FitStatus = "Unassigned"
    obj.Proxy = _FittingProxy()
    FittingScene().validate()
    doc.recompute()
    return obj


def set_body_measurements(measurements, unit="mm"):
    from freecad_cloth.avatar.AvatarFitting import BodyMeasurements
    import FreeCAD as App
    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _scene(doc) or create_fitting_scene()
    data = BodyMeasurements(dict(measurements), unit)
    data.validate()
    scene.MeasurementData = data.to_json()
    scene.MeasurementUnit = data.unit
    scene.FitStatus = "Measurements set"
    doc.recompute()
    return scene


def assign_avatar_source(source=None):
    import FreeCAD as App
    import FreeCADGui as Gui
    from freecad_cloth.simulation.SimulationObjects import create_avatar_collision, set_avatar_collision_source

    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _scene(doc) or create_fitting_scene()
    if source is None:
        source = next((o for o in Gui.Selection.getSelection() if hasattr(o, "Shape") or hasattr(o, "Mesh")), None)
    if source is None:
        raise ValueError("select a FreeCAD body or mesh to use as the avatar source")
    avatar = create_avatar_collision(doc) if doc.getObject("AvatarCollision") is None else doc.getObject("AvatarCollision")
    avatar = set_avatar_collision_source(scene, source)
    scene.AvatarProxy = avatar
    existing_target = doc.getObject("DrapeTarget")
    if existing_target is not None:
        scene.DrapeTarget = existing_target
    scene.FitStatus = "Avatar assigned"
    doc.recompute()
    return scene


def add_selected_pattern_pieces():
    import FreeCAD as App
    import FreeCADGui as Gui
    from freecad_cloth.avatar.AvatarFitting import PiecePlacement, FittingScene, BodyMeasurements

    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _scene(doc) or create_fitting_scene()
    pieces = [o for o in Gui.Selection.getSelection() if getattr(o, "PatternType", "") == "PatternPiece"]
    if not pieces:
        raise ValueError("select one or more pattern pieces before adding them to the fitting scene")
    existing = [PiecePlacement.from_string(v) for v in scene.PiecePlacements]
    homes = [PiecePlacement.from_string(v) for v in scene.HomePlacements]
    by_id = {p.piece_id: p for p in existing}
    home_by_id = {p.piece_id: p for p in homes}
    for piece in pieces:
        placement = piece.Placement
        base = placement.Base
        value = PiecePlacement(str(piece.PieceId), (float(base.x), float(base.y), float(base.z)), float(placement.Rotation.Angle))
        by_id[value.piece_id] = value
        home_by_id.setdefault(value.piece_id, value)
    scene.PatternPieces = sorted(set(list(scene.PatternPieces) + pieces), key=lambda o: str(o.PieceId))
    scene.PiecePlacements = [by_id[k].to_string() for k in sorted(by_id)]
    scene.HomePlacements = [home_by_id[k].to_string() for k in sorted(home_by_id)]
    FittingScene(BodyMeasurements.from_json(scene.MeasurementData), getattr(scene.AvatarProxy, "Label", "") if scene.AvatarProxy else "", tuple(by_id.values())).validate()
    scene.FitStatus = "Ready" if scene.AvatarProxy else "Pieces assigned"
    doc.recompute()
    return scene


def position_piece(piece, x, y, z=0.0, rotation_z=0.0):
    from freecad_cloth.avatar.AvatarFitting import PiecePlacement
    import FreeCAD as App
    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _scene(doc) or create_fitting_scene()
    if getattr(piece, "PatternType", "") != "PatternPiece":
        raise ValueError("piece must be a Cloth PatternPiece object")
    placement = App.Placement(App.Vector(float(x), float(y), float(z)), App.Rotation(App.Vector(0, 0, 1), float(rotation_z)))
    piece.Placement = placement
    entries = {p.piece_id: p for p in (PiecePlacement.from_string(v) for v in scene.PiecePlacements)}
    entries[str(piece.PieceId)] = PiecePlacement(str(piece.PieceId), (float(x), float(y), float(z)), float(rotation_z))
    scene.PiecePlacements = [entries[k].to_string() for k in sorted(entries)]
    doc.recompute()
    return piece


def create_arrangement_point(name, x, y, offset=0.0, wrap_direction="front", rotation_z=0.0, symmetry_group="", mirror=False):
    import FreeCAD as App
    from freecad_cloth.avatar.AvatarFitting import ArrangementPoint
    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _scene(doc) or create_fitting_scene()
    point = ArrangementPoint(str(name), float(x), float(y), float(offset), str(wrap_direction), float(rotation_z), str(symmetry_group))
    point.validate()
    values = {p.name: p for p in (ArrangementPoint.from_string(v) for v in scene.ArrangementPoints)}
    values[point.name] = point
    if mirror:
        if not symmetry_group.strip():
            raise ValueError("mirror arrangement points require a symmetry group")
        mirrored = point.mirrored()
        values[mirrored.name] = mirrored
    scene.ArrangementPoints = [values[k].to_string() for k in sorted(values)]
    scene.SymmetryEnabled = bool(scene.SymmetryEnabled)
    _sync_visuals(scene)
    return point


def set_arrangement_point(name, x=None, y=None, offset=None, wrap_direction=None, rotation_z=None, symmetry_group=None):
    from freecad_cloth.avatar.AvatarFitting import ArrangementPoint
    import FreeCAD as App
    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _scene(doc)
    if scene is None:
        raise ValueError("create a fitting scene first")
    values = {p.name: p for p in (ArrangementPoint.from_string(v) for v in scene.ArrangementPoints)}
    if name not in values:
        raise ValueError("unknown arrangement point: %s" % name)
    old = values[name]
    point = ArrangementPoint(old.name, old.x if x is None else float(x), old.y if y is None else float(y),
                             old.offset if offset is None else float(offset), old.wrap_direction if wrap_direction is None else str(wrap_direction),
                             old.rotation_z if rotation_z is None else float(rotation_z), old.symmetry_group if symmetry_group is None else str(symmetry_group))
    point.validate()
    values[name] = point
    scene.ArrangementPoints = [values[k].to_string() for k in sorted(values)]
    _sync_visuals(scene)
    doc.recompute()
    return point


def delete_arrangement_point(name):
    import FreeCAD as App
    from freecad_cloth.avatar.AvatarFitting import ArrangementPoint
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before deleting an arrangement point")
    scene = _scene(doc)
    if scene is None:
        raise ValueError("create a fitting scene first")
    values = {p.name: p for p in (ArrangementPoint.from_string(v) for v in scene.ArrangementPoints)}
    if name not in values:
        raise ValueError("unknown arrangement point: %s" % name)
    del values[name]
    scene.ArrangementPoints = [values[k].to_string() for k in sorted(values)]
    _sync_visuals(scene)
    return scene


def create_bounding_volume(name, center=(0.0, 0.0, 0.0), size=(100.0, 100.0, 100.0)):
    from freecad_cloth.avatar.AvatarFitting import BoundingVolume
    import FreeCAD as App
    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _scene(doc) or create_fitting_scene()
    volume = BoundingVolume(str(name), tuple(float(v) for v in center), tuple(float(v) for v in size))
    volume.validate()
    values = {v.name: v for v in (BoundingVolume.from_string(v) for v in scene.BoundingVolumes)}
    values[volume.name] = volume
    scene.BoundingVolumes = [values[k].to_string() for k in sorted(values)]
    _sync_visuals(scene)
    return volume


def delete_bounding_volume(name):
    from freecad_cloth.avatar.AvatarFitting import BoundingVolume
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before deleting a bounding volume")
    scene = _scene(doc)
    if scene is None:
        raise ValueError("create a fitting scene first")
    values = {v.name: v for v in (BoundingVolume.from_string(v) for v in scene.BoundingVolumes)}
    if name not in values:
        raise ValueError("unknown bounding volume: %s" % name)
    del values[name]
    scene.BoundingVolumes = [values[k].to_string() for k in sorted(values)]
    _sync_visuals(scene)
    return scene


def set_symmetry_enabled(enabled=True):
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before changing fitting symmetry")
    scene = _scene(doc)
    if scene is None:
        raise ValueError("create a fitting scene first")
    scene.SymmetryEnabled = bool(enabled)
    doc.recompute()
    return scene


def apply_arrangement_point(piece, point, mirror=None):
    """Place a pattern piece at a named point, optionally using its symmetric mate."""
    import FreeCAD as App
    from freecad_cloth.avatar.AvatarFitting import ArrangementPoint
    if getattr(piece, "PatternType", "") != "PatternPiece":
        raise ValueError("piece must be a Cloth PatternPiece object")
    doc = App.ActiveDocument
    scene = _scene(doc) if doc else None
    if scene is None:
        raise ValueError("create a fitting scene first")
    values = {p.name: p for p in (ArrangementPoint.from_string(v) for v in scene.ArrangementPoints)}
    if isinstance(point, str):
        if point not in values:
            raise ValueError("unknown arrangement point: %s" % point)
        point = values[point]
    point.validate()
    if mirror is True and scene.SymmetryEnabled:
        point = point.mirrored()
    rotations = {"front": point.rotation_z, "back": point.rotation_z + 180.0, "left": point.rotation_z + 90.0, "right": point.rotation_z - 90.0}
    return position_piece(piece, point.x, point.y, point.offset, rotations[point.wrap_direction])


def reset_arrangement():
    """Restore every assigned piece to its saved pre-arrangement placement."""
    import FreeCAD as App
    from freecad_cloth.avatar.AvatarFitting import PiecePlacement
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before resetting arrangement")
    scene = _scene(doc)
    if scene is None:
        raise ValueError("create a fitting scene first")
    pieces = {str(p.PieceId): p for p in scene.PatternPieces}
    homes = {p.piece_id: p for p in (PiecePlacement.from_string(v) for v in scene.HomePlacements)}
    current = {}
    for pid, placement in homes.items():
        piece = pieces.get(pid)
        if piece is None:
            continue
        piece.Placement = App.Placement(
            App.Vector(*placement.position),
            App.Rotation(App.Vector(*placement.rotation_axis), placement.rotation_z),
        )
        sketch = getattr(piece, "Sketch", None)
        if sketch is not None:
            sketch.Placement = piece.Placement
        current[pid] = placement
    scene.PiecePlacements = [current[k].to_string() for k in sorted(current)]
    scene.FitStatus = "Arrangement reset"
    doc.recompute()
    return scene


def target_aware_place_piece(piece, target, anchors, clearance=8.0, max_translation=600.0, max_rotation=45.0):
    """Rigidly place one PatternPiece against the authoritative DrapeTarget."""
    import FreeCAD as App
    from freecad_cloth.avatar.AvatarFitting import GarmentAnchor, PiecePlacement
    from freecad_cloth.simulation.DrapeTarget import collision_surface, target_status
    from freecad_cloth.avatar.TargetAwarePlacement import (
        assert_minimum_surface_clearance, require_ready_target_status,
        solve_rigid_z, target_surface_anchor, wrap_normal,
    )
    if getattr(piece, "PatternType", "") != "PatternPiece":
        raise ValueError("piece must be a Cloth PatternPiece object")
    if target is None or getattr(target, "SourceObject", None) is None:
        raise ValueError("a DrapeTarget with a source object is required")
    source_object = target.SourceObject
    status = target_status(target)
    require_ready_target_status(status)
    surface = collision_surface(
        source_object,
        float(getattr(target, "CollisionDeflection", 1.0)),
        float(getattr(target, "CollisionThickness", 0.0)),
    )
    piece_id = str(piece.PieceId)
    selected = tuple(
        item if isinstance(item, GarmentAnchor) else GarmentAnchor.from_string(item)
        for item in anchors or ()
    )
    selected = tuple(
        sorted(
            (item for item in selected if str(item.piece_id) == piece_id),
            key=lambda item: item.name,
        )
    )
    if not selected:
        raise ValueError("target-aware placement requires at least one garment anchor")
    source_points, target_points = [], []
    for anchor in selected:
        anchor.validate()
        source = piece.Placement.multVec(App.Vector(*anchor.position))
        hit = target_surface_anchor(
            surface,
            (source.x, source.y, source.z),
            wrap_normal(anchor.wrap_direction),
        )
        desired = tuple(
            hit.point[i] + hit.normal[i] * (float(getattr(surface, "thickness", 0.0)) + float(clearance))
            for i in range(3)
        )
        source_points.append((float(source.x), float(source.y), float(source.z)))
        target_points.append(desired)
    delta = solve_rigid_z(source_points, target_points, max_translation, max_rotation)
    from freecad_cloth.avatar.TargetAwarePlacement import apply_rigid_delta
    predicted_points = apply_rigid_delta(source_points, delta)
    anchor_clearance = assert_minimum_surface_clearance(surface, predicted_points, float(clearance))
    delta_rotation = App.Rotation(App.Vector(0, 0, 1), float(delta.rotation_z))
    current = piece.Placement
    new_base = delta_rotation.multVec(current.Base) + App.Vector(*delta.translation)
    piece.Placement = App.Placement(new_base, delta_rotation.multiply(current.Rotation))
    sketch = getattr(piece, "Sketch", None)
    if sketch is not None:
        sketch.Placement = piece.Placement
    placed_points = []
    for anchor in selected:
        point = piece.Placement.multVec(App.Vector(*anchor.position))
        placed_points.append((float(point.x), float(point.y), float(point.z)))
    verified_clearance = assert_minimum_surface_clearance(surface, placed_points, float(clearance))
    if abs(verified_clearance - anchor_clearance) > 1e-6:
        raise RuntimeError("target-aware placement changed after applying bounded transform")
    doc = piece.Document
    scene = _scene(doc)
    if scene is None:
        scene = create_fitting_scene()
    scene.DrapeTarget = target
    if target.SourceObject is not None and getattr(scene, "AvatarProxy", None) is None:
        scene.AvatarProxy = target.SourceObject
    pieces = [p for p in getattr(scene, "PatternPieces", ()) if p is not piece]
    pieces.append(piece)
    scene.PatternPieces = pieces
    from freecad_cloth.avatar.AvatarFitting import PiecePlacement
    entries = {
        p.piece_id: p
        for p in (PiecePlacement.from_string(v) for v in getattr(scene, "PiecePlacements", ()) or ())
    }
    entries[piece_id] = PiecePlacement(
        piece_id,
        (float(piece.Placement.Base.x), float(piece.Placement.Base.y), float(piece.Placement.Base.z)),
        float(piece.Placement.Rotation.Angle),
    )
    scene.PiecePlacements = [entries[k].to_string() for k in sorted(entries)]
    anchor_map = {
        (a.piece_id, a.name): a
        for a in (GarmentAnchor.from_string(v) for v in getattr(scene, "GarmentAnchors", ()) or ())
    }
    for anchor in selected:
        anchor_map[(anchor.piece_id, anchor.name)] = anchor
    scene.GarmentAnchors = [
        anchor_map[k].to_string()
        for k in sorted(anchor_map)
    ]
    scene.FitStatus = "Target-aware placement applied"
    doc.recompute()
    return {
        "translation": tuple(float(v) for v in delta.translation),
        "rotation_z": float(delta.rotation_z),
        "anchor_residual": float(delta.residual_max),
        "anchor_clearance": float(verified_clearance),
        "wrap_direction": selected[0].wrap_direction,
        "target": str(getattr(target, "Label", getattr(target, "Name", "DrapeTarget"))),
    }


def _infer_piece_wrap_direction(piece, target, surface):
    """Infer front/back/left/right only from the piece's current side of the target."""
    import FreeCAD as App
    width = float(getattr(piece, "Width", 0.0))
    height = float(getattr(piece, "Height", 0.0))
    if width <= 0.0 or height <= 0.0:
        box = getattr(getattr(piece, "Shape", None), "BoundBox", None)
        width = float(getattr(box, "XLength", 0.0))
        height = float(getattr(box, "YLength", 0.0))
    if width <= 0.0 or height <= 0.0:
        raise ValueError("pattern piece has no usable 2D dimensions")
    center = piece.Placement.multVec(App.Vector(width / 2.0, height / 2.0, 0.0))
    dx = float(center.x) - float(surface.center[0])
    dy = float(center.y) - float(surface.center[1])
    if abs(dx) <= 1e-9 and abs(dy) <= 1e-9:
        raise ValueError("piece must first be arranged to one side of the DrapeTarget")
    if abs(dy) >= abs(dx):
        return "front" if dy > 0.0 else "back"
    return "right" if dx > 0.0 else "left"


def snap_selected_piece_to_drape_target():
    """Snap exactly one selected PatternPiece to its selected/current DrapeTarget."""
    import FreeCADGui as Gui
    doc = Gui.activeDocument().Document
    pieces = [o for o in Gui.Selection.getSelection() if getattr(o, "PatternType", "") == "PatternPiece"]
    if len(pieces) != 1:
        raise ValueError("select exactly one PatternPiece before snapping to a DrapeTarget")
    targets = [o for o in Gui.Selection.getSelection() if getattr(o, "TargetType", "") in ("Mannequin", "FreeCAD Geometry")]
    target = targets[0] if targets else getattr(next(
        (o for o in doc.Objects if getattr(o, "AvatarType", "") == "ClothAvatar"), None
    ), "DrapeTarget", None)
    if target is None:
        raise ValueError("select a DrapeTarget or create a Cloth Avatar with an attached DrapeTarget")
    from freecad_cloth.avatar.AvatarFitting import GarmentAnchor
    from freecad_cloth.simulation.DrapeTarget import collision_surface
    surface = collision_surface(
        target.SourceObject,
        float(getattr(target, "CollisionDeflection", 1.0)),
        float(getattr(target, "CollisionThickness", 0.0)),
    )
    direction = _infer_piece_wrap_direction(pieces[0], target, surface)
    width = float(getattr(pieces[0], "Width", 0.0))
    height = float(getattr(pieces[0], "Height", 0.0))
    anchors = (
        GarmentAnchor(str(pieces[0].PieceId), "target_left", (0.14 * width, 0.97 * height, 0.0), direction),
        GarmentAnchor(str(pieces[0].PieceId), "target_right", (0.86 * width, 0.97 * height, 0.0), direction),
    )
    result = target_aware_place_piece(
        pieces[0],
        target,
        anchors,
        clearance=max(3.0, float(getattr(target, "CollisionThickness", 0.0))),
    )
    return result


def create_simulation_from_fitting():
    import FreeCAD as App
    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _scene(doc)
    if scene is None:
        raise ValueError("create a fitting scene first")
    if not scene.PatternPieces:
        raise ValueError("add at least one pattern piece to the fitting scene")
    from freecad_cloth.simulation.SimulationObjects import create_simulation_scene
    simulation = create_simulation_scene(doc)
    simulation.ClothPieces = list(scene.PatternPieces)
    if scene.AvatarProxy is not None:
        simulation.AvatarProxy = scene.AvatarProxy
    if getattr(scene, "DrapeTarget", None) is not None:
        simulation.DrapeTarget = scene.DrapeTarget
    doc.recompute()
    return simulation


class _FittingProxy:
    Type = "ClothFittingScene"

    def execute(self, obj):
        from freecad_cloth.avatar.AvatarFitting import BodyMeasurements, FittingScene, PiecePlacement, ArrangementPoint, BoundingVolume
        _migrate_visual_output_references(obj)
        measurements = BodyMeasurements.from_json(obj.MeasurementData)
        avatar_name = getattr(obj.AvatarProxy, "Label", "") if obj.AvatarProxy else ""
        placements = tuple(PiecePlacement.from_string(v) for v in obj.PiecePlacements)
        points = tuple(ArrangementPoint.from_string(v) for v in obj.ArrangementPoints)
        volumes = tuple(BoundingVolume.from_string(v) for v in obj.BoundingVolumes)
        from freecad_cloth.avatar.AvatarFitting import GarmentAnchor
        anchors = tuple(GarmentAnchor.from_string(v) for v in getattr(obj, "GarmentAnchors", ()) or ())
        FittingScene(measurements, avatar_name, placements, points, volumes, bool(obj.SymmetryEnabled), anchors).validate()


COMMANDS = [
    "ClothFitting_CreateScene",
    "ClothFitting_SetMeasurements",
    "ClothFitting_AssignAvatar",
    "ClothFitting_AddPieces",
    "ClothFitting_CreateArrangementPoint",
    "ClothFitting_SetArrangementPoint",
    "ClothFitting_DeleteArrangementPoint",
    "ClothFitting_CreateBoundingVolume",
    "ClothFitting_DeleteBoundingVolume",
    "ClothFitting_SetSymmetry",
    "ClothFitting_ApplyArrangementPoint",
    "ClothFitting_SnapToDrapeTarget",
    "ClothFitting_ResetArrangement",
    "ClothFitting_CreateSimulation",
]
_COMMAND_HANDLERS = {
    "ClothFitting_CreateScene": create_fitting_scene,
    "ClothFitting_SetMeasurements": lambda: set_body_measurements({"height": 1700, "chest": 900, "waist": 760, "hip": 960, "shoulder": 420}),
    "ClothFitting_AssignAvatar": assign_avatar_source,
    "ClothFitting_AddPieces": add_selected_pattern_pieces,
    "ClothFitting_CreateArrangementPoint": lambda: create_arrangement_point("Point1", 0, 0),
    "ClothFitting_SetArrangementPoint": lambda: set_arrangement_point("Point1", x=0, y=0),
    "ClothFitting_DeleteArrangementPoint": lambda: delete_arrangement_point("Point1"),
    "ClothFitting_CreateBoundingVolume": lambda: create_bounding_volume("Volume1"),
    "ClothFitting_DeleteBoundingVolume": lambda: delete_bounding_volume("Volume1"),
    "ClothFitting_SetSymmetry": lambda: set_symmetry_enabled(True),
    "ClothFitting_ApplyArrangementPoint": lambda: _apply_selected_arrangement(),
    "ClothFitting_SnapToDrapeTarget": snap_selected_piece_to_drape_target,
    "ClothFitting_ResetArrangement": reset_arrangement,
    "ClothFitting_CreateSimulation": create_simulation_from_fitting,
}


def _apply_selected_arrangement():
    import FreeCADGui as Gui
    scene = _scene(Gui.activeDocument().Document)
    if scene is None:
        raise ValueError("create a fitting scene first")
    piece = next((o for o in Gui.Selection.getSelection() if getattr(o, "PatternType", "") == "PatternPiece"), None)
    point = next((o for o in Gui.Selection.getSelection() if getattr(o, "FittingType", "") == "ArrangementPoint"), None)
    if piece is None or point is None:
        raise ValueError("select a pattern piece and an arrangement point")
    return apply_arrangement_point(piece, point.PointName)


try:
    import FreeCADGui as Gui
    from freecad_cloth.common.CommandAdapter import register_commands
    register_commands(Gui, _COMMAND_HANDLERS)
except (ImportError, AttributeError):
    pass
