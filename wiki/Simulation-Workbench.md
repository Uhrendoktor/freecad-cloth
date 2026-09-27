# Cloth Simulation Workbench

## What it is for

**Cloth Simulation** is the physical layer: targets, collision data, material parameters, pins and the derived simulation state.

![Draped tunic](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-front.png)

## The DrapeTarget

A **DrapeTarget** provides a target-neutral collision contract.

Supported providers include:

- the native human mannequin;
- generic FreeCAD Shape, PartDesign, Body or Mesh geometry.

The solver consumes a solver-neutral collision surface rather than owning the document's target model.

## Before Run

| Check | Expected state |
| --- | --- |
| Target | Current and valid |
| Derived state | Rebuilt after relevant input changes |
| Material | Physical parameters configured |
| Pins / stitches | Intentional and visible |
| Diagnostics | No blocking stale or invalid state |

## Run, Step and Reset

- **Run** — normal simulation action.
- **Step** — controlled progression for debugging.
- **Reset** — recovery to the pre-run state.

The workbench deliberately prevents stale collision or non-finite state from being treated as valid simulation output.

## Fabric presentation

Physical material parameters affect the solver.

Presentation properties such as color, roughness, specular response and transparency affect viewport rendering and are persisted separately from physical parameters.

## Visual examples

<table>
<tr>
<td align="center"><img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-arranged-turntable.gif" alt="Arranged cloth" width="300"><br><sub>Arranged</sub></td>
<td align="center"><img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-turntable.gif" alt="Draped cloth" width="300"><br><sub>Draped</sub></td>
</tr>
</table>
