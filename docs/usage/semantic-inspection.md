# Semantic geometry inspection

Use a concept view to discuss unsettled topology and an inspection plate to
examine geometry that actually exists. Both support design discussion. Neither
is a new geometry authority, numerical result or acceptance threshold.

## Before construction: resolve the spatial question

When path placement, cross-section extent, termination or composition is
unsettled, draw the smallest view that explains it. A cross-section panel
separates signal widths, gaps and ground. A path panel distinguishes its
centerline from the full extruded footprint. A component panel shows proposed
composition, named endpoints, coupling regions and ports. Use known dimensions
proportionally and label unknown dimensions provisional. Show overlap and
clearance directly. A small SVG or annotated drawing is suitable for discussion;
do not label it canonical GDS or lowered geometry.

Once the design meaning is settled, implement it once in the canonical
component and inspect that implementation. Trivial parameter edits do not
require a separate concept exercise.

## After construction: bind real evidence

Before plotting, record source revision, canonical factory and settings or GDS
digest, physical units, route/case, data classification and diagnostic status.
When displaying lowered geometry, also bind the actual SGB or Gmsh artifact
identity. Extract layout polygons, ports, hierarchy, layers and physical bounds
through GDSFactory public APIs. Use the installed SCGSim inspection APIs for
actual compiled geometry; consult its version-bound guide for their contract.
Never draw an intended lowering and present it as an observed one.

Build the smallest deterministic multi-panel PNG that answers the question:

1. Show the whole component or layout from canonical geometry.
2. Add detail panels for clipping, junction sheets, ports, contacts or
   interfaces that cannot be judged at the whole-layout scale. Use comparable
   physical scales for comparable regions.
3. Distinguish source conductors, actual removed/clipped regions, active
   sheets or shells, solution domain, ports and contact footprints.
4. Label exact layer/semantic IDs, port names, physical groups, route, z-plane
   or thickness, units and known dimensions.
5. Add a cross-section or 3D panel only when it resolves a planar ambiguity.
6. Include a legend and source/settings/artifact-digest footer.

Prefer Matplotlib polygon overlays with equal aspect ratio and an opaque RGB
canvas. Solid conductor fills, hatching for clipped areas, translucent sheet
fills and explicit port/contact outlines are useful conventions; define them
in the legend and do not rely on color alone. Prefer geometry API data over a
viewer screenshot when both can show the same evidence.

Inspect the rendered image before delivery: readable labels, explicit region
extents, visible contacts and provenance matching the plotted artifacts.
Provide the image and a project-relative artifact locator for further viewer
inspection. Keep temporary renders outside tracked source unless intentionally
selected as documentation/evidence. Every output inherits its source data
classification; public procedure does not make private geometry publishable.

If units, groups, semantic IDs or provenance are unavailable, identify the
missing field and limit the plot's claims accordingly. An unbound illustration
cannot substitute for real inspection evidence. The canonical component, GDS
and solver artifacts retain their respective authority.
