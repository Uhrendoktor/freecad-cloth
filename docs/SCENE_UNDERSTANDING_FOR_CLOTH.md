# Artifact-first scene understanding for garment construction

## Decision

Do not try to solve this by asking a vision-language model to infer a complete 3D scene from one FreeCAD screenshot, and do not compensate with more solver-parameter search. Make the workflow artifact a compact, causally ordered observation of the same garment across the pattern, sewing, placement, and simulation stages.

The recommended unit of evidence is a **scene dossier**: a small machine-readable summary, a geometry-annotated 2D pattern view, fixed-camera views of the mannequin/garment, and a concise status table that states what actually ran. Every item must come from the same GitHub Actions run and exact commit. The dossier should point to the existing raw screenshots and logs instead of copying large binaries.

This is a data-interface improvement, not a claim that model weights or intrinsic 3D perception have changed. It makes the important spatial facts explicit, lets a model check rendered evidence against coordinates and topology, and provides a test of whether diagnoses improve.

## What PR #2674 demonstrates

The exact-head run [38098513772](https://github.com/Uhrendoktor/freecad-cloth/actions/runs/38098513772) produced a useful counterexample to numeric optimization:

- The avatar pose and both native Sketcher armholes were captured. The mannequin image is a before-cloth reference, not evidence that fitting succeeded.
- The native pattern and sewing screenshots were generated, but both panel outlines failed the simple-polygon validity check.
- The authoritative topology log reports a self-intersection near **(627.926, 482.858) mm**. Its nearest boundary segments are the shoulder segment (outline edge 3) and armhole arc (edge 2). The pattern’s 2D geometry is therefore invalid before it reaches a valid fit/simulation evaluation.
- The run failed with **pattern boundary self-intersects**. There is no post-drape screenshot or drape metric in this artifact. Any proposed explanation about how the cloth penetrated the avatar during that run would be unsupported.

The key failure was not a difficult penetration metric. It was a pattern-topology defect, visible in both the 2D boundary and the log. Because the failure-stage signal was mixed into a large GUI log, a reviewer has to extract the relevant facts manually. Existing six-side drape captures are valuable when simulation is reached, but they are not a substitute for stage state.

Inspect the [PR](https://github.com/Uhrendoktor/freecad-cloth/pull/2674) and [tunic visual audit artifact](https://github.com/Uhrendoktor/freecad-cloth/actions/runs/38098513772).

## Research findings

### 1. A single image is not a reliable 3D mental model

The 2025 [3DSRBench paper](https://openaccess.thecvf.com/content/ICCV2025/html/Ma_3DSRBench_A_Comprehensive_3D_Spatial_Reasoning_Benchmark_ICCV_2025_paper.html) tests spatial questions about location, orientation, height, and relationships across familiar and uncommon camera viewpoints. Its motivation and results expose that general image understanding does not automatically imply dependable 3D spatial reasoning. [Ego3D-Bench / Ego3D-VLM](https://arxiv.org/abs/2509.06266) similarly reports a human–model gap; its proposed global-coordinate cognitive map improves multi-view question answering and distance estimation.

**Implication here:** do not make the model reconstruct scale, front/back, depth, or correspondence from each screenshot independently. Supply a world-coordinate frame, camera labels, named landmarks, transforms, and measurements that refer to the same objects. Provide complementary orthographic views with consistent framing and a progression from the same fixed state.

### 2. Explicit scene relations complement image evidence

3D scene-graph work represents a scene with geometric entities and named relations rather than a flat list of pixels. The [3D scene-graphs survey](https://research.google/pubs/a-3d-scene-graphs-survey-open-challenges-and-future-directions/) describes scene graphs as a bridge between geometric grounding and semantic/relational abstractions.

**Implication here:** represent the garment as a small graph:
- nodes: mannequin, body landmarks, pattern pieces, native boundary edges, sewn seams, simulated panels, collision surface;
- relations: front-of/back-of, attached-to, stitched-to, derived-from, transformed-by, intersects, penetrates, and measured-clearance-to;
- attributes: persistent IDs, coordinate frame, units, bounds, point samples, transforms, validity, and source revision.

The sewing graph and geometric boundary graph must be linked by stable semantic edge IDs. A seam connecting the wrong shoulder is a relation error, not a parameter-tuning problem.

### 3. Garment research preserves both the flat pattern and the 3D result

[GarmentCodeData (ECCV 2024)](https://igl.ethz.ch/projects/GarmentCodeData/) explicitly connects sewing patterns, made-to-measure body shapes, materials, and a 3D draping pipeline. Its dataset has 115,000 generated garment/body/material examples. [CLOTH3D](https://github.com/hbertiche/CLOTH3D) emphasizes garment topology, shape, tightness, fabric, body shape, and motion variation.

**Implication here:** pattern→fit→simulation is not one optimization objective. It is a chain of different invariants, each with different authoritative evidence. Pattern validity, seam correspondence, initial body clearance, collision-free drape, and intended silhouette should be independently reported. A downstream symptom must not overwrite an upstream failure.

### 4. Better artifact design is the right first experiment

The repository already contains an opt-in observation-bundle mechanism: it records the exact commit/run, hashes selected evidence, and avoids duplicating large binary files. It is not enabled for the full tunic audit, and its index alone does not explain which stage failed or why. The existing progress log already includes the authoritative self-intersection coordinates and nearby edge segments, so a new vision model or remote inference service is not required for the first improvement.

**Implication here:** keep artifacts as the only observation channel. Generate a compact report from the exact run, attach it to the existing tunic artifact, and test whether a model can name the correct causal layer from that report. Do not make network inference, hidden live-state probes, persistent GUI access, or local/manual FreeCAD observations part of the process.

## Recommended scene dossier

The dossier should answer these questions in this order:

1. **What exact state is this?** Repository, PR number, commit SHA, workflow run/attempt, simulator backend/version, coordinate units, and camera conventions.
2. **Which stages actually ran?** Use explicit states such as **passed**, **failed**, **not_reached**, and **not_observed**. Absence of a final image must mean “not produced,” not “fit passed.”
3. **Is the 2D source valid?** For every piece: ordered boundary edges, stable edge IDs, line/arc/spline kind, start/end and curve samples in local millimetres, bounds, area, orientation, and polygon validity. When invalid, record the crossing coordinate and the two intersecting edge IDs.
4. **How does the pattern map to 3D?** Record each piece’s local→world transform, front/back assignment, bounding box, center, and minimum signed/unsigned distance to the mannequin surface. Record mannequin pose, shoulder/neck/axilla/hip/wrist landmarks, and the mesh/pose revision.
5. **What exactly is sewn?** For every seam: piece IDs, semantic edge IDs, edge length ratio, endpoint correspondence errors, reversal/range/alignment settings, seam validity, and gap at step 0 and checkpoints. Display edge IDs consistently in the pattern diagram.
6. **What happened during drape?** At steps 0, 1, 5, 10, 30, 60, and 90 (or the actual available checkpoints), report finite state, panel counts/bounds, minimum body clearance, number of inside vertices, representative penetration coordinates, max/median seam gap, and solver configuration. Store measurements and thresholds separately.
7. **What should happen next?** Give one current blocker, authoritative source, strongest alternative hypothesis, falsifier, expected measurable delta, and next causal layer. Never recommend solver changes before geometry, frames, topology, placement, and constraints have been checked.

### Suggested compact JSON shape

Keep a stable top-level schema while versioning payload sections independently:

    {
      "schema": "freecad-cloth.scene-understanding",
      "schema_version": 1,
      "provenance": {
        "commit_sha": "...",
        "workflow_run_id": "...",
        "artifact": "tunic-visual-audit",
        "units": "mm",
        "world_frame": {"axes": "...", "front_direction": "..."}
      },
      "status": {
        "result": "blocked",
        "failed_stage": "pattern_topology",
        "last_completed_stage": "pattern_created"
      },
      "stages": {"pattern": "...", "sewing": "...", "placement": "...", "simulation": "..."},
      "entities": [],
      "relations": [],
      "issues": [{
        "kind": "self_intersection",
        "piece_id": "...",
        "edge_ids": ["...", "..."],
        "point_local_mm": [627.926, 482.858]
      }],
      "measurements": [],
      "evidence": [{"path": "...", "role": "visual", "sha256": "..."}],
      "next_action": "repair the boundary before any simulation tuning"
    }

The schema above is illustrative; preserve exact measured values in the report and never infer unavailable values. FreeCAD world coordinates use millimetres; pattern points should explicitly say they are local 2D coordinates, so local and world space are not accidentally compared.

## Visual rendering contract

Generate a dedicated annotated SVG from the same sampled boundary and intersection data, not by image-editing the screenshots. It should:
- show each panel at the same scale, outline edge IDs, and distinguish the specific intersecting edges;
- draw the reported crossing point and print its local coordinate in millimetres;
- show the avatar’s front/back and shoulder/axilla landmarks in a separate alignment diagram when placement evidence is available;
- render fixed front/rear/left/right/top views with the same camera orientation and comparable framing for step 0 and final step;
- use a small number of views with high information density instead of a single full-desktop screenshot; keep raw screenshots untouched and in the artifact.

A raw FreeCAD viewport is useful for UI regressions, but toolbars, task panels, tiny geometry, inconsistent zoom, and changing camera direction reduce its usefulness for spatial diagnosis. Retain it as evidence; add a purpose-built geometry view for reasoning.

## Failure ordering and anti-optimization gates

The intended diagnosis ladder is:

**authoritative native geometry → unit/coordinate frames → topology/semantic mapping → placement/orientation → seam relation/attachments → initial body clearance → collision representation → solver/time integration → camera/presentation.**

A pattern that fails polygon validity must stop before sewing/fitting is marked successful or the simulation starts. When an audit intentionally continues to collect multiple diagnostics, the report must label later artifacts “generated from invalid input,” not pass them off as a valid garment state.

Only vary one causal layer per experiment. The report must preserve unchanged acceptance thresholds and show predicted versus observed delta. If a geometry change leaves the same wrong spatial relation, check the coordinate frame or mapping rather than trying another nearby numeric value. This follows the repository’s existing debugging philosophy while making the state easier to see from artifacts.

## Evaluation plan

Start with a small artifact-only challenge set, not fine-tuning. Select exact workflow artifacts representing distinct failure classes:

- invalid/self-intersecting pattern boundary;
- incorrect semantic edge or front/back seam pairing;
- wrong local/world transform or side placement;
- initial panel/avatar overlap or inadequate clearance;
- residual penetration after a valid pattern and placement;
- seam convergence/attachment failure;
- genuinely numerical instability after upstream checks pass;
- successful garment used as a contrast case.

For each case, give the model only the dossier and its indexed workflow evidence. Require it to identify (a) the first failed stage, (b) the visible/geometric symptom, (c) the authoritative data, (d) the likeliest causal layer, (e) one falsifying check, and (f) the next single experiment. Score root-cause class accuracy, exact entity/edge localization, unsupported-claim rate, and whether it avoids prohibited downstream tuning. Include counterfactual pairs with similar screenshots but different geometry/topology causes. Keep the source commit, model/prompt version, answer, and human adjudication in an artifact.

If this experiment does not improve diagnosis, the next question is whether the model failed to read a clear dossier or whether the dossier omitted the needed relationship. Only then consider model-specific prompting, tool use, or fine-tuning. There is no evidence yet that fine-tuning is necessary.

## Proposed rollout

1. Add an always-generated compact JSON/Markdown scene summary and annotated outline SVG to the existing tunic workflow artifact, including when FreeCAD exits before simulation.
2. Include those three files in the existing observation manifest and keep original images/logs alongside them.
3. Verify with PR #2674’s known self-intersection: the report should identify the topology stage, both edge IDs, and the crossing; state that drape was not reached; and explicitly reject solver tuning as the next step.
4. Verify a successful tunic run: the same schema should show completed stages, link final multi-view evidence, and summarize penetration and seam metrics rather than inventing a failure.
5. Run the artifact-only challenge set before considering any model adaptation.

The acceptance criterion is better causal diagnosis from the GitHub Actions artifact alone—not a greener CI run achieved by weakening geometry, collision, or simulation gates.
