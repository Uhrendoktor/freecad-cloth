# Tool State

```yaml
schema: 2
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md (missing from repository; supervisor policy retained in this file)
supervisor_task: cloth-sewing-workbench-roadmap-replan-v2
current_mainline_replan_commits: [7f40792d03de00e24093f794c61b9f3eecc846a3, 829e051bb288dd9cd45d8afebbe9162bcbee1ab2]
parallel_task_issues: [143, 145, 147, 148, 155, 159, 161, 162, 163]
completed_milestones: [144, 146, 152, 156]
active_release_gates: [143, 155, 145, 159, 161]
queued_release_gates: [162, 147, 163]
non_blocking: [148]
workflow_changes:
  - post-merge GUI screenshot comments from the existing cloth-gui-screenshots artifact
  - GUI visual regression captures Pattern, Sewing, Simulation-arranged, and Simulation-draped states under Xvfb with content/state validation
  - GUI screenshot capture is opt-in via PR label gui-screenshot or workflow_dispatch gui_screenshots=true
  - GUI screenshot runs use concurrency cancellation so superseded captures do not consume a full runner
  - normal push/PR validation no longer starts the GUI screenshot job

policy:
  - one canonical workflow only
  - never declare an in-progress CI run successful
  - review diffs before merge
  - require terminal green CI before dependent merge/close decisions
  - verify merged mainline after merge
```
