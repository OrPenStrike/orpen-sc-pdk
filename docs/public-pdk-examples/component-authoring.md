# Public Component Authoring

Author public reusable layout with the registered OrPen PDK cells. The PDK
owns public process layers, cross-sections, component factories, and their
registration; a consuming project supplies its own assembly and parameters.

The [package usage inventory](../usage/index.md) also identifies notebook
pairing rules and the boundary to installed SCGSim runtime knowledge.

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

## Environment, discovery and preview defaults

Use the package versions selected by the consuming environment. Activate
OrPen before resolving string component or cross-section specifications;
never silently replace it with the generic PDK. Discover `get_pdk().cells`
and `get_pdk().cross_sections` and inspect factory signatures before passing
settings. Public sample assemblies are separately discoverable through
`get_sample_functions()`; they do not redefine the reusable cell registry.

Every newly registered or modified viewer-facing factory must build by name
without supplied settings. Preview defaults must be public, valid physical
settings on the manufacturing grid. They are not an accepted device target;
explicit design settings take precedence. A missing factory, required argument
or invalid setting needs a source correction, not an unregistered wrapper.

```python
import inspect

from orpen_sc_pdk import activate, get_pdk

activate()
pdk = get_pdk()
factory = pdk.cells["taper"]
print(inspect.signature(factory))
component = pdk.get_component("taper")
print(component.name, component.dbbox(), component.layers)
for port in component.ports:
    print(port.name, port.center, port.orientation)
```

The project metadata in `pyproject.toml` identifies `orpen_sc_pdk` as both
project and PDK for GDSFactory+ discovery. In the matching VS Code project,
select the canonical factory, edit its typed settings, then Build/Reload and
inspect the layout. Headless construction uses the same factory. If a live
viewer is unavailable, report the factory and settings with headless evidence
and leave live viewer confirmation explicit.

## Geometry and physical units

Bind dimensions to the design request, exact candidate, or public PDK record.
Reuse registered cells, cross-sections and GDSFactory primitives first. Keep
the component body readable as a physical layout: named dimensions, shallow
hierarchy, child ports and semantic anchors. An independently reusable,
previewable or routable piece can be a `@gf.cell` subcomponent. Do not create
another geometry implementation just for a viewer or a notebook.

Use public GDSFactory APIs for polygons, booleans, paths, cross-sections,
references, transforms, flattening and GDS/OASIS export. Ordinary dimensions
and coordinates are in micrometres; integer database units are a different
representation. Check dimensions independently with `Component.dbbox()` or
the applicable physical-unit API. A self-consistent database-unit probe or a
plausible picture cannot establish correct physical size. Do not use transform
magnification to create a parametric size variant.

Direct KLayout database access is reserved for a concrete interoperability
operation lacking a suitable public GDSFactory API. Document that missing
capability and the unit conversion at the narrow boundary; do not expose
database types through ordinary component APIs. Use `gf.boolean()` directly
for ordinary set operations; a shared helper should carry reusable layout
meaning rather than simply rename a boolean operation.

## PDK records and component semantics

Use `LAYER`, `LAYER_STACK`, `LAYER_VIEWS` and `LAYER_CONNECTIVITY` from OrPen.
`get_material_records()` and `get_material_alias_records()` return copies of
the public material authority. Use `get_interface_preset_records()` with
`validate_interface_preset_records()` for interface presets. A component
selects these records and owns its source geometry, nets, reference conductors,
ports, keepouts and annotations. Preserve child-owned port metadata when
forwarding ports; do not reconstruct it from guessed parent coordinates.

```python
from orpen_sc_pdk import (
    get_interface_preset_records,
    validate_interface_preset_records,
)

records = validate_interface_preset_records(get_interface_preset_records())
selected = {key: records[key] for key in (
    "LiteratureCentral_MA", "LiteratureCentral_MS", "LiteratureCentral_SA"
)}
```

These named presets are synthetic literature-central model conventions, not
measured process properties. Their records own values and provenance: ordinary
medians for permittivity/thickness, log-space medians for loss tangent and
documented row exclusions. Missing records must fail visibly; do not insert
notebook-local values. Preserve material IDs from stack records, including
indium bump identity, through downstream consumption. Backend assignment and
conductor lowering are SCGSim responsibilities.

For simulation-facing components, inspect the real `component_semantics`
record, port sheet geometry and net/owner identity. Do not infer identity from
labels, bounding boxes or residual polygons. Mesh controls and solver L/C/R
belong to the simulation consumer/runtime, not layout locator ports. Refer to
the installed SCGSim bundle for ingestion and lowering contracts.

## Small validation loop

Build the canonical factory headlessly, inspect layers, hierarchy, physical
bounds, settings, ports and orientation, then render and inspect a PNG. Check
route continuity, clearances, intended coupling and grounding. Validate GDS
round-trip and applicable repository connectivity/DRC checks when required by
the changed surface. Clear the cell cache between independent generations so
the preview represents the intended source/settings. Use the
[semantic inspection procedure](../usage/semantic-inspection.md) when local
contacts, ports or lowered geometry need a more detailed view.

Retain exact source/settings and classify previews as diagnostic. Missing
semantic IDs, incompatible parameters, unit errors or export failures are
concrete findings; a successful preview does not establish solver correctness
or fabrication qualification.

## Review the rendered result

The [component gallery](../notebooks/Public_Docs/component_gallery.ipynb)
shows checked-in public notebook code and output. The [Layout
Viewer](../layout-viewer.qmd) provides browser-only pan, zoom, and component
selection for publication-safe exports. Use the existing [layout and simulation
notebooks](../notebooks.qmd) for runnable SCGSim examples.
