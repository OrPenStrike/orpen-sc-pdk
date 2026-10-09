# GDSFactory+ PDK Discovery

**Target:** `orpen-sc-pdk`

Open this repository as the active VS Code folder with the GDSFactory+
extension. The project and PDK are both named `orpen_sc_pdk` in
`pyproject.toml`; the extension supplies its own SDK.

Required shape:

- the existing top-level Python package;
- public `orpen_sc_pdk.cells` registry for reusable PDK cells;
- public sample catalog for demo-only assemblies;
- reserved `orpen_sc_pdk.models`;
- `[tool.gdsfactoryplus]` metadata in `pyproject.toml`.

Reusable layout factories live in `orpen_sc_pdk/cells/layout/`; public source
simulation coupons and sample-only chip factories live in
`orpen_sc_pdk/cells/simulation/`. The public `cells` exports and active-PDK
keys remain unchanged. See the [migration and tag table](../usage/cell-organization.md)
for deep imports and discovery metadata. Sample-only assemblies remain in the
sample catalog, not the PDK registry.

Activate OrPen, select the canonical factory by its existing name, then use
Build/Reload and inspect the Layout Viewer. Default builds require no settings;
explicit consumer settings take precedence over public preview defaults.
For example, `resonator` is sourced from `cells/layout/resonator.py` and
`square_pad_capacitor` from `cells/simulation/simple_pad.py`.

The equivalent headless entry point is:

```python
from orpen_sc_pdk import activate, get_pdk

activate()
component = get_pdk().get_component("resonator")
```

Headless registration/name-build evidence does not confirm a live extension
session. When an OrPen GF+ project is unavailable, live Viewer confirmation
remains a Human check in that project; do not substitute a private project.
