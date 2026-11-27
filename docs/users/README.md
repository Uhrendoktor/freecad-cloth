# FreeCAD Cloth user documentation

This section is for people using the workbench in FreeCAD. It focuses on completing garment tasks, understanding visible commands, and recovering from common problems.

## Start here

| Goal | Guide |
| --- | --- |
| Install or update the workbench | [Installation](INSTALLATION.md) |
| Complete the pattern-to-drape workflow | [End-to-end user guide](USER_GUIDE.md) |
| Try a small simulation before a full garment | [Examples](EXAMPLES.md) |
| Inspect the experimental layered contact test and its visual failure | [Layered multi-garment contact test](examples/layered-outfit.md) |
| Learn a specific interaction | [Visual feature guides](wiki/README.md) |
| Diagnose a missing workbench, invalid seam, misplaced piece, or stale simulation | [Troubleshooting](TROUBLESHOOTING.md) |
| Look up commands and interaction behavior | [Workbench guide](WORKBENCH_GUIDE.md) |

## Suggested learning path

1. Verify the supported FreeCAD version and install the workbench.
2. Run **Blanket over Cube** to confirm a basic pattern, target, pinning, and drape without garment complexity.
3. Follow the **Tunic** workflow for a complete pattern-to-simulation journey.
4. Review the [layered contact test](examples/layered-outfit.md) as diagnostic material only; its current garment appearance is not accepted.
5. Open the visual feature guide for the specific interaction you need to learn or verify.

## Audience boundary

These guides describe the workbench from a user's point of view. Software architecture, development setup, tests, CI, and release criteria live in [Developer documentation](../developers/README.md). AI-agent-specific instructions are indexed separately under [Agent documentation](../agents/README.md).
