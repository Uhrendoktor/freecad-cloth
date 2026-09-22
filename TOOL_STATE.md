# Tool State

```yaml
schema: 6
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
workflow_blob_sha: ad6c8789d91ce3ca34825f055087e75b976647b4
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_task: "#647 release lifecycle"
current_main: 7e50a27caf0c7a6fea553e2f3d542cb0e17738f6
open_prs: [651, 659, 693, 730, 745, 756, 757, 760, 761, 762, 766, 768, 769, 770, 771, 772, 773, 774, 775, 776, 777]
merged_release_slices: [687, 732, 735, 759]
historical_closed_release_prs: [695, 701, 702, 708, 713]
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
  screenshot_display: 1280x720
  screenshot_artifact: tunic-visual-audit
  turntable_outputs: [cloth-avatar-turntable.gif, cloth-simulation-arranged-turntable.gif, cloth-simulation-draped-turntable.gif]
  turntable_frames: 73
  turntable_artifact: readme-turntables
  readme_publish_branch: docs/screenshots
  policy: preserve_existing_Docker_Xvfb_PNG_path; one_canonical_workflow; no_second_workflow

latest_verified_ci:
  run_id: 35785019676
  run_number: 2636
  commit: 7e50a27caf0c7a6fea553e2f3d542cb0e17738f6
  status: completed
  conclusion: success
  jobs:
    python: success
    gui-sewing-creation: success
    gui-pattern-export: success
    gui-tunic-visual: success
    gui-turntables: success
    publish-readme-turntables: success
    benchmark: success
  artifacts:
    pattern-production-export: 10720125000
    readme-turntables: 10720120231
    sewing-creation-smoke: 10719866290
    workbench-benchmark: 10719504060
    tunic-visual-audit: 10719494242

release_slices:
  patternir:
    current_candidates: [745, 773, 774]
    historical_closed: [695]
  sewing:
    current_candidates: [776, 651]
    merged_baseline: 759
    historical_closed: [702]
  garment_hierarchy:
    followups: [693, 775]
    merged_baseline: 732
    historical_closed: [701]
  garment_e2e:
    current_candidates: [762, 761, 756, 659]
    historical_closed: [708]
  pinned_stitch:
    merged_baseline: 687
    historical_closed: [713]
  tunic_validation:
    current_candidates: [777, 760, 768, 766, 757]
    related_experiments: [769, 770]

outstanding_gates:
  - preserve one canonical workflow
  - reconcile PatternIR candidates into one validated line
  - reconcile sewing candidates after merged #759
  - reconcile hierarchy follow-ups after merged #732
  - reconcile garment-E2E candidates while keeping one canonical E2E path
  - reconcile tunic/reversion candidates without threshold weakening
  - require terminal-green exact-head CI and artifact inspection before dependent merges

policy:
  - inspect_open_prs_and_issues_before_changes
  - one_canonical_workflow
  - terminal_green_CI_before_dependent_merge_or_close
  - review_diffs_before_merge
  - never_weaken_GUI_or_PNG_assertions
  - close_issues_only_with_explicit_state_reason
  - recut_branches_from_current_main

current_focus:
  ci_status: current main 7e50a27caf0c7a6fea553e2f3d542cb0e17738f6 is terminal-green in canonical run 35785019676 (#2636)
  queue_status: active open PRs are [651,659,693,730,745,756,757,760,761,762,766,768,769,770,771,772,773,774,775,776,777]
  next_supervisor_focus: reconcile the current-main PatternIR, sewing, hierarchy, garment-E2E, and tunic-validation candidates after the merged release slices #732/#735/#759, preserving the one-workflow contract
```
