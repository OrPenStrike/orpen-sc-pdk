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
- `gsim` commit `f12312c`: adds `summarize_domain_loss()`,
  `summarize_surface_loss()`, `summarize_loss_budget()`, and
  `EigenmodeReport.domain_loss` / `surface_loss` / `loss_budget`, deriving
  inverse-Q, equivalent Q, gamma, and T1 columns from reusable public report
  frames;
- `gsim` commit `61d7d66`: adds `resolve_palace_materials_with_report()`,
  writes `palace_material_resolution.json` beside generated Palace configs,
  and extends `load_domain_material_summary()` with stack material, matched
  material, model source, validity, and frequency provenance columns;
- `gsim` commit `1da6783`: extends the same material-resolution path to
  dielectric postprocessing interfaces, so a typed interface can reference a
  public material overlay entry and reports can show interface material name,
  matched material, model source, validity, and resolution frequency;
- public `orpen-sc-pdk` tests now pass `get_gsim_material_overlay()` into
  Driven, Eigenmode, and Electrostatic `gsim` config generation, verify the
  generated substrate material block uses the public `Si` permittivity, and
  verify the effective substrate material row and material-resolution
  provenance are loadable through the reusable `gsim` report/index-map API;
- public `orpen-sc-pdk` tests now verify the public
  `AlOx_native_generic` material can be resolved into
  `Boundaries.Postprocessing.Dielectric` without writing non-Palace handoff
  keys into `config.json`;
- public `orpen-sc-pdk` tests now also verify a synthetic Eigenmode artifact
  bundle can load through `gsim.palace.load_eigenmode_report()` and expose
  public domain/surface loss budget rows;
- `orpen-sc-pdk` now exposes an empty-by-default
  `tech.interface_preset_records` table, validates caller-supplied
  MA/MS/SA-style records through `validate_interface_preset_records()`, and
  adapts validated records into `gsim.palace.mesh.DielectricInterfaceSpec`
  keyword arguments through `get_gsim_dielectric_interface_preset_kwargs()`;
- public tests now prove a caller-supplied source-backed interface preset can
  feed `gsim` dielectric postprocessing, resolve `AlOx_native_generic` through
  the public material overlay, strip non-Palace handoff keys from
  `config.json`, and load interface material provenance through the reusable
  report/index-map path;
- read-only NCUAS audit confirms the private repo already has MA/MS/SA
  classification, thin-film MA+MS duplicate-spec behavior, preset lookup,
  `materials.json` numeric interface-loss values, notebook-local override
  maps, and masked Surface EPR; this public slice preserves the schema/adapter
  boundary without copying private values or private layer names;
- the exported overlay keeps finite dielectric records as constant material
  models and keeps conductor-like `inf` records out of solver permittivity.

Remaining slices:

- introduce a validated public material-record schema when the current dict
  grows to include aliases, provenance, conditions, loss, conductivity,
  London-depth, or surface/interface presets;
- populate public interface preset records only after MA/MS/SA thickness, loss
  tangent, and automatic-selection values have source-backed public records.
- upstream a generic `gsim` role/physical-group assignment path for
  user-supplied interface preset maps before trying to reproduce private
  notebook-local automatic MA/MS/SA selection.

Related feature:

- {doc}`../features/material-db-overlay`
