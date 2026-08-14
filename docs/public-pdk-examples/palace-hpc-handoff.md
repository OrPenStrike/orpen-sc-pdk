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

## Continue with the existing public workflow

Use [Problem notebooks](problem-notebooks.md) for public Driven, Eigenmode, and
Electrostatic examples. [Palace configuration](../features/palace-config-generation.md)
and [Palace reporting](../features/palace-reporting.md) explain the reusable
`gsim` ownership boundary. The generated handoff is an input package, not solver
evidence or a claim that a remote job completed.
