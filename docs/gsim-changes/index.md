# gsim Changes

These pages are implementation notes under the
[../features/gsim-resolve-results](../features/gsim-resolve-results.qmd) capability. They explain reusable
Palace workflow changes that belong in `gsim`, not in the public PDK.

## Suggested Review Slices

| Order | Slice | Why it comes here |
| --- | --- | --- |
| 1 | API boundary | This decides which modules own new behavior and which imports are public. |
| 2 | Mesh and config provenance | This adds identity artifacts used by config and reports. |
| 3 | Run, resolve, and results | This is the active product surface for completed Palace runs. |
| 4 | Runtime handoff records | This is operational support; it should not change report semantics. |

- [API boundary](api-boundary.md): Palace root API ownership.
- [Mesh and config provenance](mesh-config-provenance.md): reviewable manifests,
  index maps, and material identity.
- [Run, resolve, and results](run-resolve-results.md): typed run reports and
  visualization ownership.
- [Runtime handoff records](runtime-handoff-records.md): local runs, Slurm,
  sweeps, and resource records.
