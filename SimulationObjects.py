"""FreeCAD-facing deterministic cloth simulation scene objects."""
def _mesh_object(doc,name,label):
    import Mesh
    obj=doc.addObject("Mesh::Feature",name);obj.Label=label;obj.addProperty("App::PropertyString","ClothMeshType","Simulation").ClothMeshType="DrapedCloth";return obj

def _write_grid_mesh(obj,positions,indices,nx,ny):
    import FreeCAD as App,Mesh
    native=Mesh.Mesh()
    for j in range(ny-1):
        for i in range(nx-1):
            a=positions[indices[j*nx+i]];b=positions[indices[j*nx+i+1]];c=positions[indices[(j+1)*nx+i+1]];d=positions[indices[(j+1)*nx+i]];native.addFacet(App.Vector(*a),App.Vector(*b),App.Vector(*c));native.addFacet(App.Vector(*a),App.Vector(*c),App.Vector(*d))
    obj.Mesh=native

def _parse_pair_list(values,particle_count=None):
    pairs=[]
    for value in values or ():
        parts=[p.strip() for p in str(value).replace(",","-").split("-") if p.strip()]
        if len(parts)==2:
            try:pair=(int(parts[0]),int(parts[1]))
            except ValueError:continue
            if particle_count is None or all(0<=i<particle_count for i in pair):pairs.append(pair)
    return tuple(dict.fromkeys(pairs))

def _parse_int_list(values,particle_count=None):
    result=[]
    for value in values or ():
        for part in str(value).replace(";",",").split(","):
            try:i=int(part.strip())
            except ValueError:continue
            if particle_count is None or 0<=i<particle_count:result.append(i)
    return tuple(dict.fromkeys(result))

class SimulationProxy:
    Type="ClothSimulation"
    def __init__(self):self.backend=None;self.left_indices=None;self.right_indices=None;self.last_steps=0;self.collision_surface=None
    def execute(self,obj):
        if self.backend is None or int(obj.Steps)<self.last_steps:self._build(obj)
        steps=int(obj.Steps)
        if steps>self.last_steps:
            for _ in range(steps-self.last_steps):
                self.backend.step(float(obj.TimeStep),int(obj.Iterations),(float(obj.GravityX),float(obj.GravityY),float(obj.GravityZ)),(float(obj.CollisionX),float(obj.CollisionY),float(obj.CollisionZ),float(obj.CollisionRadius)),self.collision_surface)
            self.last_steps=steps
        positions=self.backend.positions()
        a,b=obj.Document.getObject("DrapePanelA"),obj.Document.getObject("DrapePanelB")
        if a:_write_grid_mesh(a,positions,self.left_indices,8,5)
        if b:_write_grid_mesh(b,positions,self.right_indices,8,5)
        obj.SimulatedTime=self.backend.time;obj.ParticleCount=len(positions);obj.FiniteState=self.backend.finite()
    def _build(self,obj):
        from ClothSolver import ClothSystem
        from ClothBackend import default_backend_registry
        from AvatarCollision import surface_from_freecad
        nx,ny=8,5;left=ClothSystem.grid(100.,60.,nx,ny,origin=(-100.,-30.,90.));right=ClothSystem.grid(100.,60.,nx,ny,origin=(0.,-30.,90.));offset=len(left.particles);particles=left.particles+right.particles;constraints=list(left.constraints)+[type(c)(c.a+offset,c.b+offset,c.rest,c.compliance) for c in right.constraints];system=ClothSystem(particles,constraints);self.backend=default_backend_registry().create("xpbd-cpu",system);self.left_indices=tuple(range(offset));self.right_indices=tuple(range(offset,offset*2));default_seams=[(j*nx+nx-1,offset+j*nx) for j in range(ny)];self.backend.set_stitches(_parse_pair_list(obj.SeamSelection,len(particles)) or tuple(default_seams));default_pins=(0,nx-1,offset,offset+nx-1);self.backend.pin(_parse_int_list(obj.PinSelection,len(particles)) or default_pins)
        self.collision_surface=None
        avatar=getattr(obj,"AvatarProxy",None)
        source=getattr(avatar,"SourceObject",None) if avatar is not None else None
        if source is not None:
            self.collision_surface=surface_from_freecad(source, float(getattr(avatar,"CollisionDeflection",1.0)), float(getattr(avatar,"CollisionThickness",0.0)))
        self.last_steps=0
    def reset(self,obj):
        self.backend.reset();obj.Steps=0;obj.SimulatedTime=0.;obj.ParticleCount=len(self.backend.positions());obj.FiniteState=self.backend.finite();self.last_steps=0

def create_humanoid_avatar(doc, scale=1.0):
    """Create a deterministic, editable mannequin collision proxy for draping tests."""
    import Part,FreeCAD
    s=float(scale)
    if s<=0: raise ValueError("avatar scale must be positive")
    parts=[]
    parts.append(Part.makeCylinder(28*s,70*s,FreeCAD.Vector(0,0,-30*s)))
    parts.append(Part.makeSphere(22*s,FreeCAD.Vector(0,0,62*s)))
    parts.append(Part.makeCylinder(12*s,60*s,FreeCAD.Vector(-40*s,0,20*s),FreeCAD.Vector(0,0,1)))
    parts.append(Part.makeCylinder(12*s,60*s,FreeCAD.Vector(28*s,0,20*s),FreeCAD.Vector(0,0,1)))
    parts.append(Part.makeCylinder(14*s,75*s,FreeCAD.Vector(-15*s,0,-105*s),FreeCAD.Vector(0,0,1)))
    parts.append(Part.makeCylinder(14*s,75*s,FreeCAD.Vector(1*s,0,-105*s),FreeCAD.Vector(0,0,1)))
    avatar=doc.addObject("Part::Feature","HumanoidAvatar");avatar.Label="Humanoid Avatar";avatar.Shape=Part.makeCompound(parts)
    avatar.addProperty("App::PropertyString","AvatarType","Avatar").AvatarType="ParametricHumanoid"
    avatar.addProperty("App::PropertyFloat","Scale","Avatar").Scale=s
    return avatar

def create_avatar_collision(doc, source_obj=None, thickness=2.0, deflection=1.0):
    """Create a solver-neutral collision proxy linked to an imported body mesh."""
    import Part,FreeCAD
    avatar=doc.addObject("App::FeaturePython","AvatarCollision");avatar.Label="Avatar Collision Proxy";avatar.addProperty("App::PropertyString","CollisionType","Simulation").CollisionType="SphereProxy";avatar.addProperty("App::PropertyLink","SourceObject","Simulation");avatar.addProperty("App::PropertyFloat","CollisionThickness","Simulation").CollisionThickness=float(thickness);avatar.addProperty("App::PropertyFloat","CollisionDeflection","Simulation").CollisionDeflection=float(deflection);avatar.addProperty("App::PropertyInteger","CollisionVertexCount","Simulation").CollisionVertexCount=0;avatar.addProperty("App::PropertyInteger","CollisionTriangleCount","Simulation").CollisionTriangleCount=0
    if source_obj is not None:
        from AvatarCollision import surface_from_freecad
        surface=surface_from_freecad(source_obj,deflection,thickness);avatar.SourceObject=source_obj;avatar.CollisionType="MeshSurface";avatar.CollisionVertexCount=len(surface.vertices);avatar.CollisionTriangleCount=len(surface.triangles)
    else:
        shape=create_humanoid_avatar(doc)
        avatar.SourceObject=shape;avatar.CollisionType="MeshSurface"
        surface=surface_from_freecad(shape,deflection,thickness);avatar.CollisionVertexCount=len(surface.vertices);avatar.CollisionTriangleCount=len(surface.triangles)
    return avatar

def set_avatar_collision_source(scene, source_obj, thickness=2.0, deflection=1.0):
    """Replace the scene's fallback avatar with a real FreeCAD body/mesh source."""
    avatar=scene.Document.getObject("AvatarCollision")
    if avatar is None or getattr(avatar,"TypeId","") != "App::FeaturePython":
        avatar=create_avatar_collision(scene.Document,source_obj,thickness,deflection)
    else:
        from AvatarCollision import surface_from_freecad
        surface=surface_from_freecad(source_obj,deflection,thickness);avatar.SourceObject=source_obj;avatar.CollisionType="MeshSurface";avatar.CollisionThickness=float(thickness);avatar.CollisionDeflection=float(deflection);avatar.CollisionVertexCount=len(surface.vertices);avatar.CollisionTriangleCount=len(surface.triangles)
    scene.AvatarProxy=avatar
    scene.Document.recompute()
    return avatar

def create_simulation_scene(doc):
    import Part,FreeCAD
    scene=doc.addObject("App::FeaturePython","ClothSimulation");scene.Label="Cloth Simulation";scene.addProperty("App::PropertyInteger","Iterations","Solver").Iterations=8;scene.addProperty("App::PropertyFloat","TimeStep","Solver").TimeStep=1/60;scene.addProperty("App::PropertyFloat","Steps","Solver").Steps=0;scene.addProperty("App::PropertyFloat","GravityX","Solver").GravityX=0.;scene.addProperty("App::PropertyFloat","GravityY","Solver").GravityY=0.;scene.addProperty("App::PropertyFloat","GravityZ","Solver").GravityZ=-9810.;scene.addProperty("App::PropertyLinkList","ClothPieces","Selection");scene.addProperty("App::PropertyLink","AvatarProxy","Selection");scene.addProperty("App::PropertyStringList","PinSelection","Selection").PinSelection=["0","7","40","47"];scene.addProperty("App::PropertyStringList","SeamSelection","Selection").SeamSelection=["7-8","15-16","23-24","31-32","39-40"];scene.addProperty("App::PropertyFloat","SimulatedTime","State").SimulatedTime=0.;scene.addProperty("App::PropertyInteger","ParticleCount","State").ParticleCount=0;scene.addProperty("App::PropertyBool","FiniteState","State").FiniteState=True;scene.addProperty("App::PropertyFloat","CollisionX","Collision").CollisionX=0.;scene.addProperty("App::PropertyFloat","CollisionY","Collision").CollisionY=0.;scene.addProperty("App::PropertyFloat","CollisionZ","Collision").CollisionZ=0.;scene.addProperty("App::PropertyFloat","CollisionRadius","Collision").CollisionRadius=38.
    proxy=SimulationProxy();scene.Proxy=proxy;a=_mesh_object(doc,"DrapePanelA","Drape Panel A");b=_mesh_object(doc,"DrapePanelB","Drape Panel B");scene.ClothPieces=[a,b];avatar=create_avatar_collision(doc);scene.AvatarProxy=avatar;proxy._build(scene);_write_grid_mesh(a,proxy.backend.positions(),proxy.left_indices,8,5);_write_grid_mesh(b,proxy.backend.positions(),proxy.right_indices,8,5);return scene

def step_scene(scene,steps=1):scene.Steps=int(scene.Steps)+int(steps);scene.Document.recompute();return scene

def reset_scene(scene):
    proxy=getattr(scene,"Proxy",None)
    if proxy is not None and hasattr(proxy,"reset"):proxy.reset(scene)
    scene.Document.recompute();return scene

def create_drape_scene(doc):scene=create_simulation_scene(doc);step_scene(scene,30);return scene
