# Tool State

```yaml
schema: 21
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_issue: 2492
experiment_ledger: 2492
workflow_count: 1
workflow_image: ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3
validation_policy: preserve_canonical_docker_xvfb_freecad_path; fail_closed_evidence; inspect_jobs_logs_artifacts; mandatory_human_screenshot_review; no_second_workflow
visual_review_policy:
  mandatory_human_inspection: true
  governing_record: issue_or_pr_2492_children
  inline_screenshots_required: true
  artifact_link_alone_insufficient: true
  simulation_checkpoints: step_0_plus_experiment_checkpoints
  garment_final_views: front_rear_right_left_top_bottom
  visual_review_retention_days: 14
  terminal_requires_visual_review_record: true
recovery:
  main: e3e66e29938d5c71512eec08bc26b2c5a244aa41
  production_tissu_fix_merged: false
  sparse_orientation_status: falsified_and_retired
  active_ladder_pr: 2481
  active_process_pr: 2527
  release_gate_changes: none
  solver_budget_changes: none
  workflow_topology_changes: none
  next_gate: exact_head_ladder_2481_then_first_failure_review
```
