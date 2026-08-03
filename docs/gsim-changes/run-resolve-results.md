# Run, Resolve, and Results

The Palace workflow now has three separate jobs: run the solver, resolve a run
folder, and present typed results. Keeping those jobs separate is what lets
public notebooks show real report usage without becoming debug scripts.

## Why This Was Needed

The old notebook style mixed artifact checks, report loading, missing-file
summaries, and visualization in one place. That made the notebooks useful for
debugging but unclear as public examples.

The public PDK needs this path instead:

```python
resolved_result = resolve_palace_result(analysis_run_root, problem_type="Driven")
driven_report = resolved_result.load_report(require_report=True).require_report()

driven_report.show_all_results()
```

## What gsim Already Had

`gsim` upstream/main already had Palace simulation classes, mesh/config
generation, and basic S-parameter/text result helpers. It did not have a
dedicated completed-run Resolve package or typed electrostatic report assembly
for terminal-C, domain-E, and surface-Q convergence.

The public PDK needs a clearer completed-run contract. A user should point at a
run folder, state the problem type, and receive a typed report or a hard
failure. That is why run-folder resolution and report assembly were split from
raw solver execution.

## What Changed

Code pointers:

| Area | Path |
| --- | --- |
| Run-folder resolution | `../GDSFactory_Community_Workbench/gsim/src/gsim/palace/resolve/` |
| Report assembly | `../GDSFactory_Community_Workbench/gsim/src/gsim/palace/resolve/assembly/` |
| Primitive loaders | `../GDSFactory_Community_Workbench/gsim/src/gsim/palace/resolve/loaders/` |
| Derived loss/material tables | `../GDSFactory_Community_Workbench/gsim/src/gsim/palace/resolve/derived/` |
| Typed result data and reports | `../GDSFactory_Community_Workbench/gsim/src/gsim/palace/results/` |

Boundary change:

- `gsim.palace.run` owns solver execution and raw artifact production.
- `gsim.palace.resolve` owns run-folder audit and report assembly.
- `gsim.palace.results` owns typed data and report visualization semantics.
- Public PDK notebooks call the high-level path and do not manually assemble
  `missing_artifacts`, `config_path`, or `mesh_path` as their main output.

Related detailed ledger: {doc}`../issues/palace-report-ownership`.
