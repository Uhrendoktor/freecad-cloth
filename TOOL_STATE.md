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
current_release_head: 74eab90b06c46eb4b9d9f888ce98c3c6891e7933
workflow_count: 1
workflow_image: ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3
validation_policy: preserve_canonical_docker_xvfb_freecad_path; fail_closed_evidence; inspect_jobs_logs_artifacts; no_second_workflow
release_gate:
  candidate: PR_1066
  exact_head: 74eab90b06c46eb4b9d9f888ce98c3c6891e7933
  pr_run_state: no_pull_request_run_or_status_on_current_head; latest push run #3437 (35855977273) failed with zero jobs/artifacts; retry rejected with HTTP 403
  supporting_run: 35845226384
  supporting_basic_artifact: 10743635540
  supporting_basic_result: finite_connected_mesh; motion_and_material_acceptance_passed
  supporting_turntable_failure: detached_candidate_on_older_20mm_32iteration_cpu_source
  external_ci_blocker: repeated_zero_job_push_runs; no_pull_request_delivery; no connector access to Actions administration; keep production workflow unchanged
final_gate: exact_head_canonical_pr_green; inspect_jobs_logs_artifacts; merge; merged_main_canonical_green; fresh_repo_audit
open_actionable_issues: [1017, 1020, 1043, 1053, 1067]
closed_research_issues: [1042, 1055]
stale_branch_cleanup: unavailable_via_current_connector; 483_remote_branches_observed
```
