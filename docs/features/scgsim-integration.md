---
title: "Use OrPen source with SCGSim"
---

OrPen supplies geometry, layers/stack, materials and source annotations.
SCGSim is the reusable runtime for native geometry, backend preparation,
meshes, solver handoff and result resolution/reporting.

## Choose the notebook and its runtime

Start from [Simulation](../notebooks.qmd), select the component/backend and
follow that canonical source's declared runtime environment. The ordinary
project cohort and revised source-only v2 notebooks are distinct; installing
an optional backend group does not turn one into the other. Saved output may
belong to an earlier source/stack and is not evidence of executing a revision.
Canonical `.qmd`/`.py` sources and saved `.ipynb` pairs remain the example
authority; this guide does not define a parallel workflow.

## Preserve geometry and problem intent

- Keep conductor regions, material IDs and stack choices intact.
- Carry real port/locator sheets; nonmetal locators are not positive metal or
  native terminal assignments.
- Assign final Nets, reference conductors and excitation in the consuming
  design, using the selected runtime's supported contract.
- Export the geometry required by that example; a source GDS file or image
  does not prove native import or contacts.

[Process](../materials-and-technology.md) explains DRAW/masks/holes, stack
selection and materials. Follow the selected notebook's version-bound links
for backend APIs and prerequisites. The [SCGSim development documentation](https://github.com/OrPenStrike/scgsim/tree/develop/docs)
is the current moving development branch, not a fixed notebook runtime.

## Preparation is not execution

The sequence is source intent → runtime preparation → native handoff/execution
→ returned-run resolution → reports. Inspect actual native readback when
required by your example, then retain its returned outputs and provenance.
Palace and AEDT have separate prerequisites; source availability does not
establish an implemented branch. No runnable native branch is added here for
the source-only spline, flip-chip or airbridge Test Set views.
