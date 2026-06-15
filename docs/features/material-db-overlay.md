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
- `gsim` commit `0197b64` adds `load_domain_material_summary()` and wires
  `EigenmodeReport.domain_materials`, so effective Palace material rows can be
  loaded from `config.json` and joined to domain physical names through
  `palace_index_map.json`;
- `gsim` commit `bbd74fe` adds `load_dielectric_interface_summary()` and wires
  `EigenmodeReport.dielectric_interfaces`, so configured
  `Boundaries.Postprocessing.Dielectric` interface parameters can be joined to
  index-map physical names;
- `gsim` commit `f12312c` adds domain/surface loss interpretation on top of
  the existing report joins, deriving inverse-Q, equivalent Q, gamma, and T1
  columns without moving report parsing into the PDK;
- `gsim` commit `61d7d66` adds material-resolution provenance sidecars for
  generated Palace configs and extends `load_domain_material_summary()` so
  reports can show the stack material name, matched material record, model
  source, validity status, and resolution frequency used for each Palace
  material attribute;
- `gsim` commit `1da6783` lets dielectric postprocessing interfaces reference a
  material overlay entry, resolves that reference before writing Palace
  `config.json`, strips the non-Palace handoff key, records interface material
  provenance in `palace_material_resolution.json`, and exposes that provenance
  through `load_dielectric_interface_summary()`;
- public Driven, Eigenmode, and Electrostatic fixtures now pass
  `get_gsim_material_overlay()` into local `gsim` config generation, verify
  that the public `Si` record reaches the generated substrate material block,
  and load that effective substrate material row back through the `gsim`
  report/index-map API;
- public material-overlay tests now verify `AlOx_native_generic` can be used as
  a dielectric-interface material reference while interface thickness and
  MA/MS/SA default selection remain explicit caller choices;
- conductor-like public records that currently use
  `relative_permittivity = inf` are preserved as material-role metadata rather
  than exported as solver permittivity values.

Remaining slices:

- add a validated material-record schema and aliases table once the public
  material contract grows beyond the current minimal records;
- add a validated public interface-preset schema before treating MA/MS/SA
  thickness, loss tangent, and automatic preset selection as PDK-owned
  defaults.

Related issue:

- {doc}`../issues/material-schema-boundary`
