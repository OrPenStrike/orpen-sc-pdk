# Problem Notebooks

The Surface EPR notebooks demonstrate independent A, B, and C representations
on the public Martinis ribbon capacitor. `gsim` owns the generated interface
groups, supported inset partitioning, logical total aggregation, and Palace
postprocessing; the notebooks select public interface presets through
`sim.set_surface_epr(...)`. Local Route B and Route C activate public
MS/MA/SA postprocessing rows; Route C also validates generated MA/MS/SA child
inset physical groups and keeps `TOTAL` as a postprocessing/report aggregate
only.

The public problem notebooks are examples, not private-run evidence. They show
how a user prepares a public layout, writes a Palace run folder, and loads a
completed run through `gsim` typed reports.

## Fast Conclusions

| Notebook | What it shows | Why it matters |
| --- | --- | --- |
| `notebooks/src/public_surface_epr_ribbon_capacitor_representation_a_workflow.py` | Handoff workflow for Martinis 2022 ribbon capacitor representation A Surface EPR, MS-only. | Lets a reviewer inspect the representation A public notebook path without publishing private geometry. |
| `notebooks/src/public_surface_epr_ribbon_capacitor_workflow.py` | Handoff workflow for Martinis 2022 ribbon capacitor Route B Surface EPR, MS-only. | Lets a reviewer inspect generated finite-shell interface groups and public MS-bottom postprocessing config without publishing private geometry. |
| `notebooks/src/public_surface_epr_ribbon_capacitor_representation_c_workflow.py` | Handoff workflow for Martinis 2022 ribbon capacitor representation C Surface EPR, with public MS/MA/SA postprocessing rows and child inset mesh groups. | Lets a reviewer inspect retained-volume physical groups, logical total rows, BBox checks, and Palace handoff readiness without publishing private geometry. |
| `notebooks/src/public_surface_epr_ribbon_capacitor_representation_b_local_workflow.py` | Local `sim.run_local()` Route B finite-metal shell Surface EPR test, with public MS/MA/SA postprocessing rows. | Uses the same generated interface catalog while exposing direct local execution controls. |
| `notebooks/src/Inset_Surface_EPR_Demo/` | Six Martinis 2022 ribbon Surface EPR demo notebooks: A/B/C local runs and A/B/C F1 handoff packages. | Keeps material parameters, inset margins, solver order, and refinement controls aligned while comparing Route A, B, and C behavior. |
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
| Surface EPR notebooks | `notebooks/src/public_surface_epr_ribbon_capacitor_representation_a_workflow.py`, `notebooks/src/public_surface_epr_ribbon_capacitor_workflow.py`, `notebooks/src/public_surface_epr_ribbon_capacitor_representation_c_workflow.py`, `notebooks/src/public_surface_epr_ribbon_capacitor_representation_b_local_workflow.py`, `notebooks/src/Inset_Surface_EPR_Demo/` |
| Rendered notebook index | {doc}`../notebooks` |

Boundary change:

- notebooks own example composition and public parameters;
- `gsim` owns mesh, config, run, resolve, and report behavior;
- the current Surface EPR examples own only public representation/profile
  selection, public interface-preset selection, and test-mode choices; `gsim`
  owns interface discovery, supported inset mechanics, manifest roles,
  postprocessing rows, and reports;
- calibrated MA/SA process-default policy and true metal-volume loss remain
  later public material/solver workflow slices; Route C child inset
  mesh-interface validation is public notebook evidence;
- docs convert and render the notebooks but do not execute result cells by
  default, because tracked public docs do not include Palace result CSVs.

Related pages:

- {doc}`../gsim-changes/run-resolve-results`
- {doc}`../features/problem-type-notebook-suite`
