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
current_release_head: 97f145e8214a8f951030eabf7fc14d9255b7dc6
workflow_count: 1
workflow_image: ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3
validation_policy: preserve_canonical_docker_xvfb_freecad_path; fail_closed_evidence; inspect_jobs_logs_artifacts; no_second_workflow
release_gate:
  candidate: PR_1066
  exact_head: 97f145e8214a8f951030eabf7fc14d9255b7dc6
  pr_run_state: no_pull_request_run_or_status_after_close_reopen; latest_zero_job_retry_35855453586_forbidden_403_cannot_be_retried
  supporting_run: 35845226384
  supporting_basic_artifact: 10743635540
  supporting_basic_result: finite_connected_mesh; motion_and_material_acceptance_passed
  supporting_turntable_failure: detached_candidate_on_older_20mm_32iteration_cpu_source
  external_ci_blocker: repeated_zero_job_push_runs; no connector access to Actions administration; keep production workflow unchanged
final_gate: exact_head_canonical_pr_green; inspect_jobs_logs_artifacts; merge; merged_main_canonical_green; fresh_repo_audit
open_actionable_issues: [1017, 1020, 1043, 1053, 1067]
closed_research_issues: [1042, 1055]
stale_branch_cleanup: unavailable_via_current_connector
```
