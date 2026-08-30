# FreeCAD Cloth Roadmap

Research/roadmap review: 2026-08-30

## Status

The project has crossed the “basic capability accumulation” phase. The native three-workbench workflow, semantic sewing model, fitting metadata and deterministic reference simulation already exist. The next release should be judged by a complete user-facing vertical slice rather than by isolated feature count. The current repository README confirms the intended Pattern → Sewing → fitting scene → Simulation workflow and the authoritative-pattern/derived-mesh rule. fileciteturn1file0L2-L2

## Obsolete assumptions from earlier roadmap versions

The following assumptions are now obsolete and are explicitly superseded:

1. **“Rectangle-first authoring is sufficient for MVP.” — OBSOLETE.** Current garment-CAD workflows require curved outlines and construction details; curved authoring is a P1 release blocker, not an optional polish item. Style3D's current authoring workflow explicitly includes curve editing and structural details. citeturn2search11
2. **“Pairwise edge sewing is the complete sewing model.” — OBSOLETE.** The semantic model must support ranges, reversal/correspondence and M:N/free sewing. Commercial workflows use more flexible sewing relationships; the existing project already treats sewing as semantic assembly. fileciteturn4file0L2-L2
3. **“Simulation quality can remain a stored preference.” — OBSOLETE.** Quality/resolution changes actual simulation cost and behavior and therefore must change derived topology/solver settings and invalidate simulation state. CLO and Style3D both expose meaningful simulation quality controls. citeturn0search6turn0search5
4. **“The generated mesh can define seam identity.” — OBSOLETE.** Open-source DXF/SVG workflows demonstrate metadata loss when edge information is flattened; semantic IDs must survive independently of generated topology. citeturn2search17
5. **“CLO-SET-like cloud/product management belongs in the core MVP.” — OBSOLETE.** CLO-SET is primarily a collaboration/asset/product-workflow layer around 3D assets. It is a useful downstream reference, not a prerequisite for garment authoring and drape. citeturn0search1
6. **“A proprietary project format is a necessary compatibility target.” — OBSOLETE.** Native FCStd plus standard 2D/3D interchange is sufficient for the core release; vendor-specific formats remain future research.
7. **“An external native solver should replace the CPU reference early.” — OBSOLETE.** A backend benchmark should precede any dependency/ABI commitment.

## Feature priority matrix

| Feature | Priority | Rationale / release gate |
|---|---:|---|
| Native pattern piece creation/editing | P0 | Required working garment authoring |
| Stable semantic IDs | P0 | Required for sewing, persistence and regeneration |
| Seam allowance metadata + deterministic derived outline | P0 | Required production pattern behavior |
| Notches, grainline, internal marks | P0 | Required construction semantics and diagnostics |
| Segment sewing with ranges/reversal | P0 | Required assembly |
| Sewing validation + mismatch diagnostics | P0 | Required correctness feedback |
| Reproducible fitting scene + avatar/collision proxy | P0 | Required pre-simulation arrangement |
| Simulation mesh generation | P0 | Required drape |
| Fast/Balanced/Final quality mapping | P0 | Required usable simulation lifecycle |
| Fabric density/thickness/stretch/shear/bend/friction | P0 | Required material behavior contract |
| Simulate / Step / Pause / Reset / Pin | P0 | Required interactive control |
| Save/reload + deterministic re-simulation | P0 | Required project reliability |
| Curved pattern authoring | P1 | Real garment authoring blocker after vertical slice |
| Sketcher-backed dimensional/geometric constraints | P1 | Reuse mature FreeCAD solver rather than duplicate it |
| M:N / free sewing editor | P1 | Important sewing parity and robust assembly |
| Rich avatar arrangement points / wrap direction | P1 | Important fitting workflow improvement |
| Tension/stretch/collision diagnostics visualization | P1 | Important fit-debugging aid; Optitex demonstrates value of tension maps. citeturn0search9 |
| DXF/AAMA/ASTM-oriented production export | P1 | Highest-value external CAD interchange; Style3D demonstrates this boundary. citeturn2search1 |
| SVG/TechDraw production sheets | P1 | Native FreeCAD export path |
| DXF import and semantic round-trip tests | P2 | Useful interoperability after export contract is stable |
| Measurement-driven multi-size parametric drafting | P2 | Strong Seamly2D reference, but not required for first drape release. citeturn2search3 |
| Fold/pleat visualization | P2 | Advanced construction visualization |
| Topstitch/buttons/trims as rich objects | P2 | Production-detail layer, not core drape correctness |
| Optional Tissu/PBD backend benchmark | P2 | Only after P0/P1 release gates |
| Grading automation | P2 | Important later production capability |
| Marker/nesting optimization | P3 | Future production research |
| Full avatar soft-body/animation simulation | P3 | Separate simulation research area |
| Photorealistic fabric rendering | P3 | Presentation, not CAD correctness |
| Cloud collaboration/marketplace | P3 | CLO-SET-like downstream service, outside core |
| Vendor-specific proprietary project formats | P3 | Research only when a concrete interoperability requirement exists |

## Release sequence

### P0 — Working garment vertical slice

`Create curved-capable pieces → construction marks → seam ranges → sew → arrange → simulate → diagnose → edit → invalidate → save/reload → deterministic re-simulate`

Exit criteria:
- native workbench UI only;
- no developer-only helper imports required;
- persistent semantic IDs survive recompute/save/reload;
- quality/material/arrangement changes invalidate derived state;
- deterministic reference solver passes regression checks.

### P1 — Garment-CAD authoring and production contract

Prioritize curved drafting, real constraints through Sketcher, M:N/free sewing, richer arrangement, diagnostics and DXF/TechDraw export. Style3D's current workflow confirms that curved editing, notches, sewing and rapid 2D↔3D iteration are normal CAD behavior. citeturn2search11

Exit criteria:
- non-rectangular garment piece can be authored and revised natively;
- sewing remains valid after geometry edits where semantics are preserved;
- production export has deterministic units/scale and regression tests.

### P2 — Advanced production/simulation

Add robust DXF import/round-trip, measurement-driven grading, richer construction visualization and evidence-based optional solver benchmarks.

### P3 — Research / ecosystem

Explore nesting, soft-body avatars, animation, high-end rendering, cloud collaboration and vendor-specific formats only after the core model is stable.

## Verification policy

Every implementation feature should have the smallest appropriate combination of core tests, real FreeCAD runtime coverage, GUI coverage for UI changes, save/reload coverage for persistent data, and deterministic evidence for solver changes. The repository's canonical workflow remains the sole CI execution path; this task changes documentation only and does not modify implementation.
