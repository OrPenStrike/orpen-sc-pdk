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
only reusable plugin integration into `gplugins`; Palace compatibility wrappers
should delegate to `gsim` instead of growing a second solver runtime.
:::

:::{grid-item-card} ISSUE-004 Integration branch hygiene
:link: issues/integration-branch-hygiene
:link-type: doc

**Repo:** `gsim`, `gplugins`

**Related features:** all upstream-facing features

Prototype branches may move quickly. Upstream PR branches should be rebuilt
from upstream `main` and contain only one human-reviewable feature slice.
:::

:::{grid-item-card} ISSUE-005 Palace config ownership
:link: issues/palace-config-ownership
:link-type: doc

**Repo:** `gsim`

**Related features:** FEAT-001, FEAT-003, FEAT-006, FEAT-008

Reusable Palace config generation should extend `gsim` and consume PDK metadata
instead of creating a solver runtime inside `orpen-sc-pdk`.
:::

:::{grid-item-card} ISSUE-006 CAD/mesh identity provenance
:link: issues/cad-mesh-identity-provenance
:link-type: doc

**Repo:** `meshwell`, `gsim`

**Related features:** FEAT-002, FEAT-006, FEAT-007

Physical names, interface identities, mesh roles, and Palace indices need one
public handoff contract across CAD, mesh, config, and reports.
:::

:::{grid-item-card} ISSUE-007 Public problem-type notebook coverage
:link: issues/public-problem-type-notebook-coverage
:link-type: doc

**Repo:** `orpen-sc-pdk`, `gsim`

**Related features:** FEAT-001, FEAT-006, FEAT-008

Public notebooks should validate driven, eigenmode, and electrostatic workflows
with public fixtures and coarse local Palace smoke tests.
:::

:::{grid-item-card} ISSUE-008 Source-backed interface presets
:link: issues/source-backed-interface-presets
:link-type: doc

**Repo:** `orpen-sc-pdk`, `gsim`

Public MA/MS/SA dielectric-interface presets need source-selection and
default-selection gates before becoming PDK data.
:::

::::

```{toctree}
:hidden:

issues/palace-report-ownership
issues/material-schema-boundary
issues/gplugins-boundary
issues/integration-branch-hygiene
issues/palace-config-ownership
issues/cad-mesh-identity-provenance
issues/public-problem-type-notebook-coverage
issues/source-backed-interface-presets
```
