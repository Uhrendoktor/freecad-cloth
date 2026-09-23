# Tool State

```yaml
schema: 11
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_issue: 1017
active_release_pr: 1063
predecessor_release_pr: 1058
active_release_branch: supervisor/root-completion-20260923
current_main: dad152e634bcf454bc71aa02f4c1bfa858c154c1
active_candidate_head: e0b075508b008b19b65ebb0a8be6392e01e63b3f
validation_alias_pr: 1065
validation_alias_head: e0b075508b008b19b65ebb0a8be6392e01e63b3f
workflow_count: 1
workflow_image: ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3
validation_policy: preserve_canonical_docker_xvfb_freecad_path; fail_closed_evidence; inspect_jobs_logs_artifacts; no_second_workflow
release_gate:
  candidate: PR_1063
  predecessor: PR_1058_closed_without_merge
  exact_head: b95bedb7e1627f178aba437cbd8c13f62842e882
  exact_head_pr_run_state: no_pull_request_run_or_status; validation_alias_1065_reopen_also_no_run
  diagnostic_run: 35845914342
  diagnostic_result: AppRun_cli_and_FreeCAD_Sketcher_import_probes_pass; native_acceptance_times_out_after_8m_with_zero_byte_log
  supporting_run: 35844023654
  supporting_run_result: all_canonical_jobs_passed_except_native_Sketcher_acceptance_timeout
  stable_blanket_artifact: workflow_artifact_10743635540
  candidate_repairs:
    - idempotent_native_CreatePieceWithSketch
    - InitGui_bootstrap_before_workbench_activation
    - Path_import_and_stage_marker_definition
    - blanket_turntable_Shape_BoundBox_dimensions
  external_ci_blocker: pull_request_and_push_event_delivery_can_produce_no_workflow_run_or_zero_jobs; validation_prs_1060_1061_reproduced_no_run; do_not_change_workflow_topology
final_gate: exact_head_canonical_pr_green; inspect_jobs_logs_artifacts; merge; merged_main_canonical_pr_green; fresh_repo_audit
open_actionable_issues: [1017, 1020, 1041, 1042, 1043, 1048, 1053, 1055]
```
