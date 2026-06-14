---
orphan: true
---

# Materials And Technology

`orpen-sc-pdk` is responsible for public superconducting process semantics. The
PDK should make material and technology data easy for simulation workflows to
consume, but it should not duplicate a full solver framework.

## PDK-Owned Data

The PDK owns:

- public layer names and layer numbers;
- layer views;
- layerstack z positions, thicknesses, and material names;
- public material records and aliases for the SCQ process;
- cross-sections and port conventions for public examples;
- schema/export helpers that let solver packages consume PDK materials.

Current public material data exists in `orpen_sc_pdk.tech.material_properties`.
When `materials.json` is introduced or imported, it should remain a first-class
data source rather than a generated afterthought. It should be schema-validated
and treated as part of the public PDK contract.

The current public bridge is intentionally small:

- `orpen_sc_pdk.materials.get_material_records()` returns a copy of the public
  material records;
- `orpen_sc_pdk.materials.get_gsim_material_overlay()` adapts those records to
  the `gsim` material overlay mapping;
- `orpen_sc_pdk.materials.write_gsim_material_overlay()` writes the same
  mapping as strict JSON for tools that consume overlay files;
- local `gsim` Palace config generation accepts the overlay through
  `material_overlay=` and applies public material values to effective
  `Domains.Materials` without mutating the source layer stack;
- local `gsim` report loading can read those effective `Domains.Materials`
  rows back from generated artifacts and join them to domain physical names
  through `palace_index_map.json`.

Finite public dielectric records are exported as constant material models.
Conductor-like records currently represented by
`relative_permittivity = inf` are preserved as material-role metadata until
explicit conductivity, surface impedance, or London-depth values are part of
the public material record.

## Existing Ecosystem Material DB

The local `gsim` fork already has a common material database and resolver:

- `gsim.common.stack.materials.MaterialProperties`
- `gsim.common.stack.materials.MATERIALS_DB`
- `gsim.common.stack.materials.get_material_properties`
- `gsim.common.stack.materials.resolve_material_at_wavelength`
- `gsim.palace.materials.resolve_palace_materials_at_frequency`

It also supports a PDK overlay lookup path. That means the integration direction
should be:

1. Keep SCQ material records in `orpen-sc-pdk`.
2. Export or adapt those records into the `gsim` material overlay/schema.
3. Pass the overlay into `gsim` Palace config generation, keeping
   Palace-specific material evaluation in `gsim`, not in the PDK core.
4. Upstream reusable adapter support into `gsim` when it is not PDK-specific.

`gplugins` also has material utilities for existing plugin workflows. Use it
when the capability belongs to the broader plugin ecosystem rather than the
simulation workflow layer.

## Palace Support Surface

For Palace electrostatic, EPR, reporting, and surface-Q index mapping, the PDK
should provide:

- stable layer semantics for conductor, dielectric, vacuum, and simulation
  boundary layers;
- material names and material properties that can be resolved by solver tools;
- public-safe component metadata that lets solver workflows consume private
  cells without depending on private repository internals;
- documentation and notebooks that show how the workflow is wired without
  publishing private layout/IP.

Reusable Palace execution, report generation, and benchmark analysis belong in
`gsim` unless the capability is only a PDK data export. This prevents the PDK
from becoming a solver orchestration repository.

## Meshing Direction

Meshing strategy should follow the reusable `gsim` direction. PDK docs should
describe required process/layer/material inputs, but mesh generation logic
should not be duplicated in `orpen-sc-pdk` when `gsim` provides the correct
route.
