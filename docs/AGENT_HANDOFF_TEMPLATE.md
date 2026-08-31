# Cloth implementation-agent handoff template

Use this template for every non-trivial implementation branch. Keep one issue focused unless a dependency makes a combined change unavoidable.

## Scope

- Issue:
- Branch:
- Dependency issues:
- Current `main` SHA at branch creation:

## Authoritative model

- Persistent document object(s):
- Authoritative properties/API:
- Derived data:
- Compatibility APIs that must remain:

## Files allowed to change

- Production:
- Tests:
- Documentation:
- CI: **must remain unchanged unless explicitly approved by supervisor**.

## Invalidation / recovery

Describe exactly what makes the result stale or invalid and what the user can do to recover.

| Upstream change | Derived state | Persistent status/reason | Recovery |
| --- | --- | --- | --- |
| | | | |

Never silently retarget a seam, collision source, or other semantic relationship.

## UI/UX contract

- Primary action:
- Secondary actions:
- Persistent values:
- Staged/cancel behavior:
- Invalid-state presentation:
- Reset/Repair behavior:

Use native FreeCAD controls where they already express the interaction correctly. Icons are for actions; text fields and values remain textual/native.

## Tests

### Focused/headless

List exact tests and expected contracts.

### Real FreeCAD/Xvfb

Describe the public-workbench scenario, including save/reload where persistence is involved.

### Screenshot artifacts

If GUI-visible behavior changes, name the affected canonical screenshot state(s). Do not weaken the existing 1280x720 PNG assertions.

## Non-goals

List adjacent features explicitly excluded from this branch.

## Handoff evidence

- Focused tests:
- Canonical Python job:
- Canonical FreeCAD/Xvfb job:
- Screenshot artifacts reviewed:
- Save/reload verified:
- Mainline compatibility checked:

## Supervisor merge gate

Do not request merge until:

1. the branch is based on current `main`;
2. the diff has been inspected;
3. focused tests pass;
4. real FreeCAD/Xvfb acceptance passes where relevant;
5. canonical screenshot/export behavior remains intact;
6. persistent data and invalidation behavior are verified;
7. documentation and `AGENT_STATUS.md` are updated when the slice changes an architecture or workflow contract.
