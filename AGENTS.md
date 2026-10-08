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

When issue bodies contain YAML front matter or agent-routing fields, treat those fields as task-routing metadata, not repository state. Do not infer implementation authority or current status from them unless the task explicitly targets that protocol.

## Context firewall

Do not:
- read the entire `docs/` tree before every task;
- enumerate or ingest all open/closed issues or PRs;
- follow chains of related issues merely because they are linked;
- paste large logs, artifacts, or PR conversations into the working context;
- revive stale branch names or historical implementation plans.

Instead, read the smallest set of files needed for the task. Search GitHub narrowly by exact issue/PR number, file path, symbol, or hypothesis. Prefer current main plus one governing issue/PR over broad history.

For simulation work, use the current coordination ledger named in `AGENT_STATUS.md`. Its child lanes are independent evidence sources, not a substitute for current main. Read a child lane only when its hypothesis matches the task.

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

## Planning contract

For multi-step refactors or architectural changes, use `.agent/PLANS.md` as the bounded execution-plan template. Keep evidence and review discussion in the governing issue/PR; do not turn the plan into a history log.

## Documentation contract

Public Python APIs in `freecad_cloth/` and `tools/` require docstrings. Use a one-line summary first, then document non-obvious behavior, invariants, side effects, exceptions and lifecycle restrictions. Keep architecture in `docs/ARCHITECTURE.md`, durable decisions in `docs/DECISIONS.md`, current state in `AGENT_STATUS.md`/`TOOL_STATE.md`, and task evidence in the governing issue/PR.

## Verification

Choose the smallest evidence set that proves the change. Use focused tests for core changes, real FreeCAD coverage for document/API changes, Xvfb for GUI changes, save/reload checks for persistence, deterministic solver checks for simulation changes, and the canonical workflow when its acceptance path is required.

Do not declare success from a stale run. Verify the run belongs to the exact commit under review.

## Test design contract for agents

Tests are part of the repository's production infrastructure. Optimize for trustworthy evidence with the fewest independent execution paths.

1. Test observable behavior first. Prefer real application state, persisted FreeCAD documents, exported files, structured manifests, and captured artifacts over implementation details.
2. Never make a test prove itself. A test must not read its own source, copy expected strings from its own implementation, or use a log line emitted by the same test as evidence that the behavior occurred.
3. Treat stdout/stderr and progress logs as diagnostics, not acceptance evidence. A `*-passed` marker is never an oracle.
4. Use source inspection only for repository policy or architecture that is itself the requirement. Prefer AST/YAML/XML parsing over raw substring checks when a check is worth keeping.
5. Before adding a validator or validation command, name the distinct failure mode it catches that the producing test cannot already catch. If there is no distinct failure mode, do not add the extra run.
6. For acceptance gates, derive PASS/FAIL from artifacts or state observed independently from the producer's success claims. Existing validators should be extended before introducing another verifier.
7. Every new harness component must be tested as infrastructure. At minimum, exercise a valid case and a deliberately invalid/tampered case when the component makes an acceptance decision.
8. Use the cheapest evidence that distinguishes the failure: pure-Python unit/property tests first; real FreeCAD/Xvfb only where FreeCAD or GUI state is the behavior under test; expensive end-to-end runs only for integration boundaries.
9. Reuse existing fixtures, validators, and canonical CI paths. Do not create parallel workflows, duplicate evidence formats, or one-off frameworks for a single feature.
10. Keep the test surface smaller than the problem it protects. Prefer deleting a redundant check over adding another layer that repeats the same assertion.

For autonomous work, a green run must mean that the product or produced artifact satisfied an independently stated invariant, not merely that the agent emitted a convincing success message.

## State-file hygiene

`AGENT_STATUS.md` and `TOOL_STATE.md` are compact summaries. Do not turn them into experiment logs. Put detailed evidence in the governing issue/PR, and update these files only when the live repository state or execution policy changes.

Do not add another permanent "status", "current state", "proposal", or duplicate architecture document when an existing canonical document can hold the information.
