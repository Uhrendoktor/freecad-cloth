"""FreeCAD-facing deterministic cloth simulation scene objects."""


def _mesh_object(doc, name, label):
    import Mesh
    obj = doc.addObject("Mesh::Feature", name)
    obj.Label = label
    obj.addProperty("App::PropertyString", "ClothMeshType", "Simulation").ClothMeshType = "DrapedCloth"
    return obj


def _write_grid_mesh(obj, system, indices, nx, ny):
    import FreeCAD as App
    import Mesh
    native = Mesh.Mesh()
    for j in range(ny - 1):
        for i in range(nx - 1):
            a = indices[j*nx+i]
            b = indices[j*nx+i+1]
            c = indices[(j+1)*nx+i+1]
            d = indices[(j+1)*nx+i]
            native.addFacet(App.Vector(*system.particles[a].position()), App.Vector(*system.particles[b].position()), App.Vector(*system.particles[c].position()))
            native.addFacet(App.Vector(*system.particles[a].position()), App.Vector(*system.particles[c].position()), App.Vector(*system.particles[d].position()))
    obj.Mesh = native


def _parse_pair_list(values):
    pairs = []
    for value in values or ():
        text = str(value).replace(",", "-")
        parts = [p.strip() for p in text.split("-") if p.strip()]
        if len(parts) == 2:
            try:
                pairs.append((int(parts[0]), int(parts[1])))
            except ValueError:
                pass
    return tuple(pairs)


def _parse_int_list(values):
    result = []
    for value in values or ():
        for part in str(value).replace(";", ",").split(","):
            try:
                result.append(int(part.strip()))
            except ValueError:
                pass
    return tuple(dict.fromkeys(result))


class SimulationProxy:
    Type = "ClothSimulation"

    def __init__(self):
        self.system = None
        self.left_indices = None
        self.right_indices = None
        self.last_steps = 0

    def execute(self, obj):
        if self.system is None or int(obj.Steps) < self.last_steps:
            self._build(obj)
        steps = int(obj.Steps)
        if steps > self.last_steps:
            for _ in range(steps - self.last_steps):
                self.system.step(float(obj.TimeStep), int(obj.Iterations), (float(obj.GravityX), float(obj.GravityY), float(obj.GravityZ)), (float(obj.CollisionX), float(obj.CollisionY), float(obj.CollisionZ), float(obj.CollisionRadius)))
            self.last_steps = steps
        doc = obj.Document
        a, b = doc.getObject("DrapePanelA"), doc.getObject("DrapePanelB")
        if a is not None:
            _write_grid_mesh(a, self.system, self.left_indices, 8, 5)
        if b is not None:
            _write_grid_mesh(b, self.system, self.right_indices, 8, 5)
        obj.SimulatedTime = self.system.time
        obj.ParticleCount = len(self.system.particles)
        obj.FiniteState = self.system.finite()

    def _build(self, obj):
        from ClothSolver import ClothSystem
        nx, ny = 8, 5
        left = ClothSystem.grid(100.0, 60.0, nx, ny, origin=(-100.0, -30.0, 90.0))
        right = ClothSystem.grid(100.0, 60.0, nx, ny, origin=(0.0, -30.0, 90.0))
        offset = len(left.particles)
        particles = left.particles + right.particles
        constraints = list(left.constraints) + [type(c)(c.a+offset, c.b+offset, c.rest, c.compliance) for c in right.constraints]
        self.system = ClothSystem(particles, constraints)
        self.left_indices = tuple(range(offset))
        self.right_indices = tuple(range(offset, offset*2))
        default_seams = [(j*nx + (nx-1), offset + j*nx) for j in range(ny)]
        seam_pairs = _parse_pair_list(obj.SeamSelection) or tuple(default_seams)
        self.system.add_stitches(seam_pairs)
        pins = _parse_int_list(obj.PinSelection) or (0, nx-1, offset, offset+nx-1)
        self.system.pin(pins)
        self.last_steps = 0

    def reset(self, obj):
        self._build(obj)
        obj.Steps = 0
        obj.SimulatedTime = 0.0
        obj.ParticleCount = len(self.system.particles)
        obj.FiniteState = self.system.finite()


def create_simulation_scene(doc):
    import Part
    scene = doc.addObject("App::FeaturePython", "ClothSimulation")
    scene.Label = "Cloth Simulation"
    scene.addProperty("App::PropertyInteger", "Iterations", "Solver").Iterations = 8
    scene.addProperty("App::PropertyFloat", "TimeStep", "Solver").TimeStep = 1.0 / 60.0
    scene.addProperty("App::PropertyFloat", "GravityX", "Solver").GravityX = 0.0
    scene.addProperty("App::PropertyFloat", "GravityY", "Solver").GravityY = 0.0
    scene.addProperty("App::PropertyFloat", "GravityZ", "Solver").GravityZ = -9810.0
    scene.addProperty("App::PropertyInteger", "Steps", "Solver").Steps = 0
    scene.addProperty("App::PropertyLinkList", "ClothPieces", "Selection")
    scene.addProperty("App::PropertyLink", "AvatarProxy", "Selection")
    scene.addProperty("App::PropertyStringList", "PinSelection", "Selection").PinSelection = ["0", "7", "32", "39"]
    scene.addProperty("App::PropertyStringList", "SeamSelection", "Selection").SeamSelection = ["7-8", "15-16", "23-24", "31-32", "39-40"]
    scene.addProperty("App::PropertyFloat", "SimulatedTime", "State").SimulatedTime = 0.0
    scene.addProperty("App::PropertyInteger", "ParticleCount", "State").ParticleCount = 0
    scene.addProperty("App::PropertyBool", "FiniteState", "State").FiniteState = True
    scene.addProperty("App::PropertyFloat", "CollisionX", "Collision").CollisionX = 0.0
    scene.addProperty("App::PropertyFloat", "CollisionY", "Collision").CollisionY = 0.0
    scene.addProperty("App::PropertyFloat", "CollisionZ", "Collision").CollisionZ = 0.0
    scene.addProperty("App::PropertyFloat", "CollisionRadius", "Collision").CollisionRadius = 38.0
    proxy = SimulationProxy()
    scene.Proxy = proxy
    a = _mesh_object(doc, "DrapePanelA", "Drape Panel A")
    b = _mesh_object(doc, "DrapePanelB", "Drape Panel B")
    scene.ClothPieces = [a, b]
    proxy._build(scene)
    _write_grid_mesh(a, proxy.system, proxy.left_indices, 8, 5)
    _write_grid_mesh(b, proxy.system, proxy.right_indices, 8, 5)
    avatar = doc.addObject("Part::Feature", "AvatarCollision")
    avatar.Label = "Avatar Collision Proxy"
    avatar.Shape = Part.makeSphere(38.0, __import__('FreeCAD').Vector(0, 0, 0))
    avatar.addProperty("App::PropertyString", "CollisionType", "Simulation").CollisionType = "SphereProxy"
    scene.AvatarProxy = avatar
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
