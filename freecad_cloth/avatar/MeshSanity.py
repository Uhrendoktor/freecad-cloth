"""Helpers for keeping authored avatar meshes free of unreferenced vertices."""


def compact_mesh(vertices, triangles):
    used = sorted({int(i) for tri in triangles for i in tri})
    remap = {old: new for new, old in enumerate(used)}
    compact_vertices = tuple(vertices[i] for i in used)
    compact_triangles = tuple(tuple(remap[int(i)] for i in tri) for tri in triangles)
    return compact_vertices, compact_triangles
