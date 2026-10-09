# Cells

Public examples demonstrate OrPen components and PDK facts through SCGSim. They
must not duplicate solver, handoff, or report implementation inside this repo.

Choose reusable layout factories from `orpen_sc_pdk.cells` and build them by
their registered names in the active PDK. Layout sources include CPW, resonator,
capacitor, junction, qubit, airbridge and indium geometry. Simulation sources
provide public coupons and sample-only assemblies; those folder names do not
promise native solver support.

- [Component authoring](component-authoring.md) covers registered public layout
  factories.
- [Source test components](test-components.md) describes seven public source
  layout families and their native-evidence limitations.
- [Cell organization and tags](../usage/cell-organization.md) maps the current
  layout/simulation source folders and unchanged public discovery names.
- [Notebooks](../notebooks.qmd) lists the current Palace and AEDT component and
  cross-section workflows.
- [SCGSim integration](../features/scgsim-integration.md) defines the ownership
  boundary used by those notebooks.
- [Static SVG gallery](../layout-viewer.qmd) offers pan/zoom of the existing
  public previews, not native/GDS or semantic inspection.
