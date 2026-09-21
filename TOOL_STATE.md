# Tool State

```yaml
schema: 6
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_task: cloth-sewing-workbench-structure-and-roadmap
current_main: ed25f2044853025c2db844a91cb0116242583042
open_prs: []
active_release_gates: [155, 278, 284, 298, 297, 145]
queued_release_gates: [275, 162, 360]
non_blocking: [148]
closed_this_pass: [594, 590, 593, 572, 581, 571, 592, 495, 556, 560, 567, 563, 565, 568, 574, 578, 579, 580]

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
  run_id: 35551331000
  run_number: 2084
  commit: 1934c16936ccc45be2f10487ffcacaebbe7f8356
  status: completed
  conclusion: success
  python_job: success
  gui_job: success
  artifact_id: 10617779616
  note: PR #594 merged to main as ed25f2044853025c2db844a91cb0116242583042 after six-view review found materially reduced side stand-off versus the 30 mm baseline; #472 human visual trust remains unresolved.

policy:
  - inspect_open_prs_and_issues_before_changes
  - one_canonical_workflow
  - terminal_green_CI_before_dependent_merge_or_close
  - review_diffs_before_merge
  - never_weaken_GUI_or_PNG_assertions
  - close_issues_only_with_explicit_state_reason
  - recut_branches_from_current_main

current_focus:
  queue_cleanup: all open PRs are closed; active queue is #472 plus execution-required agent issues #555/#576/#585
  imports: package-qualified module namespace is authoritative
  structure: package-tree cleanup remains historical; current active release focus is M0 garment visual trust (#472)
  ci_status: latest verified canonical run is 35551331000 (#2084) on PR head 1934c16936ccc45be2f10487ffcacaebbe7f8356; merged main head is ed25f2044853025c2db844a91cb0116242583042
  visual_regression: canonical GUI audit is green; 8 mm authored clearance reduces stand-off but does not yet satisfy the human worn-garment gate.
```
