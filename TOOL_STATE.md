# Tool State

```yaml
schema: 13
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_issue: 1017
active_release_pr: 1066
active_release_branch: supervisor/complete-audit-20260923
current_main: ccac198eae37bb162830895b1d8259ca84d7047f
current_release_head: 55093e754484ee5fed4b94e0ce26575024707e16
workflow_count: 1
workflow_image: ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3
validation_policy: preserve_canonical_docker_xvfb_freecad_path; fail_closed_evidence; inspect_jobs_logs_artifacts; no_second_workflow
release_gate:
  candidate: PR_1066
  exact_head: 55093e754484ee5fed4b94e0ce26575024707e16
  pr_run_state: no_pull_request_run_or_status_on_current_head; validation_probe_pr_1070_same_head_also_no_pull_request_run; latest_push_run_35856489062_failed_with_zero_jobs_artifacts
  supporting_run: 35845226384
  supporting_basic_artifact: 10743635540
  supporting_basic_result: finite_connected_mesh; motion_and_material_acceptance_passed
  supporting_turntable_failure: detached_candidate_on_older_20mm_32iteration_cpu_source
  external_ci_blocker: repeated_zero_job_push_runs; no_pull_request_delivery; no connector access to Actions administration; keep production workflow unchanged
final_gate: exact_head_canonical_pr_green; inspect_jobs_logs_artifacts; merge; merged_main_canonical_green; fresh_repo_audit
open_actionable_issues: [1017, 1020, 1043, 1053, 1067]
closed_research_issues: [1042, 1055]
validation_probe_pr: 1070
validation_probe_result: closed_no_pull_request_run
latest_zero_job_run: 35856489062
stale_branch_cleanup: unavailable_via_current_connector; many remote agent/supervisor branches remain
```
