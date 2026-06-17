# Material Database Overlay

**Target:** `orpen-sc-pdk` and `gsim`

**Status:** prototype

SCQ material records should live in the PDK. Reusable material resolution,
frequency evaluation, and Palace material translation should live in `gsim`.

The integration should preserve `materials.json` style data sources when they
are introduced, rather than treating them as generated artifacts.

Acceptance direction:

- `orpen-sc-pdk` publishes only public material names, aliases, and parameter
  records;
- `gsim` loads PDK material overlays, applies frequency-dependent evaluation,
  and writes Palace material blocks;
- material provenance is visible in generated configs and reports;
- private material overlays can be mounted locally without becoming part of the
  public PDK.

Current public baseline:

- `gsim` commit `20538ec` adds `load_overlay_data()` and PDK-style field
  aliases such as `relative_permittivity`, `epsilon_r`, `eps_r`, and
  `relative_permeability` to the reusable material overlay loader;
- `orpen-sc-pdk` exposes public material records through
  `get_material_records()`;
- `orpen-sc-pdk` exposes `get_gsim_material_overlay()` and
  `write_gsim_material_overlay()` so public PDK material records can be handed
  to `gsim` either in memory or as strict JSON;
- `gsim` commit `49be250` adds `material_overlay=` to Palace config generation
  and high-level `write_config()`, so public PDK overlays can affect effective
  Palace `Domains.Materials` without mutating `LayerStack.materials`;
- `gsim` commit `0197b64` adds
  `gsim.palace.resolve.derived.materials.load_domain_material_summary()` and
  wires
  `EigenmodeReport.domain_materials`, so effective Palace material rows can be
  loaded from `config.json` and joined to domain physical names through
  `palace_index_map.json`;
- `gsim` commit `bbd74fe` adds
  `gsim.palace.resolve.derived.materials.load_dielectric_interface_summary()`
  and wires
  `EigenmodeReport.dielectric_interfaces`, so configured
  `Boundaries.Postprocessing.Dielectric` interface parameters can be joined to
  index-map physical names;
- `gsim` commit `f12312c` adds domain/surface loss interpretation on top of
  the existing report joins, deriving inverse-Q, equivalent Q, gamma, and T1
  columns without moving report parsing into the PDK;
- `gsim` commit `61d7d66` adds material-resolution provenance sidecars for
  generated Palace configs and extends the domain-material summary path so
  reports can show the stack material name, matched material record, model
  source, validity status, and resolution frequency used for each Palace
  material attribute;
- `gsim` commit `1da6783` lets dielectric postprocessing interfaces reference a
  material overlay entry, resolves that reference before writing Palace
  `config.json`, strips the non-Palace handoff key, records interface material
  provenance in `palace_material_resolution.json`, and exposes that provenance
  through the dielectric-interface summary path;
- `gsim` commit `667cd21` adds
  `build_dielectric_interface_specs_from_assignments()`, so caller-owned
  preset maps can target exact manifest entry names, physical group names, or
  parsed interface pairs and produce ordered `DielectricInterfaceSpec` records
  without baking private layer names or MA/MS/SA values into `gsim`;
- `gsim` commit `34f2a4d` adds
  `build_dielectric_interface_specs_from_material_kinds()`, so caller-owned
  material-kind maps can classify parsed manifest interfaces into generic
  `MA`, `MS`, and `SA` specs while skipping exterior boundaries and non-loss
  material-kind pairs;
- `orpen-sc-pdk` public material records now include explicit generic
  `material_kind` metadata, validated through
  `validate_material_kind_records()` and exported as
  `get_gsim_material_kind_map()` for `gsim` interface classification without
  exposing private process values or preset-selection policy;
- `orpen-sc-pdk` now exposes `tech.material_alias_records`,
  `get_material_alias_records()`, `validate_material_alias_records()`, and
  `get_gsim_material_kind_alias_map()` so generated material names such as
  `air` and `silicon` can be classified through public `vacuum` and `Si`
  records without becoming duplicate material records or overlay entries;
- local `gsim` commit `2b2d1bc` extends reusable material overlay loading with
  optional `material_aliases`, so generated material names such as `air` and
  `silicon` can resolve through public PDK `vacuum` and `Si` overlay records
  during Palace material resolution without making OrPen duplicate material
  records;
- `orpen-sc-pdk` now includes `material_aliases` in
  `get_gsim_material_overlay()` and written overlay JSON, while keeping those
  aliases as metadata for `gsim` expansion rather than entries in
  `tech.material_properties`;
- public Driven, Eigenmode, and Electrostatic fixtures now pass
  `get_gsim_material_overlay()` into local `gsim` config generation, verify
  that the public `Si` record reaches the generated substrate material block,
  and load that effective substrate material row back through the `gsim`
  report/index-map API;
- public material-overlay tests now verify `AlOx_native_generic` can be used as
  a dielectric-interface material reference while interface thickness and
  MA/MS/SA default selection remain explicit caller choices;
- public material-overlay tests now also verify a caller-supplied, source-backed
  interface preset record can flow through the `gsim` material-kind classifier
  using OrPen's public material-kind map and generated-name alias map, and then
  through reusable Palace config/material-resolution/report loading;
- `orpen-sc-pdk` now exposes an empty-by-default
  `tech.interface_preset_records` table plus
  `get_interface_preset_records()`,
  `validate_interface_preset_records()`, and
  `get_gsim_dielectric_interface_preset_kwargs()` so caller-supplied
  source-backed MA/MS/SA records can be validated, rejected when missing
  explicit source/provenance, and handed to
  `gsim.palace.mesh.postprocessing.DielectricInterfaceSpec` without making
  private defaults public;
- `orpen-sc-pdk` now has a public surface-loss source-review queue and a
  source-backed interface preset issue, so future MA/MS/SA records have a
  documented path from public papers to PDK data instead of being copied from
  private presets;
- the public source-review queue now includes candidate Wenner-style
  assumed/scaled rows and Woods-style fitted CPW rows, keeping candidate values
  reviewable without adding them to the default PDK table;
- the same source-review queue is mirrored as
  `scripts/fixtures/public_interface_preset_review_queue.json` and displayed
  from the public simulation inventory notebook, making MA/MS/SA promotion
  gates reviewable without widening the PDK or `gsim` public runtime APIs;
- `public_interface_preset_promotion_gate_evidence.json` now records each
  candidate's missing acceptance decisions, so notebook review can see that
  interface candidates remain `awaiting_public_policy` until accepted IDs,
  process scope, default-selection rules, and public-default decisions exist;
- public thin-film conductor-sheet proxy evidence now uses OrPen material-kind
  maps and generated-name aliases with `gsim` material-kind classification to
  emit separate caller-supplied `MA` and `MS` dielectric-interface rows for
  public `Al___air` and `Al___silicon` interface names, then reloads the
  generated rows through
  `gsim.palace.resolve.derived.materials.load_dielectric_interface_summary()`;
- local `gsim` now carries caller-supplied interface preset name/source
  metadata through `palace_index_map.json`, dielectric-interface summaries, and
  surface-loss summaries; `orpen-sc-pdk` passes its validated preset source
  strings into that path without adding non-Palace fields to `config.json`;
- public evidence and report-backed notebook cells now load generated domain
  material rows through report-owned `domain_materials` and the
  `gsim.palace.resolve.derived.materials.load_domain_material_summary()` owner
  path, proving
  `palace_material_resolution.json` can explain stack material name, matched
  material record, model source, validity status, resolution frequency,
  permittivity, permeability, loss, and conductivity for Driven, Eigenmode,
  and Electrostatic public configs;
- public nonmagnetic dielectric/vacuum material records now carry unit
  permeability through the same OrPen material overlay and `gsim` Palace
  material-resolution path; the current public fixtures verify generated
  `silicon` and `air` domains through the public `Si` and `vacuum` records via
  `gsim` overlay alias expansion;
- conductor-like public records that currently use
  `relative_permittivity = inf` are preserved as material-role metadata rather
  than exported as solver permittivity values.

Remaining slices:

- add a broader validated material-record schema once the public material
  contract grows beyond explicit material kinds, generated-name aliases, and
  current minimal electromagnetic records;
- populate public interface preset records only after source-backed public
  MA/MS/SA values and automatic-selection rules are accepted into the PDK
  contract; until then, keep selection caller-supplied and explicitly sourced
  through the `gsim` assignment/classification helpers.

Related issue:

- {doc}`../issues/material-schema-boundary`
- {doc}`../issues/source-backed-interface-presets`
