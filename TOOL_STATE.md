# Tool State

```yaml
schema: 6
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_task: cloth-sewing-workbench-structure-and-roadmap
current_main: 6ac97ec7b1019252ba650d1aa1c2107ece901f5f
open_prs: []
active_release_gates: [155, 278, 284, 298, 297, 145]
queued_release_gates: [275, 162, 360]
non_blocking: [148]
closed_this_pass: [551, 549, 546, 543, 536, 535, 541, 538]

architecture:
  package_root: freecad_cloth/
  domain_packages: [avatar, pattern, sewing, simulation]
  shared_packages: [common, shared]
  root_python: [Init.py, InitGui.py, sitecustomize.py]
  root_domain_implementations: forbidden
  root_compatibility_shims: forbidden
  drape_target_owner: freecad_cloth.simulation.DrapeTarget
  diagnostics_owner: freecad_cloth.common.ClothDiagnostics
  policy: migrate_callers_to_package_namespace; never_restore_root_domain_modules

workflow_contract:
  workflow_count: 1
  workflow: .github/workflows/canonical-execution.yml
  image: ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3
  image_policy: publish_on_main_when_missing; PR validation may build locally with the same tag
  screenshot_display: 1280x720
  screenshot_outputs:
    - docs/images/generated/cloth-simulation-draped.png
    - docs/images/generated/cloth-simulation-draped-front.png
    - docs/images/generated/cloth-simulation-draped-rear.png
    - docs/images/generated/cloth-simulation-draped-left.png
    - docs/images/generated/cloth-simulation-draped-right.png
    - docs/images/generated/cloth-simulation-draped-top.png
    - docs/images/generated/cloth-simulation-draped-bottom.png
  screenshot_artifacts: [tunic-visual-audit]
  policy: preserve_existing_Docker_Xvfb_PNG_path; one canonical tunic visual audit; no_second_workflow

latest_verified_ci:
  run_id: 35496744774
  run_number: 2042
  commit: a5c87145d20c5358296eb1612b83bd677df4225d
  status: completed
  conclusion: success
  python_job: success
  gui_job: success
  note: PR #551 passed canonical verification and squash-merged to main as e151cb27c1f317b15fc50ed904b9cc3491f1e547; supervisor state was then synchronized in commit 6ac97ec7b1019252ba650d1aa1c2107ece901f5f.

policy:
  - inspect_open_prs_and_issues_before_changes
  - one_canonical_workflow
  - terminal_green_CI_before_dependent_merge_or_close
  - review_diffs_before_merge
  - never_weaken_GUI_or_PNG_assertions
  - close_issues_only_with_explicit_state_reason
  - recut_branches_from_current_main

current_focus:
  imports: package-qualified module namespace is authoritative
  structure: package-tree cleanup remains historical; current active release focus is M0 garment visual trust (#472)
  ci_status: latest verified canonical run is 35496744774 (#2042) on PR head a5c87145d20c5358296eb1612b83bd677df4225d; merged main head is e151cb27c1f317b15fc50ed904b9cc3491f1e547, followed by state-only sync commit 6ac97ec7b1019252ba650d1aa1c2107ece901f5f
  visual_regression: canonical GUI audit is green; diagnostic drape metrics are structured/diagnostic-first, while human visual review remains tracked by #472
```
