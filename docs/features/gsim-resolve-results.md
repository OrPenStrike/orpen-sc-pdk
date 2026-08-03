# gsim Resolve/Results

**Target:** `gsim`

**Status:** upstream-slice candidate

Resolve/Results exists so notebooks can point at a completed Palace run folder
and display typed results through `gsim` report APIs.

## Need

The public workflow needs a hard boundary between solver execution and result
review:

- run or hand off Palace separately;
- resolve a completed analysis package by path;
- fail loudly when required artifacts are missing;
- load terminal capacitance, domain energy, surface-Q, and convergence data;
- display report-owned tables and plots from typed result objects.

## Native gsim Upstream Baseline

`gsim` upstream/main already provides Palace simulation classes, mesh/config
generation, and basic result helpers such as S-parameter/text loading. It does
not yet provide the full completed-run contract needed here:

- no dedicated Resolve package for run-folder audit;
- no typed electrostatic report assembly for `terminal-C.csv`, `domain-E.csv`,
  and `surface-Q.csv`;
- no notebook-facing `show_all_results()` style report surface for C-matrix,
  domain-E, and surface-Q convergence;
- no sidecar-aware bridge from mesh/config identity into report rows.

## What We Changed

The local `gsim` work adds the missing completed-run layer:

- `resolve` owns path resolution, artifact discovery, and report assembly;
- primitive loaders own Palace CSV/JSON loading;
- derived loaders own material, domain, surface, and loss summary tables;
- `results` owns typed data objects and problem reports;
- notebook code calls the high-level report path instead of assembling report
  state by hand.

This is the part most suitable for upstream review because it improves generic
Palace usability for public and private layout consumers.

## Design

```{mermaid}
flowchart LR
    A["gsim simulation"] --> B["Mesh/config/handoff"]
    B --> C["Palace run folder"]
    C --> D["resolve_palace_result(path, problem_type)"]
    D --> E["Report assembly"]
    E --> F["Typed results"]
    F --> G["Tables and convergence plots"]
```

Expected notebook shape:

```python
resolved = resolve_palace_result(analysis_run_root, problem_type="Electrostatic")
report = resolved.load_report(require_report=True).require_report()
report.show_all_results()
```

## Folder Structure

| Area | Path |
| --- | --- |
| Run-folder resolution | `../GDSFactory_Community_Workbench/gsim/src/gsim/palace/resolve/` |
| Primitive loaders | `../GDSFactory_Community_Workbench/gsim/src/gsim/palace/resolve/loaders/` |
| Derived tables | `../GDSFactory_Community_Workbench/gsim/src/gsim/palace/resolve/derived/` |
| Typed data and reports | `../GDSFactory_Community_Workbench/gsim/src/gsim/palace/results/` |
| Public electrostatic notebooks | `notebooks/src/public_electrostatic_workflow.py`, `notebooks/src/public_electrostatic_local_workflow.py` |
| Masked surface handoff notebook | `notebooks/src/Native_Masked_Surface_EPR/martinis2022_ribbon_native_mask_hpc_handoff.py` |

## Pipeline

1. Build a public geometry through `gsim` or an SGB handoff.
2. Generate mesh/config and, when needed, a Slurm handoff package.
3. Run Palace outside the notebook or point at an existing analysis package.
4. Resolve the run folder through `gsim`.
5. Display C-matrix, domain-E, surface-Q, and convergence views from the typed
   report.

## Notebooks

Use these notebooks to understand the current product:

- {doc}`../notebooks/public_electrostatic_workflow`
- {doc}`../notebooks/public_electrostatic_local_workflow`
- `notebooks/Native_Masked_Surface_EPR/martinis2022_ribbon_native_mask_hpc_handoff.ipynb`
- {doc}`../notebooks/public_driven_workflow`
- {doc}`../notebooks/public_eigenmode_workflow`

Driven and Eigenmode notebooks are secondary examples. The electrostatic and
masked-surface handoff notebooks are the current path for C-matrix, domain-E,
and surface-Q review.
