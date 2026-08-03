# Developing Features

This page groups the current reusable GDSFactory/`gsim` development scope into
two capabilities: SGB for geometry semantics and Resolve/Results for
completed-run reporting.

## Active Capability Pages

::::{grid} 1 1 2 2
:gutter: 3

:::{grid-item-card} Semantic Geometry Builder
:link: features/semantic-geometry-builder
:link-type: doc

Preserve route, terminal, interface, and physical-group identity before `gsim`
generates Palace mesh/config artifacts.
:::

:::{grid-item-card} gsim Resolve/Results
:link: features/gsim-resolve-results
:link-type: doc

Turn completed Palace run folders into typed reports for capacitance, domain
energy, surface-Q, and convergence review.
:::

::::

## Scope Boundary

| Area | Current decision |
| --- | --- |
| SGB Package | Keep it as a semantic handoff package. It owns Route A/B/C intent, terminal plans, interface ownership, and sidecar ledgers. |
| Resolve/Results | Keep it as the main `gsim` upstream candidate. It owns run-folder resolution, artifact loading, typed report data, and notebook display surfaces. |
| `orpen-sc-pdk` | Keep it as public docs, public fixtures, and notebooks that consume SGB and `gsim`. |
| Private layout repos | Use them as validation consumers for the same public contracts. |

## Review Order

| Order | Work | Done when |
| --- | --- | --- |
| 1 | Harden Resolve/Results | A public electrostatic notebook can point at a completed run folder and show C-matrix, domain-E, and surface-Q convergence through `gsim` report APIs. |
| 2 | Minimize SGB | SGB emits only the semantic route/topology/terminal/interface sidecar needed by downstream mesh/config/report consumers. |
| 3 | Update public notebooks | OrPen notebooks demonstrate the two capabilities through public fixtures and completed-run report paths. |

```{toctree}
:hidden:

features/semantic-geometry-builder
features/gsim-resolve-results
gsim-changes/index
notebooks
```
