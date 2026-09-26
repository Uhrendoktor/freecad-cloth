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
    obj.addProperty("App::PropertyLinkGlobal", "AvatarProxy", "Fitting")
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
    if source is None:
        source = next((o for o in Gui.Selection.getSelection() if hasattr(o, "Shape") or hasattr(o, "Mesh")), None)
    if source is None:
        raise ValueError("select a FreeCAD body or mesh to use as the avatar source")
    avatar = create_avatar_collision(doc) if doc.getObject("AvatarCollision") is None else doc.getObject("AvatarCollision")
    avatar = set_avatar_collision_source(scene, source)
    scene.AvatarProxy = avatar
    from freecad_cloth.simulation.DrapeTarget import assign_drape_target, create_drape_target
    target_type = "Mannequin" if str(getattr(source, "AvatarType", "")) == "ClothAvatar" else "FreeCAD Geometry"
    target = doc.getObject("DrapeTarget")
    if target is None:
        target = create_drape_target(
            doc,
            source=source,
            target_type=target_type,
            deflection=1.0,
            thickness=float(getattr(avatar, "CollisionThickness", 0.0)),
        )
    else:
        assign_drape_target(target, source, target_type)
    scene.DrapeTarget = target
    scene.FitStatus = "Avatar and target assigned"
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


def _world_surface_vertices(target):
    """Resolve the authoritative DrapeTarget surface into world space."""
    from freecad_cloth.simulation.DrapeTarget import collision_surface
    import FreeCAD as App

    source = getattr(target, "SourceObject", None)
    if source is None:
        raise ValueError("drape target has no source object")
    surface = collision_surface(
        source,
        float(getattr(target, "CollisionDeflection", 1.0)),
        float(getattr(target, "CollisionThickness", 0.0)),
    )
    placement = getattr(source, "Placement", None)
    if placement is None:
        return tuple(tuple(float(c) for c in p) for p in surface.vertices)
    result = []
    for point in surface.vertices:
        world = placement.multVec(App.Vector(*point))
        result.append((float(world.x), float(world.y), float(world.z)))
    return tuple(result)


def snap_pattern_pieces_to_target(pieces=None, clearance=None):
    """Rigidly arrange PatternPieces around a current DrapeTarget.

    The placement is persisted fitting state, not solver state. The operation is
    transactional: target, ambiguity, and step-0 clearance checks happen before
    any PatternPiece placement is mutated.
    """
    import FreeCAD as App
    from freecad_cloth.simulation.DrapeTarget import target_status
    from freecad_cloth.avatar.AvatarProvider import provider_from_target
    from freecad_cloth.avatar.AvatarFitting import PiecePlacement

    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before snapping garment pieces to a target")
    scene = _scene(doc)
    if scene is None or not scene.PatternPieces:
        raise ValueError("create a fitting scene with pattern pieces first")

    target = getattr(scene, "DrapeTarget", None)
    if target is None:
        target = doc.getObject("DrapeTarget")
        if target is not None:
            scene.DrapeTarget = target
    status = target_status(target)
    if status["state"] != "ready":
        raise ValueError("cannot arrange against target: %s" % status["message"])

    source = getattr(target, "SourceObject", None)
    if source is None:
        raise ValueError("drape target has no source object")

    selected = tuple(sorted(
        (piece for piece in (pieces or scene.PatternPieces)
         if getattr(piece, "PatternType", "") == "PatternPiece"),
        key=lambda item: str(getattr(item, "PieceId", getattr(item, "Name", ""))),
    ))
    if not selected:
        raise ValueError("no PatternPiece objects were supplied")

    target_vertices = _world_surface_vertices(target)
    if len(target_vertices) < 3:
        raise ValueError("drape target collision surface has insufficient geometry")

    tx = (min(p[0] for p in target_vertices) + max(p[0] for p in target_vertices)) / 2.0
    ty_min = min(p[1] for p in target_vertices)
    ty_max = max(p[1] for p in target_vertices)
    tz_min = min(p[2] for p in target_vertices)
    tz_max = max(p[2] for p in target_vertices)

    # Built-in mannequin providers expose stable semantic landmarks. Generic
    # FreeCAD targets intentionally remain target-neutral and fall back to the
    # collision-surface midpoint.
    tz_anchor = (tz_min + tz_max) / 2.0
    try:
        provider = provider_from_target(
            source,
            str(getattr(target, "TargetType", "FreeCAD Geometry")),
            deflection=float(getattr(target, "CollisionDeflection", 1.0)),
            thickness=float(getattr(target, "CollisionThickness", 0.0)),
        )
        landmark_map = {
            record.name: tuple(record.position)
            for record in provider.landmarks()
        }
        if "chest" in landmark_map and "hip" in landmark_map:
            chest = source.Placement.multVec(App.Vector(*landmark_map["chest"]))
            hip = source.Placement.multVec(App.Vector(*landmark_map["hip"]))
            tz_anchor = float((chest.z + hip.z) / 2.0)
    except (AttributeError, TypeError, ValueError, RuntimeError):
        pass
    if not (tz_min <= tz_anchor <= tz_max):
        tz_anchor = (tz_min + tz_max) / 2.0

    target_clearance = max(
        2.0,
        float(getattr(target, "CollisionThickness", 0.0)) + 2.0,
    )
    requested_clearance = target_clearance if clearance is None else float(clearance)
    clearance = max(target_clearance, requested_clearance)

    boxes = {
        str(piece.PieceId): _world_bounds(piece)
        for piece in selected
    }
    centers = {
        pid: (
            (box[0] + box[1]) / 2.0,
            (box[2] + box[3]) / 2.0,
            (box[4] + box[5]) / 2.0,
        )
        for pid, box in boxes.items()
    }

    sides = {}
    for pid, box in boxes.items():
        if box[3] <= ty_min:
            sides[pid] = "front"
        elif box[2] >= ty_max:
            sides[pid] = "back"
        else:
            raise ValueError(
                "pattern piece %s overlaps the target Y span; refusing ambiguous arrangement" % pid
            )

    group_cx = sum(center[0] for center in centers.values()) / len(centers)
    group_cz = sum(center[2] for center in centers.values()) / len(centers)
    proposed = {}
    for piece in selected:
        pid = str(piece.PieceId)
        center = centers[pid]
        desired_y = ty_min - clearance if sides[pid] == "front" else ty_max + clearance
        delta_x = tx - group_cx
        delta_y = desired_y - center[1]
        delta_z = tz_anchor - group_cz
        placement = piece.Placement
        base = placement.Base
        proposed[pid] = App.Placement(
            App.Vector(
                float(base.x) + delta_x,
                float(base.y) + delta_y,
                float(base.z) + delta_z,
            ),
            placement.Rotation,
        )

    # Before mutation, prove the proposed world Y bounds clear the authoritative
    # DrapeTarget envelope by the requested margin at simulation step 0.
    proofs = {}
    for piece in selected:
        pid = str(piece.PieceId)
        before = boxes[pid]
        shift = proposed[pid].Base - piece.Placement.Base
        moved_y_min = before[2] + float(shift.y)
        moved_y_max = before[3] + float(shift.y)
        actual_clearance = (
            ty_min - moved_y_max
            if sides[pid] == "front"
            else moved_y_min - ty_max
        )
        proofs[pid] = float(actual_clearance)
        if actual_clearance + 1e-6 < clearance:
            raise ValueError(
                "target arrangement clearance proof failed for %s: %.6f" %
                (pid, actual_clearance)
            )

    current = {
        placement.piece_id: placement
        for placement in (
            PiecePlacement.from_string(value)
            for value in scene.PiecePlacements
        )
    }
    for piece in selected:
        pid = str(piece.PieceId)
        piece.Placement = proposed[pid]
        current[pid] = PiecePlacement(
            pid,
            (
                float(piece.Placement.Base.x),
                float(piece.Placement.Base.y),
                float(piece.Placement.Base.z),
            ),
            float(piece.Placement.Rotation.Angle),
        )
    scene.PiecePlacements = [
        current[key].to_string()
        for key in sorted(current)
    ]
    scene.FitStatus = "Target arrangement ready (step-0 Y clearance %.3f mm)" % min(proofs.values())
    doc.recompute()
    return scene


def _world_shape(obj):
    """Return a copy of an object's geometry with its document placement applied."""
    import FreeCAD as App
    import Part

    shape = getattr(obj, "Shape", None)
    if shape is not None and not shape.isNull():
        world = shape.copy()
    else:
        mesh = getattr(obj, "Mesh", None)
        topology = getattr(mesh, "Topology", None) if mesh is not None else None
        if topology is None:
            raise ValueError("object has no usable Part Shape or Mesh topology")
        vertices, triangles = topology
        faces = []
        for triangle in triangles:
            try:
                points = [App.Vector(*vertices[int(i)]) for i in triangle]
                points.append(points[0])
                faces.append(Part.Face(Part.makePolygon(points)))
            except (IndexError, TypeError, ValueError, RuntimeError):
                continue
        if not faces:
            raise ValueError("object mesh has no usable triangular faces")
        world = Part.makeCompound(faces)

    placement = getattr(obj, "Placement", None)
    if placement is not None:
        world.Placement = placement
    return world


def snap_pattern_pieces_to_target(
    pieces=None,
    clearance=8.0,
    max_translation=240.0,
    max_iterations=16,
):
    """Snap pattern pieces to the persistent DrapeTarget surface.

    This is a reversible rigid fitting operation. It consumes the authoritative
    DrapeTarget geometry, fails closed on missing/stale targets, preserves each
    piece rotation, never creates solver pins, and bounds the correction.
    """
    import FreeCAD as App
    from freecad_cloth.avatar.AvatarFitting import PiecePlacement
    from freecad_cloth.simulation.DrapeTarget import target_status

    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before snapping garment pieces to a target")
    target = doc.getObject("DrapeTarget")
    if target is None:
        raise ValueError("a DrapeTarget is required before snapping pattern pieces")
    status = target_status(target)
    if status["state"] != "ready":
        raise RuntimeError("snap blocked: %s" % status["message"])

    source = getattr(target, "SourceObject", None)
    if source is None:
        raise ValueError("drape target has no source object")
    target_shape = _world_shape(source)

    clearance = float(clearance)
    max_translation = float(max_translation)
    max_iterations = int(max_iterations)
    if clearance <= 0.0:
        raise ValueError("clearance must be positive")
    if max_translation <= 0.0 or max_iterations < 1:
        raise ValueError("snap limits must be positive")

    scene = _scene(doc)
    if scene is None or not scene.PatternPieces:
        raise ValueError("create a fitting scene with pattern pieces first")
    selected = tuple(pieces or scene.PatternPieces)
    selected = tuple(
        sorted(
            (piece for piece in selected if getattr(piece, "PatternType", "") == "PatternPiece"),
            key=lambda item: str(getattr(item, "PieceId", getattr(item, "Name", ""))),
        )
    )
    if not selected:
        raise ValueError("no PatternPiece objects were supplied")

    placements = {
        p.piece_id: p
        for p in (PiecePlacement.from_string(v) for v in scene.PiecePlacements)
    }
    results = []
    for piece in selected:
        piece_shape = _world_shape(piece)
        before_distance = None
        moved = 0.0
        for iteration in range(max_iterations):
            distance, nearest, _details = piece_shape.distToShape(target_shape)
            distance = float(distance)
            if before_distance is None:
                before_distance = distance
            if abs(distance - clearance) <= 1e-6:
                break

            if nearest and len(nearest) >= 2:
                target_point, piece_point = nearest[0], nearest[1]
                direction = piece_point.sub(target_point)
            else:
                bound = piece_shape.BoundBox
                target_bound = target_shape.BoundBox
                direction = App.Vector(
                    ((float(bound.XMin) + float(bound.XMax)) - (float(target_bound.XMin) + float(target_bound.XMax))) / 2.0,
                    ((float(bound.YMin) + float(bound.YMax)) - (float(target_bound.YMin) + float(target_bound.YMax))) / 2.0,
                    ((float(bound.ZMin) + float(bound.ZMax)) - (float(target_bound.ZMin) + float(target_bound.ZMax))) / 2.0,
                )
            if direction.Length <= 1e-9:
                raise RuntimeError(
                    "snap blocked: ambiguous target direction for piece %s"
                    % getattr(piece, "Name", "<unnamed>")
                )
            direction.normalize()

            step = clearance - distance
            remaining = max_translation - moved
            if abs(step) > remaining + 1e-9:
                raise RuntimeError(
                    "snap blocked: required translation exceeds %.3f mm for %s"
                    % (max_translation, getattr(piece, "Name", "<unnamed>"))
                )
            piece.Placement = App.Placement(
                piece.Placement.Base + direction.multiply(step),
                piece.Placement.Rotation,
            )
            moved += abs(step)
            piece_shape = _world_shape(piece)

        final_distance = float(piece_shape.distToShape(target_shape)[0])
        tolerance = max(0.5, clearance * 0.05)
        if final_distance + 1e-6 < clearance or abs(final_distance - clearance) > tolerance:
            raise RuntimeError(
                "snap failed for %s: final clearance %.6f mm is not near %.6f mm"
                % (getattr(piece, "Name", "<unnamed>"), final_distance, clearance)
            )

        piece_id = str(getattr(piece, "PieceId", "")).strip()
        if piece_id:
            base = piece.Placement.Base
            placements[piece_id] = PiecePlacement(
                piece_id,
                (float(base.x), float(base.y), float(base.z)),
                float(piece.Placement.Rotation.Angle),
            )
        results.append(
            {
                "piece_id": piece_id,
                "distance_before": float(before_distance if before_distance is not None else final_distance),
                "distance_after": final_distance,
                "translation": moved,
                "clearance": clearance,
                "iterations": iteration + 1,
            }
        )

    scene.PiecePlacements = [placements[k].to_string() for k in sorted(placements)]
    scene.FitStatus = "Target snapped"
    doc.recompute()
    return tuple(results)


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
    if getattr(scene, "DrapeTarget", None) is None:
        raise ValueError("assign a current DrapeTarget before creating simulation")
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
    "ClothFitting_SnapPiecesToTarget": snap_pattern_pieces_to_target,
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
