---
title: "Get Started"
---

Use Python 3.12 or 3.13 and the GDSFactory version selected by this package.
Install OrPen in your existing Python environment:

```bash
python -m pip install "orpen-sc-pdk @ git+https://github.com/OrPenStrike/orpen-sc-pdk.git@develop"
```

This selects the public `develop` line, not a stable release. Record the exact
revision your environment resolves so the installation can be reproduced.

## Activate and build

```python
import gdsfactory as gf
from orpen_sc_pdk import activate, get_pdk

activate()
component = gf.get_component("resonator", length=3500)
print(component.name, component.dbbox(), component.layers)
print(sorted(get_pdk().cells))
```

If a compatible local layout viewer is available, call `component.show()` to
open the cell. This is optional; the build above does not require a viewer.

Dimensions are in micrometres. Public factory defaults are preview settings,
not measured device specifications; choose your own process and design
parameters. Activate OrPen before resolving named cells or
cross-sections; do not silently substitute another PDK.

Choose the existing [Cells](public-pdk-examples/index.md) and read their typed
settings/source intent before composing a design. Use [Process](materials-and-technology.md)
for layers, materials and stack facts. The [GDSFactory+ guide](features/gdsfactoryplus-discovery.md)
describes optional interactive by-name build/review in the same public project.

## Add simulation only when needed

Layout use does not require an AEDT or Palace installation. Public simulation
notebooks consume SCGSim's reusable simulation runtime.
Select a [Simulation](notebooks.qmd) example and follow its exact runtime
prerequisites. The newer source-only examples require a separate SCGSim v2
environment; the ordinary project dependency groups do not select that cohort.
Saved outputs and source-only revisions are not interchangeable evidence.
