# FreeCAD Cloth documentation

The project documentation now has a human-auditable visual wiki. Start with `USER_GUIDE.md`; do not load the whole directory by default. Start at [docs/wiki/README.md](wiki/README.md).

## Documentation layers

| Layer | Use it for |
| --- | --- |
| [../README.md](../README.md) | Human project orientation and visual feature map |
| [wiki/](wiki/README.md) | Feature-by-feature user-facing audit with visuals and evidence links |
| [WORKBENCH_GUIDE.md](WORKBENCH_GUIDE.md) | Detailed operating instructions |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Domain ownership and dependency direction |
| [FEATURE_MATRIX.md](FEATURE_MATRIX.md) | Capability boundaries and roadmap taxonomy |
| [SIMULATION_REVIEW.md](SIMULATION_REVIEW.md) | Human visual review of simulation evidence |
| [RELEASE_GATES.md](RELEASE_GATES.md) | Release definition and executable evidence requirements |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Testing, CI and contribution rules |

## Human audit rule

A user-visible capability is documented only when the page tells a human what to look for and points to executable evidence and source files. Issue/PR history is task-local evidence; verify the current branch before treating historical text as state.

Generated visuals come from the canonical GitHub Actions workflow and are published on the <code>docs/screenshots</code> branch. They are evidence artifacts, not an alternate source of truth.

## Source of truth

- <code>README.md</code> — project-level visual orientation.
- <code>docs/wiki/</code> — durable human-facing feature documentation.
- <code>AGENTS.md</code> — portable agent contract.
- <code>AGENT_STATUS.md</code> — live machine-readable supervisor/release record.
- <code>TOOL_STATE.md</code> — compact execution-policy/state record.
- <code>docs/PROJECT_STRUCTURE.md</code> — implementation placement.
- <code>docs/ARCHITECTURE.md</code> — domain ownership.
- <code>docs/ROADMAP.md</code> — durable roadmap.
- <code>docs/RESEARCH.md</code> — design research.
- <code>docs/DEVELOPMENT.md</code> — testing, CI, screenshots and contribution rules.
