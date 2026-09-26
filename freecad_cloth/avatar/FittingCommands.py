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

def _ensure_fitting_properties(scene):
    """Migrate persisted fitting scenes to the current property contract."""
    if scene is None:
        return None
    properties = set(getattr(scene, "PropertiesList", ()) or ())
    if "DrapeTarget" not in properties:
        scene.addProperty("App::PropertyLinkGlobal", "DrapeTarget", "Fitting")
    if "PiecePlacements" not in properties:
        scene.addProperty("App::PropertyStringList", "PiecePlacements", "Fitting")
        scene.PiecePlacements = []
        properties.add("PiecePlacements")
    if "HomePlacements" not in properties:
        scene.addProperty("App::PropertyStringList", "HomePlacements", "Fitting")
        scene.HomePlacements = list(scene.PiecePlacements)
        properties.add("HomePlacements")
    if "FitStatus" not in properties:
        scene.addProperty("App::PropertyString", "FitStatus", "Fitting")
        scene.FitStatus = "Unassigned"
        properties.add("FitStatus")
    if getattr(scene, "DrapeTarget", None) is None:
        target = scene.Document.getObject("DrapeTarget")
        if target is not None:
            scene.DrapeTarget = target
    return scene


def create_fitting_scene():
    import FreeCAD as App
    from freecad_cloth.avatar.AvatarFitting import BodyMeasurements, FittingScene

    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    existing = _scene(doc)
    if existing is not None:
        _ensure_fitting_properties(existing)
        doc.recompute()
        return existing
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
    _ensure_fitting_properties(scene)
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
    _ensure_fitting_properties(scene)
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



def _fitting_target(scene):
    """Return the single persistent, current DrapeTarget for the fitting workflow."""
    from freecad_cloth.simulation.DrapeTarget import target_status
    candidates = tuple(
        obj for obj in scene.Document.Objects
        if hasattr(obj, "TargetType") and hasattr(obj, "SourceObject") and hasattr(obj, "Enabled")
    )
    if not candidates:
        raise ValueError("create or select a DrapeTarget before arranging garment pieces")
    ready = tuple(obj for obj in candidates if target_status(obj)["state"] == "ready")
    if len(candidates) != 1:
        raise ValueError("exactly one DrapeTarget is required for garment fitting")
    target = getattr(scene, "DrapeTarget", None) or candidates[0]
    if target not in candidates:
        raise ValueError("fitting scene DrapeTarget is not a document target")
    status = target_status(target)
    if status["state"] != "ready":
        raise ValueError(status["message"])
    if len(ready) != 1:
        raise ValueError("exactly one ready DrapeTarget is required for garment fitting")
    return target


def _world_target_surface(target):
    """Build a world-space collision surface from the persistent DrapeTarget source."""
    import FreeCAD as App
    from freecad_cloth.avatar.AvatarCollision import surface_from_freecad, CollisionSurface
    source = getattr(target, "SourceObject", None)
    if source is None:
        raise ValueError("DrapeTarget has no source object")
    local = surface_from_freecad(
        source,
        float(getattr(target, "CollisionDeflection", 1.0)),
        float(getattr(target, "CollisionThickness", 0.0)),
    )
    placement = getattr(source, "Placement", None)
    if placement is None:
        return local
    vertices = []
    for x, y, z in local.vertices:
        point = placement.multVec(App.Vector(x, y, z))
        vertices.append((float(point.x), float(point.y), float(point.z)))
    surface = CollisionSurface(tuple(vertices), local.triangles, local.region, local.thickness)
    surface.validate()
    return surface


def _piece_world_samples(piece, deflection=1.0):
    """Return deterministic world-space surface samples for a pattern piece."""
    import FreeCAD as App
    shape = getattr(piece, "Shape", None)
    placement = getattr(piece, "Placement", None)
    if shape is not None and not getattr(shape, "isNull", lambda: True)():
        tessellate = getattr(shape, "tessellate", None)
        def world_point(point):
            value = placement.multVec(point) if placement is not None else point
            return (float(value.x), float(value.y), float(value.z))
        if callable(tessellate):
            points, _triangles = tessellate(float(deflection))
            if points:
                return tuple(world_point(point) for point in points)
        vertices = getattr(shape, "Vertexes", ())
        if vertices:
            return tuple(world_point(vertex.Point) for vertex in vertices)
    mesh = getattr(piece, "Mesh", None)
    topology = getattr(mesh, "Topology", None) if mesh is not None else None
    if topology is not None:
        points, _triangles = topology
        def world_mesh_point(point):
            value = placement.multVec(App.Vector(point.x, point.y, point.z)) if placement is not None else point
            return (float(value.x), float(value.y), float(value.z))
        return tuple(world_mesh_point(point) for point in points)
    raise ValueError("pattern piece %s has no usable geometry samples" % getattr(piece, "Name", "<unnamed>"))


def snap_pattern_pieces_to_target(pieces=None, target=None, clearance=None, max_translation=750.0, sample_deflection=1.0):
    """Place selected garment pieces directly outside the persistent DrapeTarget."""
    import FreeCAD as App
    from freecad_cloth.avatar.AvatarFitting import PiecePlacement
    from freecad_cloth.avatar.TargetPlacement import average_point, minimum_signed_clearance, nearest_target_projection
    from freecad_cloth.simulation.DrapeTarget import target_status

    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before arranging garment pieces")
    scene = _scene(doc)
    if scene is None or not scene.PatternPieces:
        raise ValueError("create a fitting scene with pattern pieces first")
    scene_target = _fitting_target(scene)
    if target is None:
        target = scene_target
    elif target is not scene_target:
        raise ValueError("selected DrapeTarget is not the fitting scene's authoritative target")
    status = target_status(target)
    if status["state"] != "ready":
        raise ValueError(status["message"])
    surface = _world_target_surface(target)
    required_clearance = max(2.0, float(getattr(target, "CollisionThickness", 0.0))) if clearance is None else max(0.0, float(clearance))
    guard = max(0.0, float(max_translation))
    if guard <= 0.0:
        raise ValueError("max_translation must be positive")
    selected = tuple(sorted((piece for piece in (pieces or scene.PatternPieces) if getattr(piece, "PatternType", "") == "PatternPiece"), key=lambda item: str(getattr(item, "PieceId", getattr(item, "Name", "")))))
    if not selected:
        raise ValueError("no PatternPiece objects were supplied")
    if any(piece not in tuple(scene.PatternPieces) for piece in selected):
        raise ValueError("all target-arranged pieces must belong to the fitting scene")

    home_before = tuple(scene.HomePlacements)
    placement_before = {piece: piece.Placement for piece in selected}
    sketch_before = {piece: getattr(getattr(piece, "Sketch", None), "Placement", None) for piece in selected if getattr(piece, "Sketch", None) is not None}
    persisted_before = tuple(scene.PiecePlacements)
    fit_status_before = str(getattr(scene, "FitStatus", ""))
    try:
        results = []
        for piece in selected:
            samples = _piece_world_samples(piece, sample_deflection)
            center = average_point(samples)
            projection = nearest_target_projection(center, surface)
            desired = tuple(projection.point[i] + projection.normal[i] * required_clearance for i in range(3))
            delta = tuple(desired[i] - center[i] for i in range(3))
            travel = (sum(value * value for value in delta)) ** 0.5
            if travel > guard + 1e-9:
                raise ValueError("target-aware placement for %s exceeds the translation guard: %.3f > %.3f mm" % (getattr(piece, "Label", getattr(piece, "Name", "<unnamed>")), travel, guard))
            placement = piece.Placement
            base = placement.Base
            updated = App.Placement(App.Vector(float(base.x) + delta[0], float(base.y) + delta[1], float(base.z) + delta[2]), placement.Rotation)
            piece.Placement = updated
            sketch = getattr(piece, "Sketch", None)
            if sketch is not None:
                sketch.Placement = updated
            doc.recompute()

            report = minimum_signed_clearance(_piece_world_samples(piece, sample_deflection), surface)
            total_travel = travel
            for _attempt in range(3):
                deficit = required_clearance - report.minimum_signed_clearance
                if deficit <= 1e-6:
                    break
                if total_travel + deficit > guard + 1e-9:
                    raise ValueError("target-aware placement for %s cannot satisfy %.3f mm clearance within the translation guard" % (getattr(piece, "Label", getattr(piece, "Name", "<unnamed>")), required_clearance))
                correction = tuple(report.projection.normal[i] * deficit for i in range(3))
                current = piece.Placement; current_base = current.Base
                corrected = App.Placement(App.Vector(float(current_base.x) + correction[0], float(current_base.y) + correction[1], float(current_base.z) + correction[2]), current.Rotation)
                piece.Placement = corrected
                sketch = getattr(piece, "Sketch", None)
                if sketch is not None:
                    sketch.Placement = corrected
                total_travel += deficit
                doc.recompute()
                report = minimum_signed_clearance(_piece_world_samples(piece, sample_deflection), surface)
            if report.minimum_signed_clearance + 1e-6 < required_clearance:
                raise ValueError("target-aware placement for %s did not prove the requested step-0 clearance" % getattr(piece, "Label", getattr(piece, "Name", "<unnamed>")))
            results.append({
                "piece_id": str(piece.PieceId),
                "translation_mm": float(total_travel),
                "minimum_signed_clearance_mm": float(report.minimum_signed_clearance),
                "triangle_index": int(report.projection.triangle_index),
            })

        _ensure_fitting_properties(scene)
        scene.DrapeTarget = target
        placements = {p.piece_id: p for p in (PiecePlacement.from_string(v) for v in scene.PiecePlacements)}
        for piece in selected:
            final = piece.Placement; base = final.Base; axis = final.Rotation.Axis
            placements[str(piece.PieceId)] = PiecePlacement(str(piece.PieceId), (float(base.x), float(base.y), float(base.z)), float(final.Rotation.Angle), (float(axis.x), float(axis.y), float(axis.z)))
        scene.PiecePlacements = [placements[key].to_string() for key in sorted(placements)]
        if tuple(scene.HomePlacements) != home_before:
            raise RuntimeError("target-aware placement mutated HomePlacements")
        scene.FitStatus = "Target snapped"
        doc.recompute()
        return {"target": str(getattr(target, "Name", "DrapeTarget")), "clearance_mm": required_clearance, "pieces": tuple(results)}
    except BaseException:
        for piece, original in placement_before.items():
            piece.Placement = original
        for piece, original in sketch_before.items():
            sketch = getattr(piece, "Sketch", None)
            if sketch is not None and original is not None:
                sketch.Placement = original
        scene.PiecePlacements = list(persisted_before)
        scene.HomePlacements = list(home_before)
        scene.FitStatus = fit_status_before
        doc.recompute()
        raise


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
        axis = getattr(placement, "rotation_axis", (0.0, 0.0, 1.0))
        restored = App.Placement(App.Vector(x, y, z), App.Rotation(App.Vector(*axis), placement.rotation_z))
        piece.Placement = restored
        sketch = getattr(piece, "Sketch", None)
        if sketch is not None:
            sketch.Placement = restored
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
    target = getattr(scene, "DrapeTarget", None)
    if target is None:
        raise ValueError("assign a current DrapeTarget before creating simulation")
    from freecad_cloth.simulation.DrapeTarget import target_status
    status = target_status(target)
    if status["state"] != "ready":
        raise ValueError(status["message"])
    simulation.DrapeTarget = target
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
    "ClothFitting_SnapPiecesToTarget": lambda: _snap_selected_to_target(),
    "ClothFitting_ResetArrangement": reset_arrangement,
    "ClothFitting_CreateSimulation": create_simulation_from_fitting,
}


def _snap_selected_to_target():
    import FreeCADGui as Gui
    active = Gui.activeDocument()
    if active is None:
        raise ValueError("open a document before snapping pattern pieces to a target")
    selection = tuple(Gui.Selection.getSelection())
    pieces = tuple(obj for obj in selection if getattr(obj, "PatternType", "") == "PatternPiece")
    targets = tuple(obj for obj in selection if hasattr(obj, "TargetType") and hasattr(obj, "SourceObject"))
    if not pieces:
        raise ValueError("select one or more PatternPiece objects")
    if len(targets) != 1:
        raise ValueError("select exactly one DrapeTarget and one or more PatternPiece objects")
    return snap_pattern_pieces_to_target(pieces, targets[0])


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
