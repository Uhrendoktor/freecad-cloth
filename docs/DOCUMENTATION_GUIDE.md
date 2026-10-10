# Documentation guide

This page records the editorial and maintenance rules for FreeCAD Cloth documentation. The goal is not to maximize page count; it is to help readers find the right task, complete it, verify the result, and recover when the result differs from expectations.

The rules below synthesize the [Diátaxis documentation framework](https://www.diataxis.fr/start-here/), the [Google developer documentation style guide](https://developers.google.com/style), GitHub's guidance on [README files](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes), and the [Write the Docs guides to docs as code](https://www.writethedocs.org/guide/docs-as-code/) and [documentation testing](https://www.writethedocs.org/guide/tools/testing/). These are reference points, not a rigid template: clarity for FreeCAD Cloth users takes precedence over mechanical conformance.

## Start from the reader's task

Before drafting, state who the page is for and what they should be able to do or understand after reading it. Use a title that describes the page's main purpose.

Separate the four common documentation needs:

| Type | Reader's question | FreeCAD Cloth entry point |
| --- | --- | --- |
| Tutorial | "Can you guide me through a first successful result?" | [User guide](USER_GUIDE.md) |
| How-to guide | "How do I complete this task?" | [Feature guides](wiki/README.md) and [Troubleshooting](TROUBLESHOOTING.md) |
| Reference | "What does this field, command, state, or boundary mean?" | [Workbench guide](WORKBENCH_GUIDE.md), [Data model](wiki/07-data-model.md) |
| Explanation | "Why does the product work this way?" | [Architecture](ARCHITECTURE.md), [Data model](wiki/07-data-model.md), [Validation](wiki/08-validation.md) |

The distinctions are useful because an onboarding tutorial, a task recipe, and a technical contract need different levels of context. Do not force every page into four separate folders. Let reader goals and existing content determine the structure, and make links between related page types explicit.

## Use a predictable page shape

For a task guide, prefer this order:

1. **Goal and scope.** Describe the result the reader will produce and important limitations.
2. **Before you start.** Name required documents, selections, workbench, and assumptions.
3. **Steps.** Use numbered, imperative instructions. Each step should say where the action happens, what action to take, and what should happen next.
4. **Verify the result.** Name the visible state, persistent document state, or diagnostic that demonstrates success.
5. **Recover.** Link to one canonical troubleshooting page rather than copying a second version of the same fix.
6. **Related reading.** Link to deeper concepts, commands, source, and acceptance evidence.

For an explanation or reference page, lead with a definition or the rule the reader needs, then organise details around the product's domain model. Do not interrupt a short task with deep implementation detail; link to the reference when the reason matters but the reader does not need it to finish the task.

Use sentence-case headings and descriptive link text. Keep steps in the same grammatical form. Put prerequisites before the instructions that rely on them, describe the result after each important action, and label optional steps explicitly. Do not make users infer a feature's limit from an implementation name or a test fixture.

## Use visual evidence purposefully

Visuals should answer a question that is hard to answer from text alone: where to click, what state appears, how an interaction changes, or whether the final geometry looks plausible.

- Use generated screenshots for a stable UI state and a short recording when the important behavior changes over time.
- Put an introductory sentence next to each informative image and provide concise, contextual alt text.
- Describe the important action and outcome in text as well. GIFs can be unavailable, motion-sensitive, slow to load, or difficult to inspect frame by frame.
- Do not encode meaning by color alone. Add labels, shape/direction cues, and text; for seam pairing, explain the A/B identity as well as highlight color.
- Crop captures to the relevant UI, keep labels readable, and avoid using screenshots of text/code/terminal output where real text is selectable.
- Avoid repeated images unless they teach a distinct task. A hero image introduces the product; a task GIF should demonstrate an interaction; a multi-view set should support geometry review.
- Do not hand-edit generated UI or geometry evidence. Correct the capture fixture and regenerate through the canonical path.

Public visual assets are published to the docs/screenshots branch at the generated-image path referenced by the [README](../README.md) and [wiki index](wiki/README.md). That branch is a publication target, not the authoritative copy of the feature implementation.

## Describe the actual product

Documentation is part of the user interface. Treat feature and command names as labels, not as interchangeable synonyms. Confirm them against the current UI or registered command contracts before documenting them.

For every substantial user-facing behavior, distinguish:

- **Persistent authority:** what is saved in the FCStd document and can be edited by the user.
- **Derived state:** meshes, solver state, or other information rebuilt from persistent inputs.
- **Transient state:** hover labels, selection highlights, and previews that are not saved.
- **Capability boundary:** what the current implementation can do, what it rejects, and what remains future work.

Use precise status words. A passing unit test shows that a particular assertion passed; it does not, on its own, prove that a workflow looks correct in the GUI. A screenshot shows a rendered state; it does not prove save/reload persistence. Pair visual evidence with relevant automated checks and state the limitation of each.

Do not present a research note, roadmap item, or hypothesis as an implemented feature. Link to the current implementation contract, test fixture, or [feature matrix](FEATURE_MATRIX.md) when the status could be misunderstood.

## Information architecture

Keep the root [README](../README.md) concise enough to act as an orientation page. It should answer what the workbench is, what to try first, and where to go next.

- [Installation](INSTALLATION.md) owns requirements, installation, and replacement instructions.
- [User guide](USER_GUIDE.md) owns the first end-to-end learning path.
- [Examples](EXAMPLES.md) owns the simple-first validation ladder and example scope.
- [Troubleshooting](TROUBLESHOOTING.md) owns recovery steps.
- [Visual wiki](wiki/README.md) owns feature discovery and links to per-feature visual evidence.
- [Workbench guide](WORKBENCH_GUIDE.md) owns detailed commands and interaction contracts.
- Architecture, project structure, tests, and release documents own engineering contracts.

If a procedure is needed in several places, document it once and link to it. A page can add a short symptom-specific hint, but should not introduce a competing recovery path.

## Validate every documentation change

Run the lightweight Markdown link check after editing:

<code>python tools/check_markdown_contract.py</code>

The checker verifies local Markdown and HTML file references across the README, agent/contribution pages, and docs/**/*.md. It does not validate external URLs or whether remote screenshot assets still exist.

For a documentation-only change, also inspect the rendered GitHub Markdown and verify that screenshots/GIFs load, tables remain readable, alt text describes the right state, and internal links navigate to the intended page. When a change affects published UI evidence, update the real generator and inventory rather than editing the output image.

The canonical workflow includes <code>python tools/check_documentation_contract.py</code>, <code>python tools/check_markdown_contract.py</code>, and visual evidence/provenance gates. Use the canonical FreeCAD/Xvfb workflow when a UI state or screenshot generator changes.

## Research references

- [Diátaxis: Start here](https://www.diataxis.fr/start-here/) — the four documentation needs and how they differ.
- [Google: Procedures](https://developers.google.com/style/procedures) — imperative steps, context before action, result after action, and avoiding repeated procedures.
- [Google: Images](https://developers.google.com/style/images) — alt text, image captions, text equivalents, and selective use of visuals.
- [Google: Accessibility](https://developers.google.com/style/accessibility) — don't make images or color the sole carrier of information.
- [GitHub Docs: README files](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes) — project orientation, relative links, and where to put longer documentation.
- [Write the Docs: Docs as code](https://www.writethedocs.org/guide/docs-as-code/) — version control, code review, and automated checks for docs.
- [Write the Docs: Testing documentation](https://www.writethedocs.org/guide/tools/testing/) — links, builds, and repeatable documentation checks.
- [FreeCAD Documentation: Add-on and workbench installation](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/How_to_install_additional_workbenches.md) — native workbench distribution and manual-install context.
