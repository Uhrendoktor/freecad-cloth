# Implementation Agent Handoff

Use for every non-trivial branch. One issue per branch; re-cut from current `main`.

## Scope
- Issue:
- Branch:
- Dependencies:
- Main SHA:

## Authority
- Persistent objects/properties/API:
- Derived data:
- Compatibility constraints:

## Files / CI
- Production:
- Tests:
- Docs:
- CI: unchanged unless explicitly approved.

## Invalidation / recovery

| Upstream change | Derived state | Status/reason | Recovery |
|---|---|---|---|
| | | | |

Never silently retarget semantic relationships.

## UI
- Primary action:
- Secondary actions:
- Persistent values:
- Commit/cancel:
- Invalid state:
- Reset/Repair:

Prefer native FreeCAD controls.

## Acceptance
- Focused tests:
- Real FreeCAD/Xvfb scenario:
- Save/reload:
- Affected screenshot states:
- Artifacts reviewed:

GUI changes must preserve the canonical 1280×720 PNG generation/validation path.

## Non-goals

List adjacent work deliberately excluded.

## Merge gate

Supervisor merges only when the branch is current-main based, the diff is reviewed, focused tests pass, required FreeCAD/Xvfb acceptance passes, persistence/invalidation is verified, and canonical screenshot/export behavior remains intact.
