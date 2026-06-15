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
- `orpen_sc_pdk.materials.get_interface_preset_records()` returns a copy of
  public dielectric-interface preset records, currently empty by default;
- `orpen_sc_pdk.materials.validate_interface_preset_records()` validates
  caller-supplied MA/MS/SA-style records with explicit thickness and either a
  public material name or explicit permittivity;
- `orpen_sc_pdk.materials.get_gsim_dielectric_interface_preset_kwargs()` adapts
  a validated record into keyword arguments accepted by
  `gsim.palace.mesh.DielectricInterfaceSpec` without importing `gsim` into the
  base PDK package;
- local `gsim` Palace config generation accepts the overlay through
  `material_overlay=` and applies public material values to effective
  `Domains.Materials` without mutating the source layer stack;
- local `gsim` report loading can read those effective `Domains.Materials`
  rows back from generated artifacts and join them to domain physical names
  through `palace_index_map.json`.
- local `gsim` report loading can also read configured
  `Boundaries.Postprocessing.Dielectric` rows, including `Thickness`,
  `Permittivity`, and `LossTan`, and join them to interface physical names
  through `palace_index_map.json`.
- local `gsim` can build ordered
  `gsim.palace.mesh.DielectricInterfaceSpec` tuples from caller-supplied preset
  maps and exact manifest entry names, physical group names, or parsed
  interface pairs without hard-coding private process values.
- local `gsim` can derive reusable domain/surface loss budgets from those
  loaded artifacts, including inverse-Q, equivalent Q, gamma, and T1 columns
  when mode frequency is available.

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
5. Use `gsim` interface material references when a Palace dielectric interface
   should draw permittivity/loss fields from a public material record.
6. Keep public interface preset records schema-validated in the PDK, but do not
   populate MA/MS/SA thickness, loss, or automatic-selection defaults until
   source-backed public records exist.
7. Use `gsim` assignment helpers for caller-supplied physical-name or
   interface-pair selection; automatic public selection policy belongs in a
   later source-backed PDK contract.

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
