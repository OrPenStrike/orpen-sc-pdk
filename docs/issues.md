# Issues

This page tracks ecosystem issues that matter to the `orpen-sc-pdk` workflow.
Items may later become upstream GitHub issues or PRs. Do not add private layout
details, benchmark values from private layouts, or private run directories here.

::::{grid} 1 1 2 3
:gutter: 3

:::{grid-item-card} ISSUE-001 Palace report ownership
:link: issues/palace-report-ownership
:link-type: doc

**Repo:** `gsim`

**Related features:** FEAT-001, FEAT-004

Reusable Palace report generation should live upstream instead of in a private
layout repo or inside the PDK core.
:::

:::{grid-item-card} ISSUE-002 Material schema boundary
:link: issues/material-schema-boundary
:link-type: doc

**Repo:** `gsim`, `orpen-sc-pdk`

**Related features:** FEAT-003

The PDK should own SCQ material records and aliases. `gsim` should own reusable
material resolution and Palace-specific evaluation.
:::

:::{grid-item-card} ISSUE-003 GDSFactory plugin boundary
:link: issues/gplugins-boundary
:link-type: doc

**Repo:** `gplugins`

**Related features:** FEAT-001, FEAT-004

Generic GDSFactory plugin helpers should not be duplicated in the PDK. Move
only reusable plugin integration into `gplugins`.
:::

:::{grid-item-card} ISSUE-004 Integration branch hygiene
:link: issues/integration-branch-hygiene
:link-type: doc

**Repo:** `gsim`, `gplugins`

**Related features:** all upstream-facing features

Prototype branches may move quickly. Upstream PR branches should be rebuilt
from upstream `main` and contain only one human-reviewable feature slice.
:::

::::

```{toctree}
:hidden:

issues/palace-report-ownership
issues/material-schema-boundary
issues/gplugins-boundary
issues/integration-branch-hygiene
```
