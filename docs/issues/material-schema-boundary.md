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
- `gsim` commit `667cd21`: adds
  `build_dielectric_interface_specs_from_assignments()` for caller-supplied
  interface preset maps, exact manifest entry or physical-name selectors,
  parsed interface-pair selectors, ordered duplicate MA/MS entries on one
  boundary, and default rejection of exterior/non-interface boundaries;
- `gsim` commit `34f2a4d`: adds
  `build_dielectric_interface_specs_from_material_kinds()` for caller-supplied
  material-kind maps, generic `conductor/vacuum -> MA`,
  `conductor/dielectric -> MS`, and `dielectric/vacuum -> SA` classification,
  exterior `None`/`boundary` skipping, conductive aliases, and optional
  kind-pair overrides for duplicate MA/MS specs on one boundary;
- `orpen-sc-pdk` now records explicit generic `material_kind` values on public
  material records and exposes `validate_material_kind_records()` plus
  `get_gsim_material_kind_map()`, giving `gsim` classifier callers a public
  material-name-to-kind map without exporting preset defaults or copying
  private process constants;
- `orpen-sc-pdk` now records public generated-name aliases in
  `tech.material_alias_records` and exposes
  `get_material_alias_records()`, `validate_material_alias_records()`, and
  `get_gsim_material_kind_alias_map()`, so generated `air`/`silicon` names can
  classify through public `vacuum`/`Si` records without becoming duplicate
  material records or overlay entries;
- `gsim` commit `2b2d1bc`: extends reusable
  `gsim.common.stack.overlays.load_overlay_data()` with optional
  `material_aliases` expansion, keeps alias validation in the shared overlay
  loader rather than Palace-specific code, and lets generated `air` use
  resolved overlay material properties during Palace config generation instead
  of hard-coded built-in `gsim` vacuum fields;
- `orpen-sc-pdk` now exports `tech.material_alias_records` through
  `get_gsim_material_overlay()["material_aliases"]`, so generated `air` and
  `silicon` domains can resolve through public `vacuum` and `Si` overlay
  records while `tech.material_properties` remains the only public material
  record table;
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
  MA/MS/SA-style records through `validate_interface_preset_records()`,
  rejects records without explicit source/provenance strings, and adapts
  validated records into
  `gsim.palace.mesh.postprocessing.DielectricInterfaceSpec` keyword arguments
  through `get_gsim_dielectric_interface_preset_kwargs()`;
- public tests now prove a caller-supplied source-backed interface preset can
  feed `gsim` dielectric postprocessing, resolve `AlOx_native_generic` through
  the public material overlay, strip non-Palace handoff keys from
  `config.json`, and load interface material provenance through the reusable
  report/index-map path;
- public tests now also prove the same caller-supplied interface preset records
  can flow through the `gsim` material-kind classifier using OrPen's public
  material-kind map and generated-name alias map before Palace config and
  report loading, without introducing public default MA/MS/SA values;
- public Eigenmode workflow tests now prove the same path against a real
  generated public resonator mesh manifest: the generated `air___silicon`
  interface classifies through public `air -> vacuum` and `silicon -> Si`
  aliases, resolves `AlOx_native_generic` through the public material overlay,
  and loads interface material provenance through the reusable report/index-map
  path;
- the public simulation workflow notebook now shows that generated-interface
  classification path with a notebook-local caller-supplied preset, keeping
  public preset defaults source-gated while making the handoff visible in docs;
- the public surface-loss paper board now lists candidate sources and extracted
  review rows for `MA`/`MS`/`SA` taxonomy, source-backed interface-loss
  extraction, transmon validation targets, and uncertainty-aware CPW
  interpretation;
- {doc}`source-backed-interface-presets` now records the issue-level gate for
  converting those sources into public PDK preset records and later default
  selection without copying private NCUAS preset names;
- local `gsim` now preserves caller preset name/source metadata in index maps
  and dielectric-interface report summaries, and OrPen passes validated
  source strings into that reusable handoff without changing Palace
  `config.json`;
- public Driven, Eigenmode, and Electrostatic workflow examples intentionally
  continue to pass only `get_gsim_material_overlay()` into generated configs:
  those examples should not wire `get_gsim_material_kind_map()` into automatic
  interface postprocessing until source-backed public presets and a public
  default-selection policy exist;
- public evidence and notebook outputs now load generated domain material
  provenance through `gsim.palace.load_domain_material_summary()`, verifying
  public Driven, Eigenmode, and Electrostatic configs expose stack material,
  matched material, model source, validity, frequency, permittivity,
  permeability, loss, and conductivity without PDK-owned material report
  parsing;
- public `orpen-sc-pdk` material records now include explicit unit
  permeability for the public nonmagnetic vacuum, silicon, and generic native
  aluminum-oxide dielectric records; local evidence verifies that the generated
  `silicon` domain resolves through the public `Si` overlay record, reaches
  `Domains.Materials[*].Permeability`, and reloads through the reusable
  `gsim.palace.load_domain_material_summary()` material-provenance table;
- read-only NCUAS audit confirms the private repo already has MA/MS/SA
  classification, thin-film MA+MS duplicate-spec behavior, preset lookup,
  `materials.json` numeric interface-loss values, notebook-local override
  maps, and masked Surface EPR; this public slice preserves the schema/adapter
  boundary without copying private values or private layer names;
- read-only NCUAS material audit also confirms private `materials.json` and
  Palace material models include `LondonDepth`, default permeability, and
  boundary material fields, but public `gsim` currently has no London-depth
  overlay alias, resolved-material field, Palace config emission, or report
  column; London-depth therefore remains a later schema/config/report feature,
  not a value to copy into current public OrPen material records;
- the exported overlay keeps finite dielectric records as constant material
  models and keeps conductor-like `inf` records out of solver permittivity.

Remaining slices:

- introduce a broader validated public material-record schema when the current
  dict grows beyond explicit material kinds, generated-name aliases, and
  minimal EM fields to include provenance, conditions, loss, conductor
  conductivity policy, London-depth, or surface/interface presets;
- add public London-depth only with an explicit source-bearing schema, units and
  process validity fields, `gsim` overlay aliases, Palace config emission, and
  report/provenance columns;
- populate public interface preset records only after MA/MS/SA thickness, loss
  tangent, material-kind data, and automatic-selection values have selected
  source-backed public records that satisfy the explicit source/provenance
  schema;
- design the later public default-selection policy separately from private
  notebook-local MA/MS/SA heuristics.

Related docs:

- {doc}`../features/material-db-overlay`
- {doc}`source-backed-interface-presets`
