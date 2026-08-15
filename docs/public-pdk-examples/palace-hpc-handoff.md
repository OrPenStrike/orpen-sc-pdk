# Palace HPC Handoff

OrPen owns the public run-profile catalog used by its notebooks. `gsim` owns
Palace configuration, scheduler-script rendering, handoff archives, run
resolution, and reports. This page is a public handoff guide, not an operations
runbook.

## Choose a public profile

The public catalog exposes F1 CPU and Nano4 GPU profiles through
`list_public_palace_run_profiles()` and resolves one through
`resolve_public_palace_run_profile()`. Select a catalog profile in the
notebook, provide an organization-approved allocation at run time, and pass the
resolved profile to the configured `gsim` simulation object.

```python
from orpen_sc_pdk.simulation import resolve_public_palace_run_profile

profile = resolve_public_palace_run_profile(
    "f1:ct112",
    resource_overrides={"account": "<allocation>"},
)
sim.write_config(hints=profile.to_palace_config_hints())
sbatch_handoff = sim.write_slurm_sbatch_handoff(profile, job_name="public-example")
sim.generate_handoff_package(
    write_config=False,
    profile=profile,
    script_path=sbatch_handoff.script_path,
)
```

| Surface | Public responsibility |
| --- | --- |
| F1 profiles | CPU-oriented public scheduler shapes |
| Nano4 profiles | GPU-oriented public scheduler shapes |
| Generic single-node Ubuntu/Slurm | Use the same handoff sequence with an organization-owned scheduler profile |
| `gsim` | Config, scheduler script, archive, run resolution, and report behavior |

The catalog intentionally does not make access decisions or publish connection
details. Provide any allocation, credential, connection endpoint, local path,
or executable configuration only in the deployment environment that owns it.

## Return solver results without unnecessary bulk

An outbound Palace handoff package carries inputs to the execution machine. An
inbound result-return archive carries selected outputs back beside the
originating run. They are different artifacts with different manifests; never
use one as evidence for the other.

::: {.callout-warning title="CONVERGING runtime contract"}
The shared Runtime producer for these archives is still being implemented. The
profile names and behavior below record the public candidate contract, not an
available API or generated script. Until the producer publishes an exact
identity, there is no canonical public packaging command.
:::

| Profile | Returned content | Deliberate omissions | Intended use and transfer cost |
| --- | --- | --- | --- |
| `light` | Numerical tables and reports, solver logs, executed config and script, metadata, provenance, receipts, and manifests | Standalone meshes and field snapshots | Routine analysis and audit; smallest transfer |
| `with-mesh` | Everything in `light`, plus input and adaptive or refined mesh artifacts | Field snapshots | Mesh inspection or local remapping; larger than `light` |
| `with-field` | Everything in `light`, plus field and visualization artifacts | Standalone meshes, except mesh bytes intrinsic to a field format | Field inspection without a separate mesh payload; potentially large |
| `full` | Everything in `light`, plus mesh and field artifacts | None of the profile-selectable mesh or field classes | Complete return for deep investigation; largest transfer |

The candidate archive name is
`<run-id>-palace-results-<profile>.tar.gz`. A generated pure-shell packager is
required so a manual local or Slurm/HPC execution machine does not need Python
or `gsim` merely to package completed or partial results. Cloud execution is
outside this workflow.

Each archive receipt must bind the selected profile; included and excluded
artifact classes; file sizes and hashes; run, executed-config, mesh, handoff,
and solver identities; and whether the return is partial or completed. A
profile-authorized omission of mesh or field data is expected, not an error.
Missing numerical, log, or provenance artifacts required by the selected
profile must remain visibly missing; neither packaging nor resolution may
invent them or silently upgrade a partial return to completed.

The generic return sequence is:

1. At `<remote-run-root>`, select `<profile>` and use the generated shell
   packager to produce the archive and receipt for `<run-id>`.
2. Transfer both files from `<remote-host>` to `<local-run-root>`.
3. Verify the receipt and archive hash before extraction.
4. Extract the archive beside the originating local run identified by the same
   `<run-id>`.
5. Resolve and analyze the returned run. The resolver must honor the receipt's
   profile and partial/completed state when deciding whether absent mesh or
   field artifacts are expected.

Concrete host commands, accounts, scheduler allocations, executable paths, and
run-specific values belong to the owning execution environment, not this public
guide.

## Continue with the existing public workflow

Use [Problem notebooks](problem-notebooks.md) for public Driven, Eigenmode, and
Electrostatic examples. [Palace configuration](../features/palace-config-generation.md)
and [Palace reporting](../features/palace-reporting.md) explain the reusable
`gsim` ownership boundary. The generated handoff is an input package, not solver
evidence or a claim that a remote job completed.
