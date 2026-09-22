# Tool State

```yaml
schema: 6
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
workflow_blob_sha: ad6c8789d91ce3ca34825f055087e75b976647b4
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_task: "#647 release lifecycle"
current_main: 03273ddf34e9658a91111e4f6bd575664367b37f
open_prs: [659, 695, 702, 706, 726, 727, 728, 731, 734, 735, 738, 739, 740, 741, 743, 744, 745, 746, 747, 749, 750, 751, 752]
merged_release_slices: [687, 732]
historical_closed_release_prs: [701, 708, 713]
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

latest_verified_exact_main:
  current_main: 03273ddf34e9658a91111e4f6bd575664367b37f
  run_id: 35783458955
  run_number: 2584
  status: completed
  conclusion: cancelled
  note: main advanced through merged PR #732 while the canonical run was active; the run is not terminal-green.

latest_verified_job_level:
  run_id: 35783007599
  run_number: 2560
  commit: cc93d0f8cd9451cc96667de5584cecf38c7a6350
  tunic_rerun_job_id: 106933253526
  tunic_rerun_conclusion: success
  artifacts:
    pattern-production-export: 10719155792
    sewing-creation-smoke: 10718832779
    tunic-visual-audit: 10719056530
    readme-turntables: 10719560452
    workbench-benchmark: 10718268347

historical_terminal_green:
  run_id: 35782037267
  run_number: 2520
  commit: 5acc453e12e1462481b85df49ba16a9c31483ee1
  conclusion: success
  note: superseded by later main merges.

release_slices:
  sewing:
    current_main_candidates: [746, 731]
    stale_or_replacement: [702, 728]
  patternir:
    current_main_candidates: [747]
    stale_or_duplicate: [695, 744, 745]
  garment_hierarchy:
    merged: [732]
    stale_or_duplicate: [701, 739, 741, 743]
  garment_e2e:
    current_main_candidates: [750, 726]
    stale_or_duplicate: [659, 706]
  tunic_validation:
    current_main_candidates: [749, 751, 752]
    diagnostic_ancestors: [734, 735, 738, 740, 727]

outstanding_gates:
  - fresh terminal-green canonical validation on current main after PR #732
  - reconcile PatternIR overlap: #747 vs #695/#744/#745
  - reconcile sewing overlap: #746/#731 vs #702/#728
  - reconcile garment-E2E overlap: #750/#726/#659/#706
  - keep tunic A/B work bounded and evidence-led; no arbitrary threshold changes
  - preserve one canonical workflow; do not add another E2E workflow

policy:
  - inspect_open_prs_and_issues_before_changes
  - one_canonical_workflow
  - terminal_green_CI_before_dependent_merge_or_close
  - review_diffs_before_merge
  - never_weaken_GUI_or_PNG_assertions
  - close_issues_only_with_explicit_state_reason
  - recut_branches_from_current_main

current_focus:
  ci_status: current main 03273ddf34e9658a91111e4f6bd575664367b37f has no terminal-green canonical run; exact-head run 35783458955 (#2584) was cancelled during rapid main evolution.
  queue_status: active open PRs are [659,695,702,706,726,727,728,731,734,735,738,739,740,741,743,744,745,746,747,749,750,751,752]
  next_supervisor_focus: obtain fresh terminal-green current-main validation, then collapse duplicate release candidates to one validated current-main PR per sewing, PatternIR, garment hierarchy/E2E, and tunic-validation concern.
```
