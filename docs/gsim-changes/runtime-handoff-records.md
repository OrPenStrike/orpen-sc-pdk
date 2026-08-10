# Runtime Handoff Records

Solver execution is not a PDK feature. Local runs, Slurm handoff packages,
sweeps, and resource records belong in `gsim` so every consumer can use the
same runtime evidence.

## Why This Was Needed

The public PDK needs examples that can prepare runs for local or HPC use, but
it should not grow a second Palace runtime. It also should not publish private
HPC account names, node names, private run folders, or lab-specific scripts.

The reusable requirement is smaller:

- write a run folder;
- optionally run Palace locally;
- package a Slurm handoff;
- record sanitized runtime and resource metadata;
- summarize sweeps from explicit point metadata.

## What gsim Already Had

`gsim` already had a public cloud-oriented execution path. The likely
maintainer intent was to keep notebooks simple by sending jobs through the
existing reusable execution surface.

The public PDK needs local and HPC handoff review without publishing private
site details. The change keeps execution orchestration in `gsim`, while OrPen
only selects public profiles and shows publication-safe examples.

## What Changed

Code pointers:

| Area | Path |
| --- | --- |
| Local execution | `../GDSFactory_Community_Workbench/gsim/src/gsim/palace/run/local.py` |
| Slurm handoff | `../GDSFactory_Community_Workbench/gsim/src/gsim/palace/handoff.py` |
| Run stage models | `../GDSFactory_Community_Workbench/gsim/src/gsim/palace/run_stage.py` |
| Run-folder helpers | `../GDSFactory_Community_Workbench/gsim/src/gsim/palace/run_folder.py` |
| Run summaries and sidecars | `../GDSFactory_Community_Workbench/gsim/src/gsim/palace/resolve/sources/` |
| Sweep records | `../GDSFactory_Community_Workbench/gsim/src/gsim/palace/resolve/sweeps.py` |

Boundary change:

- `gsim` owns local execution, handoff packaging, sweeps, and resource records.
- `orpen-sc-pdk` owns only public profile selection and notebook examples.
- Private lab/HPC catalogs remain outside the public PDK.

Related detailed ledgers:

- [../issues/palace-hpc-handoff-records](../issues/palace-hpc-handoff-records.md)
- [../features/benchmark-cost-analysis](../features/benchmark-cost-analysis.md)
