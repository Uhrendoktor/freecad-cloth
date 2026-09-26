import FreeCAD as App
import Part
import MeshPart
import time

doc = App.newDocument("MeshParityProbe")
shape = Part.makeBox(10.0, 12.0, 14.0)
mesh_obj = doc.addObject("Mesh::Feature", "Probe")
mesh_obj.Mesh = MeshPart.meshFromShape(
    Shape=shape,
    LinearDeflection=0.5,
    AngularDeflection=0.5,
)
doc.recompute()

for name, p in (
    ("inside", App.Vector(5, 6, 7)),
    ("outside", App.Vector(15, 6, 7)),
    ("boundary", App.Vector(0, 6, 7)),
):
    hits = mesh_obj.Mesh.foraminate(
        ((p.x, p.y, p.z), (1.0, 0.0, 0.0)),
        3.141592653589793,
    )
    print(name, type(hits).__name__, len(hits), hits[:3])

print("solid", bool(mesh_obj.Mesh.isSolid()))
start = time.perf_counter()
count = 0
for _ in range(1000):
    hits = mesh_obj.Mesh.foraminate(
        ((5.0, 6.0, 7.0), (1.0, 0.0, 0.0)),
        3.141592653589793,
    )
    count += len(hits)
elapsed = time.perf_counter() - start
print("benchmark_calls=1000 hits=%d elapsed_ms=%.3f" % (count, elapsed * 1000.0))
doc.close()
