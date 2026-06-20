# Issues

This page tracks ecosystem issues that matter to the `orpen-sc-pdk` workflow.
Items may later become upstream GitHub issues or PRs. Do not add private layout
details, benchmark values from private layouts, or private run directories here.

## Priority Queue

Conclusion: high-priority issues are the breakpoints. They create the base that
later notebook and PDK PRs consume. Lower priority means "do after the owner
contract lands", not "unimportant".

| Priority | Issue | Owner repo | Breakpoint | First useful PR | Done when |
|---|---|---|---|---|---|
| P0 | Palace API responsibility boundary | `gsim` | Yes | shrink root/package exports and keep owner-module imports | public callers have one clear import path per responsibility |
| P1 | CAD/mesh identity provenance | `meshwell`, `gsim` | Yes | physical-name contract plus manifest/index-map consumer | mesh physical groups can be inspected from config/report paths |
| P2 | Material schema boundary | `gsim`, `orpen-sc-pdk` | Yes | material overlay/provenance in `gsim`, then PDK JSON demo | generated Palace material rows point back to PDK material records |
| P3 | Palace report ownership | `gsim` | Yes | typed Driven/Eigenmode/Electrostatic report loaders and displays | public notebooks can call `resolve_palace_result(...).load_report()` and render reports |
| P4 | Palace config ownership | `gsim` | Yes | mesh/config/postprocessing handoff objects, including ThinMetal MS Surface EPR | generated configs expose source/surface identities without PDK solver code |
| P5 | Source-backed interface presets | `orpen-sc-pdk`, `gsim` | No | keep MS notebook-local or explicit; defer MA/SA defaults | no automatic MA/SA policy exists before public process scope is accepted |
| P6 | Public problem-type notebook coverage | `orpen-sc-pdk` | No | basic public notebooks after `gsim` report/config contracts land | notebooks demonstrate public outcomes, not private workflow copies |
| P7 | Palace HPC handoff and resource records | `gsim` | No | Slurm/resource/benchmark records after report/run contracts | benchmark tables are reproducible from public fixtures |
| P8 | GDSFactory plugin boundary | `gplugins`, `gsim` | No | only if wrapper duplication remains after `gsim` owner APIs land | no second Palace runtime grows in `orpen-sc-pdk` |
| P9 | gsim Palace branch integration | `gsim` | No | tracking issue only; split into P0-P7 PRs | personal branch stops being the review unit |

Known incomplete area:

| Area | Current state | Next meaningful issue/PR |
|---|---|---|
| Surface EPR results | MS geometry/config is usable; final report presentation is not complete. | Add report tables/plots after P3/P4, not inside the geometry helper PR. |
| MA/SA and 3D interfaces | Deferred by design. | Start after the MS ThinMetal path is accepted and mesh-level interface banding is designed. |
| Purcell examples | Important, but consumer-level. | Add after P1/P3 so layout-authored sheets consume accepted contracts. |

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

:::{grid-item-card} ISSUE-009 Palace HPC handoff and resource records
:link: issues/palace-hpc-handoff-records
:link-type: doc

**Repo:** `gsim`

NCUAS-style runtime staging, Slurm/Sbatch handoff, archives, and resource
records should extend `gsim` run summaries instead of becoming PDK or
`gplugins` runtime code.
:::

:::{grid-item-card} ISSUE-010 Palace API responsibility boundary
:link: issues/palace-api-responsibility-boundary
:link-type: doc

**Repo:** `gsim`, `gplugins`, `orpen-sc-pdk`

Simulation features should be placed by problem/config/result responsibility
and exposed publicly only when notebooks or downstream packages should call the
symbol directly.
:::

:::{grid-item-card} ISSUE-011 gsim Palace branch integration
:link: issues/gsim-palace-branch-integration
:link-type: doc

**Repo:** `gsim`

**Related features:** FEAT-006, FEAT-009

The local Palace personal branch is far ahead of upstream `gsim`. Its reusable
solver capabilities need to be split into upstream-reviewable slices before
the public PDK treats them as accepted contracts.
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
issues/palace-hpc-handoff-records
issues/palace-api-responsibility-boundary
issues/gsim-palace-branch-integration
```
