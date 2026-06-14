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
- conductor-like public records that currently use
  `relative_permittivity = inf` are preserved as material-role metadata rather
  than exported as solver permittivity values.

Remaining slices:

- add a validated material-record schema and aliases table once the public
  material contract grows beyond the current minimal records;
- let `gsim` Palace config generation accept material overlays without
  mutating PDK layer stacks;
- derive material-loss/T1/gamma report tables only after raw report rows and
  effective Palace config material fields are joined in a public `gsim` layer.

Related issue:

- {doc}`../issues/material-schema-boundary`
