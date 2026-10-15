# FreeCAD Cloth documentation

Use this page as the documentation map. Choose the section for your audience; the three groups have different goals and are intentionally kept separate.

## Choose your audience

| Audience | Start here | Purpose |
| --- | --- | --- |
| FreeCAD users | [User documentation](users/README.md) | Installation, garment workflows, feature guides, examples, and troubleshooting |
| Software developers | [Developer documentation](developers/README.md) | Architecture, code organization, development, testing, design decisions, and release validation |
| AI agents | [Agent documentation and guidelines](agents/README.md) | Agent-specific reference material and pointers to the repository's authoritative agent instructions |

## Common destinations

- [Install FreeCAD Cloth](users/INSTALLATION.md)
- [Follow the end-to-end garment workflow](users/USER_GUIDE.md)
- [Try the examples](users/EXAMPLES.md)
- [Browse visual feature guides](users/wiki/README.md)
- [Troubleshoot common problems](users/TROUBLESHOOTING.md)
- [Look up workbench commands](users/WORKBENCH_GUIDE.md)
- [Set up a development environment](developers/DEVELOPMENT.md)
- [Read the CI configuration](developers/CI_CONFIGURATION.md)
- [Understand the package boundaries](developers/ARCHITECTURE.md)

## Documentation boundaries

- User documentation explains what to do in FreeCAD and how to confirm or recover from the result.
- Developer documentation explains how the software is structured, built, tested, and maintained.
- Agent documentation covers AI-agent-specific instructions and artifacts. The root [`AGENTS.md`](../AGENTS.md) remains the repository-wide agent contract; this index does not replace it.

When one audience needs a topic owned by another, link to the canonical page rather than copying it.
