---
title: "Process: layers, stack and materials"
---

Use OrPen's layer names for XY geometry and its stack records for physical Z
and material identity. They are different parts of the same source model.
The current [technology source](https://github.com/OrPenStrike/orpen-sc-pdk/blob/develop/orpen_sc_pdk/tech.py)
and [material database](https://github.com/OrPenStrike/orpen-sc-pdk/blob/develop/orpen_sc_pdk/materials.json)
are the authorities; the figures here do not redefine them.

## Pick the layer by purpose

```python
from orpen_sc_pdk import LAYER, LAYER_VIEWS
from orpen_sc_pdk.tech import get_single_die_layer_stack

metal_xy = LAYER.D0_TOP_M1_DRAW
stack = get_single_die_layer_stack()
for name, level in stack.layers.items():
    print(name, level.zmin, level.thickness, level.material)
```

`D0`/`D1` identify dies; `TOP`/`BOTTOM` identify faces. A layer pair is
`(layer, datatype)`, not a height or a material. `LAYER_VIEWS` controls display
colors and visibility, not fabrication or solver physics.

| Source purpose | Common layers | Meaning |
|---|---|---|
| Positive conductor polygons | D0 top DRAW `1/0`, D1 bottom DRAW `2/0` | Source metal islands, traces and explicit ground strips |
| Clearance/removal | D0 top ETCH `1/1`, GROUND_MASK `110/0` | Removal/domain recipes, not additional metal |
| Die footprint | D0 substrate `201/0`, D1 substrate `201/2` | XY substrate extent |
| Bump body / UBM | `40/0` / `40/1` | Separate indium and under-bump source footprints |
| Airbridge deck / piers | `10/0` / `10/1` | Separate elevated Al parts |
| Nonmetal locator | D0 top SIM_BOUNDARY `202/1` | Zero-thickness vacuum sheet locating an interface, not a conductor |

### DRAW, masks and holes

Positive DRAW polygons explicitly carry source metal. The stack's derived M1
recipe is `DOMAIN - (ETCH - DRAW)`. Component simulation also has explicit
face/ground-mask geometry metadata, so carry the full selected stack and the
component's annotations instead of treating every GDS layer as a conductor.

Square/circular pad coupons contain positive PAD and GROUND geometry plus an
opening mask. A ring's inner hole remains nonmetal, not another Ground entity.
The small east-edge locator across the pad gap is a nonmetal sheet, even where
its source footprint lands on conductors. Its optional circuit element and
excitation belong to the selected simulation problem.

## Select the physical stack

Stack getters live in `orpen_sc_pdk.tech`:

- `get_layer_stack()` returns the full die/face-aware public stack.
- `get_two_die_flip_chip_layer_stack()` selects that two-die stack.
- `get_single_die_layer_stack()` returns detached D0 substrate, top M1 and
  locator levels, without an upper die/interdie cavity.
- `get_single_die_layer_stack(include_airbridges=True)` adds D0 top piers/deck.

| Current source level | Z range (µm) | Material |
|---|---|---|
| D0 substrate | −500..0 | Si |
| D0 top base M1 | 0..0.1 | Al (100 nm film) |
| D0 top locator | z = 0.05, thickness 0 | vacuum |
| Flip-chip bump body | 0.1..8.1 | In |
| D1 bottom M1 | 8.1..8.2, outward −Z | Al |
| D1 substrate | 8.2..508.2 | Si |
| D0 airbridge piers | 0.1..3.1 | Al |
| D0 airbridge deck | 3.1..3.4 | Al (300 nm film) |

The 8 µm metal-to-metal bump gap and 3 µm gap above base metal are separately
declared dimensions, not 100 nm films. UBM `40/1` remains source process detail
with `exclude_from_simulation=True`. The nominal airbridge is a rectangular
deck/post model, not a measured reflow arch. Saved examples/results retain
their original notebook-local stacks; they are not regenerated here.

## Material records and presets

The copy-returning [material API](https://github.com/OrPenStrike/orpen-sc-pdk/blob/develop/orpen_sc_pdk/materials.py)
is available from the package root:

```python
from orpen_sc_pdk import (
    get_material_records, get_material_alias_records,
    get_interface_preset_records,
)

materials = get_material_records()
aliases = get_material_alias_records()
presets = get_interface_preset_records()
```

Records carry material identity/kind, superconducting status, numerical
properties and explicit AEDT library identity. Select records appropriate to
your model; retain their IDs and provenance through downstream preparation.
The database contains Woods2019 Si MA/MS/SA and LiteratureCentral MA/MS/SA
interface presets. They are caller-selected model conventions, not measured
properties for every process or automatic defaults. Their authority is
`materials.json`, not the empty technology-level preset dictionary.

## From source intent to simulation

A component declares source regions, layer/stack choices and nonmetal locator
geometry. The consuming design assigns final electrical Nets and problem
intent. A name such as `GROUND` or a layer connectivity declaration alone does
not prove native connectivity or create a solver terminal.

SCGSim consumes structured source/material records and owns native geometry,
backend material/terminal lowering, meshes/configs and returned-result handling.
For AEDT its superconducting records lower to PEC; other records use explicit
library identity. Follow the selected [Simulation example](notebooks.qmd) and
its runtime contract rather than inferring backend behavior from a colored
image. See the [Test Set](public-pdk-examples/test-components.md) for
layer-separated holes, locators, bumps and airbridge crossings.
