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

## Deep dive: the two research papers and what transfers to FreeCAD Cloth

### 3DSRBench: measure spatial reasoning rather than image recognition

**Primary sources:** [ICCV 2025 paper and supplementary material](https://openaccess.thecvf.com/content/ICCV2025/html/Ma_3DSRBench_A_Comprehensive_3D_Spatial_Reasoning_Benchmark_ICCV_2025_paper.html), [project page with benchmark splits and results](https://3dsrbench.github.io/), [arXiv version](https://arxiv.org/abs/2412.07825).

3DSRBench is a diagnostic benchmark, not a new scene-reconstruction engine. Its central contribution is a controlled way to ask whether a vision-language model can answer questions whose answers depend on 3D geometry rather than superficial 2D cues.

**Benchmark construction.** The paper reports 2,772 manually annotated visual question-answer pairs across 12 subtypes. The real split has 2,100 questions over MS-COCO images. The synthetic split has 672 questions rendered from HSSD indoor scenes: 336 under common 6D camera viewpoints and 336 under uncommon viewpoints of the same underlying scenes. The paper uses complementary horizontal-flip augmentation to reach 5,250 real and 1,692 synthetic questions. The 12 subtypes form four families:

- **Height:** which object is higher in world space. Correct reasoning must distinguish world height from vertical pixel location and account for camera pitch/roll.
- **Location:** near/far, closer to the camera, and directly above/underneath. These require separating image-plane proximity from 3D distance and depth.
- **Orientation:** which side of an object faces the camera, front/behind relations, and left/right from an object's perspective. Viewer-relative and object-relative directions are not interchangeable.
- **Multi-object reasoning:** five subtypes requiring relations over several objects, including reasoning about which way an object faces or which object is nearer to a reference.

The construction explicitly tries to remove dataset shortcuts: answer distributions are balanced, questions with trivial answers are avoided, and some questions are phrased so familiar language priors (for example, which side a stereotypical object is on) cannot solve them.

**Evaluation controls.** The paper combines two important ideas. *CircularEval* reorders multiple-choice options; a prediction is considered reliable only when the answer stays the same across option permutations. *FlipEval* pairs original images with horizontally flipped images. For relations whose meaning changes under the image reflection (notably viewer/image left-right), the target answer is changed consistently; for relations such as world height, the underlying answer normally remains the same. This tests for answer-position bias and ungrounded left/right heuristics, not just average accuracy.

The synthetic split is particularly relevant to CAD screenshots because the same scene is viewed from different camera 6D poses. The project's published results show material degradation from common to uncommon viewpoints: for example GPT-4o goes from 51.2% to 44.3% and LLaVA-NeXT-8B from 45.5% to 36.8% in that reported table. A model that seems to understand a standard front/axonometric view may therefore fail when the camera is rotated, even though the underlying geometry has not changed. Orientation and multi-object reasoning are especially difficult categories.

**Transfer to FreeCAD Cloth.** Reuse the benchmark *design*, not its natural-image inputs or its vision-model stack:

1. Hold the garment, mannequin pose, placements, sewing graph and simulator checkpoint constant while rendering front, rear, left, right, top, axonometric and at least one less familiar oblique view. Every view must carry a declared camera name/orientation and the same scene ID.
2. Ask questions whose ground truth is computed directly from the CAD model: Is the front panel in front of or behind the mannequin surface in this world frame? Which specific semantic edge crosses another? Does a visible gap belong to a side seam or to the unsewn armhole? Is a panel outside the body at step 0, or only after draping?
3. Use matched viewpoint pairs. For **world-space** relations, rotating the camera must not change the answer. For **camera-relative** left/right questions, the expected answer must be derived from the camera transform. Never assume a horizontal bitmap flip is semantically equivalent to a 3D mirror; reflect the scene or camera and recompute the expected label when the tested relation requires it.
4. Use option-order permutations where multiple-choice questions are used, and balanced counterfactuals with opposite answers. Include successful cases alongside superficially similar failures so the model cannot pass by always declaring overlap or topology invalid.

This makes the goal *spatial consistency under controlled transformations*, rather than memorizing that a particular view tends to correspond to a particular defect.

### Ego3D-Bench / Ego3D-VLM: supply one shared coordinate map across views

**Primary sources:** [arXiv paper, version 2](https://arxiv.org/html/2509.06266v2), [official implementation](https://github.com/vbdi/Ego3D-Bench).

Ego3D addresses a related but different weakness: a model sees several views yet fails to consolidate them into a coherent world model. Ego3D-Bench contains more than 8,600 question-answer pairs from NuScenes (six views), Waymo (seven views) and Argoverse 1 (five views). It deliberately excludes questions answerable from each image independently. Its five task families are absolute distance, relative distance, localization from one object's perspective to another, motion reasoning, and travel time; questions can be ego-centric or object-centric. Ground-truth 3D annotations support rule-generated answers, with human review for harder motion questions. The benchmark scores multiple-choice accuracy and metric distance with RMSE.

Ego3D-VLM constructs a compact textual **cognitive map** alongside the images:

1. A referring-expression model grounds objects named in the question in every relevant view, returning bounding boxes.
2. A metric depth estimator supplies depth at each box centre. The system projects pixel centres through camera intrinsics into camera-frame 3D coordinates.
3. It applies camera extrinsics (rotation and translation) to express detections in a shared global frame anchored to the front camera. This is the key step: the same object in the front-left view and the rear view is not treated as unrelated 2D observations.
4. A relational scaling step can use a known-size category such as a human to calibrate uncertain metric scale.
5. The generator records the named object, its shared 3D location, and the view it came from in a compact text/JSON map. The VLM reasons using that map **and** the original images: the map anchors direction, position and distance; images preserve appearance and fine visual evidence.

The paper reports an average 12% improvement in multiple-choice accuracy and 56% improvement in distance-estimation RMSE when integrating Ego3D-VLM. In its results table GPT-4o moves from 56.7% to 73.2% average multiple-choice accuracy, with average distance RMSE falling from 19.2 m to 7.4 m. Its ablation with estimated camera parameters already improves InternVL3-8B from 43.1% to 56.0% accuracy and RMSE 27.2 m to 10.8 m; using a ground-truth cognitive map reaches 79.4% and 1.3 m. The large gap between estimated and ground-truth maps is informative: errors in grounding, depth and transforms can become errors in the model's reasoning, so perception/geometry errors must be visible and measurable rather than hidden in a single prose description.

The authors also list limitations: weak reasoning models may gain little; redundant detections/false positives can mislead; metric-depth estimates may be wrong; and relational scaling from assumed object size is approximate. This argues against adding an image-derived reconstruction stage to FreeCAD when exact CAD geometry is available.

**Transfer to FreeCAD Cloth: a CAD-native cognitive map.** Replace Ego3D's estimated 2D box/depth/pose pipeline with exact quantities already owned by FreeCAD:

- Use one explicit **world frame** (mm; axis directions documented; front/back defined by the mannequin frame) and store every view's camera transform relative to that frame.
- For every pattern piece, store the stable piece ID, local 2D boundary samples, native curve/edge IDs and kinds, validity, local bounding box/area, local-to-world homogeneous transform, and sampled world-space boundary points. Do not silently conflate local sketch coordinates with world coordinates.
- For every mannequin landmark, store a persistent semantic name (neck, left/right shoulder, axilla, hip, wrist, and any garment-specific landmark) and world XYZ in mm. Store mannequin pose/source revision and collision-surface bounds/identity with it.
- For every seam, store both piece IDs and stable edge IDs, normalized ranges, reversal/alignment, the transformed edge samples, length mismatch, endpoint gap, and validation state. A seam is a named graph edge between geometry entities, not just a coloured line on screen.
- For each simulation checkpoint, refer to the same piece IDs and world frame, and add exact initial/final bounds, clearance, inside/penetration samples, seam-gap metrics, solver step/time, finite-state flag, and measured threshold. Distinguish what was computed from what was merely visible in a screenshot.
- Keep images in the dossier because appearance reveals useful details, but present them with the map. Use the numeric scene map as grounding, not as a replacement for visual inspection.

For FreeCAD, the map is better than a learned visual depth estimator because it has authoritative units and transforms. It should nevertheless carry provenance and validity flags: a mathematically precise transform does not make an invalid pattern outline or a stale collision mesh valid.

### Derived benchmark: test whether the map improves diagnosis

Ego3D's use of explicit ablations suggests a useful experiment rather than an assumption that more JSON is automatically better. Build a set of representative GitHub Actions artifact cases, each frozen by workflow run ID and source commit. For each case, require the same structured answer: first failed stage; entities and semantic IDs involved; relevant local/world coordinates; evidence supporting the diagnosis; one falsifying check; and the single next experiment. Include at least these contrasts:

| Challenge | Required reasoning | Ground truth |
|---|---|---|
| Invalid pattern vs valid pattern with similar silhouette | Identify upstream topology failure rather than guessing from the rendered fill | Native PatternIR/Sketcher boundary validity and exact crossing edges |
| Same garment from familiar vs unfamiliar camera views | Keep world relations invariant under view changes; correctly handle camera-relative directions | Camera transforms and exact entity coordinates |
| Correct vs swapped seam edge IDs | Reason over semantic relations, not seam colour or index alone | Native seam references and boundary IDs |
| Correct vs incorrect local-to-world transform | Detect front/back, rotation or offset error across all views | Persisted transform matrices and target-relative distances |
| Initial overlap vs post-drape penetration | Identify the earliest checkpoint that violates clearance | Step-0 and checkpoint geometry/clearance metrics |
| Bad collision mesh vs genuinely unstable solver | Distinguish geometry/contact failure from numerical failure | Surface source/currentness, collision diagnostics, finite-state history |
| Valid successful garment | Avoid a default-to-failure bias | Stage gates plus final multi-view and fit measurements |

Use three controlled information conditions: **images only**, **structured map only**, and **images + map**. Keep the prompt, case, source revision and evaluation rubric fixed. The map-only condition measures whether the report contains the necessary geometry; images+map measures whether the visual evidence adds causal information beyond the measurements. Do not expose run outcomes or filenames containing labels that leak the answer to the evaluator.

Adopt benchmark controls inspired by the papers:

- **Viewpoint robustness:** matched rendered views of the same exact scene; test whether diagnoses contradict one another when world facts do not change.
- **Balanced counterfactual pairs:** geometrically mirror/swap relevant components or change a seam reference, then regenerate ground truth; use opposite answers where appropriate instead of relying on class frequency.
- **Permutation robustness:** reorder answer options and entity presentation while requiring the same underlying diagnosis.
- **Per-family scores:** topology, coordinate-frame/transform, orientation/relationship, seam mapping, initial clearance/contact and numerical stability; do not hide a weak category in an overall accuracy.
- **Localization and metric errors:** exact edge/entity accuracy, correct first failed stage, coordinate error in mm normalized by a declared scale (such as mannequin height), stage-order violations, unsupported-claim rate, and false success/failure rate.
- **Causal discipline:** explicitly score whether the answer proposes tuning the solver while an upstream geometry, mapping or placement invariant is still false.

For a first pass, use authored rules and known workflow-failure artifacts to create gold answers; humans adjudicate disputed labels. Only consider model adaptation after the images-only versus map-only versus combined experiment identifies a repeatable reasoning error that remains after the coordinate/geometry evidence has been made complete. The papers do not justify assuming fine-tuning is the first fix.

### Important difference from the papers

Both papers address uncertain geometry inferred from ordinary camera images. FreeCAD has a stronger oracle: the source sketches, transforms, semantic seam links, mannequin target and simulation state are available inside the CAD process. Therefore, do not introduce Grounding-DINO, Depth-Anything or a generic point-cloud reconstruction simply to mimic Ego3D-VLM. The transferable principle is **a shared, explicit spatial representation and a benchmark designed to expose viewpoint shortcuts**. Generate that representation during the FreeCAD workflow and consume only the resulting GitHub Actions artifacts during diagnosis.

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

## Execution success is not garment-fit success

The first successful run of the new dossier exposed a missing semantic layer. In workflow run [38136418907](https://github.com/Uhrendoktor/freecad-cloth/actions/runs/38136418907), the pattern outlines were valid, four sewing relationships were present, the script exited successfully, and the collision metrics reported zero penetrating vertices with a maximum sampled seam correspondence gap of about 2.85 mm. However, the uploaded front/left views showed the fabric gathered around the hips with the upper torso and shoulders uncovered. The scene report's previous `PASSED` label therefore overstated what those checks establish.

The same artifact's final panel bounds span approximately Z=663.16..1235.46 mm, while its metrics record a declared hem level of Z=920 mm and an estimated shoulder reference at Z=1347.5 mm. The cloth extends about 256.84 mm below the declared hem and its highest point is about 112.05 mm below the shoulder reference. Both panels already carry `below-hem-candidate`. The shoulder reference is derived from the avatar bounding box rather than a named anatomical landmark, so these differences are **review signals, not definitive fit ground truth**.

Keep separate statuses for (a) script / workflow execution, (b) topology and physical plausibility, and (c) garment coverage/alignment/attachment. A successful script, non-penetration, and low seam gap cannot certify that the garment covers its intended body regions or remains anchored where intended. The dossier now includes a separate fit-alignment screen; when large Z-bound deviations or the existing below-hem diagnostic are present it should say `review_required`, preserve the collision and seam observations, list the evidence and uncertainty, and request multi-view review. It must not fail the solver or modify numerical thresholds solely because this heuristic fires.

The next iteration should replace the bounding-box shoulder proxy with explicit, persisted world-space body landmarks (at minimum shoulder/neck/axilla/hip) and record intended garment coverage zones and attachment/pinning constraints. The artifact-only evaluation should then score whether the garment's final surface covers the expected zones, whether panel top and hem align to those declared anchors, and whether the relevant attachments remain satisfied across checkpoints. If no authoritative landmark or coverage contract was emitted, the correct output is `not_assessed`, not an invented fit verdict.

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
