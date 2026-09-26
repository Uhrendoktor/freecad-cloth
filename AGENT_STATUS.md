# Agent status

Machine-readable supervisor/release record. Durable guidance lives in docs/DEVELOPMENT.md.

## Repository
- Repository: Uhrendoktor/freecad-cloth
- Default branch: main
- Validated release code commit: `b43b8a2982e4570f25824509674dad9b66a38677`.
- Later main commits are release-state documentation only and do not alter the validated release code.
- Canonical workflow: .github/workflows/canonical-execution.yml; exactly one workflow.
- Supervisor completion issue: #1017 (closed completed).
- Continuation/recovery issue: #1098 (closed completed).

## Final release outcome
- Release PR #1165 merged into main.
- PR #1177 supplied bounded sewing-smoke stale-task-panel fixes and is integrated.
- PR #1187 hardened README GUI startup/readiness and screenshot-settle handling and is integrated.
- PR #1190 fixed the README publisher blanket artifact extraction path and is integrated.
- PR #1191 repaired the Native Sketcher post-Commit continuation and is integrated.
- PR #1195 repaired README turntable GIF timing and added fail-closed timing assertions; it is integrated.
- Exact PR validation for #1195 passed; merged-main validation subsequently passed the complete canonical graph and publication job.

## Evidence
- Native Sketcher acceptance: passed on the merged release code.
- Sewing staged creation smoke: passed, including correspondence, persistence, invalidation, and UI teardown checks.
- Tunic visual/simulation audit: passed; evidence covers sewing, arrangement, mannequin drape target, diagnostics, persistence, determinism, and SVG/DXF export.
- Basic blanket visual: passed with 16 motion frames at 640x480, 100 ms/frame, finite movement, connected mesh, plausible drape, and material presentation.
- README turntables: all three are 73 frames at 640x480 with uniform 80 ms frame timing; rendered representative frames were inspected from exact canonical artifacts.
- Publication verification confirmed the live README GIFs have the required 640x480, 73-frame, uniform-80-ms structure, the blanket GIF is 640x480 with 16 frames at uniform 100 ms, and the published tunic-front PNG matches the final artifact blob.
- Publisher job #108293224713 successfully populated `docs/screenshots` at publication commit `2a7fd1e`.
- The published turntable GIF Git blobs do not currently reproduce from the downloaded run #3976/#3979 GIF artifact bytes; exact-byte GIF provenance is therefore unverified. The durable ledger does not assert byte-identical publication.
- README references the five stable generated assets: cloth-blanket-motion.gif, cloth-avatar-turntable.gif, cloth-simulation-arranged-turntable.gif, cloth-simulation-draped-turntable.gif, cloth-simulation-draped-front.png.
- Canonical workflow remains fail-closed; no thresholds or validation topology were weakened.

## Reconciled failures and decisions
- Run #3964 exposed a FreeCAD GUI startup race in the README turntable job. PR #1187 added bounded GUI readiness and screenshot redraw/settle waits.
- Run #3966 exposed a deterministic publisher artifact-path bug. PR #1190 corrected only that path.
- PR #1191 repaired Native Sketcher post-Commit continuation through a bounded Qt event-loop deferral with callback-traceback evidence.
- Media audit exposed zero-duration README turntable GIFs. PR #1195 moved `-delay 8` before the frame glob and added uniform-delay assertions.
- Publication provenance reconciliation: the live published assets pass the existing structural/timing gates and the publisher populated `docs/screenshots` at `2a7fd1e`, but direct content-addressed comparison did not reproduce the published GIF blob SHAs from canonical runs #3976/#3979 downloads. This is an evidence/provenance uncertainty, not a demonstrated user-facing media defect; no publisher checksum-manifest workflow change is made in this bounded repair.

## Repository hygiene
- Exactly one GitHub Actions workflow exists.
- No open PRs remain.
- No open issues remain; #1017 and #1098 are closed completed.
- No actionable TODO/FIXME/XXX findings were identified in the audited code/state.
- Branch deletion remains connector-limited; no claim of full remote branch purge is made. Scheduled retention remains fail-closed and present.

## Current gate
- Release scope: complete.
- Exact-head validation: complete.
- Merged-main validation: complete.
- Artifact and rendered-output inspection: complete.
- README publication validation: complete for structural/timing properties; exact-byte GIF provenance remains unverified.
- Final repository/issue/PR reconciliation: complete.
