# Developing Features

This page is a public feature board for capability that this project needs from
the GDSFactory ecosystem. Each item should stay reviewable without private
layout/IP.

Feature status labels:

- `candidate`: useful direction, not yet prototyped.
- `prototype`: being explored on a personal branch.
- `integration`: mature enough to slice into an upstream-review branch.
- `accepted`: merged or otherwise adopted by the target public repo.

::::{grid} 1 1 2 3
:gutter: 3

:::{grid-item-card} FEAT-001 Palace analysis/reporting contract
:link: features/palace-reporting
:link-type: doc

**Target:** `gsim`

**Status:** candidate

Define reusable electrostatic and EPR report surfaces that can consume public
PDK layer/material metadata without depending on private layout repos.
:::

:::{grid-item-card} FEAT-002 Surface-Q index mapping
:link: features/surface-q-index-mapping
:link-type: doc

**Target:** `gsim` with `orpen-sc-pdk` metadata

**Status:** candidate

Map simulation surfaces back to PDK layer semantics so reports can identify
participation, loss, and surface-Q contributors in a publication-safe way.
:::

:::{grid-item-card} FEAT-003 Material database overlay
:link: features/material-db-overlay
:link-type: doc

**Target:** `orpen-sc-pdk` and `gsim`

**Status:** candidate

Keep SCQ material records in the PDK while adapting them into `gsim` material
resolver overlays for Palace and other solver workflows.
:::

:::{grid-item-card} FEAT-004 Benchmark and cost analysis
:link: features/benchmark-cost-analysis
:link-type: doc

**Target:** `gsim`

**Status:** candidate

Provide solver performance records that help estimate runtime, memory, mesh
cost, and cloud/HPC spend without exposing private geometry or private runs.
:::

:::{grid-item-card} FEAT-005 GDSFactory+ PDK discovery
:link: features/gdsfactoryplus-discovery
:link-type: doc

**Target:** `orpen-sc-pdk`

**Status:** prototype

Keep the PDK in a flat package layout with public `cells/`, `samples/`,
reserved `models/`, and GDSFactory+ metadata so VSCode preview works on the
active repo.
:::

:::{grid-item-card} FEAT-006 Static private layout mount
:link: features/private-static-mount
:link-type: doc

**Target:** `orpen-sc-pdk`

**Status:** prototype

Expose ignored repo-local private layout packages to GF+ static discovery
without tracking private source in the public PDK.
:::

::::

```{toctree}
:hidden:

features/palace-reporting
features/surface-q-index-mapping
features/material-db-overlay
features/benchmark-cost-analysis
features/gdsfactoryplus-discovery
features/private-static-mount
```
