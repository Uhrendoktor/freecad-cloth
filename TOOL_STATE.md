# Tool State

```yaml
schema: 12
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_issue: 1017
active_release_pr: 1073
active_release_branch: supervisor/final-release-20260923
current_main: refs/heads/main (resolve current tip at audit time)
workflow_count: 1
workflow_image: ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3
validation_policy: preserve_canonical_docker_xvfb_freecad_path; fail_closed_evidence; inspect_jobs_logs_artifacts; no_second_workflow
release_gate:
  candidate: PR_1073
  exact_head: resolve current PR #1073 head at validation time
  pr_run_state: no pull_request run/status; recent candidate push runs fail pre-job with zero jobs/artifacts
  supporting_run: 35845226384
  supporting_artifact: 10743635540
  supporting_run_result: 200 mm Blanket-over-Cube real FreeCAD/Xvfb acceptance passed; final checkpoint and motion frames inspected
  external_ci_blocker: current Actions event/schedule delivery is externally blocked; keep production workflow unchanged
final_gate: exact_head_canonical_pr_green; inspect_jobs_logs_artifacts; merge; merged_main_canonical_pr_green; fresh_repo_audit
open_actionable_issues: [1017, 1020, 1043, 1053, 1067]
```

closed_research_issues: [1042, 1055]
stale_branch_cleanup: unavailable_via_current_connector; 486_remote_branches_observed
