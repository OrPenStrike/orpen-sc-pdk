# GDSFactory+ PDK Discovery

**Target:** `orpen-sc-pdk`

**Status:** prototype

The PDK should remain discoverable when opened as the active VSCode folder with
the GDSFactory+ extension.

Required shape:

- flat package layout;
- public `orpen_sc_pdk.cells` registry;
- public `orpen_sc_pdk.samples`;
- reserved `orpen_sc_pdk.models`;
- `[tool.gdsfactoryplus]` metadata in `pyproject.toml`.
