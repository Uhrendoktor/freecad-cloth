> Planning matrix only: this document describes sequencing and desired capability boundaries. It is not a live implementation-status record. Verify current behavior against the current branch, `AGENT_STATUS.md`, and `TOOL_STATE.md`.

# Feature matrix and UI/UX roadmap

This document is the supervisor-level planning reference for turning the three
workbenches into a CLO-like garment workflow without copying CLO's internals.

## What a mature garment workflow normally needs

| Area | Prototype | MVP | Production |
|---|---|---|---|
| Pattern geometry | Native Sketcher PatternPiece | Stable semantic references, seam allowance, notches, grainlines | Grading, production annotations, robust topology repair |
| Sewing | Pairwise seams | M:N/free sewing, direction, correspondence, validation | Easing, seam groups, automatic sewing assistance |
| 2D/3D relationship | Explicit arrangement | Persistent arrangement + fitting scene | 3D editing/tape/flatten/extraction workflows |
| Avatar/target | Deterministic mannequin | Human mannequin + arbitrary FreeCAD target | Higher-fidelity provider, poses, measurements, fitting suit |
| Fabric | Basic material | Density, thickness, stretch, shear, bend, friction, presets | Measurement/calibration workflow and material libraries |
| Simulation | Deterministic CPU reference | Quality presets, collisions, reset/step/debug | Optional accelerated backend after parity evidence |
| Diagnostics | Status + invalidation reason | Fit/strain/stress inspection primitives | Fit, stress, strain and pressure maps; numerical inspection |
| Production 2D | Export basics | DXF/SVG/TechDraw path | Grading, marker/nesting, manufacturing validation |
| Trims/construction | Out of scope | Core semantic placeholders | Buttons, buttonholes, zippers, bindings, piping, pleats |
| Presentation | FreeCAD viewport | Stable garment scene | Materials/textures, render-oriented presentation |

CLO's current workflow confirms that fitting is not just simulation: it combines
sewing/drape with fit maps and garment/Avatar measurements. Its simulation UI
also separates faster normal simulation from more accurate fitting-oriented
modes. These concepts map well to Cloth's existing quality/material and
DrapeTarget boundaries.

## UI/UX principles

1. **One task panel per user goal.** Prefer Context → Primary action → Secondary
   actions → Parameters → Recovery.
2. **Make state visible.** Show target, pattern/seam validity, mesh quality,
   simulation status, and the reason for stale derived state.
3. **Progressive disclosure.** Keep the default toolbar small; put advanced
   solver/material/diagnostic controls behind explicit sections.
4. **Use native FreeCAD where users already expect it.** Sketcher remains the
   pattern editor; Property Editor remains authoritative for persistent values.
5. **Never hide destructive or ambiguous topology changes.** If a seam reference
   cannot be resolved, show it as invalid and require an explicit repair/remap.
6. **Keep 2D and 3D selection symmetric.** A seam selected in one view should be
   obvious in the other, without inventing a second document model.
7. **Use recoverable workflows.** Reset arrangement, invalidate/rebuild, refresh
   target, and step/reset simulation should be first-class recovery actions.
8. **Do not overload the avatar concept.** Body provider, pose, measurements,
   collision surface and fitting controls are separate concepts.

## Avatar direction

The requested real humanoid avatar should be implemented as a provider, not as a
new simulation model. The existing target-neutral `DrapeTarget` contract should
remain the common boundary for:

- deterministic native mannequin;
- production-quality human avatar provider;
- arbitrary FreeCAD Part/PartDesign/Body/Mesh object.

The document should persist provider identity, measurements, pose and rebuild
state. Visual geometry and collision geometry should be allowed to differ.
Changing a provider, pose, or collision geometry must invalidate target-dependent
derived simulation state deterministically.

## Conceptual maturity sequencing

The stages below are a design taxonomy, not an implementation checklist. Do not infer whether an item is implemented from its column or wording; verify the current code, tests, and live state records.


### Prototype

- Establish native Pattern/Sewing/DrapeTarget boundaries.
- Establish deterministic arrangement and a reference simulation path.
- Establish save/reload and stale-state invalidation semantics.

### MVP

- Harden semantic references and topology repair.
- Support richer sewing relationships and fitting controls.
- Provide reproducible quality/material modes and production-oriented 2D output.

### Production

- Add a high-fidelity human provider behind `AvatarService`.
- Add pose libraries/controls and a fitting-suit equivalent where justified.
- Add fit/stress/strain/pressure diagnostics.
- Add grading, nesting/marker planning and manufacturing reports.
- Add construction details such as bindings, piping, buttons, buttonholes and
  zippers as semantic objects.
- Benchmark optional solver backends only after reference parity.

## Research basis

The feature categories above were cross-checked against CLO's public support
material in August 2026, including simulation modes, auto fitting, free sewing,
fit maps, avatar properties, and 3D garment/Avatar measurement workflows.
