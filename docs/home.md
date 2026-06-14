# Home

`orpen-sc-pdk` is the public superconducting quantum/RF PDK for contributors who
need to keep a Primary Layout in a private repository while still improving
shared GDSFactory ecosystem infrastructure.

The public PDK does not migrate private layout/IP into a public repo. It owns
the public process contract: layer names, layer views, the layer stack, material
semantics, public CPW cross-sections, reusable layout helpers, public cells,
static GF+ import mechanics, and
publication-safe documentation. Private layout repositories keep real chip geometry, private
parameters, private notebooks, GDS inputs from private designs, and private
run evidence.

The intended workflow is local and reviewable: open the private layout repo as
the GF+ project, install `orpen-sc-pdk` as its base PDK, use private layouts to
validate public infrastructure, then slice accepted public work into clean
upstream PR branches.

Palace source development is a separate solver-source lane. Most reusable
Palace workflow work should go through `gsim`; direct Palace fork work is for
solver-side outputs, postprocessing internals, or behavior that cannot be
implemented reliably from the Python workflow layer.

## Start By Task

::::{grid} 1 1 2 3
:gutter: 3

:::{grid-item-card} Use The Public PDK
:link: home/pdk-responsibilities
:link-type: doc

Understand what `orpen-sc-pdk` owns: public process semantics, public cells,
materials direction, static GF+ import mechanics, and docs.
:::

:::{grid-item-card} Connect A Private Layout Repo
:link: home/ecosystem-workspace
:link-type: doc

Set up the private GF+ project without publishing private layout/IP.
:::

:::{grid-item-card} Develop Ecosystem Features
:link: developing-features
:link-type: doc

Track reusable capability that may belong in `gsim`, `gplugins`, or this PDK.
Use a Palace fork only when a feature must change solver-side behavior.
:::

:::{grid-item-card} Prepare Upstream PRs
:link: home/ecosystem-workspace
:link-type: doc

Use personal prototype work as a source for focused `features/<topic>` and
`integration/<topic>` branches.
:::

:::{grid-item-card} Review Public/Private Boundaries
:link: home/ecosystem-workspace
:link-type: doc

Check which data may be documented publicly and which data must remain in the
private layout repository.
:::

::::

```{toctree}
:hidden:

home/ecosystem-workspace
home/pdk-responsibilities
```
