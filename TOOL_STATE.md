# Tool State

```yaml
schema: 12
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_issue: 1017
continuation_issue: 1081
active_release_pr: 1075
active_release_branch: supervisor/final-release-fixed-main-20260923
current_main: b99e8dbdfc2b91c8da645c4b41bf22ff4aa0cec6
workflow_count: 1
workflow_image: ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3
validation_policy: preserve_canonical_docker_xvfb_freecad_path; fail_closed_evidence; inspect_jobs_logs_artifacts; no_second_workflow
release_gate:
  candidate: PR_1075
  exact_head: 69215e7286ffda3da655f53094c5ae86d4644eb3
  pr_run_state: no pull_request run/status; latest exact-head push run #3507 / 35879364633 failed pre-job with zero jobs/artifacts; prior candidate/main push failures show the same event-delivery pattern
  supporting_run: 35845226384
  supporting_artifact: 10743635540
  supporting_run_result: 200 mm Blanket-over-Cube real FreeCAD/Xvfb acceptance passed; rendered checkpoints and motion frames inspected
  external_ci_blocker: push/pull_request Actions delivery is externally blocked before job allocation; connector exposes no workflow-dispatch operation and cannot inspect required Actions administration policy endpoints
final_gate: exact_head_canonical_pr_green; inspect_jobs_logs_artifacts; merge; merged_main_canonical_pr_green; fresh_repo_audit
open_actionable_issues: [1017, 1020, 1043, 1053, 1081, 1083]
```

closed_research_issues: [1042, 1055]
stale_branch_cleanup: unavailable_via_current_connector; 490_remote_branches_observed; scheduled maintenance not currently evidenced
