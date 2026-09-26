import json
import math
from pathlib import Path

import numpy as np
from tissu import Simulation

ARTIFACT = Path("/workspace/artifacts/tissu-mesh-response.json")
ARTIFACT.parent.mkdir(parents=True, exist_ok=True)

cube_vertices = np.asarray([
    (-0.1, -0.1, -0.1), (0.1, -0.1, -0.1),
    (0.1, 0.1, -0.1), (-0.1, 0.1, -0.1),
    (-0.1, -0.1, 0.1), (0.1, -0.1, 0.1),
    (0.1, 0.1, 0.1), (-0.1, 0.1, 0.1),
], dtype=np.float64)

outward = np.asarray([
    (0, 1, 2), (0, 2, 3),
    (4, 6, 5), (4, 7, 6),
    (0, 4, 5), (0, 5, 1),
    (3, 2, 6), (3, 6, 7),
    (0, 3, 7), (0, 7, 4),
    (1, 5, 6), (1, 6, 2),
], dtype=np.int32)
inverted = outward[:, [0, 2, 1]]

cloth_vertices = np.asarray([
    (0.099, -0.02, -0.02),
    (0.099,  0.00, -0.02),
    (0.099, -0.02,  0.00),
], dtype=np.float64)
cloth_triangles = np.asarray([(0, 1, 2)], dtype=np.int32)


def signed_volume(vertices, triangles):
    total = 0.0
    for a, b, c in triangles:
        va, vb, vc = vertices[a], vertices[b], vertices[c]
        total += float(np.dot(va, np.cross(vb, vc))) / 6.0
    return total


def mesh_case(triangles):
    sim = Simulation(substeps=1, iterations=1, gravity=0.0, thickness=0.002)
    sim.create_from_arrays("cloth", cloth_vertices, cloth_triangles, material="cotton")
    sim.add_mesh_from_arrays("cube", cube_vertices, triangles, friction=0.5)
    before = np.asarray(sim.positions, dtype=np.float64).copy()
    sim.step(1.0 / 60.0)
    after = np.asarray(sim.positions, dtype=np.float64).copy()
    return {
        "before_min_x": float(before[:, 0].min()),
        "after_min_x": float(after[:, 0].min()),
        "after_mean_x": float(after[:, 0].mean()),
        "displacement_mean_x": float((after[:, 0] - before[:, 0]).mean()),
    }


def sphere_case():
    sim = Simulation(substeps=1, iterations=1, gravity=0.0, thickness=0.002)
    sim.create_from_arrays("cloth", cloth_vertices, cloth_triangles, material="cotton")
    sim.add_sphere("sphere", np.asarray((0.0, 0.0, 0.0), dtype=np.float64), 0.1, 0.5)
    before = np.asarray(sim.positions, dtype=np.float64).copy()
    sim.step(1.0 / 60.0)
    after = np.asarray(sim.positions, dtype=np.float64).copy()
    return {
        "before_min_x": float(before[:, 0].min()),
        "after_min_x": float(after[:, 0].min()),
        "after_mean_x": float(after[:, 0].mean()),
        "displacement_mean_x": float((after[:, 0] - before[:, 0]).mean()),
    }


result = {
    "mesh_signed_volume_outward": signed_volume(cube_vertices, outward),
    "mesh_signed_volume_inverted": signed_volume(cube_vertices, inverted),
    "mesh_outward": mesh_case(outward),
    "mesh_inverted": mesh_case(inverted),
    "sphere": sphere_case(),
}
result["mesh_winding_sensitive"] = not math.isclose(
    result["mesh_outward"]["after_mean_x"],
    result["mesh_inverted"]["after_mean_x"],
    rel_tol=0.0,
    abs_tol=1e-9,
)
result["mesh_pushes_outward"] = (
    result["mesh_outward"]["after_mean_x"] > 0.099
)
result["sphere_pushes_outward"] = (
    result["sphere"]["after_mean_x"] > 0.099
)
ARTIFACT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
