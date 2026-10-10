"""FreeCAD-facing body measurement, avatar fitting, and arrangement commands."""

import hashlib
import json


def _scene(doc):
    return next((o for o in doc.Objects if getattr(o, "FittingType", "") == "FittingScene"), None)


def _safe_name(value):
    return "".join(ch if ch.isalnum() else "_" for ch in str(value)) or "Item"


def _ensure_anchor_property(scene):
    """Add anchor persistence to fitting scenes created by older workbench versions."""
    if hasattr(scene, "ArrangementAnchorData"):
        return
    add_property = getattr(scene, "addProperty", None)
    if callable(add_property):
        add_property("App::PropertyStringList", "ArrangementAnchorData", "Arrangement")
        scene.ArrangementAnchorData = []


def _anchor_records(scene):
    """Read the compact persistent anchor metadata keyed by arrangement-point name."""
    _ensure_anchor_property(scene)
    result = {}
    for value in tuple(getattr(scene, "ArrangementAnchorData", ()) or ()):
        try:
            record = json.loads(str(value))
            name = str(record.get("name", ""))
            if name:
                result[name] = record
        except (AttributeError, TypeError, ValueError):
            continue
    return result


def _store_anchor_records(scene, records):
    """Persist a stable, sorted representation of surface-anchor references."""
    _ensure_anchor_property(scene)
    scene.ArrangementAnchorData = [
        json.dumps(records[name], sort_keys=True, separators=(",", ":")) for name in sorted(records)
    ]


def _point_xyz(point):
    """Normalize a tuple or FreeCAD vector to a numeric XYZ triple."""
    try:
        return tuple(float(value) for value in point[:3])
    except (TypeError, ValueError, IndexError):
        return (float(point.x), float(point.y), float(point.z))


def _geometry_round(value, digits=5):
    """Round geometry values and canonicalize negative zero for stable signatures."""
    rounded = round(float(value), digits)
    return 0.0 if rounded == 0.0 else rounded


def _mesh_topology(target):
    """Return mesh-local vertices and triangle indices, or None for non-mesh targets."""
    mesh = getattr(target, "Mesh", None)
    topology = getattr(mesh, "Topology", None) if mesh is not None else None
    if topology is None:
        return None
    try:
        vertices, triangles = topology
        points = tuple(_point_xyz(point) for point in vertices)
        placement = getattr(target, "Placement", None)
        if placement is not None:
            # A placed Mesh::Feature can expose Mesh.Topology coordinates with the
            # object placement already applied. Anchors persist in object-local
            # space, so normalize here before calculating or resolving barycentric
            # coordinates; _anchor_world_position applies Placement exactly once.
            try:
                import FreeCAD as App

                inverse_placement = placement.inverse()
                points = tuple(
                    _point_xyz(inverse_placement.multVec(App.Vector(*point)))
                    for point in points
                )
            except (AttributeError, ImportError, RuntimeError, TypeError, ValueError) as exc:
                raise ValueError("could not normalize target mesh vertices to object-local coordinates") from exc
        faces = tuple(tuple(int(index) for index in face) for face in triangles)
        if (
            not points
            or not faces
            or any(len(face) != 3 or min(face) < 0 or max(face) >= len(points) for face in faces)
        ):
            raise ValueError("mesh topology must contain valid triangles")
        return points, faces
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("the selected target has unusable mesh topology") from exc


def _target_signature(target):
    """Sign local geometry/topology, deliberately excluding object Placement and mesh vertices.

    Mesh anchors use stable triangle connectivity plus barycentric coordinates. This lets a
    generated avatar deform its vertices during skeleton posing without invalidating the
    anchor, while still detecting a topology rebuild. Non-mesh anchors follow object
    Placement and become stale if the underlying shape geometry itself changes.
    """
    mesh_topology = _mesh_topology(target)
    if mesh_topology is not None:
        vertices, triangles = mesh_topology
        payload = json.dumps(
            {"vertex_count": len(vertices), "triangles": triangles},
            separators=(",", ":"),
        ).encode("ascii")
        return "mesh-topology:" + hashlib.sha256(payload).hexdigest()

    shape = getattr(target, "Shape", None)
    if shape is None:
        raise ValueError("the selected target does not expose supported geometry")
    # In FreeCAD, a Shape's returned geometry can include the owning object's
    # Placement. Normalize a copy into object-local coordinates before signing it.
    # A BRep serialization hash is not stable across an inverse rigid transform,
    # so use rounded local vertex positions and intrinsic edge/face measures.
    try:
        normalized_shape = shape.copy()
        placement = getattr(target, "Placement", None)
        if placement is not None:
            normalized_shape.transformShape(placement.inverse().toMatrix())
        if bool(normalized_shape.isNull()):
            raise ValueError("the selected target shape is null")

        vertices = tuple(
            sorted(
                tuple(_geometry_round(value) for value in _point_xyz(vertex.Point))
                for vertex in tuple(normalized_shape.Vertexes)
            )
        )
        edges = tuple(
            sorted(
                (
                    _geometry_round(edge.Length),
                    tuple(_geometry_round(value) for value in _point_xyz(edge.CenterOfMass)),
                )
                for edge in tuple(normalized_shape.Edges)
            )
        )
        faces = tuple(
            sorted(
                (
                    str(type(face.Surface).__name__),
                    _geometry_round(face.Area),
                    tuple(_geometry_round(value) for value in _point_xyz(face.CenterOfMass)),
                    len(tuple(face.Edges)),
                )
                for face in tuple(normalized_shape.Faces)
            )
        )
        box = normalized_shape.BoundBox
        signature = (
            "ShapeLocal",
            int(len(tuple(normalized_shape.Solids))),
            len(vertices),
            vertices,
            edges,
            faces,
            _geometry_round(box.XMin),
            _geometry_round(box.XMax),
            _geometry_round(box.YMin),
            _geometry_round(box.YMax),
            _geometry_round(box.ZMin),
            _geometry_round(box.ZMax),
        )
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        raise ValueError("could not normalize the selected target shape") from exc
    if not vertices and not edges and not faces:
        raise ValueError("the selected target does not expose supported geometry")
    return repr(("shape-geometry", signature))


def _closest_triangle_weights(point, a, b, c):
    """Return barycentric coordinates of the closest point on triangle ABC."""

    def subtract(left, right):
        return tuple(left[i] - right[i] for i in range(3))

    def dot(left, right):
        return sum(left[i] * right[i] for i in range(3))

    ab = subtract(b, a)
    ac = subtract(c, a)
    ap = subtract(point, a)
    d1, d2 = dot(ab, ap), dot(ac, ap)
    if d1 <= 0.0 and d2 <= 0.0:
        return (1.0, 0.0, 0.0)

    bp = subtract(point, b)
    d3, d4 = dot(ab, bp), dot(ac, bp)
    if d3 >= 0.0 and d4 <= d3:
        return (0.0, 1.0, 0.0)

    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        denom = d1 - d3
        v = d1 / denom if abs(denom) > 1e-15 else 0.0
        return (1.0 - v, v, 0.0)

    cp = subtract(point, c)
    d5, d6 = dot(ab, cp), dot(ac, cp)
    if d6 >= 0.0 and d5 <= d6:
        return (0.0, 0.0, 1.0)

    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        denom = d2 - d6
        w = d2 / denom if abs(denom) > 1e-15 else 0.0
        return (1.0 - w, 0.0, w)

    va = d3 * d6 - d5 * d4
    if va <= 0.0 and d4 - d3 >= 0.0 and d5 - d6 >= 0.0:
        denom = (d4 - d3) + (d5 - d6)
        w = (d4 - d3) / denom if abs(denom) > 1e-15 else 0.0
        return (0.0, 1.0 - w, w)

    denom = va + vb + vc
    if abs(denom) <= 1e-15:
        return (1.0, 0.0, 0.0)
    inv = 1.0 / denom
    v, w = vb * inv, vc * inv
    return (1.0 - v - w, v, w)


def _weighted_triangle_point(vertices, triangle, weights):
    """Interpolate the current mesh position associated with saved triangle weights."""
    return tuple(
        sum(vertices[triangle[i]][axis] * float(weights[i]) for i in range(3)) for axis in range(3)
    )


def _mesh_anchor_local_position(target, anchor):
    """Resolve a mesh anchor against current vertices, preserving its material location."""
    topology = _mesh_topology(target)
    if topology is None or "triangle_index" not in anchor or "barycentric" not in anchor:
        return tuple(float(value) for value in anchor.get("local_point", (0.0, 0.0, 0.0)))
    vertices, triangles = topology
    triangle_index = int(anchor["triangle_index"])
    if triangle_index < 0 or triangle_index >= len(triangles):
        raise ValueError("anchored mesh triangle no longer exists")
    weights = tuple(float(value) for value in anchor["barycentric"])
    if len(weights) != 3 or abs(sum(weights) - 1.0) > 1e-5:
        raise ValueError("stored mesh-anchor barycentric coordinates are invalid")
    return _weighted_triangle_point(vertices, triangles[triangle_index], weights)


def _mesh_anchor_coordinates(target, local_point):
    """Find the closest mesh triangle and retain its barycentric hit coordinate."""
    topology = _mesh_topology(target)
    if topology is None:
        return None
    vertices, triangles = topology
    best = None
    best_distance = float("inf")
    for triangle_index, triangle in enumerate(triangles):
        a, b, c = (vertices[index] for index in triangle)
        weights = _closest_triangle_weights(local_point, a, b, c)
        projected = _weighted_triangle_point(vertices, triangle, weights)
        distance = sum((projected[axis] - local_point[axis]) ** 2 for axis in range(3))
        if distance < best_distance:
            best_distance = distance
            best = (triangle_index, weights, projected)
    if best is None:
        raise ValueError("the selected mesh contains no usable surface triangles")
    return best


def _anchor_record_status(scene, target, anchor, document=None):
    if target is None:
        return "missing target"
    if document is None:
        document = getattr(scene, "Document", None) if scene is not None else None
    if document is not None:
        drape_target = document.getObject("DrapeTarget")
        configured_target = getattr(scene, "AvatarProxy", None)
        if configured_target is None:
            configured_target = getattr(drape_target, "SourceObject", None)
        if configured_target is None:
            return "unconfigured target"
        if str(getattr(configured_target, "Name", "")) != str(getattr(target, "Name", "")):
            return "wrong target"
    try:
        return (
            "valid"
            if _target_signature(target) == str(anchor.get("geometry_signature", ""))
            else "stale"
        )
    except (AttributeError, TypeError, ValueError, RuntimeError):
        return "invalid"


def _anchor_world_position(target, anchor):
    """Resolve a persistent local/mesh anchor into the document's world coordinates."""
    import FreeCAD as App

    local = _mesh_anchor_local_position(target, anchor)
    placement = getattr(target, "Placement", None)
    if placement is not None:
        world = placement.multVec(App.Vector(*local))
        return float(world.x), float(world.y), float(world.z)
    return tuple(float(value) for value in local)


def _refresh_anchor_positions(scene, update_visuals=False):
    """Follow valid anchors after a target deforms or its object Placement changes."""
    if scene is None or getattr(scene, "Document", None) is None:
        return ()
    import FreeCAD as App

    doc = scene.Document
    from freecad_cloth.avatar.AvatarFitting import ArrangementPoint

    anchors = _anchor_records(scene)
    values = {
        point.name: point
        for point in (
            ArrangementPoint.from_string(value)
            for value in tuple(getattr(scene, "ArrangementPoints", ()) or ())
        )
    }
    changed = []
    for name, anchor in anchors.items():
        point = values.get(name)
        if point is None:
            continue
        target = doc.getObject(str(anchor.get("target", "")))
        if _anchor_record_status(scene, target, anchor) != "valid":
            continue
        try:
            x, y, z = _anchor_world_position(target, anchor)
        except (AttributeError, IndexError, TypeError, ValueError, RuntimeError):
            continue
        if max(abs(point.x - x), abs(point.y - y), abs(point.offset - z)) <= 1e-6:
            continue
        updated = ArrangementPoint(
            point.name, x, y, z, point.wrap_direction, point.rotation_z, point.symmetry_group
        )
        values[name] = updated
        changed.append((name, updated))
    if not changed:
        return ()

    scene.ArrangementPoints = [values[key].to_string() for key in sorted(values)]
    if update_visuals:
        import Part

        objects = {
            str(getattr(obj, "PointName", "")): obj
            for obj in (
                doc.getObject(str(name))
                for name in tuple(getattr(scene, "ArrangementPointObjects", ()) or ())
            )
            if obj is not None
        }
        for name, point in changed:
            obj = objects.get(name)
            if obj is None:
                continue
            obj.X, obj.Y, obj.Offset, obj.RotationZ = (
                point.x,
                point.y,
                point.offset,
                point.rotation_z,
            )
            center = App.Vector(point.x, point.y, point.offset)
            obj.Shape = Part.makeCompound(
                [
                    Part.makeSphere(0.8, center),
                    Part.makeCircle(7.0, center, App.Vector(0.0, 0.0, 1.0)),
                    Part.makeLine(
                        center - App.Vector(10.0, 0.0, 0.0),
                        center + App.Vector(10.0, 0.0, 0.0),
                    ),
                    Part.makeLine(
                        center - App.Vector(0.0, 10.0, 0.0),
                        center + App.Vector(0.0, 10.0, 0.0),
                    ),
                ]
            )
    return tuple(name for name, _point in changed)


def arrangement_anchor_status(point):
    """Report whether a snap point's persisted surface reference is still current."""
    expected = str(getattr(point, "AnchorGeometrySignature", "") or "")
    if not expected:
        return "unanchored"
    target = getattr(point, "AnchorTarget", None)
    if target is None:
        return "missing target"
    document = getattr(point, "Document", None)
    scene = _scene(document) if document is not None else None
    return _anchor_record_status(scene, target, {"geometry_signature": expected}, document=document)


def _sync_visuals(scene):
    """Synchronize visible FreeCAD point/volume adapters from canonical strings."""
    import FreeCAD as App
    import Part

    from freecad_cloth.avatar.AvatarFitting import ArrangementPoint, BoundingVolume

    _ensure_anchor_property(scene)
    _refresh_anchor_positions(scene)
    anchor_records = _anchor_records(scene)
    points = tuple(ArrangementPoint.from_string(v) for v in scene.ArrangementPoints)
    volumes = tuple(BoundingVolume.from_string(v) for v in scene.BoundingVolumes)
    point_objects = []
    volume_objects = []
    existing = {o.Name: o for o in scene.Document.Objects}
    for point in points:
        name = "ArrangementPoint_" + _safe_name(point.name)
        obj = existing.get(name) or scene.Document.addObject("Part::Feature", name)
        obj.Label = "Snap target: " + point.name
        if not hasattr(obj, "FittingType"):
            obj.addProperty(
                "App::PropertyString", "FittingType", "Fitting"
            ).FittingType = "ArrangementPoint"
        for prop, value in (
            ("PointName", point.name),
            ("WrapDirection", point.wrap_direction),
            ("SymmetryGroup", point.symmetry_group),
        ):
            if not hasattr(obj, prop):
                obj.addProperty("App::PropertyString", prop, "Fitting")
            setattr(obj, prop, value)
        if not hasattr(obj, "X"):
            obj.addProperty("App::PropertyDistance", "X", "Arrangement")
            obj.addProperty("App::PropertyDistance", "Y", "Arrangement")
            obj.addProperty("App::PropertyDistance", "Offset", "Arrangement")
            obj.addProperty("App::PropertyAngle", "RotationZ", "Arrangement")
        if not hasattr(obj, "AnchorTarget"):
            obj.addProperty("App::PropertyLinkGlobal", "AnchorTarget", "Surface Anchor")
            obj.addProperty("App::PropertyString", "AnchorSubelement", "Surface Anchor")
            obj.addProperty("App::PropertyVector", "AnchorLocalPoint", "Surface Anchor")
            obj.addProperty("App::PropertyString", "AnchorGeometrySignature", "Surface Anchor")
            obj.addProperty("App::PropertyString", "AnchorStatus", "Surface Anchor")
        obj.X, obj.Y, obj.Offset, obj.RotationZ = point.x, point.y, point.offset, point.rotation_z
        anchor = anchor_records.get(point.name)
        if anchor:
            obj.AnchorTarget = scene.Document.getObject(str(anchor.get("target", "")))
            obj.AnchorSubelement = str(anchor.get("subelement", ""))
            obj.AnchorGeometrySignature = str(anchor.get("geometry_signature", ""))
            local_point = tuple(anchor.get("local_point", (0.0, 0.0, 0.0)))
            obj.AnchorLocalPoint = App.Vector(*(float(v) for v in local_point))
            obj.AnchorStatus = arrangement_anchor_status(obj)
        else:
            obj.AnchorTarget = None
            obj.AnchorSubelement = ""
            obj.AnchorGeometrySignature = ""
            obj.AnchorLocalPoint = App.Vector(0.0, 0.0, 0.0)
            obj.AnchorStatus = "unanchored"
        if obj.AnchorStatus in {
            "stale",
            "missing target",
            "invalid",
            "wrong target",
            "unconfigured target",
        }:
            obj.Label = "Stale anchor: " + point.name
            obj.ViewObject.ShapeColor = (0.95, 0.24, 0.16)
            obj.ViewObject.LineColor = (0.65, 0.10, 0.08)
        else:
            obj.Label = "Snap target: " + point.name
            obj.ViewObject.ShapeColor = (0.15, 0.75, 1.0)
            obj.ViewObject.LineColor = (0.05, 0.45, 0.72)
        center = App.Vector(point.x, point.y, point.offset)
        obj.Shape = Part.makeCompound(
            [
                Part.makeSphere(0.8, center),
                Part.makeCircle(7.0, center, App.Vector(0.0, 0.0, 1.0)),
                Part.makeLine(
                    center - App.Vector(10.0, 0.0, 0.0),
                    center + App.Vector(10.0, 0.0, 0.0),
                ),
                Part.makeLine(
                    center - App.Vector(0.0, 10.0, 0.0),
                    center + App.Vector(0.0, 10.0, 0.0),
                ),
            ]
        )
        obj.ViewObject.LineWidth = 2.0
        point_objects.append(obj)
    for volume in volumes:
        name = "BoundingVolume_" + _safe_name(volume.name)
        obj = existing.get(name) or scene.Document.addObject("Part::Feature", name)
        obj.Label = "Bounding Volume: " + volume.name
        if not hasattr(obj, "FittingType"):
            obj.addProperty(
                "App::PropertyString", "FittingType", "Fitting"
            ).FittingType = "BoundingVolume"
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
    # The proxy's persisted-state validation is also exercised with lightweight
    # headless objects. They have no FreeCAD property API to migrate; real
    # document objects always expose addProperty.
    if not callable(getattr(scene, "addProperty", None)):
        return
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
    obj.addProperty(
        "App::PropertyString", "MeasurementData", "Measurements"
    ).MeasurementData = BodyMeasurements().to_json()
    obj.addProperty("App::PropertyString", "MeasurementUnit", "Measurements").MeasurementUnit = "mm"
    obj.addProperty("App::PropertyLinkGlobal", "AvatarProxy", "Fitting")
    obj.addProperty("App::PropertyLinkListGlobal", "PatternPieces", "Fitting")
    obj.addProperty("App::PropertyStringList", "PiecePlacements", "Fitting").PiecePlacements = []
    obj.addProperty("App::PropertyStringList", "HomePlacements", "Fitting").HomePlacements = []
    obj.addProperty(
        "App::PropertyStringList", "ArrangementPoints", "Arrangement"
    ).ArrangementPoints = []
    obj.addProperty(
        "App::PropertyStringList", "ArrangementAnchorData", "Arrangement"
    ).ArrangementAnchorData = []
    obj.addProperty(
        "App::PropertyStringList", "BoundingVolumes", "Arrangement"
    ).BoundingVolumes = []
    obj.addProperty(
        "App::PropertyStringList", "ArrangementPointObjects", "Arrangement"
    ).ArrangementPointObjects = []
    obj.addProperty(
        "App::PropertyStringList", "BoundingVolumeObjects", "Arrangement"
    ).BoundingVolumeObjects = []
    obj.addProperty("App::PropertyBool", "SymmetryEnabled", "Arrangement").SymmetryEnabled = True
    obj.addProperty("App::PropertyString", "FitStatus", "Fitting").FitStatus = "Unassigned"
    obj.Proxy = _FittingProxy()
    FittingScene().validate()
    doc.recompute()
    return obj


def set_body_measurements(measurements, unit="mm"):
    import FreeCAD as App

    from freecad_cloth.avatar.AvatarFitting import BodyMeasurements

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

    from freecad_cloth.simulation.DrapeTarget import assign_drape_target, create_drape_target

    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _scene(doc) or create_fitting_scene()
    if source is None:
        source = next(
            (o for o in Gui.Selection.getSelection() if hasattr(o, "Shape") or hasattr(o, "Mesh")),
            None,
        )
    if source is None:
        raise ValueError("select a FreeCAD body or mesh to use as the avatar source")

    target = doc.getObject("DrapeTarget")
    target_type = (
        "Mannequin"
        if str(getattr(source, "AvatarType", "")) == "ClothAvatar"
        else "FreeCAD Geometry"
    )
    if target is None:
        target = create_drape_target(doc, source, target_type, 1.0, 2.0)
    else:
        target.CollisionDeflection = 1.0
        target.CollisionThickness = 2.0
        assign_drape_target(target, source, target_type)

    scene.AvatarProxy = source
    scene.FitStatus = "Avatar assigned"
    doc.recompute()
    return scene


def add_selected_pattern_pieces():
    import FreeCAD as App
    import FreeCADGui as Gui

    from freecad_cloth.avatar.AvatarFitting import BodyMeasurements, FittingScene, PiecePlacement

    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _scene(doc) or create_fitting_scene()
    pieces = [
        o for o in Gui.Selection.getSelection() if getattr(o, "PatternType", "") == "PatternPiece"
    ]
    if not pieces:
        raise ValueError(
            "select one or more pattern pieces before adding them to the fitting scene"
        )
    existing = [PiecePlacement.from_string(v) for v in scene.PiecePlacements]
    homes = [PiecePlacement.from_string(v) for v in scene.HomePlacements]
    by_id = {p.piece_id: p for p in existing}
    home_by_id = {p.piece_id: p for p in homes}
    for piece in pieces:
        placement = piece.Placement
        base = placement.Base
        value = PiecePlacement(
            str(piece.PieceId),
            (float(base.x), float(base.y), float(base.z)),
            float(placement.Rotation.Angle),
        )
        by_id[value.piece_id] = value
        home_by_id.setdefault(value.piece_id, value)
    scene.PatternPieces = sorted(
        set(list(scene.PatternPieces) + pieces), key=lambda o: str(o.PieceId)
    )
    scene.PiecePlacements = [by_id[k].to_string() for k in sorted(by_id)]
    scene.HomePlacements = [home_by_id[k].to_string() for k in sorted(home_by_id)]
    FittingScene(
        BodyMeasurements.from_json(scene.MeasurementData),
        getattr(scene.AvatarProxy, "Label", "") if scene.AvatarProxy else "",
        tuple(by_id.values()),
    ).validate()
    scene.FitStatus = "Ready" if scene.AvatarProxy else "Pieces assigned"
    doc.recompute()
    return scene


def position_piece(piece, x, y, z=0.0, rotation_z=0.0):
    import FreeCAD as App

    from freecad_cloth.avatar.AvatarFitting import PiecePlacement

    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _scene(doc) or create_fitting_scene()
    if getattr(piece, "PatternType", "") != "PatternPiece":
        raise ValueError("piece must be a Cloth PatternPiece object")
    placement = App.Placement(
        App.Vector(float(x), float(y), float(z)),
        App.Rotation(App.Vector(0, 0, 1), float(rotation_z)),
    )
    piece.Placement = placement
    entries = {
        p.piece_id: p for p in (PiecePlacement.from_string(v) for v in scene.PiecePlacements)
    }
    entries[str(piece.PieceId)] = PiecePlacement(
        str(piece.PieceId), (float(x), float(y), float(z)), float(rotation_z)
    )
    scene.PiecePlacements = [entries[k].to_string() for k in sorted(entries)]
    doc.recompute()
    return piece


def create_arrangement_point(
    name, x, y, offset=0.0, wrap_direction="front", rotation_z=0.0, symmetry_group="", mirror=False
):
    import FreeCAD as App

    from freecad_cloth.avatar.AvatarFitting import ArrangementPoint

    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _scene(doc) or create_fitting_scene()
    point = ArrangementPoint(
        str(name),
        float(x),
        float(y),
        float(offset),
        str(wrap_direction),
        float(rotation_z),
        str(symmetry_group),
    )
    point.validate()
    values = {p.name: p for p in (ArrangementPoint.from_string(v) for v in scene.ArrangementPoints)}
    values[point.name] = point
    anchors = _anchor_records(scene)
    anchors.pop(point.name, None)
    if mirror:
        if not symmetry_group.strip():
            raise ValueError("mirror arrangement points require a symmetry group")
        mirrored = point.mirrored()
        values[mirrored.name] = mirrored
        anchors.pop(mirrored.name, None)
    scene.ArrangementPoints = [values[k].to_string() for k in sorted(values)]
    _store_anchor_records(scene, anchors)
    scene.SymmetryEnabled = bool(scene.SymmetryEnabled)
    _sync_visuals(scene)
    return point


def set_arrangement_point(
    name, x=None, y=None, offset=None, wrap_direction=None, rotation_z=None, symmetry_group=None
):
    import FreeCAD as App

    from freecad_cloth.avatar.AvatarFitting import ArrangementPoint

    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _scene(doc)
    if scene is None:
        raise ValueError("create a fitting scene first")
    values = {p.name: p for p in (ArrangementPoint.from_string(v) for v in scene.ArrangementPoints)}
    if name not in values:
        raise ValueError(f"unknown arrangement point: {name}")
    old = values[name]
    point = ArrangementPoint(
        old.name,
        old.x if x is None else float(x),
        old.y if y is None else float(y),
        old.offset if offset is None else float(offset),
        old.wrap_direction if wrap_direction is None else str(wrap_direction),
        old.rotation_z if rotation_z is None else float(rotation_z),
        old.symmetry_group if symmetry_group is None else str(symmetry_group),
    )
    point.validate()
    values[name] = point
    scene.ArrangementPoints = [values[k].to_string() for k in sorted(values)]
    anchors = _anchor_records(scene)
    anchors.pop(name, None)
    _store_anchor_records(scene, anchors)
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
        raise ValueError(f"unknown arrangement point: {name}")
    del values[name]
    scene.ArrangementPoints = [values[k].to_string() for k in sorted(values)]
    anchors = _anchor_records(scene)
    anchors.pop(name, None)
    _store_anchor_records(scene, anchors)
    _sync_visuals(scene)
    return scene


def create_bounding_volume(name, center=(0.0, 0.0, 0.0), size=(100.0, 100.0, 100.0)):
    import FreeCAD as App

    from freecad_cloth.avatar.AvatarFitting import BoundingVolume

    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _scene(doc) or create_fitting_scene()
    volume = BoundingVolume(
        str(name), tuple(float(v) for v in center), tuple(float(v) for v in size)
    )
    volume.validate()
    values = {v.name: v for v in (BoundingVolume.from_string(v) for v in scene.BoundingVolumes)}
    values[volume.name] = volume
    scene.BoundingVolumes = [values[k].to_string() for k in sorted(values)]
    _sync_visuals(scene)
    return volume


def delete_bounding_volume(name):
    import FreeCAD as App

    from freecad_cloth.avatar.AvatarFitting import BoundingVolume

    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before deleting a bounding volume")
    scene = _scene(doc)
    if scene is None:
        raise ValueError("create a fitting scene first")
    values = {v.name: v for v in (BoundingVolume.from_string(v) for v in scene.BoundingVolumes)}
    if name not in values:
        raise ValueError(f"unknown bounding volume: {name}")
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
            raise ValueError(f"unknown arrangement point: {point}")
        point = values[point]
    point.validate()
    if mirror is True and scene.SymmetryEnabled:
        point = point.mirrored()
    rotations = {
        "front": point.rotation_z,
        "back": point.rotation_z + 180.0,
        "left": point.rotation_z + 90.0,
        "right": point.rotation_z - 90.0,
    }
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
        piece.Placement = App.Placement(
            App.Vector(x, y, z), App.Rotation(App.Vector(0, 0, 1), placement.rotation_z)
        )
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
    from freecad_cloth.simulation.SimulationObjects import (
        create_simulation_scene,
        set_avatar_collision_source,
    )

    simulation = create_simulation_scene(doc)
    simulation.ClothPieces = list(scene.PatternPieces)
    if scene.AvatarProxy is not None:
        set_avatar_collision_source(
            simulation,
            scene.AvatarProxy,
            thickness=2.0,
            deflection=1.0,
        )
    doc.recompute()
    return simulation


def open_interactive_arrange(scene=None):
    """Open the direct-manipulation fitting panel for the active fitting scene."""
    import FreeCAD as App
    import FreeCADGui as Gui

    doc = App.ActiveDocument
    if doc is None:
        raise RuntimeError("open a document before opening Interactive Arrange")
    scene = scene or _scene(doc) or create_fitting_scene()
    from freecad_cloth.avatar.FittingGui import show_fitting_task

    panel = show_fitting_task(scene)
    if Gui.activeDocument():
        Gui.activeDocument().activeView().fitAll()
    return panel


def create_arrangement_point_from_viewport():
    """Open Interactive Arrange and arm the viewport surface-pick workflow."""
    panel = open_interactive_arrange()
    panel.start_anchor_pick()
    return panel


def create_arrangement_anchor(
    name, target, world_point, subelement="Face", wrap_direction="front", rotation_z=0.0
):
    """Create a named snap point from a pick on persistent target geometry.

    The anchor keeps a target-local location. Mesh surfaces use triangle indices and
    barycentric weights so stable-topology deformations follow the same surface region;
    non-mesh surfaces follow their object's Placement. Incompatible geometry is marked
    stale instead of silently snapping to old world coordinates.
    """
    import FreeCAD as App

    doc = App.ActiveDocument
    if doc is None:
        raise RuntimeError("open a document before creating a surface anchor")
    scene = _scene(doc) or create_fitting_scene()
    target_document = getattr(target, "Document", None) if target is not None else None
    if target_document is None or getattr(target_document, "Name", "") != doc.Name:
        raise ValueError("select a surface on geometry in the active document")
    signature = _target_signature(target)
    try:
        coords = (float(world_point.x), float(world_point.y), float(world_point.z))
    except AttributeError:
        coords = tuple(float(value) for value in world_point[:3])
    if len(coords) != 3:
        raise ValueError("picked surface location must contain three coordinates")
    world = App.Vector(*coords)
    try:
        local = target.Placement.inverse().multVec(world)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        local = world

    local_coords = (float(local.x), float(local.y), float(local.z))
    anchor = {
        "name": str(name),
        "target": str(target.Name),
        "subelement": str(subelement),
        "local_point": list(local_coords),
        "geometry_signature": signature,
    }
    mesh_hit = _mesh_anchor_coordinates(target, local_coords)
    if mesh_hit is not None:
        triangle_index, barycentric, projected = mesh_hit
        anchor["triangle_index"] = int(triangle_index)
        anchor["barycentric"] = [float(value) for value in barycentric]
        anchor["local_point"] = [float(value) for value in projected]
        local = App.Vector(*projected)
        try:
            world = target.Placement.multVec(local)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            world = local
        coords = (float(world.x), float(world.y), float(world.z))

    from freecad_cloth.avatar.AvatarFitting import ArrangementPoint

    point = ArrangementPoint(
        str(name), coords[0], coords[1], coords[2], str(wrap_direction), float(rotation_z)
    )
    point.validate()
    anchors = _anchor_records(scene)
    anchors[point.name] = anchor
    values = {
        item.name: item
        for item in (ArrangementPoint.from_string(value) for value in scene.ArrangementPoints)
    }
    values[point.name] = point
    scene.ArrangementPoints = [values[key].to_string() for key in sorted(values)]
    _store_anchor_records(scene, anchors)
    _sync_visuals(scene)
    doc.recompute()
    return point


class _FittingProxy:
    Type = "ClothFittingScene"

    def execute(self, obj):
        from freecad_cloth.avatar.AvatarFitting import (
            ArrangementPoint,
            BodyMeasurements,
            BoundingVolume,
            FittingScene,
            PiecePlacement,
        )

        _migrate_visual_output_references(obj)
        measurements = BodyMeasurements.from_json(obj.MeasurementData)
        avatar_name = getattr(obj.AvatarProxy, "Label", "") if obj.AvatarProxy else ""
        placements = tuple(PiecePlacement.from_string(v) for v in obj.PiecePlacements)
        points = tuple(ArrangementPoint.from_string(v) for v in obj.ArrangementPoints)
        volumes = tuple(BoundingVolume.from_string(v) for v in obj.BoundingVolumes)
        FittingScene(
            measurements, avatar_name, placements, points, volumes, bool(obj.SymmetryEnabled)
        ).validate()


COMMANDS = [
    "ClothFitting_CreateScene",
    "ClothFitting_InteractiveArrange",
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
]
_COMMAND_HANDLERS = {
    "ClothFitting_CreateScene": create_fitting_scene,
    "ClothFitting_InteractiveArrange": open_interactive_arrange,
    "ClothFitting_SetMeasurements": lambda: set_body_measurements(
        {"height": 1700, "chest": 900, "waist": 760, "hip": 960, "shoulder": 420}
    ),
    "ClothFitting_AssignAvatar": assign_avatar_source,
    "ClothFitting_AddPieces": add_selected_pattern_pieces,
    "ClothFitting_CreateArrangementPoint": create_arrangement_point_from_viewport,
    "ClothFitting_SetArrangementPoint": lambda: set_arrangement_point("Point1", x=0, y=0),
    "ClothFitting_DeleteArrangementPoint": lambda: delete_arrangement_point("Point1"),
    "ClothFitting_CreateBoundingVolume": lambda: create_bounding_volume("Volume1"),
    "ClothFitting_DeleteBoundingVolume": lambda: delete_bounding_volume("Volume1"),
    "ClothFitting_SetSymmetry": lambda: set_symmetry_enabled(True),
    "ClothFitting_ApplyArrangementPoint": lambda: _apply_selected_arrangement(),
    "ClothFitting_ResetArrangement": reset_arrangement,
    "ClothFitting_CreateSimulation": create_simulation_from_fitting,
}


def _apply_selected_arrangement():
    import FreeCADGui as Gui

    scene = _scene(Gui.activeDocument().Document)
    if scene is None:
        raise ValueError("create a fitting scene first")
    piece = next(
        (
            o
            for o in Gui.Selection.getSelection()
            if getattr(o, "PatternType", "") == "PatternPiece"
        ),
        None,
    )
    point = next(
        (
            o
            for o in Gui.Selection.getSelection()
            if getattr(o, "FittingType", "") == "ArrangementPoint"
        ),
        None,
    )
    if piece is None or point is None:
        raise ValueError("select a pattern piece and an arrangement point")
    return apply_arrangement_point(piece, point.PointName)


try:
    import FreeCADGui as Gui

    from freecad_cloth.common.CommandAdapter import register_commands

    register_commands(Gui, _COMMAND_HANDLERS)
except (ImportError, AttributeError):
    pass
