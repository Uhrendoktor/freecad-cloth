# Tool State

```yaml
schema: 22
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_issue: 2492
experiment_ledger: 2492
workflow_count: 1
workflow_image: ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3
validation_policy: preserve_canonical_docker_xvfb_freecad_path; fail_closed_evidence; mandatory_human_screenshot_review; artifact_link_alone_insufficient; no_second_workflow
current_main: dc1feac2d7d80b13a5afb5176164c016a05dd88a
production_tissu_fix_merged: false
active_diagnostics: 2537,2482,2535,2540
retired_contact_lanes: 2516,2524
screenshot_review:
  implementation_pr: 2541
  authentication_fix_pr: 2542
  inline_screenshots_required: true
  exact_head_required: true
  garment_final_views: front,rear,right,left,top,bottom
release_gate_changes: none
solver_budget_changes: none
workflow_topology_changes: none
next_gate: exact_head_diagnostic_run_and_human_visual_inspection
```