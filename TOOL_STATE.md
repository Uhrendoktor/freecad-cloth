# Tool State

```yaml
schema: 24
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
workflow_count: 1
workflow_image: ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3
validation_policy: preserve_canonical_docker_xvfb_freecad_path; fail_closed_evidence; mandatory_human_screenshot_review; artifact_link_alone_insufficient; no_second_workflow
agent_context_policy: current_head_first; task_scoped_docs; no_broad_issue_pr_history; no_historical_issue_routing
state_documents: AGENT_STATUS.md, TOOL_STATE.md
```
