# Tool State

```yaml
schema: 6
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_task: cloth-sewing-workbench-structure-and-roadmap
current_main: 35cb29db06e57fdf58a137fbe4e20279fb8225dd
open_prs: []
active_release_gates: [155, 278, 284, 298, 297, 145]
queued_release_gates: [275, 162, 360]
non_blocking: [148]
closed_this_pass: [598, 595, 597, 594, 590, 593, 572, 581, 571, 592, 495, 556, 560, 567, 563, 565, 568, 574, 578, 579, 580]

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
  run_id: 35580478353
  run_number: 2087
  commit: 226fb38f2795450af42c6d2429dddc8c1429627f
  status: completed
  conclusion: success
  python_job: success
  gui_job: success
  artifact_id: 10629862765
  artifact_sha256: e6d420236b42407855d06624e41a532a1c46ae56990c31b496183a3f1c4266a7
  note: PR #598 merged to main as 35cb29db06e57fdf58a137fbe4e20279fb8225dd after terminal-green canonical verification and direct six-view artifact inspection. Drape panels are finite with one connected component each; seam correspondence diagnostics report a maximum gap of 452.652642 mm. These measurements remain diagnostic-only; #472 visual trust remains unresolved.

policy:
  - inspect_open_prs_and_issues_before_changes
  - one_canonical_workflow
  - terminal_green_CI_before_dependent_merge_or_close
  - review_diffs_before_merge
  - never_weaken_GUI_or_PNG_assertions
  - close_issues_only_with_explicit_state_reason
  - recut_branches_from_current_main

current_focus:
  queue_cleanup: #595 is complete and #597 was a duplicate supervisor PR closed without merge; no open implementation PR remains
  imports: package-qualified module namespace is authoritative
  structure: package-tree cleanup remains historical; current active release focus is M0 garment visual trust (#472)
  ci_status: latest verified canonical run is 35580478353 (#2087) on PR head 226fb38f2795450af42c6d2429dddc8c1429627f; merged main head is 35cb29db06e57fdf58a137fbe4e20279fb8225dd
  visual_regression: canonical GUI audit is green and all six drape views are present; both panels are connected/finite and classified structurally-plausible, while post-drape seam evidence exposes large correspondence gaps. #472 remains unresolved; do not resume blind fixture A/B churn.
  next_supervisor_focus: localize post-drape seam/target coherence root cause from the canonical evidence without solver redesign, fixture A/B churn, or a second workflow.
```
