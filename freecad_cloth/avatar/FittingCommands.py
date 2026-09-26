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
    target = doc.getObject("DrapeTarget")
    if target is None:
        raise RuntimeError("avatar assignment did not create a DrapeTarget")
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
    entries[str(piece.PieceId)] = PiecePlacement(str(piece.PieceId), (float(x), float(y), float(z)), float(rotation_z), (0.0, 0.0, 1.0))
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


def _piece_world_surface_points(piece, deflection=1.0):
    """Sample PatternIR with the same placement semantics used by simulation."""
    import FreeCAD as App
    from freecad_cloth.common.PatternSimulationAdapter import geometry_from_piece_ir, resolve_piece_ir
    from freecad_cloth.pattern.PatternMesh import refine_linear_boundary, triangulate

    piece_ir = resolve_piece_ir(piece)
    pattern = geometry_from_piece_ir(piece_ir)
    spacing = max(0.25, float(deflection))
    mesh = triangulate(
        refine_linear_boundary(pattern, spacing),
        max_area=0.45 * spacing * spacing,
    )
    if not mesh.vertices:
        raise ValueError("pattern piece mesh produced no clearance samples")
    placement = getattr(piece, "Placement", None)
    if placement is None:
        raise ValueError("pattern piece has no persistent placement")
    points = []
    for x, y in mesh.vertices:
        world = placement.multVec(App.Vector(float(x), float(y), 0.0))
        points.append((float(world.x), float(world.y), float(world.z)))
    if not points:
        raise ValueError("pattern piece produced no world-space clearance samples")
    return tuple(points)


def set_garment_anchors(anchors):
    """Persist deterministic garment-local anchors on the existing fitting scene."""
    import FreeCAD as App
    from freecad_cloth.avatar.AvatarFitting import GarmentAnchor
    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _scene(doc) or create_fitting_scene()
    parsed = []
    for anchor in anchors or ():
        item = anchor if isinstance(anchor, GarmentAnchor) else GarmentAnchor.from_string(anchor)
        item.validate()
        parsed.append(item)
    scene.GarmentAnchors = [item.to_string() for item in sorted(parsed, key=lambda a: (a.piece_id, a.name))]
    doc.recompute()
    return scene


def _build_target_surface_index(surface):
    from freecad_cloth.avatar.TargetAwarePlacement import SurfaceSpatialIndex
    return SurfaceSpatialIndex(surface)


def target_aware_place_piece(piece, target, anchors, clearance=8.0, max_translation=600.0, max_rotation=45.0):
    """Place one piece rigidly against the persistent DrapeTarget transactionally."""
    import FreeCAD as App
    from freecad_cloth.avatar.AvatarFitting import GarmentAnchor, PiecePlacement
    from freecad_cloth.simulation.DrapeTarget import collision_surface, target_status
    from freecad_cloth.avatar.TargetAwarePlacement import (
        TargetPlacementError, SurfaceSpatialIndex, assert_minimum_surface_clearance, minimum_surface_clearance,
        minimum_surface_clearance_detail, minimum_target_vertex_clearance,
        require_ready_target_status,
        solve_rigid_z, target_surface_anchor, wrap_normal,
    )
    if getattr(piece, "PatternType", "") != "PatternPiece":
        raise ValueError("piece must be a Cloth PatternPiece object")
    doc = piece.Document
    scene = _scene(doc)
    original_placement = piece.Placement
    sketch = getattr(piece, "Sketch", None)
    original_sketch_placement = getattr(sketch, "Placement", None) if sketch is not None else None
    previous_piece_placements = list(getattr(scene, "PiecePlacements", ())) if scene is not None else None
    previous_fit_status = str(getattr(scene, "FitStatus", "")) if scene is not None else None
    try:
        require_ready_target_status(target_status(target))
        source_object = getattr(target, "SourceObject", None)
        if source_object is None:
            raise ValueError("drape target source is required")
        surface = collision_surface(source_object, float(getattr(target, "CollisionDeflection", 1.0)), float(getattr(target, "CollisionThickness", 0.0)))
        target_index = _build_target_surface_index(surface)
        piece_id = str(piece.PieceId)
        selected = tuple(item if isinstance(item, GarmentAnchor) else GarmentAnchor.from_string(item) for item in anchors or ())
        selected = tuple(sorted((item for item in selected if str(item.piece_id) == piece_id), key=lambda item: item.name))
        if not selected:
            raise ValueError("target-aware placement requires at least one garment anchor")
        source_points, target_points = [], []
        anchor_hits = []
        for anchor in selected:
            anchor.validate()
            source = piece.Placement.multVec(App.Vector(*anchor.position))
            hit = target_surface_anchor(surface, (source.x, source.y, source.z), wrap_normal(anchor.wrap_direction), index=target_index)
            desired = tuple(hit.point[i] + hit.normal[i] * (float(surface.thickness) + float(clearance)) for i in range(3))
            source_points.append((float(source.x), float(source.y), float(source.z)))
            target_points.append(desired)
            anchor_hits.append(hit)
        delta = solve_rigid_z(source_points, target_points, max_translation, max_rotation)
        delta_rotation = App.Rotation(App.Vector(0, 0, 1), float(delta.rotation_z))
        current = piece.Placement
        new_base = delta_rotation.multVec(current.Base) + App.Vector(*delta.translation)
        piece.Placement = App.Placement(new_base, delta_rotation.multiply(current.Rotation))
        if sketch is not None:
            sketch.Placement = piece.Placement
        placed_points = []
        for anchor in selected:
            point = piece.Placement.multVec(App.Vector(*anchor.position))
            placed_points.append((float(point.x), float(point.y), float(point.z)))
        anchor_clearance = minimum_surface_clearance(surface, placed_points)
        piece_points = _piece_world_surface_points(piece, deflection=max(0.25, float(clearance) / 2.0))
        piece_clearance, worst_hit = minimum_surface_clearance_detail(surface, piece_points, index=target_index)
        vertex_clearance = minimum_target_vertex_clearance(surface, piece_points, index=target_index)
        correction_count = 0
        while (
            (piece_clearance < float(clearance) - 1e-6 or vertex_clearance < float(clearance) - 1e-6)
            and correction_count < 8
        ):
            surface_deficit = float(clearance) - float(piece_clearance)
            vertex_deficit = float(clearance) - float(vertex_clearance)
            correction = max(surface_deficit, vertex_deficit)
            correction_vec = App.Vector(
                float(worst_hit.normal[0]) * correction,
                float(worst_hit.normal[1]) * correction,
                float(worst_hit.normal[2]) * correction,
            )
            corrected_base = piece.Placement.Base + correction_vec
            if (corrected_base - original_placement.Base).Length > float(max_translation):
                raise TargetPlacementError("target-aware clearance correction exceeds the configured translation bound")
            piece.Placement = App.Placement(corrected_base, piece.Placement.Rotation)
            if sketch is not None:
                sketch.Placement = piece.Placement
            piece_points = _piece_world_surface_points(piece, deflection=max(0.25, float(clearance) / 2.0))
            piece_clearance, worst_hit = minimum_surface_clearance_detail(surface, piece_points, index=target_index)
            vertex_clearance = minimum_target_vertex_clearance(surface, piece_points, index=target_index)
            correction_count += 1
        piece_clearance = assert_minimum_surface_clearance(surface, piece_points, float(clearance), index=target_index)
        anchor_clearance = assert_minimum_surface_clearance(surface, tuple(
            tuple(float(value) for value in piece.Placement.multVec(App.Vector(*anchor.position)))
            for anchor in selected
        ), float(clearance), index=target_index)
        if vertex_clearance < float(clearance) - 1e-6:
            raise TargetPlacementError(
                "target-aware vertex clearance %.6f mm is below the required %.6f mm"
                % (float(vertex_clearance), float(clearance))
            )
        if scene is not None:
            entries = {p.piece_id: p for p in (PiecePlacement.from_string(v) for v in scene.PiecePlacements)}
            axis = piece.Placement.Rotation.Axis
            entries[piece_id] = PiecePlacement(
                piece_id,
                (float(piece.Placement.Base.x), float(piece.Placement.Base.y), float(piece.Placement.Base.z)),
                float(piece.Placement.Rotation.Angle),
                (float(axis.x), float(axis.y), float(axis.z)),
            )
            scene.PiecePlacements = [entries[k].to_string() for k in sorted(entries)]
            scene.FitStatus = "Target-aware placement applied"
        doc.recompute()
        return {
            "translation": tuple(float(v) for v in delta.translation),
            "rotation_z": float(delta.rotation_z),
            "anchor_residual": float(delta.residual_max),
            "anchor_clearance": float(anchor_clearance),
            "piece_clearance": float(piece_clearance),
        }
    except Exception:
        piece.Placement = original_placement
        if sketch is not None and original_sketch_placement is not None:
            sketch.Placement = original_sketch_placement
        if scene is not None and previous_piece_placements is not None:
            scene.PiecePlacements = previous_piece_placements
            scene.FitStatus = previous_fit_status
        try:
            doc.recompute()
        except Exception:
            pass
        raise

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


def snap_pieces_to_target(clearance=8.0, max_translation=600.0, max_rotation=45.0):
    """Apply authored target-aware garment anchors atomically across all fitted pieces."""
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before snapping garment pieces to the target")
    scene = _scene(doc)
    if scene is None or not scene.PatternPieces:
        raise ValueError("create a fitting scene with pattern pieces first")
    if not getattr(scene, "DrapeTarget", None):
        raise ValueError("assign an authoritative DrapeTarget before target-aware placement")
    from freecad_cloth.avatar.AvatarFitting import GarmentAnchor, PiecePlacement
    anchors = tuple(GarmentAnchor.from_string(value) for value in getattr(scene, "GarmentAnchors", ()) or ())
    if not anchors:
        raise ValueError("target-aware placement requires authored GarmentAnchors in the fitting scene")
    candidates = []
    snapshots = {}
    for piece in sorted(scene.PatternPieces, key=lambda item: str(getattr(item, "PieceId", ""))):
        piece_anchors = tuple(anchor for anchor in anchors if str(anchor.piece_id) == str(piece.PieceId))
        if not piece_anchors:
            continue
        sketch = getattr(piece, "Sketch", None)
        snapshots[str(piece.PieceId)] = (
            piece,
            piece.Placement,
            getattr(sketch, "Placement", None) if sketch is not None else None,
        )
        candidates.append((piece, piece_anchors))
    if not candidates:
        raise ValueError("no fitted pattern piece has an authored garment anchor")
    previous_piece_placements = list(getattr(scene, "PiecePlacements", ()) or ())
    previous_fit_status = str(getattr(scene, "FitStatus", ""))
    try:
        results = []
        for piece, piece_anchors in candidates:
            results.append(
                target_aware_place_piece(
                    piece,
                    scene.DrapeTarget,
                    piece_anchors,
                    clearance=float(clearance),
                    max_translation=float(max_translation),
                    max_rotation=float(max_rotation),
                )
            )
        scene.FitStatus = "Target-aware placement applied"
        doc.recompute()
        return tuple(results)
    except Exception:
        for _piece_id, (piece, placement, sketch_placement) in snapshots.items():
            piece.Placement = placement
            sketch = getattr(piece, "Sketch", None)
            if sketch is not None and sketch_placement is not None:
                sketch.Placement = sketch_placement
        scene.PiecePlacements = previous_piece_placements
        scene.FitStatus = previous_fit_status
        doc.recompute()
        raise


def snap_pattern_pieces_to_target(pattern_pieces=None, clearance=8.0, max_translation=600.0, max_rotation=45.0):
    """Compatibility adapter for the Simulation Quality panel.

    The UI passes the PatternPiece tuple returned by the fitting handoff. The
    fitting scene remains authoritative, while this adapter preserves the
    established UI call signature and accepts a numeric first positional
    argument for older callers that treated the alias as the canonical helper.
    """
    if pattern_pieces is not None and isinstance(pattern_pieces, (int, float)):
        clearance = float(pattern_pieces)
        pattern_pieces = None
    return snap_pieces_to_target(clearance, max_translation, max_rotation)


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
        piece.Placement = App.Placement(App.Vector(x, y, z), App.Rotation(App.Vector(*placement.rotation_axis), placement.rotation_z))
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
    fitting_target = getattr(scene, "DrapeTarget", None)
    if fitting_target is not None:
        simulation.DrapeTarget = fitting_target
    doc.recompute()
    return simulation


class _FittingProxy:
    Type = "ClothFittingScene"

    def execute(self, obj):
        from freecad_cloth.avatar.AvatarFitting import BodyMeasurements, FittingScene, PiecePlacement, ArrangementPoint, BoundingVolume, GarmentAnchor
        _migrate_visual_output_references(obj)
        measurements = BodyMeasurements.from_json(obj.MeasurementData)
        avatar_name = getattr(obj.AvatarProxy, "Label", "") if obj.AvatarProxy else ""
        placements = tuple(PiecePlacement.from_string(v) for v in obj.PiecePlacements)
        points = tuple(ArrangementPoint.from_string(v) for v in obj.ArrangementPoints)
        volumes = tuple(BoundingVolume.from_string(v) for v in obj.BoundingVolumes)
        anchors = tuple(GarmentAnchor.from_string(v) for v in getattr(obj, "GarmentAnchors", ()))
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
    "ClothFitting_SnapPiecesToTarget": snap_pieces_to_target,
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
