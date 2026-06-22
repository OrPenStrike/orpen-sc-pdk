# Problem Notebooks

The Surface EPR notebooks demonstrate Route B finite-metal shell Surface EPR on
the public Martinis ribbon capacitor. `gsim` discovers the generated interface
groups; the notebooks select the MS bottom total/band/core entries for the
public Martinis preset. MA/SA reporting, non-planar geodesic inset bands, and
true metal-volume loss remain deferred instead of silently becoming public
defaults.

The public problem notebooks are examples, not private-run evidence. They show
how a user prepares a public layout, writes a Palace run folder, and loads a
completed run through `gsim` typed reports.

## Fast Conclusions

| Notebook | What it shows | Why it matters |
| --- | --- | --- |
| `notebooks/src/public_surface_epr_ribbon_capacitor_workflow.py` | Handoff workflow for Martinis 2022 ribbon capacitor Route B Surface EPR, MS-only. | Lets a reviewer inspect generated finite-shell interface groups and public MS-bottom postprocessing config without publishing private geometry. |
| `notebooks/src/public_surface_epr_ribbon_capacitor_local_workflow.py` | Local `sim.run_local()` Route B finite-metal shell Surface EPR test, MS-only. | Uses the same generated interface catalog while exposing direct local execution controls. |
| `notebooks/src/public_eigenmode_workflow.py` | PDK material overlay reaching `gsim` Palace config/report provenance. | Shows PDK-owned material records flowing into solver-owned material resolution. |
| Driven, Eigenmode, and Electrostatic notebooks | Public Geometry -> LayerStack -> Mesh -> Config -> Run -> Resolve -> Visualize chains. | Keeps reusable workflow examples public while private lab notebooks stay private. |

## Why This Was Needed

Private NCUAS notebooks cannot be published because they include private
geometry, private run folders, and lab-specific assumptions. The public PDK
still needs examples that explain the workflow shape.

The public notebooks provide that shape with public fixtures:

- Driven CPW;
- Eigenmode resonator;
- Electrostatic same-layer capacitor;
- Surface EPR Martinis 2022 ribbon capacitor.

## What gsim Already Had

`gsim` already had simulation classes and report loaders. It did not provide
OrPen-specific public layouts or publication-safe notebooks. That is the PDK's
job.

The PDK examples use `gsim`; they do not parse Palace output or build runtime
packages themselves.

Official upstream `gsim` remains the baseline for generic Palace simulation
classes. The Route B finite-metal Surface EPR interface-catalog helpers are
consumed from the local Palace branch documented in
{doc}`../features/gsim-palace-branch-comparison`; do not present them as
accepted upstream `gsim` behavior until that branch is reviewed and merged.

## What Changed

Code pointers:

| Area | Path |
| --- | --- |
| Driven notebooks | `notebooks/src/public_driven_workflow.py`, `notebooks/src/public_driven_local_workflow.py` |
| Eigenmode notebooks | `notebooks/src/public_eigenmode_workflow.py`, `notebooks/src/public_eigenmode_local_workflow.py` |
| Electrostatic notebooks | `notebooks/src/public_electrostatic_workflow.py`, `notebooks/src/public_electrostatic_local_workflow.py` |
| Surface EPR notebooks | `notebooks/src/public_surface_epr_ribbon_capacitor_workflow.py`, `notebooks/src/public_surface_epr_ribbon_capacitor_local_workflow.py` |
| Rendered notebook index | {doc}`../notebooks` |

Boundary change:

- notebooks own example composition and public parameters;
- `gsim` owns mesh, config, run, resolve, and report behavior;
- the current Surface EPR examples own only public MS channel selection and
  test-mode choices; `gsim` owns finite-shell interface discovery, inset
  mechanics, manifest roles, postprocessing rows, and reports;
- MA/SA reporting, non-planar geodesic inset bands, and true metal-volume loss
  remain later `gsim`/mesh workflow slices;
- docs convert and render the notebooks but do not execute result cells by
  default, because tracked public docs do not include Palace result CSVs.

Related pages:

- {doc}`../gsim-changes/run-resolve-results`
- {doc}`../features/problem-type-notebook-suite`
