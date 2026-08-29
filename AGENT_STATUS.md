# AGENT STATUS

## Supervisor

- Active milestone: #119 CLO-style workbench UI and end-to-end workflow.
- Previous seam-contract milestones (#108-#111) are integrated and green.
- #120 is the dedicated screenshot-workflow tracking issue.
- Current UI subtasks: #121 Pattern Design, #122 Sewing, #124 Simulation, #125 2D↔3D architecture, #126 GUI/screenshot regression, #127 FreeCAD workbench packaging/UX.

## Coordination

- #119 is the parent/epic acceptance gate; implementation work is delegated through its subtasks.
- Keep subtasks narrowly scoped and require PRs with tests and clear linkage to the parent.
- Do not allow duplicated semantic state between UI objects and PatternModel/Seam/SewingOperation.
- Screenshot QA must show the actual FreeCAD workbench chrome: workbench selector, custom toolbars, Combo View/task panels, and representative 2D/3D content.

## Execution order

1. #127: stabilize genuine FreeCAD workbench registration, commands, toolbars, resources, and activation.
2. #121 + #122: Pattern Design and Sewing UI against the canonical seam/data contracts.
3. #124: Simulation UI integrated with existing solver/avatar/material infrastructure.
4. #125: harden authoritative 2D→sewing→3D/simulation data flow and save/reload behavior.
5. #126: enforce full-window GUI screenshots and UI assertions for Pattern/Sewing/Simulation.
6. Supervisor integrates PRs, runs canonical CI, inspects GUI artifacts, fixes cross-cutting regressions, and repeats until all gates pass.

## Required supervisor gates

- Every implementation PR has automated coverage appropriate to its scope.
- Canonical CI is terminal-green before merge; no stopping while required CI is running.
- Real FreeCAD GUI smoke demonstrates activation and usable workflows, not merely Python imports.
- Screenshots visibly include the workbench toolbars and task panels.
- #119 remains open until the complete Pattern → Sewing → Simulation workflow is usable and persistent.
