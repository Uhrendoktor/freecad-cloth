# GitHub Wiki Bridge

## Purpose

The connected GitHub MCP can read and write normal repository files but does not expose GitHub Wiki pages as first-class resources.

FreeCAD Cloth therefore treats the repository directory wiki/ as the editable source and publishes that tree to the separate Git repository used by the GitHub Wiki.

The intended flow is:

MCP → repository/wiki → path-scoped wiki-sync.yml → freecad-cloth.wiki.git → GitHub Wiki

This restores practical read/write access to Wiki content through the repository interface that agents already use.

## Repository contract

The following rule is intentional:

**wiki/ is canonical. The GitHub Wiki is the published human-facing copy.**

That makes Wiki changes durable, reviewable and reproducible.

### Publish

Repository wiki files are published as part of the canonical workflow.

- A push to `main` publishes the repository wiki tree when `wiki/**` changed.
- The publishing workflow does not run for code-only changes, pull requests, schedules or unrelated paths.
- The bridge copies the whole wiki tree into the Wiki Git repository.
- The published copy therefore has deterministic content.

### Import

Direct Wiki edits are intentionally not part of the automatic publish workflow. To preserve a direct Wiki edit, run the bridge locally with `python3 tools/wiki_bridge.py import`, inspect the resulting `wiki/` diff, and submit it through the normal repository PR flow.

There is no silent three-way merge and no automatic last-writer-wins import.

## Credential

The bridge uses the repository Actions secret:

WIKI_SYNC_TOKEN

The token must be able to clone and push the separate Wiki repository at:

Uhrendoktor/freecad-cloth.wiki.git

For a personal repository/Wiki, a dedicated classic personal access token with repository access is the simplest documented setup. Prefer a dedicated automation credential rather than reusing a token for unrelated work.

The current connected GitHub MCP does not expose Actions-secret creation or rotation, so adding WIKI_SYNC_TOKEN remains a one-time GitHub settings step.

## Workflow contract

FreeCAD Cloth has one canonical engineering/test workflow and one intentionally narrow documentation workflow:

- `.github/workflows/canonical-execution.yml` — engineering, GUI, simulation, benchmark and release validation.
- `.github/workflows/wiki-sync.yml` — human documentation publishing only; it triggers on `push` to `main` with `paths: [wiki/**]`.

The Wiki workflow does not participate in PR validation and does not share runner orchestration with engineering CI.

## Agent rules

### Normal agent edit

Edit the source file under wiki/ through the repository interface.

Do not edit the live Wiki UI for ordinary documentation work. Repository changes are easier to review, diff and reproduce.

### Direct Wiki edit

When a human intentionally edits the live Wiki:

1. Import it with the canonical workflow.
2. Review the generated pull request.
3. Resolve any documentation conflicts there.
4. Merge the pull request.
5. Continue normal editing from repository wiki/ sources.

### Conflict policy

- A merged repository change is the canonical state.
- Direct Wiki edits must be imported before they are preserved.
- If both sides changed, use the generated import PR as the comparison point.
- Do not introduce an automatic last-writer-wins merge.

## Images

Prefer the stable generated assets published on the docs/screenshots branch for screenshots and visual evidence.

For permanent Wiki-specific images that are not generated CI evidence, place them under wiki/assets/ so the bridge publishes them with the page tree.

## Local use

The bridge script has two operations:

- publish — repository wiki/ to the live Wiki
- import — live Wiki to repository wiki/

The script reads WIKI_REMOTE_URL from the environment so credentials do not need to be stored in source code.

A basic syntax check is:

python3 -m py_compile tools/wiki_bridge.py

The canonical Python validation compiles the repository tree, so the bridge script is syntax checked as part of engineering CI. The Wiki workflow itself is intentionally small and has no project test matrix.
