"""FreeCAD-facing deterministic cloth simulation scene objects."""

def _mesh_object(doc, name, label):
    import Mesh
    obj = doc.addObject("Mesh::Feature", name)
    obj.Label = label
    obj.addProperty("App::PropertyString", "ClothMeshType", "Simulation").ClothMeshType = "DrapedCloth"
    return obj


def _write_mesh(obj, positions, triangles):
    import FreeCAD as App
    import Mesh
    native = Mesh.Mesh()
    for a, b, c in triangles:
        native.addFacet(App.Vector(*positions[a]), App.Vector(*positions[b]), App.Vector(*positions[c]))
    obj.Mesh = native


def _write_grid_mesh(obj, positions, indices, nx, ny):
    triangles = []
    for j in range(ny - 1):
        for i in range(nx - 1):
            a = indices[j * nx + i]
            b = a + 1
            c = (j + 1) * nx + i + 1
            d = (j + 1) * nx + i
            triangles.extend(((a, b, c), (a, c, d)))
    _write_mesh(obj, positions, triangles)


def _update_seam_visuals(doc, seam_stitch_pairs, positions):
    """Render each semantic solver seam as one canonical-color native overlay."""
    if doc is None:
        return ()
    from freecad_cloth.sewing.SewingView import seam_color_map
    seam_ids = tuple(sorted(
        str(seam_id).strip()
        for seam_id in (seam_stitch_pairs or {})
        if str(seam_id).strip()
    ))
    colors = seam_color_map(seam_ids)
    existing = {
        str(getattr(obj, "SimulationSeamId", "")).strip(): obj
        for obj in getattr(doc, "Objects", ())
        if str(getattr(obj, "SimulationSeamId", "")).strip()
    }
    active = set()
    for seam_id in seam_ids:
        visual = existing.get(seam_id)
        if visual is None:
            safe_id = "".join(char if char.isalnum() else "_" for char in seam_id).strip("_") or "seam"
            visual = doc.addObject("Part::Feature", "SimulationSeamVisual_%s" % safe_id)
            visual.Label = "Simulation seam: %s" % seam_id
            visual.addProperty("App::PropertyString", "SimulationSeamId", "Simulation").SimulationSeamId = seam_id
            existing[seam_id] = visual
        stitch_pairs = tuple(seam_stitch_pairs.get(seam_id, ()))
        side_a = [App.Vector(*positions[a]) for a, _ in stitch_pairs]
        side_b = [App.Vector(*positions[b]) for _, b in stitch_pairs]
        shapes = []
        if len(side_a) >= 2:
            shapes.append(Part.makePolygon(side_a))
        if len(side_b) >= 2:
            shapes.append(Part.makePolygon(side_b))
        visual.Shape = Part.makeCompound(shapes) if shapes else Part.Shape()
        view = getattr(visual, "ViewObject", None)
        if view is not None:
            view.LineColor = colors[seam_id]
            view.LineWidth = 3.0
            view.Visibility = bool(shapes)
        active.add(seam_id)
    for seam_id, visual in existing.items():
        if seam_id not in active:
            view = getattr(visual, "ViewObject", None)
            if view is not None:
                view.Visibility = False
    return tuple(existing[seam_id] for seam_id in seam_ids)


def _parse_pair_list(values, particle_count=None):
    pairs = []
    for value in values or ():
        parts = [p.strip() for p in str(value).replace(",", "-").split("-") if p.strip()]
        if len(parts) == 2:
            try:
                pair = (int(parts[0]), int(parts[1]))
            except ValueError:
                continue
            if particle_count is None or all(0 <= i < particle_count for i in pair):
                pairs.append(pair)
    return tuple(dict.fromkeys(pairs))


def _parse_int_list(values, particle_count=None):
    result = []
    for value in values or ():
        for part in str(value).replace(";", ",").split(","):
            try:
                i = int(part.strip())
            except ValueError:
                continue
            if particle_count is None or 0 <= i < particle_count:
                result.append(i)
    return tuple(dict.fromkeys(result))


def _placement_signature(piece):
    placement = getattr(piece, "Placement", None)
    if placement is None:
        return ()
    base = getattr(placement, "Base", None)
    rotation = getattr(placement, "Rotation", None)
    axis = getattr(rotation, "Axis", None) if rotation is not None else None
    return (
        float(getattr(base, "x", 0.0)),
        float(getattr(base, "y", 0.0)),
        float(getattr(base, "z", 0.0)),
        float(getattr(rotation, "Angle", 0.0)) if rotation is not None else 0.0,
        float(getattr(axis, "x", 0.0)) if axis is not None else 0.0,
        float(getattr(axis, "y", 0.0)) if axis is not None else 0.0,
        float(getattr(axis, "z", 1.0)) if axis is not None else 1.0,
    )


def _simulation_source_signature(obj, pieces):
    """Return deterministic inputs that require rebuilding the cloth scene."""
    if pieces:
        from freecad_cloth.common.PatternSimulationAdapter import resolve_simulation_pattern
        resolved = resolve_simulation_pattern(
            getattr(obj, "Document", None),
            tuple(pieces),
        )
        pattern_signature = resolved.signature
    else:
        pattern_signature = ((), ())
    target = getattr(obj, "DrapeTarget", None)
    target_signature = ()
    if target is not None:
        try:
            from freecad_cloth.simulation.DrapeTarget import source_signature
            source = getattr(target, "SourceObject", None)
            target_signature = source_signature(
                source,
                float(getattr(target, "CollisionDeflection", 1.0)),
                float(getattr(target, "CollisionThickness", 0.0)),
            ) if source is not None else ("unassigned",)
        except (ImportError, AttributeError, TypeError, ValueError):
            target_signature = ("invalid-target",)
    else:
        avatar = getattr(obj, "AvatarProxy", None)
        source = getattr(avatar, "SourceObject", None) if avatar is not None else None
        target_signature = (
            "legacy-avatar",
            str(getattr(source, "Name", "")),
            float(getattr(avatar, "CollisionDeflection", 0.0)) if avatar is not None else 0.0,
            float(getattr(avatar, "CollisionThickness", 0.0)) if avatar is not None else 0.0,
        )
    pin_signature = _parse_int_list(getattr(obj, "PinSelection", ()))
    return (
        pattern_signature,
        target_signature,
        int(getattr(obj, "StitchSamples", 8)),
        pin_signature,
    )


def _piece_mesh(piece, start_height, piece_ir=None):
    from freecad_cloth.common.PatternSimulationAdapter import geometry_from_piece_ir, resolve_piece_ir
    from freecad_cloth.pattern.PatternMesh import triangulate
    import FreeCAD as App

    if piece_ir is None:
        piece_ir = resolve_piece_ir(piece)
    mesh = triangulate(geometry_from_piece_ir(piece_ir))
    placement = getattr(piece, "Placement", None)
    vertices = []
    for x, y in mesh.vertices:
        point = App.Vector(x, y, float(start_height))
        if placement is not None:
            point = placement.multVec(point)
        vertices.append((float(point.x), float(point.y), float(point.z)))

    boundary = tuple(int(index) for index in mesh.boundary_vertex_indices)
    segment_ids = tuple(str(value) for value in mesh.boundary_edge_segment_ids)
    if not segment_ids:
        raise ValueError("pattern mesh semantic boundary provenance is missing")
    if len(segment_ids) != len(boundary):
        raise ValueError("pattern mesh boundary provenance length does not match boundary vertices")

    edge_pairs = {}
    for index, segment_id in enumerate(segment_ids):
        raw_key = str(segment_id)
        base = next(
            (
                str(boundary_ir.id)
                for boundary_ir in piece_ir.boundaries
                if raw_key == str(boundary_ir.id)
                or raw_key.startswith(str(boundary_ir.id) + "::sub::")
            ),
            None,
        )
        if base is None:
            raise ValueError("pattern mesh boundary provenance contains an unknown semantic edge")
        pair = (boundary[index], boundary[(index + 1) % len(boundary)])
        edge_pairs.setdefault(base, []).append(pair)

    by_id = {}
    mesh_vertices = tuple(mesh.vertices)
    for boundary_ir in piece_ir.boundaries:
        edge_id = str(boundary_ir.id)
        pairs = edge_pairs.get(edge_id)
        if not pairs:
            raise ValueError(
                "pattern mesh has no boundary provenance for semantic edge %s"
                % edge_id
            )
        vertex_indices = {vertex for pair in pairs for vertex in pair}
        samples = tuple(tuple(point[:2]) for point in boundary_ir.samples)
        ordered = tuple(
            sorted(
                vertex_indices,
                key=lambda vertex: _polyline_parameter(mesh_vertices[vertex], samples),
            )
        )
        if len(ordered) < 2:
            raise ValueError(
                "pattern mesh semantic edge %s has too few boundary vertices"
                % edge_id
            )
        actual_pairs = {frozenset(pair) for pair in pairs}
        ordered_pairs = {
            frozenset((left, right))
            for left, right in zip(ordered, ordered[1:])
        }
        if ordered_pairs != actual_pairs:
            raise ValueError(
                "pattern mesh semantic edge %s boundary chain is disconnected"
                % edge_id
            )
        by_id[edge_id] = ordered

    return vertices, mesh.triangles, tuple(
        tuple(by_id[str(boundary_ir.id)])
        for boundary_ir in piece_ir.boundaries
    )


def _polyline_parameter(point, polyline):
    if len(polyline) < 2:
        return 0.0
    total = 0.0
    spans = []
    for start, end in zip(polyline, polyline[1:]):
        dx = float(end[0]) - float(start[0])
        dy = float(end[1]) - float(start[1])
        length = (dx * dx + dy * dy) ** 0.5
        spans.append((total, start, end, length))
        total += length
    if total <= 1e-12:
        return 0.0
    best = None
    for offset, start, end, length in spans:
        if length <= 1e-12:
            continue
        dx = float(end[0]) - float(start[0])
        dy = float(end[1]) - float(start[1])
        t = (
            (float(point[0]) - float(start[0])) * dx
            + (float(point[1]) - float(start[1])) * dy
        ) / (length * length)
        t = max(0.0, min(1.0, t))
        px = float(start[0]) + t * dx
        py = float(start[1]) + t * dy
        distance = (float(point[0]) - px) ** 2 + (float(point[1]) - py) ** 2
        candidate = (distance, offset + t * length)
        best = candidate if best is None or candidate < best else best
    return best[1] / total if best else 0.0


def _mesh_constraints(positions, triangles):
    from freecad_cloth.simulation.ClothSolver import DistanceConstraint, Particle, distance
    particles = [Particle(*p) for p in positions]
    edges = set()
    constraints = []
    for a, b, c in triangles:
        for u, v in ((a, b), (b, c), (c, a)):
            edge = (min(u, v), max(u, v))
            if edge in edges:
                continue
            edges.add(edge)
            constraints.append(DistanceConstraint(u, v, distance(particles[u], particles[v])))
    return constraints


def _sample_boundary(values, start, end, count, points=None):
    if len(values) < 2:
        raise ValueError("seam edge requires at least two boundary vertices")
    if points is not None:
        from freecad_cloth.sewing.SewingCorrespondence import arc_length_vertex_indices
        return list(arc_length_vertex_indices(values, points, count, start, end))
    count = max(2, min(int(count), len(values)))
    result = []
    last = len(values) - 1
    for i in range(count):
        t = float(start) + (float(end) - float(start)) * i / float(count - 1)
        index = max(0, min(last, int(round(t * last))))
        if result and index == result[-1] and index < last:
            index += 1
        result.append(values[index])
    return result


def _seam_pair_records(pattern, panel_data, seam_samples=8):
    """Return exact solver stitch pairs plus their semantic seam provenance."""
    pairs = []
    records = []
    for seam in pattern.seams:
        data_a = panel_data.get(str(seam.piece_a))
        data_b = panel_data.get(str(seam.piece_b))
        if data_a is None or data_b is None:
            continue
        piece_ir_a = pattern.piece(seam.piece_a)
        piece_ir_b = pattern.piece(seam.piece_b)
        edge_a = _boundary_vertices(piece_ir_a, seam.edge_a, data_a)
        edge_b = _boundary_vertices(piece_ir_b, seam.edge_b, data_b)
        points_a = tuple(data_a["positions"][index] for index in edge_a)
        points_b = tuple(data_b["positions"][index] for index in edge_b)
        va = _sample_boundary(
            edge_a,
            seam.start_a,
            seam.end_a,
            seam_samples,
            points_a,
        )
        vb = _sample_boundary(
            edge_b,
            seam.start_b,
            seam.end_b,
            seam_samples,
            points_b,
        )
        if seam.reversed_b:
            vb.reverse()
        seam_pairs = tuple(zip(va, vb))
        pairs.extend(seam_pairs)
        records.append(
            (
                str(seam.id),
                str(piece_ir_a.name),
                str(piece_ir_b.name),
                seam_pairs,
            )
        )
    return tuple(dict.fromkeys(pairs)), tuple(records)


def _boundary_vertices(piece_ir, edge_id, panel_data):
    for boundary, values in zip(piece_ir.boundaries, panel_data["boundary_edges"]):
        if str(boundary.id) == str(edge_id):
            return tuple(values)
    raise ValueError(
        "PatternIR semantic seam edge %s is missing from piece %s"
        % (edge_id, piece_ir.id)
    )


def _seam_pairs(pattern, panel_data, seam_samples=8):
    """Return the exact particle pairs used as solver stitch constraints."""
    return _seam_pair_records(pattern, panel_data, seam_samples)[0]


def _collision_for_scene(obj):
    """Resolve collision strictly from the persistent DrapeTarget."""
    target = getattr(obj, "DrapeTarget", None)
    if target is not None:
        from freecad_cloth.simulation.DrapeTarget import collision_surface, target_status
        source = getattr(target, "SourceObject", None)
        managed = str(getattr(source, "AvatarMeshProvider", "")) == "makehuman-hm08" or str(getattr(source, "Name", "")) in {"ClothAvatar", "HumanoidAvatar"}
        if managed:
            return collision_surface(source, float(getattr(target, "CollisionDeflection", 1.0)), float(getattr(target, "CollisionThickness", 0.0)))
        status = target_status(target)
        if status["state"] in ("stale", "unbuilt", "unassigned", "invalid", "missing"):
            raise RuntimeError(status["message"])
        return collision_surface(source, float(getattr(target, "CollisionDeflection", 1.0)), float(getattr(target, "CollisionThickness", 0.0)))
    return None


class SimulationProxy:
    Type = "ClothSimulation"

    def __init__(self):
        self.backend = None
        self.panel_indices = {}
        self.panel_triangles = {}
        self.panel_boundary_edges = {}
        self.panel_piece_names = {}
        self.seam_stitch_pairs = {}
        self.source_signature = None
        self.last_steps = 0
        self.collision_surface = None

    def __getstate__(self):
        """Persist only deterministic proxy metadata; runtime solver state is rebuildable."""
        return {"schema": 1}

    def __setstate__(self, state):
        """Restore an empty runtime cache; FreeCAD document properties remain authoritative."""
        self.backend = None
        self.panel_indices = {}
        self.panel_triangles = {}
        self.panel_boundary_edges = {}
        self.panel_piece_names = {}
        self.seam_stitch_pairs = {}
        self.source_signature = None
        self.last_steps = 0
        self.collision_surface = None

    def execute(self, obj):
        pieces = [p for p in getattr(obj, "ClothPieces", ()) if getattr(p, "PatternType", "") == "PatternPiece"]
        signature = _simulation_source_signature(obj, pieces)
        if getattr(self, "backend", None) is None or signature != getattr(self, "source_signature", None) or int(obj.Steps) < int(getattr(self, "last_steps", 0)):
            self._build(obj, signature)
        steps = int(obj.Steps)
        if steps > self.last_steps:
            fallback_sphere = None
            if (
                getattr(self.backend, "name", "") != "tissu"
                and getattr(self, "collision_surface", None) is None
            ):
                fallback_sphere = (
                    float(obj.CollisionX),
                    float(obj.CollisionY),
                    float(obj.CollisionZ),
                    float(obj.CollisionRadius),
                )
            for _ in range(steps - self.last_steps):
                self.backend.step(
                    float(obj.TimeStep), int(obj.Iterations),
                    (float(obj.GravityX), float(obj.GravityY), float(obj.GravityZ)),
                    fallback_sphere,
                    getattr(self, "collision_surface", None),
                )
            self.last_steps = steps
        positions = self.backend.positions()
        for panel in getattr(obj, "DrapePanels", ()):
            _write_mesh(panel, positions, self.panel_triangles.get(panel.Name, ()))
        _update_seam_visuals(obj.Document, self.seam_stitch_pairs, positions)
        obj.SimulatedTime = self.backend.time
        obj.ParticleCount = len(positions)
        obj.FiniteState = self.backend.finite()

    def _build(self, obj, signature=None):
        pieces = [p for p in getattr(obj, "ClothPieces", ()) if getattr(p, "PatternType", "") == "PatternPiece"]
        if pieces:
            self._build_pattern_scene(obj, pieces, signature)
        else:
            self._build_demo(obj)

    def _build_pattern_scene(self, obj, pieces, signature):
        from freecad_cloth.common.PatternSimulationAdapter import resolve_simulation_pattern
        from freecad_cloth.simulation.ClothBackend import default_backend_registry, preferred_backend_name
        from freecad_cloth.simulation.ClothSolver import ClothSystem, Particle

        start_height = float(getattr(obj, "StartHeight", 120.0))
        resolved = resolve_simulation_pattern(obj.Document, tuple(pieces))
        positions = []
        triangles_global = []
        panel_data = {}
        panels = list(getattr(obj, "DrapePanels", ()))
        for index, piece in enumerate(pieces):
            piece_ir = resolved.piece(str(piece.PieceId))
            vertices, triangles, boundary = _piece_mesh(
                piece,
                start_height,
                piece_ir=piece_ir,
            )
            offset = len(positions)
            positions.extend(vertices)
            triangles = tuple(tuple(a + offset for a in tri) for tri in triangles)
            triangles_global.extend(triangles)
            edges = tuple(
                tuple(int(vertex_index) + offset for vertex_index in edge)
                for edge in boundary
            )
            panel_data[str(piece.PieceId)] = {
                "offset": offset,
                "vertex_count": len(vertices),
                "boundary_edges": edges,
                "positions": tuple(positions),
                "triangles": triangles,
                "piece": piece,
            }
            panel = panels[index] if index < len(panels) else self._ensure_panel(obj.Document, index)
            panel.Label = f"Drape: {piece.Label}"
        if len(panels) < len(pieces):
            panels.extend(
                self._ensure_panel(obj.Document, i)
                for i in range(len(panels), len(pieces))
            )
        obj.DrapePanels = panels[:len(pieces)]
        panels = list(obj.DrapePanels)

        particles = [Particle(*p) for p in positions]
        system = ClothSystem(particles, _mesh_constraints(positions, triangles_global))
        seam_pairs, seam_pair_records = _seam_pair_records(
            resolved.pattern,
            panel_data,
            int(getattr(obj, "StitchSamples", 8)),
        )
        system.add_stitches(seam_pairs)
        explicit_pins = _parse_int_list(getattr(obj, "PinSelection", ()), len(particles))
        if explicit_pins:
            pins = explicit_pins
            system.pin(pins)
        elif pieces:
            first = panel_data[str(pieces[0].PieceId)]
            boundary = list(dict.fromkeys(i for edge in first["boundary_edges"] for i in edge))
            pins = tuple(boundary[:2] + boundary[-2:])
            system.pin(pins)
        else:
            pins = ()
        collision_surface = _collision_for_scene(obj)
        registry = default_backend_registry()
        backend_name = preferred_backend_name(registry)
        backend_kwargs = {}
        if backend_name == "tissu":
            backend_kwargs = {
                "triangles": tuple(triangles_global),
                "pins": pins,
                "stitches": seam_pairs,
                "collision_surface": collision_surface,
            }
        self.backend = registry.create(backend_name, system, **backend_kwargs)
        self.panel_indices = {}
        self.panel_triangles = {}
        self.panel_boundary_edges = {}
        self.panel_piece_names = {}
        self.seam_stitch_pairs = {
            seam_id: tuple(stitch_pairs)
            for seam_id, _piece_a_name, _piece_b_name, stitch_pairs in seam_pair_records
        }
        for panel, piece in zip(panels, pieces):
            data = panel_data[str(piece.PieceId)]
            self.panel_indices[panel.Name] = tuple(
                range(data["offset"], data["offset"] + data["vertex_count"])
            )
            self.panel_triangles[panel.Name] = data["triangles"]
            self.panel_boundary_edges[panel.Name] = data["boundary_edges"]
            self.panel_piece_names[panel.Name] = str(getattr(piece, "Name", ""))
        self.source_signature = signature or _simulation_source_signature(obj, pieces)
        self.last_steps = 0
        self.collision_surface = collision_surface
        for panel in panels:
            _write_mesh(panel, self.backend.positions(), self.panel_triangles[panel.Name])

    def _build_demo(self, obj):
        from freecad_cloth.simulation.ClothBackend import default_backend_registry
        from freecad_cloth.simulation.ClothSolver import ClothSystem
        nx, ny = 8, 5
        left = ClothSystem.grid(100.0, 60.0, nx, ny, origin=(-100.0, -30.0, 90.0))
        right = ClothSystem.grid(100.0, 60.0, nx, ny, origin=(0.0, -30.0, 90.0))
        offset = len(left.particles)
        particles = left.particles + right.particles
        constraints = list(left.constraints) + [type(c)(c.a + offset, c.b + offset, c.rest, c.compliance) for c in right.constraints]
        system = ClothSystem(particles, constraints)
        system.add_stitches(_parse_pair_list(getattr(obj, "SeamSelection", ()), len(particles)) or tuple((j * nx + nx - 1, offset + j * nx) for j in range(ny)))
        pins = _parse_int_list(getattr(obj, "PinSelection", ()), len(particles)) or (0, nx - 1, offset, offset + nx - 1)
        system.pin(pins)
        self.backend = default_backend_registry().create("xpbd-cpu", system)
        tris = []
        for j in range(ny - 1):
            for i in range(nx - 1):
                a = j * nx + i
                b = a + 1
                c = (j + 1) * nx + i + 1
                d = (j + 1) * nx + i
                tris.extend(((a, b, c), (a, c, d)))
        self.panel_indices = {"DrapePanelA": tuple(range(offset)), "DrapePanelB": tuple(range(offset, offset * 2))}
        self.panel_triangles = {"DrapePanelA": tuple(tris), "DrapePanelB": tuple((a + offset, b + offset, c + offset) for a, b, c in tris)}
        self.panel_boundary_edges = {}
        self.panel_piece_names = {}
        self.seam_stitch_pairs = {}
        self.source_signature = _simulation_source_signature(obj, ())
        self.last_steps = 0
        self.collision_surface = _collision_for_scene(obj)
        positions = self.backend.positions()
        for panel, key in zip(getattr(obj, "DrapePanels", ()), ("DrapePanelA", "DrapePanelB")):
            _write_grid_mesh(panel, positions, self.panel_indices[key], nx, ny)

    def _ensure_panel(self, doc, index):
        names = ["DrapePanelA", "DrapePanelB"]
        name = names[index] if index < len(names) else f"DrapePanel{index + 1}"
        obj = doc.getObject(name)
        return obj if obj is not None else _mesh_object(doc, name, name)

    def reset(self, obj):
        if self.backend is not None:
            self.backend.reset()
        obj.Steps = 0
        obj.SimulatedTime = 0.0
        obj.ParticleCount = len(self.backend.positions()) if self.backend is not None else 0
        obj.FiniteState = self.backend.finite() if self.backend is not None else True
        self.last_steps = 0


def create_humanoid_avatar(doc, scale=1.0):
    """Create the production MakeHuman mesh avatar used by simulation."""
    from freecad_cloth.avatar.AvatarCommands import create_avatar
    avatar = create_avatar(attach_collision=False, doc=doc, object_name="HumanoidAvatar")
    avatar.Label = "Humanoid Avatar (MakeHuman)"
    return avatar


def create_avatar_collision(doc, source_obj=None, thickness=2.0, deflection=1.0):
    """Create a compatibility collision proxy; DrapeTarget is authoritative."""
    avatar = doc.addObject("App::FeaturePython", "AvatarCollision")
    avatar.Label = "Avatar Collision Proxy (Compatibility)"
    avatar.addProperty("App::PropertyString", "CollisionType", "Simulation").CollisionType = "SphereProxy"
    avatar.addProperty("App::PropertyLink", "SourceObject", "Simulation")
    avatar.addProperty("App::PropertyFloat", "CollisionThickness", "Simulation").CollisionThickness = float(thickness)
    avatar.addProperty("App::PropertyFloat", "CollisionDeflection", "Simulation").CollisionDeflection = float(deflection)
    avatar.addProperty("App::PropertyInteger", "CollisionVertexCount", "Simulation").CollisionVertexCount = 0
    avatar.addProperty("App::PropertyInteger", "CollisionTriangleCount", "Simulation").CollisionTriangleCount = 0
    if source_obj is None:
        source_obj = create_humanoid_avatar(doc)
    from freecad_cloth.avatar.AvatarCollision import surface_from_freecad
    surface = surface_from_freecad(source_obj, deflection, thickness)
    avatar.SourceObject = source_obj
    avatar.CollisionType = "MeshSurface"
    avatar.CollisionVertexCount = len(surface.vertices)
    avatar.CollisionTriangleCount = len(surface.triangles)
    return avatar


def set_avatar_collision_source(scene, source_obj, thickness=2.0, deflection=1.0):
    """Set an avatar collision proxy while keeping the document DrapeTarget authoritative."""
    from freecad_cloth.simulation.DrapeTarget import create_drape_target, assign_drape_target

    doc = scene.Document
    properties = set(getattr(scene, "PropertiesList", ()) or ())
    target = getattr(scene, "DrapeTarget", None) if "DrapeTarget" in properties else None
    if target is None:
        target = doc.getObject("DrapeTarget")

    target_type = "Mannequin" if str(getattr(source_obj, "AvatarType", "")) == "ClothAvatar" else "FreeCAD Geometry"
    if target is None:
        target = create_drape_target(doc, source_obj, target_type, deflection, thickness)
    else:
        target.CollisionThickness = float(thickness)
        target.CollisionDeflection = float(deflection)
        assign_drape_target(target, source_obj, target_type)

    if "DrapeTarget" in properties:
        scene.DrapeTarget = target

    avatar = getattr(scene, "AvatarProxy", None)
    if avatar is None:
        avatar = doc.getObject("AvatarCollision")
    if avatar is None:
        avatar = create_avatar_collision(doc, source_obj, thickness, deflection)
    else:
        from freecad_cloth.avatar.AvatarCollision import surface_from_freecad
        surface = surface_from_freecad(source_obj, deflection, thickness)
        avatar.SourceObject = source_obj
        avatar.CollisionType = "MeshSurface"
        avatar.CollisionThickness = float(thickness)
        avatar.CollisionDeflection = float(deflection)
        avatar.CollisionVertexCount = len(surface.vertices)
        avatar.CollisionTriangleCount = len(surface.triangles)

    scene.AvatarProxy = avatar
    doc.recompute()
    return avatar


def create_simulation_scene(doc):
    from freecad_cloth.simulation.DrapeTarget import create_drape_target
    scene = doc.addObject("App::FeaturePython", "ClothSimulation")
    scene.Label = "Cloth Simulation"
    scene.addProperty("App::PropertyInteger", "Iterations", "Solver").Iterations = 8
    scene.addProperty("App::PropertyFloat", "TimeStep", "Solver").TimeStep = 1 / 60
    scene.addProperty("App::PropertyInteger", "Steps", "Solver").Steps = 0
    scene.addProperty("App::PropertyFloat", "StartHeight", "Solver").StartHeight = 120.0
    scene.addProperty("App::PropertyInteger", "StitchSamples", "Sewing").StitchSamples = 8
    scene.addProperty("App::PropertyFloat", "GravityX", "Solver").GravityX = 0.0
    scene.addProperty("App::PropertyFloat", "GravityY", "Solver").GravityY = 0.0
    scene.addProperty("App::PropertyFloat", "GravityZ", "Solver").GravityZ = -9810.0
    scene.addProperty("App::PropertyLinkListGlobal", "ClothPieces", "Selection")
    scene.addProperty("App::PropertyLinkListGlobal", "DrapePanels", "Output")
    scene.addProperty("App::PropertyLinkGlobal", "DrapeTarget", "Selection")
    scene.addProperty("App::PropertyLinkGlobal", "AvatarProxy", "Compatibility")
    scene.addProperty("App::PropertyStringList", "PinSelection", "Selection").PinSelection = []
    scene.addProperty("App::PropertyStringList", "SeamSelection", "Selection").SeamSelection = []
    scene.addProperty("App::PropertyFloat", "SimulatedTime", "State").SimulatedTime = 0.0
    scene.addProperty("App::PropertyInteger", "ParticleCount", "State").ParticleCount = 0
    scene.addProperty("App::PropertyBool", "FiniteState", "State").FiniteState = True
    scene.addProperty("App::PropertyFloat", "CollisionX", "Collision").CollisionX = 0.0
    scene.addProperty("App::PropertyFloat", "CollisionY", "Collision").CollisionY = 0.0
    scene.addProperty("App::PropertyFloat", "CollisionZ", "Collision").CollisionZ = 0.0
    scene.addProperty("App::PropertyFloat", "CollisionRadius", "Collision").CollisionRadius = 38.0
    proxy = SimulationProxy()
    scene.Proxy = proxy
    from freecad_cloth.common.GarmentDocument import link_garment_object
    link_garment_object(scene, "Simulation", doc)
    panel_a = _mesh_object(doc, "DrapePanelA", "Drape Panel A")
    panel_b = _mesh_object(doc, "DrapePanelB", "Drape Panel B")
    link_garment_object(panel_a, "SimulationOutput", doc)
    link_garment_object(panel_b, "SimulationOutput", doc)
    scene.DrapePanels = [panel_a, panel_b]
    avatar = create_avatar_collision(doc)
    link_garment_object(avatar, "AvatarCollision", doc)
    scene.AvatarProxy = avatar
    target = create_drape_target(doc, avatar.SourceObject, "Mannequin", avatar.CollisionDeflection, avatar.CollisionThickness)
    scene.DrapeTarget = target
    proxy._build(scene, ())
    return scene


def step_scene(scene, steps=1):
    scene.Steps = int(scene.Steps) + int(steps)
    scene.Document.recompute()
    return scene


def reset_scene(scene):
    proxy = getattr(scene, "Proxy", None)
    if proxy is not None and hasattr(proxy, "reset"):
        proxy.reset(scene)
    scene.Document.recompute()
    return scene


def create_drape_scene(doc):
    scene = create_simulation_scene(doc)
    step_scene(scene, 30)
    return scene
