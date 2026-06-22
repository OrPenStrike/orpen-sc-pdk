# Public PDK Examples

These pages explain what the public PDK demonstrates. The examples should show
how a public consumer uses `gsim`; they should not move solver ownership into
`orpen-sc-pdk`.

## Suggested Review Slices

| Order | Slice | Why it comes here |
| --- | --- | --- |
| 1 | Problem notebooks | This is the user-facing workflow and reveals the API the PDK consumes. |
| 2 | Simulation layer catalog | This supports the Purcell notebooks without changing `gsim` ownership. |
| 3 | Evidence fixtures | This proves the examples stay public-safe and can trail the main docs. |

::::{grid} 1 1 2 2
:gutter: 3

:::{grid-item-card} Problem notebooks
:link: problem-notebooks
:link-type: doc

Driven, Eigenmode, Electrostatic, and Purcell workflows with public geometry.
:::

:::{grid-item-card} Simulation layer catalog
:link: simulation-layer-catalog
:link-type: doc

Public layer names and layout-authored solver sheets for examples.
:::

:::{grid-item-card} Evidence fixtures
:link: evidence-fixtures
:link-type: doc

Tests and evidence that prove the public examples stay publication-safe.
:::

::::

```{toctree}
:hidden:

problem-notebooks
simulation-layer-catalog
evidence-fixtures
```
