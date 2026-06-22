# gsim Changes

These pages explain the reusable Palace workflow changes that belong in
`gsim`, not in the public PDK. Read them in order: the first page sets the API
boundary, and later pages only mention that boundary when they add a new
responsibility.

## Suggested Review Slices

| Order | Slice | Why it comes here |
| --- | --- | --- |
| 1 | API boundary | This decides which modules own new behavior and which imports are public. |
| 2 | Mesh and config provenance | This adds the identity artifacts used by config and reports. |
| 3 | Run, resolve, and results | This depends on run folders and generated artifacts being identifiable. |
| 4 | Runtime handoff records | This is largest operationally, but it should not change report semantics. |

::::{grid} 1 1 2 2
:gutter: 3

:::{grid-item-card} API boundary
:link: api-boundary
:link-type: doc

Why the Palace root API was narrowed before adding more helpers.
:::

:::{grid-item-card} Mesh and config provenance
:link: mesh-config-provenance
:link-type: doc

How mesh manifests, index maps, and material provenance make solver artifacts
reviewable.
:::

:::{grid-item-card} Run, resolve, and results
:link: run-resolve-results
:link-type: doc

How run folders become typed reports and where visualization belongs.
:::

:::{grid-item-card} Runtime handoff records
:link: runtime-handoff-records
:link-type: doc

How local runs, Slurm handoff, sweeps, and resource records stay in `gsim`.
:::

::::

```{toctree}
:hidden:

api-boundary
mesh-config-provenance
run-resolve-results
runtime-handoff-records
```
