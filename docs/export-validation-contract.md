# Production 2D export validation contract

This document is the coordination contract for issue #163 / roadmap gate P1-B. It deliberately does not define a second geometry model: the FreeCAD document remains authoritative and exported SVG/DXF/TechDraw output is a derived artifact.

## Scope

Every production export fixture must validate the following against the authoritative FreeCAD document before the export is considered release-ready:

1. **Units and scale** — document units and export units are explicit; a known-length reference survives export within the agreed numeric tolerance.
2. **Piece identity** — every exported pattern piece has a stable semantic piece ID that can be mapped back to exactly one source PatternPiece.
3. **Boundary geometry** — closed boundaries are deterministic and preserve curve semantics where the source supports them; sampling must not become the source of truth.
4. **Seam allowance** — allowance geometry is distinguishable from the base boundary and has deterministic ownership by piece.
5. **Notches and grainlines** — semantic marks retain piece ownership and deterministic placement/orientation.
6. **Internal marks** — darts, folds, drill/placement marks and other supported internal annotations remain attributable to their source semantic object.
7. **Sewing relationships** — exported seam metadata identifies both source pieces and stable edge identities; missing/invalid references fail validation rather than being silently retargeted.
8. **Determinism** — exporting the same saved document twice produces equivalent geometry and semantic metadata, independent of object enumeration order.
9. **Round-trip traceability** — every validated export item has a source object/semantic ID; orphaned output is a validation failure.

## Machine-checkable result

Validation should emit a compact result with:

```text
status: PASS | FAIL
format: SVG | DXF | TechDraw
source_document: <fixture identifier>
unit_scale: <numeric scale>
pieces: <count>
seams: <count>
marks: <count>
errors: [<stable error codes>]
warnings: [<stable warning codes>]
geometry_fingerprint: <deterministic digest>
semantic_fingerprint: <deterministic digest>
```

Suggested stable error codes are `UNIT_SCALE`, `PIECE_ID`, `OPEN_BOUNDARY`, `GEOMETRY_DRIFT`, `SEAM_REFERENCE`, `MARK_OWNERSHIP`, `ORPHAN_OUTPUT`, and `NONDETERMINISTIC_OUTPUT`.

Warnings must never downgrade a release-gate failure to success. A validator may report unsupported optional metadata as a warning only when the corresponding feature is explicitly outside the fixture's required capability set.

## Canonical fixture expectations

The fixture should contain at least two PatternPieces, one curved boundary, one seam, seam allowance, grainline, notch, and one internal mark. It should be saved and reloaded before export so persistence is part of the gate. The same fixture should be exported twice and compared semantically and geometrically.

The fixture must be constructed through the public Pattern/Sewing workbench workflow. Utility-only construction is insufficient evidence for a native workbench release gate.

## Collaboration and branch hygiene

- Keep this contract and export-specific tests separate from the active P0 sewing/simulation implementation branches.
- Do not add a second GitHub Actions workflow. Extend the canonical CI only when an implementation owner is ready to wire this contract into executable validation.
- Export adapters consume the authoritative Pattern/Sewing model; they must not write changes back into that model as a side effect of export.
- If a source semantic reference is invalid, report it explicitly and stop the affected validation path. Never fall back to an ordinal `EdgeN` match.
- When handing the implementation to another contributor, include the fixture identifier, expected semantic IDs, current validator output, and any known tolerance decisions in the PR description.

## Definition of done for #163

A PR can claim the gate only when it provides an executable canonical fixture, machine-checkable validation for the required fields above, deterministic repeated-export evidence, and terminal-green canonical CI. Documentation alone establishes the contract but does not close the release gate.
