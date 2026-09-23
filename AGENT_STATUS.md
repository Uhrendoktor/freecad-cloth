# Agent status

Machine-readable supervisor/release record. Durable guidance lives in `docs/DEVELOPMENT.md`.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Current main: `ccac198eae37bb162830895b1d8259ca84d7047f`
- Canonical workflow: `.github/workflows/canonical-execution.yml`; exactly one workflow.
- Supervisor completion issue: #1017.
- Active release candidate: PR #1069, branch `supervisor/release-fixture-200mm-20260923`, live head `e5676aa8091fd55d3b17a5a2cb71122e41683433`.

## Implemented release slice

- Native `CreatePieceWithSketch` is idempotent and has focused headless regression coverage.
- Native Sketcher acceptance explicitly bootstraps `InitGui.py`, emits flushed stage markers, verifies placed/world-space seam endpoints, Sketcher-side editing, save/reload and downstream invalidation.
- Blanket-over-Cube acceptance uses geometry-appropriate mesh collision, effective solver iterations, stable integration, opposite top-edge corner pins, and the existing fail-closed mesh thresholds.
- README turntable uses the same blanket fixture, requires finite connected mesh/drape sanity, and rejects duplicate turntable frames.
- Installation/docs index points users to the human-facing User Guide.

## CI evidence

- Supporting run #3331 / Actions `35845226384` executed real FreeCAD/Xvfb validation for the 200 mm × 200 mm Blanket-over-Cube fixture; artifact `10743635540` contains passing mesh, drape, motion, material and 16-frame evidence.
- Historical full canonical run #3388 / Actions `35847040632` executed the real FreeCAD/Xvfb graph; Python, sewing, export, blanket visual, README turntable and tunic audit passed, while Native Sketcher acceptance failed after its fail-closed invocation. The current `main` acceptance fixture now explicitly bootstraps `InitGui.py` and checks placed/world-space seam endpoints, save/reload and invalidation; that fix still requires exact-head canonical execution.
- Current push validation remains blocked before job allocation: main run #3423 / Actions `35849501653` and release candidate run #3428 / Actions `35849536356` both terminate `failure` with zero jobs and zero artifacts. PR #1069 has no `pull_request` run/check.
- The canonical workflow remains exactly one production workflow with unchanged validation thresholds/timeouts.

## Branch cleanup

- Historical audit found 482 remote branches. The installed GitHub connector exposes no branch-deletion operation, so stale-branch cleanup is not claimed complete.
- The retention schedule job exists in the canonical workflow, but only schedule run #3225 / Actions `35839191664` is currently visible; later scheduled executions are not appearing.

## External CI blocker

- GitHub Actions currently creates push runs that terminate with `failure` and zero jobs, while no `pull_request` run/check is exposed for the active release PR #1069. The connector can read rulesets (currently `[]`) but does not expose the repository/inherited Actions policy endpoints needed to inspect event restrictions.
- Issue #1053 is the durable restoration path: inspect repository/inherited Actions event policy with repository administration access, then trigger a real `pull_request:synchronize` or reopen on PR #1069 and verify a non-zero canonical job graph.

## Current gate

- PR #1069 is the sole open release PR; #1066 is closed as superseded and #1042/#1055 are closed evidence/diagnostic issues.
- Do not merge PR #1069 or close #1017/#1067 until exact-head canonical validation is terminal-green with all relevant jobs/logs/artifacts inspected, followed by merged-main canonical validation and a fresh final audit.
