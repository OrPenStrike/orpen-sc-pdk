---
title: "Build and compose components"
---

Activate OrPen, select a registered factory and supply the dimensions you need.
Coordinates, lengths and port widths use micrometres.

```python
import gdsfactory as gf
from orpen_sc_pdk import activate, get_pdk
from orpen_sc_pdk.cells import taper

activate()
print(sorted(get_pdk().cells))
transition = taper(width1=10, width2=7, length=100)
print(transition.dbbox(), transition.layers)
for port in transition.ports:
    print(port.name, port.center, port.orientation)
```

The [public factories](https://github.com/OrPenStrike/orpen-sc-pdk/blob/develop/orpen_sc_pdk/cells/__init__.py)
are also available by name through `gf.get_component`. Defaults are preview
settings; use explicit parameters for your design.

## Place and connect real children

```python
from orpen_sc_pdk.cells import straight

assembly = gf.Component()
a = assembly << transition
b = assembly << straight(length=200, cross_section="cpw_6_7_6")
b.connect("o1", a.ports["o_taper_out"])
assembly.add_port("input", port=a.ports["o_taper_in"])
assembly.add_port("output", port=b.ports["o2"])
```

Use the child's actual ports when connecting or forwarding them. A port's
center, orientation, width and layer describe a layout interface; they do not
assign a solver terminal, lumped inductance or final electrical Net. Use
`ref.move((x, y))` or `ref.rotate(angle)` to place a child, and inspect
`assembly.dbbox()` for its physical bounds. Change factory dimensions instead
of magnifying instances.

## Draw on the intended layer

```python
from orpen_sc_pdk import LAYER

island = gf.Component()
island << gf.components.rectangle(
    size=(200, 200), centered=True, layer=LAYER.D0_TOP_M1_DRAW
)
```

That rectangle is positive source metal. It does not by itself define a whole
die, ground, clearance or substrate. [Process](../materials-and-technology.md)
explains DRAW, ETCH, masks, nonmetal locators and stack selection. Existing
factories already carry their own layer/annotation choices, so prefer them
when composing a complete source coupon.

## View or export

If a compatible local viewer is available, `assembly.show()` opens the layout.
`assembly.write_gds("assembly.gds")` exports source geometry; use
`with_metadata=False` when a geometry-only external CAD export is wanted.
The [Cells gallery](index.md#components-layout) and
[Test Components Set](test-components.md) provide saved public image previews.

For simulation, choose an existing [version-bound example](../notebooks.qmd).
The consuming design supplies final Nets and problem intent; SCGSim owns
native geometry, meshes, backend preparation and result handling. An image or
GDS export alone does not establish those operations.
