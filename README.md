# FreeCAD Cloth

<p align="center">
  <img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped.png" alt="Finished tunic draped over the FreeCAD mannequin after cloth simulation" width="820">
</p>

<p align="center"><strong>Pattern → Sew → Fit → Simulate → Inspect</strong></p>

FreeCAD Cloth adds garment-pattern design and cloth simulation to FreeCAD. Create editable 2D pattern pieces, connect them with persistent seam relationships, fit them to a mannequin or supported CAD target, and inspect the resulting drape.

## What the workbenches do

| Workbench | Purpose |
| --- | --- |
| **Cloth Pattern** | Author garment pieces from native Sketcher geometry and add construction details such as notches, marks, and grainlines. |
| **Cloth Sewing** | Define and inspect persistent relationships between matching pattern edges. |
| **Cloth Simulation** | Shape and measure the mannequin, arrange and optionally pose it, run cloth simulation, and inspect the result. |

## A practical first run

The examples deliberately separate a basic simulation check from the complete garment workflow:

1. [Install FreeCAD Cloth](docs/users/INSTALLATION.md) and verify that the three workbenches appear in FreeCAD.
2. Run [Blanket over Cube](docs/users/EXAMPLES.md#1-blanket-over-cube) to check a small pattern, collision target, pinning, and drape without sewing or mannequin complexity.
3. Follow the [end-to-end Tunic guide](docs/users/USER_GUIDE.md) for the complete pattern-to-drape journey. The guide covers avatar dimensions, seams, fitting, optional posing, simulation, and diagnosis.

## Inside the workbench

The images below are representative states captured from real FreeCAD acceptance fixtures. They are not one continuous screen recording. Each feature guide explains the relevant interaction, expected result, and known limits; the text remains usable without the images.

<table>
  <tr>
    <td width="50%">
      <img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/cloth-pattern-design.png" alt="Editable garment front and back pattern pieces shown in the Cloth Pattern workbench" width="420">
      <p><strong>1. Pattern authoring.</strong> Build garment pieces from native Sketcher geometry so the 2D source remains editable.</p>
    </td>
    <td width="50%">
      <img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/cloth-sewing.png" alt="Garment pattern pieces with their semantic seam relationship visible in the Cloth Sewing workbench" width="420">
      <p><strong>2. Sewing.</strong> Pair the intended edges and inspect seam identity and direction before committing.</p>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/avatar-shape-editor.png" alt="Mannequin shape editor with body-shape controls, named measurements, and viewport handles" width="420">
      <p><strong>3. Avatar shape.</strong> Adjust body proportions and measurements before arranging fabric around the intended target.</p>
    </td>
    <td width="50%">
      <img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/interactive-arrange.png" alt="Pattern panels being positioned and snapped onto their mannequin arrangement points" width="420">
      <p><strong>4. Fitting.</strong> Place pieces against the target and commit their arrangement.</p>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/avatar-pose-mode.png" alt="Mannequin Pose Mode showing the joint overlay and selected rotation gizmo" width="420">
      <p><strong>5. Pose.</strong> Adjust mannequin joints when the garment needs a posture other than the default stance.</p>
    </td>
    <td width="50%">
      <img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-arranged.png" alt="Sewn garment arranged around the mannequin before the cloth simulation starts" width="420">
      <p><strong>6. Simulation setup.</strong> Review the arranged garment and target before running the solver; the hero image above shows the resulting drape.</p>
    </td>
  </tr>
</table>

## Find the right guide

| Goal | Documentation |
| --- | --- |
| Choose a user task or feature | [User documentation](docs/users/README.md) · [Feature guide index](docs/users/wiki/README.md) |
| Look up commands or recover from a problem | [Workbench guide](docs/users/WORKBENCH_GUIDE.md) · [Troubleshooting](docs/users/TROUBLESHOOTING.md) |
| Understand the architecture, test setup, or contribution process | [Developer documentation](docs/developers/README.md) · [Documentation guide](docs/developers/DOCUMENTATION_GUIDE.md) |
| Browse every documentation area | [Documentation map](docs/README.md) |

## Scope

FreeCAD Cloth is an evolving workbench, not a claim of complete commercial garment-CAD parity. Advanced grading and nesting, production construction libraries, richer avatar providers, and measurement-grade fit analysis remain separate from the workflows documented as implemented.

The screenshots are generated from acceptance fixtures and published with provenance. They demonstrate particular UI or geometry states; they do not, by themselves, prove that a saved document persists correctly. See [Validation and visual evidence](docs/developers/VALIDATION.md) for the distinction between GUI evidence, automated checks, and save/reload validation.

## License

LGPL-2.1-or-later. See [LICENSE](LICENSE).
