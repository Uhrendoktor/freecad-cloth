# Agent instructions

This repository uses a small, current-state-first agent contract. Do not reconstruct project state from the full GitHub history.

## Source of truth and priority

1. The checked-out branch and its current HEAD are the implementation truth. Verify the target HEAD before making state claims.
2. `AGENT_STATUS.md` and `TOOL_STATE.md` are compact live coordination records. Reconcile their recorded SHA/state with the actual branch before relying on them.
3. Use the canonical docs only for the topic they govern:
   - `docs/ARCHITECTURE.md` — data authority, dependencies, invalidation.
   - `docs/PROJECT_STRUCTURE.md` — file/module ownership.
   - `docs/DEVELOPMENT.md` — testing, CI, contribution and agent workflow.
   - `docs/ROADMAP.md` — durable roadmap and release boundaries, not live status.
   - `docs/RESEARCH.md` — design research, not implementation status.
4. A named current issue/PR is task-local evidence. Read it only when it governs the task.
5. Closed issues/PRs, old branches, old commits, old workflow runs, and old artifacts are historical evidence only. Never use them as current state unless the task explicitly asks for historical reconstruction.

When sources disagree, prefer current branch contents and live state records over historical prose. Treat words such as "current", "complete", "active", or "release" inside old documents as claims to verify, not facts to inherit.

## Context firewall

Do not:
- read the entire `docs/` tree before every task;
- enumerate or ingest all open/closed issues or PRs;
- follow chains of related issues merely because they are linked;
- paste large logs, artifacts, or PR conversations into the working context;
- revive stale branch names or historical implementation plans.

Instead, read the smallest set of files needed for the task. Search GitHub narrowly by exact issue/PR number, file path, symbol, or hypothesis. Prefer current main plus one governing issue/PR over broad history.

For simulation work, #2492 is the canonical coordination issue. Its child lanes are independent evidence sources, not a substitute for current main. Read a child lane only when its hypothesis matches the task.

## Task prompt contract

Write task prompts with these fields when the work is non-trivial:

```text
Objective:
Current evidence:
Authoritative source:
Scope:
Non-goals / frozen behavior:
Acceptance:
Falsifier or stop condition:
```

Keep historical context out of the prompt unless it changes the decision. State the exact current branch/commit when evidence is sensitive to repository state.

## Repository structure

Implementation code belongs under `freecad_cloth/`. The repository intentionally has two FreeCAD loader adapters: classic root `Init.py`/`InitGui.py` and modern namespaced `freecad/freecad_cloth/{__init__.py,init_gui.py}`. They are alternate loader surfaces for the same implementation and must stay aligned; `freecad/` is not a second implementation tree. `docs/ARCHITECTURE.md` and `docs/PROJECT_STRUCTURE.md` define the package boundaries.

`freecad_cloth.sewing.SeamGraph` is the canonical seam-graph implementation. `freecad_cloth.pattern.SeamReference` owns semantic edge references; `freecad_cloth.sewing.SeamReference` exists only as a legacy compatibility import. New code should import the owning module directly.

There is exactly one canonical CI workflow: `.github/workflows/canonical-execution.yml`. Do not create parallel workflows or weaken acceptance checks.

## Verification

Choose the smallest evidence set that proves the change. Use focused tests for core changes, real FreeCAD coverage for document/API changes, Xvfb for GUI changes, save/reload checks for persistence, deterministic solver checks for simulation changes, and the canonical workflow when its acceptance path is required.

Do not declare success from a stale run. Verify the run belongs to the exact commit under review.

## State-file hygiene

`AGENT_STATUS.md` and `TOOL_STATE.md` are compact summaries. Do not turn them into experiment logs. Put detailed evidence in the governing issue/PR, and update these files only when the live repository state or execution policy changes.

Do not add another permanent "status", "current state", "proposal", or duplicate architecture document when an existing canonical document can hold the information.
