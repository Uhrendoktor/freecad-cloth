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

def _ensure_fitting_runtime_properties(scene):
    _ensure_avatar_proxy_link_global(scene)
    if "DrapeTarget" not in getattr(scene, "PropertiesList", ()):
        scene.addProperty("App::PropertyLinkGlobal", "DrapeTarget", "Fitting")
    if "GarmentAnchors" not in getattr(scene, "PropertiesList", ()):
        scene.addProperty("App::PropertyStringList", "GarmentAnchors", "Arrangement")
        scene.GarmentAnchors = []
    return scene


def _ensure_avatar_proxy_link_global(scene):
    """Keep the persisted avatar link valid across native Garment scopes."""
    properties = getattr(scene, "PropertiesList", ())
    if "AvatarProxy" not in properties:
        scene.addProperty("App::PropertyLinkGlobal", "AvatarProxy", "Fitting")
        return scene
    try:
        type_id = str(scene.getTypeIdOfProperty("AvatarProxy"))
    except (AttributeError, RuntimeError):
        type_id = ""
    if type_id == "App::PropertyLinkGlobal":
        return scene
    if type_id != "App::PropertyLink":
        raise RuntimeError("FittingScene AvatarProxy must be a document-global link")
    current = getattr(scene, "AvatarProxy", None)
    scene.removeProperty("AvatarProxy")
    scene.addProperty("App::PropertyLinkGlobal", "AvatarProxy", "Fitting")
    if current is not None:
        scene.AvatarProxy = current
    return scene


def create_fitting_scene():
    import FreeCAD as App
    from freecad_cloth.avatar.AvatarFitting import BodyMeasurements, FittingScene

    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    existing = _scene(doc)
    if existing is not None:
        return _ensure_fitting_runtime_properties(existing)
    obj = doc.addObject("App::FeaturePython", "FittingScene")
    obj.Label = "Avatar Fitting Scene"
    obj.addProperty("App::PropertyString", "FittingType", "Fitting").FittingType = "FittingScene"
    obj.addProperty("App::PropertyString", "MeasurementData", "Measurements").MeasurementData = BodyMeasurements().to_json()
    obj.addProperty("App::PropertyString", "MeasurementUnit", "Measurements").MeasurementUnit = "mm"
    obj.addProperty("App::PropertyLinkGlobal", "AvatarProxy", "Fitting")
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
    target = getattr(avatar, "Document", None).getObject("DrapeTarget") if getattr(avatar, "Document", None) is not None else None
    if target is None:
        target = doc.getObject("DrapeTarget")
    if target is None:
        raise RuntimeError("avatar assignment did not create the authoritative DrapeTarget")
    _ensure_fitting_runtime_properties(scene)
    scene.DrapeTarget = target
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
        axis = placement.Rotation.Axis
        value = PiecePlacement(
            str(piece.PieceId),
            (float(base.x), float(base.y), float(base.z)),
            float(placement.Rotation.Angle),
            (float(axis.x), float(axis.y), float(axis.z)),
        )
        by_id[value.piece_id] = value
        home_by_id.setdefault(value.piece_id, value)
    scene.PatternPieces = sorted(set(list(scene.PatternPieces) + pieces), key=lambda o: str(o.PieceId))
    scene.PiecePlacements = [by_id[k].to_string() for k in sorted(by_id)]
    scene.HomePlacements = [home_by_id[k].to_string() for k in sorted(home_by_id)]
    _ensure_fitting_runtime_properties(scene)
    existing_anchor_keys = {
        (str(anchor.split("|", 3)[0]), str(anchor.split("|", 4)[1]))
        for anchor in (getattr(scene, "GarmentAnchors", ()) or ())
        if str(anchor).count("|") >= 3
    }
    from freecad_cloth.avatar.AvatarFitting import GarmentAnchor
    defaults = list(getattr(scene, "GarmentAnchors", ()) or ())
    for piece in pieces:
        pid = str(piece.PieceId)
        if any(key[0] == pid for key in existing_anchor_keys):
            continue
        width = max(1.0, float(getattr(piece, "Width", 100.0) or 100.0))
        height = max(1.0, float(getattr(piece, "Height", 100.0) or 100.0))
        wrap = "back" if "back" in str(getattr(piece, "Label", "") or getattr(piece, "Name", "")).lower() else "front"
        defaults.extend((
            GarmentAnchor(pid, "shoulder_left", (0.15 * width, 0.95 * height, 0.0), wrap).to_string(),
            GarmentAnchor(pid, "shoulder_right", (0.85 * width, 0.95 * height, 0.0), wrap).to_string(),
        ))
        existing_anchor_keys.add((pid, "shoulder_left"))
        existing_anchor_keys.add((pid, "shoulder_right"))
    scene.GarmentAnchors = sorted(set(defaults))
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
        x, y, z = placement.position
        restored_piece = App.Placement(
            App.Vector(x, y, z),
            App.Rotation(App.Vector(*placement.rotation_axis), placement.rotation_z),
        )
        piece.Placement = restored_piece
        sketch = getattr(piece, "Sketch", None)
        if sketch is not None:
            sketch.Placement = App.Placement(restored_piece)
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
    _ensure_fitting_runtime_properties(scene)
    if getattr(scene, "DrapeTarget", None) is not None:
        simulation.DrapeTarget = scene.DrapeTarget
    doc.recompute()
    return simulation



def set_garment_anchors(anchors):
    """Persist explicit garment-local anchors without changing the shared placement authority."""
    import FreeCAD as App
    from freecad_cloth.avatar.AvatarFitting import GarmentAnchor
    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _ensure_fitting_runtime_properties(_scene(doc) or create_fitting_scene())
    parsed = []
    for anchor in anchors or ():
        item = anchor if isinstance(anchor, GarmentAnchor) else GarmentAnchor.from_string(anchor)
        item.validate()
        parsed.append(item)
    scene.GarmentAnchors = [item.to_string() for item in sorted(parsed, key=lambda value: (value.piece_id, value.name))]
    doc.recompute()
    return scene


def _default_anchor_map(scene, pieces):
    from freecad_cloth.avatar.AvatarFitting import GarmentAnchor
    values = [GarmentAnchor.from_string(item) for item in (getattr(scene, "GarmentAnchors", ()) or ())]
    by_piece = {}
    for anchor in values:
        by_piece.setdefault(str(anchor.piece_id), []).append(anchor)
    missing = [str(piece.PieceId) for piece in pieces if str(piece.PieceId) not in by_piece]
    if missing:
        raise ValueError("target-aware placement requires persistent garment anchors for: %s" % ",".join(sorted(missing)))
    return {key: tuple(sorted(items, key=lambda item: item.name)) for key, items in by_piece.items()}


def _world_target_surface(target):
    import FreeCAD as App
    from freecad_cloth.avatar.AvatarCollision import CollisionSurface
    from freecad_cloth.simulation.DrapeTarget import collision_surface

    source = getattr(target, "SourceObject", None)
    if source is None:
        raise ValueError("DrapeTarget has no source object")
    local = collision_surface(
        source,
        float(getattr(target, "CollisionDeflection", 1.0)),
        float(getattr(target, "CollisionThickness", 0.0)),
    )
    placement = getattr(source, "Placement", None)
    if placement is None:
        return local
    world_vertices = []
    for point in local.vertices:
        value = placement.multVec(App.Vector(*point))
        world_vertices.append((float(value.x), float(value.y), float(value.z)))
    surface = CollisionSurface(tuple(world_vertices), tuple(local.triangles), str(local.region), float(local.thickness))
    surface.validate()
    return surface


def _piece_world_samples(piece, deflection=1.0):
    import FreeCAD as App
    shape = getattr(piece, "Shape", None)
    placement = getattr(piece, "Placement", None)
    if shape is not None and not getattr(shape, "isNull", lambda: True)():
        tessellate = getattr(shape, "tessellate", None)
        if callable(tessellate):
            points, _triangles = tessellate(float(deflection))
            if points:
                result = []
                for point in points:
                    value = placement.multVec(point) if placement is not None else point
                    result.append((float(value.x), float(value.y), float(value.z)))
                return tuple(result)
        vertices = getattr(shape, "Vertexes", ())
        if vertices:
            return tuple(
                tuple(float(v) for v in (placement.multVec(vertex.Point) if placement is not None else vertex.Point))
                for vertex in vertices
            )
    raise ValueError("pattern piece %s has no usable geometry samples" % getattr(piece, "Name", "<unnamed>"))


def _nearest_surface_projection(surface, point):
    from freecad_cloth.avatar.TargetAwarePlacement import _closest_point_on_triangle, _triangle_normal, SurfaceHit
    best = None
    best_key = None
    for triangle_index in range(len(surface.triangles)):
        ia, ib, ic = surface.triangles[triangle_index]
        closest = _closest_point_on_triangle(
            point,
            surface.vertices[ia],
            surface.vertices[ib],
            surface.vertices[ic],
        )
        distance = sum((float(point[i]) - float(closest[i])) ** 2 for i in range(3))
        key = (round(distance, 12), triangle_index)
        if best is None or key < best_key:
            best = SurfaceHit(triangle_index, closest, _triangle_normal(surface, triangle_index), distance ** 0.5)
            best_key = key
    if best is None:
        raise TargetPlacementError("DrapeTarget collision surface has no triangles")
    return best


def _minimum_signed_surface_clearance(surface, points):
    minimum = float("inf")
    for point in points:
        hit = _nearest_surface_projection(surface, point)
        signed = sum(
            (float(point[i]) - float(hit.point[i])) * float(hit.normal[i])
            for i in range(3)
        )
        minimum = min(minimum, float(signed))
    if minimum == float("inf"):
        raise TargetPlacementError("pattern piece has no geometry samples")
    return minimum


def _world_target_surface(target):
    import FreeCAD as App
    from freecad_cloth.avatar.AvatarCollision import CollisionSurface
    from freecad_cloth.simulation.DrapeTarget import collision_surface

    source = getattr(target, "SourceObject", None)
    if source is None:
        raise ValueError("DrapeTarget has no source object")
    local = collision_surface(
        source,
        float(getattr(target, "CollisionDeflection", 1.0)),
        float(getattr(target, "CollisionThickness", 0.0)),
    )
    placement = getattr(source, "Placement", None)
    if placement is None:
        return local
    world_vertices = []
    for point in local.vertices:
        value = placement.multVec(App.Vector(*point))
        world_vertices.append((float(value.x), float(value.y), float(value.z)))
    surface = CollisionSurface(tuple(world_vertices), tuple(local.triangles), str(local.region), float(local.thickness))
    surface.validate()
    return surface


def _piece_world_samples(piece, deflection=1.0):
    import FreeCAD as App
    shape = getattr(piece, "Shape", None)
    placement = getattr(piece, "Placement", None)
    if shape is not None and not getattr(shape, "isNull", lambda: True)():
        tessellate = getattr(shape, "tessellate", None)
        if callable(tessellate):
            points, _triangles = tessellate(float(deflection))
            if points:
                result = []
                for point in points:
                    value = placement.multVec(point) if placement is not None else point
                    result.append((float(value.x), float(value.y), float(value.z)))
                return tuple(result)
        vertices = getattr(shape, "Vertexes", ())
        if vertices:
            return tuple(
                tuple(float(v) for v in (placement.multVec(vertex.Point) if placement is not None else vertex.Point))
                for vertex in vertices
            )
    raise ValueError("pattern piece %s has no usable geometry samples" % getattr(piece, "Name", "<unnamed>"))


def _nearest_surface_projection(surface, point):
    from freecad_cloth.avatar.TargetAwarePlacement import _closest_point_on_triangle, _triangle_normal, SurfaceHit
    best = None
    best_key = None
    for triangle_index in range(len(surface.triangles)):
        ia, ib, ic = surface.triangles[triangle_index]
        closest = _closest_point_on_triangle(
            point,
            surface.vertices[ia],
            surface.vertices[ib],
            surface.vertices[ic],
        )
        squared_distance = sum(
            (float(point[i]) - float(closest[i])) ** 2
            for i in range(3)
        )
        key = (round(squared_distance, 12), triangle_index)
        if best is None or key < best_key:
            best = SurfaceHit(
                triangle_index,
                closest,
                _triangle_normal(surface, triangle_index),
                squared_distance ** 0.5,
            )
            best_key = key
    if best is None:
        raise TargetPlacementError("DrapeTarget collision surface has no triangles")
    return best


def _minimum_signed_surface_clearance(surface, points):
    minimum = float("inf")
    for point in points:
        hit = _nearest_surface_projection(surface, point)
        signed = sum(
            (float(point[i]) - float(hit.point[i])) * float(hit.normal[i])
            for i in range(3)
        )
        minimum = min(minimum, float(signed))
    if minimum == float("inf"):
        raise TargetPlacementError("pattern piece has no geometry samples")
    return minimum


def snap_pieces_to_target(pattern_pieces=None, clearance=8.0, max_translation=600.0, max_rotation=45.0):
    """Apply one shared rigid garment transform transactionally.

    Persistent garment anchors provide stable authored metadata and the preferred
    correspondence. When their geometry cannot be represented by one bounded
    rigid transform, fall back to one shared translation derived from whole-piece
    projections. The authored pairwise displacement/rotation remains invariant.
    """
    import FreeCAD as App
    from freecad_cloth.avatar.TargetAwarePlacement import TargetPlacementError, RigidDelta, solve_rigid_z, target_surface_anchor, wrap_normal
    from freecad_cloth.simulation.DrapeTarget import target_status

    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _ensure_fitting_runtime_properties(_scene(doc) or create_fitting_scene())
    target = getattr(scene, "DrapeTarget", None)
    status = target_status(target)
    if status.get("state") != "ready":
        raise TargetPlacementError(status.get("message", "drape target is not ready"))
    pieces = tuple(pattern_pieces or getattr(scene, "PatternPieces", ()) or ())
    if not pieces:
        raise ValueError("target-aware placement requires at least one pattern piece")
    piece_ids = {str(piece.PieceId) for piece in pieces}
    anchors_by_piece = _default_anchor_map(scene, pieces)
    anchors = [
        anchor
        for pid in sorted(anchors_by_piece)
        for anchor in anchors_by_piece[pid]
        if pid in piece_ids
    ]
    if len(anchors) < 2:
        raise TargetPlacementError("target-aware placement requires at least two persistent anchors")
    surface = _world_target_surface(target)
    tolerance = max(float(clearance) * 2.5, 20.0)
    delta_mode = "anchor-rigid"

    source_points = []
    target_points = []
    for anchor in anchors:
        piece = next(piece for piece in pieces if str(piece.PieceId) == str(anchor.piece_id))
        source = piece.Placement.multVec(App.Vector(*anchor.position))
        normal = wrap_normal(anchor.wrap_direction)
        hit = target_surface_anchor(surface, (source.x, source.y, source.z), normal)
        desired = tuple(
            hit.point[i]
            + hit.normal[i] * (float(getattr(surface, "thickness", 0.0)) + float(clearance))
            for i in range(3)
        )
        source_points.append((float(source.x), float(source.y), float(source.z)))
        target_points.append(desired)

    delta = solve_rigid_z(
        source_points,
        target_points,
        max_translation=float(max_translation),
        max_rotation=float(max_rotation),
    )

    if delta.residual_max > tolerance:
        delta_mode = "group-translation-fallback"
        centers = []
        desired = []
        for piece in pieces:
            samples = _piece_world_samples(piece, 1.0)
            center = tuple(
                sum(point[i] for point in samples) / len(samples)
                for i in range(3)
            )
            projection = _nearest_surface_projection(surface, center)
            centers.append(center)
            desired.append(tuple(
                projection.point[i]
                + projection.normal[i] * (
                    float(getattr(surface, "thickness", 0.0)) + float(clearance)
                )
                for i in range(3)
            ))
        shared_translation = tuple(
            sum(
                desired[index][axis] - centers[index][axis]
                for index in range(len(pieces))
            ) / len(pieces)
            for axis in range(3)
        )
        travel = sum(float(value) ** 2 for value in shared_translation) ** 0.5
        if travel > float(max_translation) + 1e-9:
            raise TargetPlacementError(
                "target-aware group translation exceeds %.3f mm"
                % float(max_translation)
            )
        delta = RigidDelta(
            tuple(float(value) for value in shared_translation),
            0.0,
            float(delta.residual_max),
        )

    snapshots = []
    previous_piece_placements = list(getattr(scene, "PiecePlacements", ()) or ())
    previous_fit_status = str(getattr(scene, "FitStatus", ""))
    previous_target = getattr(scene, "DrapeTarget", None)
    try:
        rotation = App.Rotation(App.Vector(0, 0, 1), float(delta.rotation_z))
        translation = App.Vector(*delta.translation)
        for piece in pieces:
            placement = piece.Placement
            sketch = getattr(piece, "Sketch", None)
            snapshots.append(
                (
                    piece,
                    App.Placement(placement),
                    None if sketch is None else App.Placement(sketch.Placement),
                )
            )
            base = rotation.multVec(placement.Base) + translation
            updated = App.Placement(
                base,
                rotation.multiply(placement.Rotation),
            )
            piece.Placement = updated
            if sketch is not None:
                sketch.Placement = updated
        doc.recompute()

        placed_surface = _world_target_surface(target)
        reports = []
        for piece in pieces:
            clearance_actual = _minimum_signed_surface_clearance(
                placed_surface,
                _piece_world_samples(piece, 1.0),
            )
            if clearance_actual + 1e-6 < float(clearance):
                raise TargetPlacementError(
                    "shared rigid placement for %s left %.3f mm signed clearance; required %.3f mm"
                    % (piece.Label, clearance_actual, float(clearance))
                )
            reports.append((str(piece.PieceId), float(clearance_actual)))

        from freecad_cloth.avatar.AvatarFitting import PiecePlacement
        placement_values = []
        for piece in sorted(
            pieces,
            key=lambda item: str(item.PieceId),
        ):
            base = piece.Placement.Base
            rotation_state = piece.Placement.Rotation
            axis = rotation_state.Axis
            placement_values.append(
                PiecePlacement(
                    str(piece.PieceId),
                    (float(base.x), float(base.y), float(base.z)),
                    float(rotation_state.Angle),
                    (float(axis.x), float(axis.y), float(axis.z)),
                ).to_string()
            )
        existing = {
            str(value.split("|", 1)[0]): value
            for value in getattr(scene, "PiecePlacements", ()) or ()
        }
        for value in placement_values:
            existing[value.split("|", 1)[0]] = value
        scene.PiecePlacements = [
            existing[key]
            for key in sorted(existing)
        ]
        scene.FitStatus = "Target-aware placement applied"
        doc.recompute()
        return {
            "piece_count": len(pieces),
            "anchor_count": len(anchors),
            "translation": tuple(round(float(v), 6) for v in delta.translation),
            "rotation_z": round(float(delta.rotation_z), 6),
            "anchor_residual": round(float(delta.residual_max), 6),
            "clearance": round(min(value[1] for value in reports), 6),
            "placement_mode": delta_mode,
        }
    except Exception:
        for piece, placement, sketch_placement in snapshots:
            piece.Placement = placement
            sketch = getattr(piece, "Sketch", None)
            if sketch is not None and sketch_placement is not None:
                sketch.Placement = sketch_placement
        scene.PiecePlacements = previous_piece_placements
        scene.FitStatus = previous_fit_status
        scene.DrapeTarget = previous_target
        doc.recompute()
        raise

def snap_pattern_pieces_to_target(pattern_pieces=None):
    """Public adapter used by the Simulation workbench target-snap button."""
    import FreeCAD as App
    pieces = tuple(pattern_pieces or ())
    doc = App.ActiveDocument
    scene = _scene(doc) if doc is not None else None
    if scene is None:
        raise ValueError("create a fitting scene before snapping pieces to target")
    _ensure_fitting_runtime_properties(scene)
    if pieces:
        scene.PatternPieces = sorted(set(tuple(scene.PatternPieces) + pieces), key=lambda item: str(item.PieceId))
    return snap_pieces_to_target(pieces or scene.PatternPieces)


class _FittingProxy:
    Type = "ClothFittingScene"

    def execute(self, obj):
        from freecad_cloth.avatar.AvatarFitting import BodyMeasurements, FittingScene, GarmentAnchor, PiecePlacement, ArrangementPoint, BoundingVolume
        _migrate_visual_output_references(obj)
        measurements = BodyMeasurements.from_json(obj.MeasurementData)
        avatar_name = getattr(obj.AvatarProxy, "Label", "") if obj.AvatarProxy else ""
        placements = tuple(PiecePlacement.from_string(v) for v in obj.PiecePlacements)
        points = tuple(ArrangementPoint.from_string(v) for v in obj.ArrangementPoints)
        volumes = tuple(BoundingVolume.from_string(v) for v in obj.BoundingVolumes)
        anchors = tuple(
            GarmentAnchor.from_string(v)
            for v in (getattr(obj, "GarmentAnchors", ()) or ())
        )
        FittingScene(
            measurements,
            avatar_name,
            placements,
            points,
            volumes,
            bool(obj.SymmetryEnabled),
            anchors,
        ).validate()


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
    "ClothFitting_ResetArrangement",
    "ClothFitting_CreateSimulation",
    "ClothFitting_SnapPiecesToTarget",
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
    "ClothFitting_ResetArrangement": reset_arrangement,
    "ClothFitting_CreateSimulation": create_simulation_from_fitting,
    "ClothFitting_SnapPiecesToTarget": lambda: snap_pattern_pieces_to_target(),
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
