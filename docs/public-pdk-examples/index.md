---
title: "Cells"
---

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
- [Notebooks](../notebooks.qmd) lists the current Palace and AEDT component and
  cross-section workflows.
- [SCGSim integration](../features/scgsim-integration.md) defines the ownership
  boundary used by those notebooks.

## Choose a cell with flat tags

Public factories declare metadata with `@gf.cell(tags=[...])`. The tags are
flat labels, not a directory tree or an electrical model. Start with purpose
(`layout` or `simulation`), then object (`capacitor`, `resonator`, `cpw`, `chip`),
then actual features (`circular_arc`, `interpolation_spline`, `flip_chip`, `bump`,
`airbridge`). For example, `circular_pad_capacitor` is a simulation capacitor
with circular source geometry; a hole is a parameter choice, not another factory.

Use the registered factory name with `gf.get_component`, or import it from
`orpen_sc_pdk.cells`. Inspect the typed parameters before changing defaults.
These labels help you choose source geometry; they do not promise a plugin
filter, solver branch or successful simulation. See [Build and compose](component-authoring.md)
and the [visible Test Components Set](test-components.md).

## Components Layout

Inspect four current default factory previews with Askr's inline Image Viewer.
Deep teal is actual DRAW `1/0`; soft light teal is actual ETCH `1/1`;
auxiliary masks, domains and locators are omitted. Missing ETCH is not invented.
Use **+ / −**, drag to pan, or **Fit**; **Expand** opens the same image in a
floating window. Closing returns to the article with the camera retained.
These are static images, not live cell builds, GDS layer inspection,
measurements or native simulation evidence.

### Resonator

[Factory source: `resonator`](https://github.com/OrPenStrike/orpen-sc-pdk/blob/develop/orpen_sc_pdk/cells/layout/resonator.py)
builds a CPW resonator from hanger and meander sections.

![Default resonator: actual DRAW and ETCH.](../_static/images/components/resonator.svg){#fig-layout-resonator}

{{< askr-image-view target="fig-layout-resonator" mode="inline" >}}

### Interdigital capacitor

[Factory source: `interdigital_capacitor`](https://github.com/OrPenStrike/orpen-sc-pdk/blob/develop/orpen_sc_pdk/cells/layout/capacitor.py)
provides the reusable interdigital capacitor layout.

![Default interdigital capacitor: actual DRAW and ETCH.](../_static/images/components/interdigital_capacitor.svg){#fig-layout-idc}

{{< askr-image-view target="fig-layout-idc" mode="inline" >}}

### Martinis ribbon capacitor

[Factory source: `martinis2022_differential_ribbon_capacitor`](https://github.com/OrPenStrike/orpen-sc-pdk/blob/develop/orpen_sc_pdk/cells/layout/martinis.py)
provides the differential ribbon capacitor layout.

![Default Martinis ribbon capacitor: actual DRAW only; the source has no ETCH.](../_static/images/components/martinis2022_differential_ribbon_capacitor.svg){#fig-layout-martinis}

{{< askr-image-view target="fig-layout-martinis" mode="inline" >}}

### Launcher

[Factory source: `launcher`](https://github.com/OrPenStrike/orpen-sc-pdk/blob/develop/orpen_sc_pdk/cells/layout/cpw.py)
provides the CPW launcher layout.

![Default CPW launcher: actual DRAW and ETCH.](../_static/images/components/launcher.svg){#fig-layout-launcher}

{{< askr-image-view target="fig-layout-launcher" mode="inline" >}}

### Bump geometry

[Factory source: `indium_ground`](https://github.com/OrPenStrike/orpen-sc-pdk/blob/develop/orpen_sc_pdk/cells/layout/indium.py)
provides indium bump `40/0` and UBM `40/1` footprints, without M1 DRAW/ETCH.
See the [Test Set's flip-chip view](test-components.md#reading-the-multi-level-views)
for layer-separated bump geometry.
