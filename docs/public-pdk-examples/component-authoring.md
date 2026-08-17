# Public Component Authoring

Author public reusable layout with the registered OrPen PDK cells. The PDK
owns public process layers, cross-sections, component factories, and their
registration; a consuming project supplies its own assembly and parameters.

## Start from a registered factory

The public registry is [`orpen_sc_pdk/cells/__init__.py`](https://github.com/OrPenStrike/orpen-sc-pdk/blob/main/orpen_sc_pdk/cells/__init__.py), and
[`orpen_sc_pdk/pdk.py`](https://github.com/OrPenStrike/orpen-sc-pdk/blob/main/orpen_sc_pdk/pdk.py)
adds those factories to the active PDK. Use an existing public primitive or
cell before creating another one:

| Need | Public source example | Public result |
| --- | --- | --- |
| CPW transition | [`cells/taper.py`](https://github.com/OrPenStrike/orpen-sc-pdk/blob/main/orpen_sc_pdk/cells/taper.py) | DRAW conductor, derived clearance, and route ports |
| Differential capacitor | [`cells/martinis.py`](https://github.com/OrPenStrike/orpen-sc-pdk/blob/main/orpen_sc_pdk/cells/martinis.py) | registered capacitor cell with named mesh locators |
| Reusable catalog | [`cells/__init__.py`](https://github.com/OrPenStrike/orpen-sc-pdk/blob/main/orpen_sc_pdk/cells/__init__.py) | the public import surface |
| PDK discovery | [`pdk.py`](https://github.com/OrPenStrike/orpen-sc-pdk/blob/main/orpen_sc_pdk/pdk.py) | active-PDK cell registration |

```python
from orpen_sc_pdk import activate
from orpen_sc_pdk.cells import taper

activate()
component = taper(width1=10, width2=7, length=100)
```

This produces a public layout component; it does not assert a chip-level
assembly, simulation result, or fabrication qualification.

## Review the rendered result

The [component gallery](../notebooks/Public_Docs/component_gallery.ipynb)
shows checked-in public notebook code and output. The [Layout
Viewer](../layout-viewer.qmd) provides browser-only pan, zoom, and component
selection for publication-safe exports. Use the existing [layout and simulation
notebooks](../notebooks.qmd) for runnable SCGSim examples.
