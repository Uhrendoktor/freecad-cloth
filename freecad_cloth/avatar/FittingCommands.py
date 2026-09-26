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
    obj.addProperty("App::PropertyLink", "DrapeTarget", "Fitting")
    obj.addProperty("App::PropertyFloat", "TargetClearance", "Fitting").TargetClearance = 20.0
    obj.addProperty("App::PropertyFloat", "PlacementTranslationLimit", "Fitting").PlacementTranslationLimit = 1000.0
    obj.addProperty("App::PropertyAngle", "PlacementRotationLimit", "Fitting").PlacementRotationLimit = 90.0
    obj.addProperty("App::PropertyLinkListGlobal", "PatternPieces", "Fitting")
    obj.addProperty("App::PropertyStringList", "PiecePlacements", "Fitting").PiecePlacements = []
    obj.addProperty("App::PropertyStringList", "HomePlacements", "Fitting").HomePlacements = []
    obj.addProperty("App::PropertyStringList", "ArrangementPoints", "Arrangement").ArrangementPoints = []
    obj.addProperty("App::PropertyStringList", "BoundingVolumes", "Arrangement").BoundingVolumes = []
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
    candidate = getattr(source, "DrapeTarget", None) or doc.getObject("DrapeTarget")
    if candidate is not None and getattr(candidate, "SourceObject", None) is source:
        scene.DrapeTarget = candidate
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



def _target_world_surface(target):
    """Return the authoritative DrapeTarget collision surface in world coordinates."""
    import FreeCAD as App
    from freecad_cloth.simulation.DrapeTarget import collision_surface, target_status

    status = target_status(target)
    if status["state"] != "ready":
        raise ValueError("drape target is not ready: %s" % status["message"])
    source = getattr(target, "SourceObject", None)
    if source is None:
        raise ValueError("drape target has no source object")
    surface = collision_surface(
        source,
        float(getattr(target, "CollisionDeflection", 1.0)),
        float(getattr(target, "CollisionThickness", 0.0)),
    )
    placement = getattr(source, "Placement", None)
    vertices = []
    for x, y, z in surface.vertices:
        point = App.Vector(float(x), float(y), float(z))
        world = placement.multVec(point) if placement is not None else point
        vertices.append((float(world.x), float(world.y), float(world.z)))
    return vertices


def _surface_y_envelope(surface_vertices, x, z, side, window=None, limit=128):
    """Find a deterministic front/back surface Y near a target-relative X/Z anchor."""
    if not surface_vertices:
        raise ValueError("drape target collision surface is empty")
    points = sorted(
        surface_vertices,
        key=lambda p: ((p[0] - float(x)) ** 2 + (p[2] - float(z)) ** 2),
    )[: max(8, int(limit))]
    if window is not None:
        local = [p for p in points if abs(p[0] - float(x)) <= window and abs(p[2] - float(z)) <= window]
        if len(local) >= 4:
            points = local
    return (min(p[1] for p in points) if side == "front" else max(p[1] for p in points))


def _target_semantic_anchor(target, surface_vertices):
    """Return target-relative centerline and shoulder height from persistent avatar semantics."""
    source = getattr(target, "SourceObject", None)
    points = {}
    for record in getattr(source, "ArrangementPoints", ()) or ():
        try:
            name, coords = str(record).split("|", 1)
            values = tuple(float(v) for v in coords.split(","))
            if len(values) == 3:
                points[name] = values
        except (ValueError, TypeError):
            continue
    placement = getattr(source, "Placement", None)
    def world(value):
        if placement is None:
            return value
        vector = placement.multVec(__import__("FreeCAD").Vector(*value))
        return (float(vector.x), float(vector.y), float(vector.z))
    shoulder = [points[name] for name in ("shoulder_left", "shoulder_right") if name in points]
    if shoulder:
        shoulder_world = [world(value) for value in shoulder]
        center_x = sum(p[0] for p in shoulder_world) / len(shoulder_world)
        shoulder_z = sum(p[2] for p in shoulder_world) / len(shoulder_world)
        waist_values = [points[name] for name in ("waist", "hip") if name in points]
        lower_z = min(world(value)[2] for value in waist_values) if waist_values else shoulder_z
        target_span = max(abs(p[0] - center_x) for p in shoulder_world) * 2.0
        return center_x, shoulder_z, lower_z, max(1.0, target_span)
    xs = [p[0] for p in surface_vertices]
    zs = [p[2] for p in surface_vertices]
    return (0.5 * (min(xs) + max(xs)), max(zs), min(zs), max(1.0, max(xs) - min(xs)))


def _piece_world_points(piece, limit=512):
    """Sample one pattern piece in world space without mutating its placement."""
    import FreeCAD as App
    shape = getattr(piece, "Shape", None)
    if shape is None or getattr(shape, "isNull", lambda: True)():
        placement = getattr(piece, "Placement", None)
        box = getattr(getattr(piece, "Mesh", None), "BoundBox", None)
        if box is None:
            raise ValueError("pattern piece has no usable Shape/Mesh geometry")
        local_points = (
            App.Vector(box.XMin, box.YMin, box.ZMin),
            App.Vector(box.XMin, box.YMin, box.ZMax),
            App.Vector(box.XMin, box.YMax, box.ZMin),
            App.Vector(box.XMin, box.YMax, box.ZMax),
            App.Vector(box.XMax, box.YMin, box.ZMin),
            App.Vector(box.XMax, box.YMin, box.ZMax),
            App.Vector(box.XMax, box.YMax, box.ZMin),
            App.Vector(box.XMax, box.YMax, box.ZMax),
        )
    else:
        try:
            local_points, _triangles = shape.tessellate(2.0)
        except Exception:
            local_points = ()
        if not local_points:
            box = shape.BoundBox
            local_points = (
                App.Vector(box.XMin, box.YMin, box.ZMin),
                App.Vector(box.XMin, box.YMin, box.ZMax),
                App.Vector(box.XMin, box.YMax, box.ZMin),
                App.Vector(box.XMin, box.YMax, box.ZMax),
                App.Vector(box.XMax, box.YMin, box.ZMin),
                App.Vector(box.XMax, box.YMin, box.ZMax),
                App.Vector(box.XMax, box.YMax, box.ZMin),
                App.Vector(box.XMax, box.YMax, box.ZMax),
            )
    if limit and len(local_points) > limit:
        stride = max(1, len(local_points) // int(limit))
        local_points = local_points[::stride][: int(limit)]
    placement = getattr(piece, "Placement", None)
    return [
        tuple(float(v) for v in (
            (placement.multVec(point) if placement is not None else point).x,
            (placement.multVec(point) if placement is not None else point).y,
            (placement.multVec(point) if placement is not None else point).z,
        ))
        for point in local_points
    ]


def target_relative_clearance_report(pieces, target, side_by_piece, required_clearance):
    """Return a deterministic step-0 outward-clearance report against the DrapeTarget surface."""
    surface = _target_world_surface(target)
    report = {}
    global_min = float("inf")
    for piece in pieces:
        side = side_by_piece[str(getattr(piece, "PieceId", piece.Name))]
        points = _piece_world_points(piece)
        gaps = []
        for point in points:
            envelope = _surface_y_envelope(surface, point[0], point[2], side)
            gap = (envelope - point[1]) if side == "front" else (point[1] - envelope)
            gaps.append(float(gap))
        if not gaps:
            raise ValueError("pattern piece has no geometry for clearance validation")
        minimum = min(gaps)
        report[str(getattr(piece, "PieceId", piece.Name))] = minimum
        global_min = min(global_min, minimum)
    if global_min < float(required_clearance):
        raise ValueError(
            "target-relative arrangement penetrates the DrapeTarget envelope: min clearance %.3f < %.3f"
            % (global_min, float(required_clearance))
        )
    return {"min_clearance": float(global_min), "per_piece": report}


def snap_pattern_pieces_to_target(
    scene=None,
    pieces=None,
    target=None,
    clearance=None,
    max_translation=None,
    max_rotation=None,
    side_by_piece=None,
):
    """Place a bounded garment rigidly around the authoritative DrapeTarget.

    The operation is solver-neutral fitting state. It uses persistent target
    geometry/landmarks, preserves authored piece rotation and relative X/Z
    spacing, rejects stale/missing/ambiguous targets, and records the resulting
    placements in the fitting scene so HomePlacements can restore them.
    """
    import FreeCAD as App
    from freecad_cloth.avatar.AvatarFitting import PiecePlacement
    from freecad_cloth.simulation.DrapeTarget import target_status

    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before fitting garment pieces")
    scene = scene or _scene(doc)
    if scene is None:
        raise ValueError("create a fitting scene first")
    target = target or getattr(scene, "DrapeTarget", None)
    if target is None:
        raise ValueError("assign a persistent DrapeTarget before target-relative fitting")
    status = target_status(target)
    if status["state"] != "ready":
        raise ValueError("drape target is not ready: %s" % status["message"])
    selected = tuple(pieces or scene.PatternPieces)
    selected = tuple(sorted(
        (piece for piece in selected if getattr(piece, "PatternType", "") == "PatternPiece"),
        key=lambda item: str(getattr(item, "PieceId", item.Name)),
    ))
    if not selected:
        raise ValueError("no PatternPiece objects were supplied")
    if side_by_piece is None:
        if len(selected) == 1:
            side_by_piece = {str(getattr(selected[0], "PieceId", selected[0].Name)): "front"}
        elif len(selected) == 2:
            side_by_piece = {
                str(getattr(selected[0], "PieceId", selected[0].Name)): "front",
                str(getattr(selected[1], "PieceId", selected[1].Name)): "back",
            }
        else:
            raise ValueError("ambiguous target-relative fitting: provide explicit side assignments for more than two pieces")
    normalized_sides = {str(key): str(value) for key, value in side_by_piece.items()}
    if set(normalized_sides.values()) - {"front", "back"}:
        raise ValueError("target-relative fitting supports front/back side assignments only")
    piece_ids = {str(getattr(piece, "PieceId", piece.Name)) for piece in selected}
    if set(normalized_sides) != piece_ids:
        raise ValueError("side assignment must cover every selected pattern piece")
    clearance = float(clearance if clearance is not None else getattr(scene, "TargetClearance", 20.0))
    max_translation = float(max_translation if max_translation is not None else getattr(scene, "PlacementTranslationLimit", 1000.0))
    max_rotation = float(max_rotation if max_rotation is not None else getattr(scene, "PlacementRotationLimit", 90.0))
    if clearance < 0 or max_translation <= 0 or max_rotation <= 0:
        raise ValueError("target-relative fitting bounds must be positive")
    surface = _target_world_surface(target)
    anchor_x, shoulder_z, _lower_z, _target_width = _target_semantic_anchor(target, surface)
    centers = {}
    spans_z = {}
    for piece in selected:
        pts = _piece_world_points(piece)
        centers[str(piece.PieceId)] = (
            sum(p[0] for p in pts) / len(pts),
            sum(p[1] for p in pts) / len(pts),
            sum(p[2] for p in pts) / len(pts),
        )
        spans_z[str(piece.PieceId)] = max(p[2] for p in pts) - min(p[2] for p in pts)
    group_cx = sum(v[0] for v in centers.values()) / len(centers)
    group_cz = sum(v[2] for v in centers.values()) / len(centers)
    garment_height = max(spans_z.values()) if spans_z else 1.0
    group_target_cz = shoulder_z - 0.5 * garment_height
    front_surface_y = _surface_y_envelope(surface, anchor_x, group_target_cz, "front")
    back_surface_y = _surface_y_envelope(surface, anchor_x, group_target_cz, "back")
    desired_y = {"front": front_surface_y - clearance, "back": back_surface_y + clearance}
    common_dx = anchor_x - group_cx
    common_dz = group_target_cz - group_cz
    homes = {}
    for value in getattr(scene, "HomePlacements", ()) or ():
        placement = PiecePlacement.from_string(value)
        homes[placement.piece_id] = placement
    updated = {}
    for piece in selected:
        pid = str(piece.PieceId)
        center = centers[pid]
        dx = common_dx
        dy = desired_y[normalized_sides[pid]] - center[1]
        dz = common_dz
        distance = (dx * dx + dy * dy + dz * dz) ** 0.5
        if distance > max_translation:
            raise ValueError("target-relative translation exceeds configured bound for %s" % pid)
        current_rotation = float(getattr(getattr(piece, "Placement", None), "Rotation", App.Rotation()).Angle)
        home_rotation = float(homes[pid].rotation_z) if pid in homes else current_rotation
        rotation_delta = abs(current_rotation - home_rotation)
        while rotation_delta > 180.0:
            rotation_delta -= 360.0
        rotation_delta = abs(rotation_delta)
        if rotation_delta > max_rotation:
            raise ValueError("target-relative rotation exceeds configured bound for %s" % pid)
        placement = piece.Placement
        base = placement.Base
        piece.Placement = App.Placement(
            App.Vector(float(base.x) + dx, float(base.y) + dy, float(base.z) + dz),
            placement.Rotation,
        )
        updated[pid] = PiecePlacement(
            pid,
            (float(piece.Placement.Base.x), float(piece.Placement.Base.y), float(piece.Placement.Base.z)),
            float(piece.Placement.Rotation.Angle),
        )
    for pid, placement in updated.items():
        existing = {p.piece_id: p for p in (PiecePlacement.from_string(v) for v in scene.PiecePlacements)}
        existing[pid] = placement
        scene.PiecePlacements = [existing[k].to_string() for k in sorted(existing)]
    scene.FitStatus = "Target-relative fit"
    doc.recompute()
    report = target_relative_clearance_report(selected, target, normalized_sides, clearance)
    return report



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
        x, y, z = placement.position
        piece.Placement = App.Placement(App.Vector(x, y, z), App.Rotation(App.Vector(0, 0, 1), placement.rotation_z))
        current[pid] = placement
    scene.PiecePlacements = [current[k].to_string() for k in sorted(current)]
    scene.FitStatus = "Arrangement reset"
    doc.recompute()
    return scene


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
        generated_target = getattr(simulation, "DrapeTarget", None)
        simulation.DrapeTarget = scene.DrapeTarget
        if generated_target is not None and generated_target is not scene.DrapeTarget:
            try:
                doc.removeObject(generated_target.Name)
            except Exception:
                pass
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
        FittingScene(measurements, avatar_name, placements, points, volumes, bool(obj.SymmetryEnabled)).validate()


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
    "ClothFitting_SnapPiecesToTarget",
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
    "ClothFitting_SnapPiecesToTarget": lambda: snap_pattern_pieces_to_target(),
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
