# Tool State

```yaml
schema: 23
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_issue: 2492
workflow_count: 1
workflow_image: ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3
validation_policy: preserve_canonical_docker_xvfb_freecad_path; fail_closed_evidence; mandatory_human_screenshot_review; artifact_link_alone_insufficient; no_second_workflow
artifact_budget: 10MB_accumulated_per_workflow_run
superseded_run_policy: cancel_when_ref_is_not_refs/heads/main; preserve_main_runs
main_head_at_audit: 3257ac54a16aebc7ddc5394949a6172b250d1fe4
production_tissu_fix_merged: false
active_diagnostics: 2577,2576,2575,2571,2554,2545
completed_diagnostics: 2537,2482,2535,2540,2578
historical_release_project_issue: 1017
agent_context_policy: current_head_first; task_scoped_docs; no_broad_issue_pr_history
state_documents: AGENT_STATUS.md, TOOL_STATE.md
```

- `batched_ci_fix_policy`: gather the complete workflow matrix before each CI repair iteration; preserve one consolidated fix commit per iteration.
