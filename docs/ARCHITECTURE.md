# Developer architecture

Pipeline: parametric pattern geometry -> stable pattern document -> sewing/seam graph -> deterministic 2D-to-mesh conversion -> solver adapter -> avatar collision surface -> drape state.

Core modules are FreeCAD-independent. GUI code translates FreeCAD document objects and selections into model operations. Serialization is versioned JSON-like data. Seam semantics remain declarative; numerical constraints belong to the solver adapter.

Testing has three layers: exact core/data tests, deterministic mesh/constraint regression tests, and optional FreeCAD runtime smoke tests. Third-party solver dependencies remain optional until a backend has passed capability, maintenance, build, and license review.

Contribution workflow: make one focused change, run core tests, update architecture docs when contracts change, and merge through the canonical CI workflow. Side-task issue dependencies are reflected by module boundaries rather than hidden coupling.
