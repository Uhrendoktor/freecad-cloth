# Agent status

Machine-readable supervisor/release record. Durable guidance lives in `docs/DEVELOPMENT.md` and `docs/PROJECT_STRUCTURE.md`.

## Repository

- Repository: `Uhrendoktor/freecad-cloth`
- Default branch: `main`
- Current main: `20abd7370e2822ff52767c1a96b5a75ee3ecc9ad`.
- Main's latest merges in this release closeout are PR #732 (native Fabric-aware garment hierarchy) and PR #735 (canonical right-shoulder seam edge mapping).
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

- Open PRs at this audit: #651, #659, #745, #754, #755, #756, #757, #758, #759, #760, #761, #762, #763.
- Current release heads:
  - #745 PatternIR runtime boundary: `d0a0128429f6e21b84310b427e236a8fdd025a9e`.
  - #759 sewing correspondence/staged free-sewing contract: `d73601e0573aae10df25ad4d3a9d3a68a4a9507e`.
  - #651 remaining sewing correspondence/diagnostics gaps: `ec6b93df4421e7c0477eca88929c803462d622c5`.
  - #659 canonical garment E2E fixture: `c9fd2aa496fa62fc1bddefa2f43eb0eb3c1819d0`.
  - #756 canonical garment E2E smoke: `e21c8528c47d714033b6bd958ce8e533667e4bfa`.
  - #762 current-main canonical garment E2E acceptance: `9efb24e7658e37741eadaf8cc4e27cbfdec0e68c`.
  - #761 current-main canonical garment E2E repair: `96e31cd76d1d252714226868d748c3815f2e3d18`.
  - #763 shoulder-mapping revert candidate: `f3d1d1c82949026d36c6c2b29df3a3f190e3b6f7`.
  - #760 tunic audit contract alignment: `bfcedf6cf425a2a35755cef3d2e95afc34559b72`.
  - #758 current-main tunic validation: `95d9b6244d8ed14ed3b0da76a7ff5c9e3e854de9`.
  - #755 left-shoulder seam mapping experiment: `1c27e828da09304f7054dda592f3a74364411d13`.
  - #754 shoulder experiment revert: `53aa54f07b8a906de48a1c65e13a6eaf2b5fc30c`.
  - #757 exact seam provenance through PatternIR preview: `c75b93ade22dbe789d19d45629e686d24c70ceea`.
- #732 is merged into main as `03273ddf34e9658a91111e4f6bd575664367b37f`; it is the native garment-hierarchy mainline.
- #735 is merged into main as `20abd7370e2822ff52767c1a96b5a75ee3ecc9ad`; it is the current canonical right-shoulder edge mapping.
- #687 is merged at `27465a33c8765c8572362eeccadc379c5c86ac5c`; it supplied the pinned-stitch fail-closed guard.
- #695 is closed without merge; its PatternIR work was superseded/rebuilt as current-main PR #745.
- #701 is closed without merge; its hierarchy work was superseded by merged #732.
- #702 is closed without merge; its sewing work was rebuilt as current-main PR #759.
- #708 is closed without merge; its garment-E2E workflow addition is historical and is not a separate workflow.
- #713 is closed without merge; the pinned-stitch guard landed through #687.
- The state-sync PR from the earlier snapshot (#730) was closed without merge; this state must only be persisted from the latest verified main snapshot.

## Verified CI / artifacts

- Latest terminal-green canonical main run: #2595 / run ID `35783765670`, head `20abd7370e2822ff52767c1a96b5a75ee3ecc9ad`, terminal-success.
- Verified run jobs: all seven workflow jobs completed successfully.
- Verified artifacts:
  - readme-turntables: `10719791544`
  - sewing-creation-smoke: `10719486915`
  - pattern-production-export: `10719482013`
  - workbench-benchmark: `10719382485`
  - tunic-visual-audit: `10718734057`
- Earlier cancelled runs (#2560/#2584) are historical and must not be reported as whole-workflow success.
- Latest terminal-green complete run is #2595; use this as the current durable CI baseline until main changes again.

## Architecture / durable rules

- Package root: `freecad_cloth/`; domain packages `avatar`, `pattern`, `sewing`, `simulation`; shared packages `common`, `shared`.
- Root Python files are limited to `Init.py`, `InitGui.py`, `sitecustomize.py`.
- Root domain implementations and compatibility shims are forbidden.
- FreeCAD owns editable geometry/persistence; Cloth owns garment semantics; solver owns physics.
- `PatternIR`, `SewingGraph`, `SimulationScene`, `DrapeTarget` remain semantic boundaries.
- `trimesh` stays optional/lazy; CPU reference remains correctness baseline; Tissu remains sandbox-only pending evidence.

## Outstanding gates / next focus

- Keep the one-workflow contract; do not add another E2E workflow.
- Reconcile PatternIR candidates, currently led by #745.
- Reconcile sewing candidates, currently led by #759/#651.
- Reconcile garment-E2E candidates #762/#761/#756/#659 and keep exactly one canonical E2E path.
- Reconcile tunic candidates #763/#760/#758/#755/#754/#757; keep them bounded and evidence-led, with no arbitrary validation-threshold changes.
- Before merging any candidate, validate its exact current-main head with terminal-green canonical CI and inspect its artifacts.

## Agent rules

Inspect → plan → execute → persist → verify. Never weaken tests or multiply workflows. Do not report a PR as merged without live GitHub confirmation. Close issues only with an explicit state reason and durable evidence.
