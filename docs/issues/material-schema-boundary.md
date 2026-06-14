# Material Schema Boundary

**Repo:** `gsim`, `orpen-sc-pdk`

The PDK should own SCQ material records and aliases. `gsim` should own reusable
material resolution and Palace-specific evaluation.

Problem:

- private simulation workflows use material records, material conditions,
  Palace domain/boundary material policies, and interface-loss presets;
- public PDK material data currently starts as a small
  `relative_permittivity` dictionary;
- `gsim` already owns reusable material overlay loading, frequency evaluation,
  and Palace translation, so the PDK should not grow a solver runtime.

Proposed path:

- keep public material records and aliases in `orpen-sc-pdk`;
- make those records exportable in the `gsim` overlay schema;
- keep frequency evaluation and Palace config material blocks in `gsim`;
- keep effective config material report joins in `gsim`;
- keep configured dielectric interface report joins in `gsim`;
- add material-loss/T1/gamma report interpretation on top of raw Palace
  reports joined to effective config material and interface fields.

Verified local changes:

- `gsim` commit `20538ec`: adds `load_overlay_data()` for in-memory PDK overlay
  mappings and extends `load_overlay()` aliases to accept PDK-style
  `relative_permittivity`, `epsilon_r`, `eps_r`, `relative_permeability`, and
  `mu_r` fields;
- `orpen-sc-pdk` now exports public material records through
  `get_material_records()`;
- `orpen-sc-pdk` now exports `get_gsim_material_overlay()` and
  `write_gsim_material_overlay()` so the current `tech.material_properties`
  records can be consumed by `gsim.common.stack.load_overlay_data()` or
  `load_overlay()` without importing private material registries;
- `gsim` commit `49be250`: adds `material_overlay=` to Palace config
  generation, keeps overlay resolution out of `LayerStack` mutation, and maps
  PDK aliases such as `Si` onto existing `gsim` material names such as
  `silicon`;
- `gsim` commit `0197b64`: adds `load_domain_material_summary()` and
  `EigenmodeReport.domain_materials`, joining effective `Domains.Materials`
  rows from `config.json` back to domain physical names through
  `palace_index_map.json`;
- `gsim` commit `bbd74fe`: adds `load_dielectric_interface_summary()` and
  `EigenmodeReport.dielectric_interfaces`, joining configured
  `Boundaries.Postprocessing.Dielectric` rows back to index-map physical names
  while keeping derived loss/T1/gamma out of this slice;
- public `orpen-sc-pdk` tests now pass `get_gsim_material_overlay()` into
  Driven, Eigenmode, and Electrostatic `gsim` config generation, verify the
  generated substrate material block uses the public `Si` permittivity, and
  verify the effective substrate material row is loadable through the reusable
  `gsim` report/index-map API;
- the exported overlay keeps finite dielectric records as constant material
  models and keeps conductor-like `inf` records out of solver permittivity.

Remaining slices:

- introduce a validated public material-record schema when the current dict
  grows to include aliases, provenance, conditions, loss, conductivity,
  London-depth, or surface/interface presets;
- add explicit material validity ranges and provenance fields to remove
  ambiguity from effective config/report material interpretation;
- introduce a validated public interface-preset schema for MA/MS/SA-style
  thickness, permittivity, and loss tangent records;
- derive material-loss/T1/gamma tables after effective domain material and
  configured interface summaries are explicit enough for downstream analysis.

Related feature:

- {doc}`../features/material-db-overlay`
