# Issues

This page tracks the current public follow-up issues for the
`orpen-sc-pdk` workflow. It intentionally mirrors {doc}`developing-features`:
there are two active development capabilities, not a long independent roadmap.

## Active Issue Clusters

| Cluster | Owner | Done when |
| --- | --- | --- |
| SGB semantic handoff | `semantic_geometry_builder`, consumed by `gsim` | Route A/B/C notebooks preserve terminal, interface, and physical-group identity. |
| Resolve/Results | `gsim` | Public electrostatic notebooks can resolve completed Palace run folders and show C-matrix, domain-E, and surface-Q convergence through typed reports. |

## Boundary Issues

::::{grid} 1 1 2 2
:gutter: 3

:::{grid-item-card} CAD/mesh identity provenance
:link: issues/cad-mesh-identity-provenance
:link-type: doc

Use this ledger only for historical identity-provenance context. Current SGB
work owns the semantic handoff scope.
:::

:::{grid-item-card} Palace report ownership
:link: issues/palace-report-ownership
:link-type: doc

Use this ledger for Resolve/Results ownership details. `gsim` owns report
loading and display semantics.
:::

:::{grid-item-card} Palace config ownership
:link: issues/palace-config-ownership
:link-type: doc

Use this ledger when config-generation identity affects Resolve/Results or SGB
handoff.
:::

:::{grid-item-card} Public problem-type notebook coverage
:link: issues/public-problem-type-notebook-coverage
:link-type: doc

Use this ledger as historical notebook coverage context. Public notebooks are
now consumer examples for the two active capabilities.
:::

::::

```{toctree}
:hidden:

issues/cad-mesh-identity-provenance
issues/palace-report-ownership
issues/palace-config-ownership
issues/public-problem-type-notebook-coverage
issues/gplugins-boundary
issues/integration-branch-hygiene
issues/material-schema-boundary
issues/palace-api-responsibility-boundary
issues/palace-hpc-handoff-records
issues/gsim-palace-branch-integration
issues/source-backed-interface-presets
```
