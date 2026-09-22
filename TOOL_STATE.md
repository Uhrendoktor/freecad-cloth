# Tool State

```yaml
schema: 6
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
workflow_blob_sha: ad6c8789d91ce3ca34825f055087e75b976647b4
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_task: "#647 release lifecycle"
current_main: 20abd7370e2822ff52767c1a96b5a75ee3ecc9ad
open_prs: [651, 659, 745, 754, 755, 756, 757, 758, 759, 760, 761, 762, 763]
merged_release_slices: [687, 732, 735]
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
  run_id: 35783765670
  run_number: 2595
  commit: 20abd7370e2822ff52767c1a96b5a75ee3ecc9ad
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
    readme-turntables: 10719791544
    sewing-creation-smoke: 10719486915
    pattern-production-export: 10719482013
    workbench-benchmark: 10719382485
    tunic-visual-audit: 10718734057

release_slices:
  patternir:
    current_candidate: 745
    historical_rebuild: 695
  sewing:
    current_candidates: [759, 651]
    historical_rebuild: 702
  garment_hierarchy:
    merged: 732
    historical_closed: [701]
  garment_e2e:
    current_candidates: [762, 761, 756, 659]
    historical_closed: [708]
  pinned_stitch:
    merged: 687
    historical_closed: [713]
  tunic_validation:
    current_candidates: [763, 760, 758, 755, 754, 757]
    diagnostic_policy: no_arbitrary_threshold_changes

outstanding_gates:
  - keep the single canonical workflow
  - reconcile PatternIR candidate #745
  - reconcile sewing candidates #759 and #651
  - reconcile garment-E2E candidates #762/#761/#756/#659
  - reconcile tunic-validation candidates without threshold weakening
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
  ci_status: current main 20abd7370e2822ff52767c1a96b5a75ee3ecc9ad is terminal-green in canonical run 35783765670 (#2595)
  queue_status: active open PRs are [651,659,745,754,755,756,757,758,759,760,761,762,763]
  next_supervisor_focus: reconcile the current-main PatternIR, sewing, garment-E2E, and tunic-validation candidates, preserving the one-workflow contract and validating exact heads before merge
```
