# GitHub Wiki Bridge

## Purpose

The connected GitHub MCP can read and write normal repository files but does not expose GitHub Wiki pages as first-class resources.

FreeCAD Cloth therefore treats the repository directory wiki/ as the editable source and publishes that tree to the separate Git repository used by the GitHub Wiki.

The intended flow is:

MCP → repository/wiki → canonical GitHub Actions workflow → freecad-cloth.wiki.git → GitHub Wiki

This restores practical read/write access to Wiki content through the repository interface that agents already use.

## Repository contract

The following rule is intentional:

**wiki/ is canonical. The GitHub Wiki is the published human-facing copy.**

That makes Wiki changes durable, reviewable and reproducible.

### Publish

Repository wiki files are published as part of the canonical workflow.

- Normal pushes to main publish the repository wiki tree.
- A manual canonical workflow run can explicitly select Wiki operation = publish.
- The bridge copies the whole wiki tree into the Wiki Git repository.
- The published copy therefore has deterministic content.

### Import

Direct Wiki edits can be imported back into the repository.

1. Run the canonical workflow from main.
2. Select Wiki operation = import.
3. The workflow clones the live Wiki.
4. The live tree replaces the repository wiki tree in the working copy.
5. If it differs, the workflow creates an agent/wiki-import-<run-id> branch.
6. A normal pull request is opened.
7. Merge that PR to make the imported state canonical.

There is no silent three-way merge.

## Credential

The bridge uses the repository Actions secret:

WIKI_SYNC_TOKEN

The token must be able to clone and push the separate Wiki repository at:

Uhrendoktor/freecad-cloth.wiki.git

For a personal repository/Wiki, a dedicated classic personal access token with repository access is the simplest documented setup. Prefer a dedicated automation credential rather than reusing a token for unrelated work.

The current connected GitHub MCP does not expose Actions-secret creation or rotation, so adding WIKI_SYNC_TOKEN remains a one-time GitHub settings step.

## Workflow contract

FreeCAD Cloth intentionally keeps one GitHub Actions workflow:

.github/workflows/canonical-execution.yml

The workflow dispatch input Wiki operation has three choices:

- none — normal canonical execution only
- publish — publish repository documentation to the live Wiki
- import — import live Wiki content and open a pull request

The automatic hosted fallback explicitly forwards publish so a runner fallback still publishes documentation from main.

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

The canonical Python validation already compiles the repository tree, so the bridge script is syntax checked as part of ordinary CI.
