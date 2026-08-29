"""FreeCAD-facing deterministic cloth simulation scene objects."""
import ast


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
            b = indices[j * nx + i + 1]
            c = indices[(j + 1) * nx + i + 1]
            d = indices[(j + 1) * nx + i]
            triangles.extend(((a, b, c), (a, c, d)))
    _write_mesh(obj, positions, triangles)


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


def _outline_points(piece):
    for attribute in ("SewingOutline", "DraftingBoundary"):
        raw = getattr(piece, attribute, "")
        if not raw:
            continue
        try:
            values = ast.literal_eval(str(raw))
            points = [(float(p[0]), float(p[1])) for p in values]
            if len(points) >= 3:
                return points
        except (ValueError, SyntaxError, TypeError, IndexError):
            pass
    width, height = float(piece.Width), float(piece.Height)
    return [(0.0, 0.0), (width, 0.0), (width, height), (0.0, height)]


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
    """Return deterministic inputs that require rebuilding the cloth scene.

    Pattern identity alone is insufficient: changing an outline, placement,
    seam topology, stitch range, or collision source must invalidate the
    solver scene so the FreeCAD document remains the source of truth.
    """
    piece_ids = {str(getattr(piece, "PieceId", "")) for piece in pieces}
    piece_signature = tuple(
        (
            str(getattr(piece, "Name", "")),
            str(getattr(piece, "PieceId", "")),
            str(getattr(piece, "SewingOutline", "")),
            str(getattr(piece, "DraftingBoundary", "")),
            _placement_signature(piece),
        )
        for piece in pieces
    )
    seam_signature = tuple(sorted(
        (
            str(getattr(seam, "SeamId", "")),
            str(getattr(seam, "PieceA", "")),
            int(getattr(seam, "EdgeA", 0)),
            float(getattr(seam, "StartA", 0.0)),
            float(getattr(seam, "EndA", 1.0)),
            str(getattr(seam, "PieceB", "")),
            int(getattr(seam, "EdgeB", 0)),
            float(getattr(seam, "StartB", 0.0)),
            float(getattr(seam, "EndB", 1.0)),
            bool(getattr(seam, "ReversedB", False)),
        )
        for seam in getattr(getattr(obj, "Document", None), "Objects", ())
        if getattr(seam, "SeamId", "")
        and (str(getattr(seam, "PieceA", "")) in piece_ids or str(getattr(seam, "PieceB", "")) in piece_ids)
    ))
    avatar = getattr(obj, "AvatarProxy", None)
    source = getattr(avatar, "SourceObject", None) if avatar is not None else None
    avatar_signature = (
        str(getattr(avatar, "Name", "")),
        str(getattr(source, "Name", "")),
        float(getattr(avatar, "CollisionDeflection", 0.0)) if avatar is not None else 0.0,
        float(getattr(avatar, "CollisionThickness", 0.0)) if avatar is not None else 0.0,
    )
    return piece_signature, seam_signature, avatar_signature, int(getattr(obj, "StitchSamples", 8))


def _piece_mesh(piece, start_height):
    from PatternGeometry import LineSegment, ParametricPattern
    from PatternMesh import triangulate
    import FreeCAD as App
    points = _outline_points(piece)
    segments = [LineSegment(f"{piece.PieceId}:edge:{i}", points[i], points[(i + 1) % len(points)]) for i in range(len(points))]
    mesh = triangulate(ParametricPattern(segments))
    placement = getattr(piece, "Placement", None)
    vertices = []
    for x, y in mesh.vertices:
        point = App.Vector(x, y, float(start_height))
        if placement is not None:
            point = placement.multVec(point)
        vertices.append((float(point.x), float(point.y), float(point.z)))
    return vertices, mesh.triangles, tuple(mesh.boundary_vertex_indices)


def _mesh_constraints(positions, triangles):
    from ClothSolver import DistanceConstraint, Particle, distance
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


def _sample_boundary(values, start, end, count):
    if len(values) < 2:
        raise ValueError("seam edge requires at least two boundary vertices")
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


def _seam_pairs(doc, panel_data, seam_samples=8):
    """Return global stitch pairs from persisted FreeCAD seam objects."""
    pieces = {str(piece.PieceId): piece for piece in panel_data}
    pairs = []
    for seam in doc.Objects:
        if not getattr(seam, "SeamId", ""):
            continue
        piece_a = pieces.get(str(getattr(seam, "PieceA", "")))
        piece_b = pieces.get(str(getattr(seam, "PieceB", "")))
        if piece_a is None or piece_b is None:
            continue
        data_a, data_b = panel_data[piece_a], panel_data[piece_b]
        ea, eb = int(seam.EdgeA), int(seam.EdgeB)
        if ea >= len(data_a["boundary_edges"]) or eb >= len(data_b["boundary_edges"]):
            continue
        va = _sample_boundary(data_a["boundary_edges"][ea], seam.StartA, seam.EndA, seam_samples)
        vb = _sample_boundary(data_b["boundary_edges"][eb], seam.StartB, seam.EndB, seam_samples)
        if bool(getattr(seam, "ReversedB", False)):
            vb.reverse()
        pairs.extend(zip(va, vb))
    return tuple(dict.fromkeys(pairs))


class SimulationProxy:
    Type = "ClothSimulation"

    def __init__(self):
        self.backend = None
        self.panel_indices = {}
        self.panel_triangles = {}
        self.source_signature = None
        self.last_steps = 0
        self.collision_surface = None

    def execute(self, obj):
        pieces = [p for p in getattr(obj, "ClothPieces", ()) if getattr(p, "PatternType", "") == "PatternPiece"]
        signature = _simulation_source_signature(obj, pieces)
        if self.backend is None or signature != self.source_signature or int(obj.Steps) < self.last_steps:
            self._build(obj, signature)
        steps = int(obj.Steps)
        if steps > self.last_steps:
            for _ in range(steps - self.last_steps):
                self.backend.step(
                    float(obj.TimeStep), int(obj.Iterations),
                    (float(obj.GravityX), float(obj.GravityY), float(obj.GravityZ)),
                    (float(obj.CollisionX), float(obj.CollisionY), float(obj.CollisionZ), float(obj.CollisionRadius)),
                    self.collision_surface,
                )
            self.last_steps = steps
        positions = self.backend.positions()
        for panel in getattr(obj, "DrapePanels", ()):
            _write_mesh(panel, positions, self.panel_triangles.get(panel.Name, ()))
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
        from ClothBackend import default_backend_registry
        from ClothSolver import ClothSystem, Particle
        from AvatarCollision import surface_from_freecad
        start_height = float(getattr(obj, "StartHeight", 120.0))
        positions = []
        triangles_global = []
        panel_data = {}
        panels = list(getattr(obj, "DrapePanels", ()))
        for index, piece in enumerate(pieces):
            vertices, triangles, boundary = _piece_mesh(piece, start_height)
            offset = len(positions)
            positions.extend(vertices)
            triangles = tuple(tuple(a + offset for a in tri) for tri in triangles)
            triangles_global.extend(triangles)
            edges = tuple((boundary[i] + offset, boundary[(i + 1) % len(boundary)] + offset) for i in range(len(boundary)))
            panel_data[piece] = {"offset": offset, "vertex_count": len(vertices), "boundary_edges": edges, "triangles": triangles}
            panel = panels[index] if index < len(panels) else self._ensure_panel(obj.Document, index)
            panel.Label = f"Drape: {piece.Label}"
        if len(panels) < len(pieces):
            panels.extend(self._ensure_panel(obj.Document, i) for i in range(len(panels), len(pieces)))
        obj.DrapePanels = panels[:len(pieces)]
        particles = [Particle(*p) for p in positions]
        system = ClothSystem(particles, _mesh_constraints(positions, triangles_global))
        system.add_stitches(_seam_pairs(obj.Document, panel_data, int(getattr(obj, "StitchSamples", 8))))
        explicit_pins = _parse_int_list(getattr(obj, "PinSelection", ()), len(particles))
        if explicit_pins:
            system.pin(explicit_pins)
        elif pieces:
            first = panel_data[pieces[0]]
            boundary = list(dict.fromkeys(i for edge in first["boundary_edges"] for i in edge))
            system.pin(boundary[:2] + boundary[-2:])
        self.backend = default_backend_registry().create("xpbd-cpu", system)
        self.panel_indices = {}
        self.panel_triangles = {}
        for panel, piece in zip(panels, pieces):
            data = panel_data[piece]
            self.panel_indices[panel.Name] = tuple(range(data["offset"], data["offset"] + data["vertex_count"]))
            self.panel_triangles[panel.Name] = data["triangles"]
        self.source_signature = signature or _simulation_source_signature(obj, pieces)
        self.last_steps = 0
        self.collision_surface = None
        avatar = getattr(obj, "AvatarProxy", None)
        source = getattr(avatar, "SourceObject", None) if avatar is not None else None
        if source is not None:
            self.collision_surface = surface_from_freecad(source, float(getattr(avatar, "CollisionDeflection", 1.0)), float(getattr(avatar, "CollisionThickness", 0.0)))
        for panel in panels:
            _write_mesh(panel, self.backend.positions(), self.panel_triangles[panel.Name])

    def _build_demo(self, obj):
        from ClothBackend import default_backend_registry
        from ClothSolver import ClothSystem
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
        self.source_signature = ()
        self.last_steps = 0
        self.collision_surface = None
        avatar = getattr(obj, "AvatarProxy", None)
        source = getattr(avatar, "SourceObject", None) if avatar is not None else None
        if source is not None:
            from AvatarCollision import surface_from_freecad
            self.collision_surface = surface_from_freecad(source, float(getattr(avatar, "CollisionDeflection", 1.0)), float(getattr(avatar, "CollisionThickness", 0.0)))
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
    """Create a deterministic, editable mannequin collision proxy for draping tests."""
    import Part, FreeCAD
    s = float(scale)
    if s <= 0:
        raise ValueError("avatar scale must be positive")
    parts = [
        Part.makeCylinder(28 * s, 70 * s, FreeCAD.Vector(0, 0, -30 * s)),
        Part.makeSphere(22 * s, FreeCAD.Vector(0, 0, 62 * s)),
        Part.makeCylinder(12 * s, 60 * s, FreeCAD.Vector(-40 * s, 0, 20 * s)),
        Part.makeCylinder(12 * s, 60 * s, FreeCAD.Vector(28 * s, 0, 20 * s)),
        Part.makeCylinder(14 * s, 75 * s, FreeCAD.Vector(-15 * s, 0, -105 * s)),
        Part.makeCylinder(14 * s, 75 * s, FreeCAD.Vector(1 * s, 0, -105 * s)),
    ]
    avatar = doc.addObject("Part::Feature", "HumanoidAvatar")
    avatar.Label = "Humanoid Avatar"
    avatar.Shape = Part.makeCompound(parts)
    avatar.addProperty("App::PropertyString", "AvatarType", "Avatar").AvatarType = "ParametricHumanoid"
    avatar.addProperty("App::PropertyFloat", "Scale", "Avatar").Scale = s
    return avatar


def create_avatar_collision(doc, source_obj=None, thickness=2.0, deflection=1.0):
    """Create a solver-neutral collision proxy linked to an imported body mesh."""
    avatar = doc.addObject("App::FeaturePython", "AvatarCollision")
    avatar.Label = "Avatar Collision Proxy"
    avatar.addProperty("App::PropertyString", "CollisionType", "Simulation").CollisionType = "SphereProxy"
    avatar.addProperty("App::PropertyLink", "SourceObject", "Simulation")
    avatar.addProperty("App::PropertyFloat", "CollisionThickness", "Simulation").CollisionThickness = float(thickness)
    avatar.addProperty("App::PropertyFloat", "CollisionDeflection", "Simulation").CollisionDeflection = float(deflection)
    avatar.addProperty("App::PropertyInteger", "CollisionVertexCount", "Simulation").CollisionVertexCount = 0
    avatar.addProperty("App::PropertyInteger", "CollisionTriangleCount", "Simulation").CollisionTriangleCount = 0
    if source_obj is not None:
        from AvatarCollision import surface_from_freecad
        surface = surface_from_freecad(source_obj, deflection, thickness)
        avatar.SourceObject = source_obj
        avatar.CollisionType = "MeshSurface"
        avatar.CollisionVertexCount = len(surface.vertices)
        avatar.CollisionTriangleCount = len(surface.triangles)
    else:
        shape = create_humanoid_avatar(doc)
        avatar.SourceObject = shape
        avatar.CollisionType = "MeshSurface"
        from AvatarCollision import surface_from_freecad
        surface = surface_from_freecad(shape, deflection, thickness)
        avatar.CollisionVertexCount = len(surface.vertices)
        avatar.CollisionTriangleCount = len(surface.triangles)
    return avatar


def set_avatar_collision_source(scene, source_obj, thickness=2.0, deflection=1.0):
    """Replace the scene's fallback avatar with a real FreeCAD body/mesh source."""
    avatar = scene.Document.getObject("AvatarCollision")
    if avatar is None or getattr(avatar, "TypeId", "") != "App::FeaturePython":
        avatar = create_avatar_collision(scene.Document, source_obj, thickness, deflection)
    else:
        from AvatarCollision import surface_from_freecad
        surface = surface_from_freecad(source_obj, deflection, thickness)
        avatar.SourceObject = source_obj
        avatar.CollisionType = "MeshSurface"
        avatar.CollisionThickness = float(thickness)
        avatar.CollisionDeflection = float(deflection)
        avatar.CollisionVertexCount = len(surface.vertices)
        avatar.CollisionTriangleCount = len(surface.triangles)
    scene.AvatarProxy = avatar
    scene.Document.recompute()
    return avatar


def create_simulation_scene(doc):
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
    scene.addProperty("App::PropertyLinkList", "ClothPieces", "Selection")
    scene.addProperty("App::PropertyLinkList", "DrapePanels", "Output")
    scene.addProperty("App::PropertyLink", "AvatarProxy", "Selection")
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
    panel_a = _mesh_object(doc, "DrapePanelA", "Drape Panel A")
    panel_b = _mesh_object(doc, "DrapePanelB", "Drape Panel B")
    scene.DrapePanels = [panel_a, panel_b]
    avatar = create_avatar_collision(doc)
    scene.AvatarProxy = avatar
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
