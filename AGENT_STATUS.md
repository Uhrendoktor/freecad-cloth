# Agent status

Machine-readable supervisor/release record. Durable guidance lives in `docs/DEVELOPMENT.md` and `docs/PROJECT_STRUCTURE.md`.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Current main: `7e50a27caf0c7a6fea553e2f3d542cb0e17738f6`.
- Main release merges recorded in this closeout: #687 pinned-stitch guard, #732 native garment hierarchy, #735 right-shoulder seam mapping, #759 sewing correspondence/staged free-sewing contract.
- M0 issue #472 is closed; its visual-trust work is complete as currently defined.
- Exactly one workflow exists under `.github/workflows/`: `.github/workflows/canonical-execution.yml`.
- CI policy: preserve the Docker/Xvfb FreeCAD path and do not add a second workflow.

## Canonical workflow contract

- Triggers: `push`, `pull_request`, `workflow_dispatch`.
- Jobs: Python and FreeCAD non-GUI tests; Sewing staged creation smoke; Pattern production export smoke; Full tunic visual and simulation audit; README turntables; Publish README turntables; Measured FreeCAD workbench benchmark.
- Workflow blob: `ad6c8789d91ce3ca34825f055087e75b976647b4`.
- FreeCAD image: `ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3`.
- Preserve the existing Docker/Xvfb PNG/screenshot path, one tunic visual audit, turntable generation/publication, and one-workflow policy.

## Release / PR state

- Open PRs at this audit: #651, #659, #693, #730, #745, #756, #757, #760, #761, #762, #766, #768, #769, #770, #771, #772, #773, #774, #775, #776, #777.
- Current-main heads (base `7e50a27caf0c7a6fea553e2f3d542cb0e17738f6)): #693 `58cd03a495dfd330708049b177abbf5b9048bb2b`, #745 `ae2eef6662de84fe53ceb9e17f082c9870ce88e0`, #773 `0a3d330730e933a4b7321162a889c260ace480c2`, #774 `faf63e8074fdd7f564464147f1b15e3681e3f4d1`, #775 `e60eec82d860b84744cc85ac121dc4d55460e3a2`, #776 `2dc9fe997f51fedbc7e3018c3c50742eb055b286`, #777 `198384baa5107d0ccebec52a3cb11caf0badb718`.
- Older-base open candidates: #772/#771/#770/#769/#768/#766 are based on `2e5294813b6a2bd40876b9b56fa3f8a7ebc1e18b`; #762/#761/#760/#757/#756/#651/#659 are based on `20abd7370e2822ff52767c1a96b5a75ee3ecc9ad`.
- #695 is closed without merge; PatternIR work was rebuilt as current-main candidates, now including #745/#773/#774.
- #701 is closed without merge; hierarchy work landed through merged #732. Open #693/#775 are follow-up candidates.
- #702 is closed without merge; sewing work landed through merged #759. Open #776 is the current-main sewing/GUI follow-up and #651/#762-era work remains to reconcile.
- #708 is closed without merge; its garment-E2E workflow addition is historical and is not a separate workflow.
- #713 is closed without merge; pinned-stitch protection landed through #687.
- #730 is the state-sync PR for this issue.

## Verified CI / artifacts

- Latest terminal-green canonical main run: #2636 / run ID `35785019676`, head `7e50a27caf0c7a6fea553e2f3d542cb0e17738f6`, terminal-success.
- All seven workflow jobs completed successfully on that run.
- Verified artifacts:
  - pattern-production-export: `10720125000`
  - readme-turntables: `10720120231`
  - sewing-creation-smoke: `10719866290`
  - workbench-benchmark: `10719504060`
  - tunic-visual-audit: `10719494242`
- Earlier cancelled runs are historical and must not be reported as whole-workflow success.
- Use #2636 as the current durable CI baseline until main changes again.

## Architecture / durable rules

- Package root: `freecad_cloth/`; domain packages `avatar`, `pattern`, `sewing`, `simulation`; shared packages `common`, `shared`.
- Root Python files are limited to `Init.py`, `InitGui.py`, `sitecustomize.py`.
- Root domain implementations and compatibility shims are forbidden.
- FreeCAD owns editable geometry/persistence; Cloth owns garment semantics; solver owns physics.
- `PatternIR`, `SewingGraph`, `SimulationScene`, `DrapeTarget` remain semantic boundaries.
- `trimesh` stays optional/lazy; CPU reference remains correctness baseline; Tissu remains sandbox-only pending evidence.

## Outstanding gates / next focus

- Keep the single canonical workflow; do not add another E2E workflow.
- Reconcile PatternIR current-main candidates (#745/#773/#774 and related older-base branches) into one validated line.
- Reconcile sewing current-main candidates (#776/#651 and older-base branches) after merged #759.
- Reconcile garment-hierarchy follow-ups (#693/#775) after merged #732.
- Reconcile garment-E2E candidates (#762/#761/#756/#659) while keeping one canonical E2E path.
- Reconcile bounded tunic/reversion candidates (#777 and older-base #768/#766/#760/#757), preserving evidence-led validation and avoiding arbitrary hard thresholds.
- Before any dependent merge/close, validate the exact PR head with terminal-green canonical CI and inspect artifacts.

## Agent rules

Inspect → plan → execute → persist → verify. Never weaken tests or multiply workflows. Do not report a PR as merged without live GitHub confirmation. Close issues only with an explicit state reason and durable evidence.
