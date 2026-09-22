# Tool State

```yaml
schema: 6
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
workflow_blob_sha: ad6c8789d91ce3ca34825f055087e75b976647b4
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_task: "#647 release lifecycle"
current_main: 5acc453e12e1462481b85df49ba16a9c31483ee1
open_prs: [695, 702, 704, 706, 711, 719, 721, 722]
historical_closed_release_prs: [708, 701]
m0_issue_472: closed-complete
one_workflow_policy: enforced

workflow_contract:
  workflow_count: 1
  triggers: [push, pull_request, workflow_dispatch]
  jobs:
    - python: "Python and FreeCAD non-GUI tests"
    - gui-sewing-creation: "Sewing staged creation smoke"
    - gui-pattern-export: "Pattern production export smoke"
    - gui-tunic-visual: "Full tunic visual and simulation audit"
    - gui-turntables: "README turntables"
    - publish-readme-turntables: "Publish README turntables"
    - benchmark: "Measured FreeCAD workbench benchmark"
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
  turntable_outputs: [cloth-avatar-turntable.gif, cloth-simulation-arranged-turntable.gif, cloth-simulation-draped-turntable.gif]
  turntable_frames: 73
  turntable_artifact: readme-turntables
  readme_publish_branch: docs/screenshots
  pr_turntable_generation: enabled
  readme_publish_on_main_merge: enabled
  policy: preserve_existing_Docker_Xvfb_PNG_path; one_canonical_tunic_visual_audit; PR_turntable_validation; publish_stable_turntables_after_main_merge; no_second_workflow

latest_verified_ci:
  run_id: 35782037267
  run_number: 2520
  commit: 5acc453e12e1462481b85df49ba16a9c31483ee1
  status: completed
  conclusion: success
  event: push
  jobs:
    python: success
    gui-sewing-creation: success
    gui-pattern-export: success
    gui-tunic-visual: success
    gui-turntables: success
    publish-readme-turntables: success
    benchmark: success
  artifact_id: 10718318860
  artifact_name: tunic-visual-audit
  artifacts:
    pattern-production-export: 10718573486
    sewing-creation-smoke: 10718403724
    tunic-visual-audit: 10718318860
    readme-turntables: 10718134220
    workbench-benchmark: 10717974490

release_slices:
  - "#695 open; current-main PatternIR runtime boundary"
  - "#702 open; stale-base sewing release slice; currently unmergeable"
  - "#704 open; current-main single-scene PatternIR follow-up"
  - "#706 open; current-main canonical garment E2E candidate"
  - "#711 open; stale-base PatternIR simulation-boundary overlap"
  - "#719 open; current-main pinned-stitch feasibility guard"
  - "#721 open; current-main right-shoulder seam-edge A/B"
  - "#722 open; current-main solver seam-sampling A/B"
  - "#708 closed without merge; historical garment-E2E workflow attempt"
  - "#701 closed without merge; historical garment-hierarchy attempt"

outstanding_gates:
  - reconcile overlapping PatternIR PRs #695/#704/#711 before merging duplicate implementations
  - rebase/reassess stale #702 and #711 against current main
  - validate #706 on its exact current-main head before any workflow contract change
  - validate #719 independently; keep #721/#722 diagnostic experiments bounded
  - continue M1/M2 release gates #473/#475/#476
  - preserve one canonical workflow and fail-closed validation

policy:
  - inspect_open_prs_and_issues_before_changes
  - one_canonical_workflow
  - terminal_green_CI_before_dependent_merge_or_close
  - review_diffs_before_merge
  - never_weaken_GUI_or_PNG_assertions
  - close_issues_only_with_explicit_state_reason
  - recut_branches_from_current_main

current_focus:
  ci_status: current main 5acc453e12e1462481b85df49ba16a9c31483ee1 is terminal-green in canonical run 35782037267 (#2520)
  queue_status: open_prs_are_695_702_704_706_711_719_721_722
  m0_status: "#472 closed-complete"
  next_supervisor_focus: reconcile PatternIR overlaps, stale-base release slices, and the current-main pinned-stitch/E2E work without multiplying workflows
```
