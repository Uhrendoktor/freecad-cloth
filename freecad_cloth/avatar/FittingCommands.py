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
    existing_target = doc.getObject("DrapeTarget")
    if existing_target is not None:
        obj.DrapeTarget = existing_target
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
    existing_target = doc.getObject("DrapeTarget")
    if existing_target is not None:
        _ensure_fitting_target_property(scene)
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



def _ensure_fitting_target_property(scene):
    """Ensure legacy fitting scenes can persist the authoritative DrapeTarget link."""
    if "DrapeTarget" not in getattr(scene, "PropertiesList", ()):
        scene.addProperty("App::PropertyLinkGlobal", "DrapeTarget", "Fitting")
    return getattr(scene, "DrapeTarget", None)


def _world_shape(obj):
    """Return object geometry with document placement applied in world space."""
    import Part

    shape = getattr(obj, "Shape", None)
    if shape is not None and not shape.isNull():
        world = shape.copy()
    else:
        mesh = getattr(obj, "Mesh", None)
        topology = getattr(mesh, "Topology", None) if mesh is not None else None
        if topology is None:
            raise ValueError("object has no usable Part Shape or Mesh topology")
        faces = []
        vertices, triangles = topology
        import FreeCAD as App
        for triangle in triangles:
            points = []
            try:
                for index in triangle:
                    vertex = vertices[int(index)]
                    if hasattr(vertex, "x"):
                        points.append(App.Vector(float(vertex.x), float(vertex.y), float(vertex.z)))
                    else:
                        points.append(App.Vector(*[float(c) for c in vertex]))
                points.append(points[0])
                faces.append(Part.Face(Part.makePolygon(points)))
            except (IndexError, TypeError, ValueError, RuntimeError, AttributeError):
                continue
        if not faces:
            raise ValueError("object mesh has no usable triangular faces")
        world = Part.makeCompound(faces)

    placement = getattr(obj, "Placement", None)
    if placement is not None:
        world.Placement = placement
    return world


def _shape_clearance(piece_shape, target_shape):
    return float(piece_shape.distToShape(target_shape)[0])


def _shape_center(shape):
    import FreeCAD as App
    box = shape.BoundBox
    return App.Vector(
        (float(box.XMin) + float(box.XMax)) * 0.5,
        (float(box.YMin) + float(box.YMax)) * 0.5,
        (float(box.ZMin) + float(box.ZMax)) * 0.5,
    )


def snap_piece_to_drape_target(piece, target=None, clearance=8.0, max_translation=240.0, max_iterations=32):
    """Rigorously place one PatternPiece at bounded clearance from DrapeTarget.

    The operation is fitting state, never solver state. All touched state is
    restored when validation fails after mutation.
    """
    import FreeCAD as App
    from freecad_cloth.avatar.AvatarFitting import PiecePlacement
    from freecad_cloth.simulation.DrapeTarget import target_status

    if getattr(piece, "PatternType", "") != "PatternPiece":
        raise ValueError("piece must be a Cloth PatternPiece object")
    clearance = float(clearance)
    max_translation = float(max_translation)
    max_iterations = int(max_iterations)
    if clearance < 0.0:
        raise ValueError("clearance must be non-negative")
    if max_translation <= 0.0 or max_iterations < 1:
        raise ValueError("snap limits must be positive")

    doc = getattr(piece, "Document", None) or App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before snapping a pattern piece")
    scene = _scene(doc)
    if scene is None:
        raise ValueError("create a fitting scene first")

    target_property_existed = "DrapeTarget" in set(getattr(scene, "PropertiesList", ()) or ())
    target_before = getattr(scene, "DrapeTarget", None) if target_property_existed else None
    home_before = tuple(getattr(scene, "HomePlacements", ()) or ())
    _ensure_fitting_target_property(scene)
    if target is None:
        target = getattr(scene, "DrapeTarget", None) or doc.getObject("DrapeTarget")
        if target is not None and getattr(scene, "DrapeTarget", None) is not target:
            scene.DrapeTarget = target
    if target is None:
        raise ValueError("a DrapeTarget is required before snapping a pattern piece")

    status = target_status(target)
    if status["state"] != "ready":
        raise RuntimeError("snap blocked: %s" % status["message"])
    source = getattr(target, "SourceObject", None)
    if source is None:
        raise ValueError("drape target has no source object")

    pieces = (piece,)
    snapshots = {
        id(item): {
            "placement": item.Placement,
            "sketch_placement": getattr(getattr(item, "Sketch", None), "Placement", None),
        }
        for item in pieces
    }
    previous_piece_placements = list(getattr(scene, "PiecePlacements", ()) or ())
    previous_status = str(getattr(scene, "FitStatus", ""))

    try:
        target_shape = _world_shape(source)
        piece_shape = _world_shape(piece)
        before_distance = None
        moved = 0.0

        for _ in range(max_iterations):
            distance, nearest, _details = piece_shape.distToShape(target_shape)
            distance = float(distance)
            if before_distance is None:
                before_distance = distance
            if distance + 1e-6 >= clearance:
                break

            if nearest and len(nearest) >= 2:
                target_point, piece_point = nearest[0], nearest[1]
                direction = piece_point.sub(target_point)
                outward = _shape_center(piece_shape).sub(_shape_center(target_shape))
                if direction.dot(outward) < 0.0:
                    direction = direction.multiply(-1.0)
            else:
                direction = _shape_center(piece_shape).sub(_shape_center(target_shape))
            if direction.Length <= 1e-9:
                raise RuntimeError("snap blocked: target and garment have no stable outward direction")
            direction.normalize()

            step = max(clearance - distance, 2.0)
            remaining = max_translation - moved
            if step > remaining + 1e-9:
                raise RuntimeError(
                    "snap blocked: required translation exceeds %.3f mm" % max_translation
                )
            base = piece.Placement.Base + direction.multiply(step)
            piece.Placement = App.Placement(base, piece.Placement.Rotation)
            sketch = getattr(piece, "Sketch", None)
            if sketch is not None:
                sketch.Placement = piece.Placement
            moved += step
            piece_shape = _world_shape(piece)

        final_distance = float(piece_shape.distToShape(target_shape)[0])
        if final_distance + 1e-6 < clearance:
            raise RuntimeError(
                "snap failed: final clearance %.6f mm is below %.6f mm" %
                (final_distance, clearance)
            )

        pid = str(getattr(piece, "PieceId", "")).strip()
        if pid:
            values = {
                placement.piece_id: placement
                for placement in (
                    PiecePlacement.from_string(value)
                    for value in getattr(scene, "PiecePlacements", ()) or ()
                )
            }
            current = values.get(pid)
            rotation_z = float(current.rotation_z) if current is not None else float(piece.Placement.Rotation.Angle)
            axis = piece.Placement.Rotation.Axis
            values[pid] = PiecePlacement(
                pid,
                (float(piece.Placement.Base.x), float(piece.Placement.Base.y), float(piece.Placement.Base.z)),
                rotation_z,
                (float(axis.x), float(axis.y), float(axis.z)),
            )
            scene.PiecePlacements = [values[key].to_string() for key in sorted(values)]
        scene.FitStatus = "Target snapped (clearance %.3f mm)" % final_distance
        doc.recompute()
        return {
            "piece_id": pid,
            "distance_before": float(before_distance if before_distance is not None else final_distance),
            "distance_after": final_distance,
            "translation": moved,
            "clearance": clearance,
        }
    except BaseException:
        snapshot = snapshots[id(piece)]
        piece.Placement = snapshot["placement"]
        sketch = getattr(piece, "Sketch", None)
        if sketch is not None and snapshot["sketch_placement"] is not None:
            sketch.Placement = snapshot["sketch_placement"]
        scene.PiecePlacements = previous_piece_placements
        scene.HomePlacements = list(home_before)
        scene.FitStatus = previous_status
        if target_property_existed:
            scene.DrapeTarget = target_before
        elif "DrapeTarget" in set(getattr(scene, "PropertiesList", ()) or ()):
            scene.removeProperty("DrapeTarget")
        doc.recompute()
        raise


def snap_pattern_pieces_to_target(pieces=None, target=None, clearance=8.0, max_translation=240.0, max_iterations=32):
    """Atomically run the singular target snap over selected PatternPieces."""
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before arranging garment pieces")
    scene = _scene(doc)
    if scene is None:
        raise ValueError("create a fitting scene first")
    selected = tuple(
        sorted(
            (piece for piece in (pieces or scene.PatternPieces) if getattr(piece, "PatternType", "") == "PatternPiece"),
            key=lambda item: str(getattr(item, "PieceId", getattr(item, "Name", ""))),
        )
    )
    if not selected:
        raise ValueError("no PatternPiece objects were supplied")
    snapshots = {
        piece: (piece.Placement, getattr(getattr(piece, "Sketch", None), "Placement", None))
        for piece in selected
    }
    placements_before = tuple(getattr(scene, "PiecePlacements", ()) or ())
    homes_before = tuple(getattr(scene, "HomePlacements", ()) or ())
    status_before = str(getattr(scene, "FitStatus", ""))
    target_before = getattr(scene, "DrapeTarget", None) if "DrapeTarget" in set(getattr(scene, "PropertiesList", ()) or ()) else None
    try:
        results = tuple(
            snap_piece_to_drape_target(
                piece, target=target, clearance=clearance,
                max_translation=max_translation, max_iterations=max_iterations,
            )
            for piece in selected
        )
        if tuple(getattr(scene, "HomePlacements", ()) or ()) != homes_before:
            raise RuntimeError("target-aware placement mutated HomePlacements")
        return results
    except BaseException:
        for piece, (placement, sketch_placement) in snapshots.items():
            piece.Placement = placement
            sketch = getattr(piece, "Sketch", None)
            if sketch is not None and sketch_placement is not None:
                sketch.Placement = sketch_placement
        scene.PiecePlacements = list(placements_before)
        scene.HomePlacements = list(homes_before)
        scene.FitStatus = status_before
        if "DrapeTarget" in set(getattr(scene, "PropertiesList", ()) or ()):
            scene.DrapeTarget = target_before
        doc.recompute()
        raise

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
    target = getattr(scene, "DrapeTarget", None) or doc.getObject("DrapeTarget")
    if target is not None:
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
    "ClothFitting_SnapPiecesToTarget": _snap_selected_pieces_to_target,
    "ClothFitting_ResetArrangement": reset_arrangement,
    "ClothFitting_CreateSimulation": create_simulation_from_fitting,
}


def _snap_selected_pieces_to_target():
    import FreeCADGui as Gui
    active = Gui.activeDocument()
    if active is None:
        raise ValueError("open a document before snapping pattern pieces")
    scene = _scene(active.Document)
    if scene is None:
        raise ValueError("create a fitting scene first")
    selected = tuple(
        obj for obj in Gui.Selection.getSelection()
        if getattr(obj, "PatternType", "") == "PatternPiece"
    )
    if not selected:
        selected = tuple(scene.PatternPieces)
    targets = tuple(
        obj for obj in Gui.Selection.getSelection()
        if hasattr(obj, "TargetType") and hasattr(obj, "SourceObject")
    )
    if len(targets) > 1:
        raise ValueError("select at most one DrapeTarget")
    return snap_pattern_pieces_to_target(selected, targets[0] if targets else None)

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
