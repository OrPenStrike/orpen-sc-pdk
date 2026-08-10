# Problem Notebooks

The public notebooks show how a reviewer uses the two active capabilities from
[../developing-features](../developing-features.md): SGB geometry semantics and `gsim`
Resolve/Results.

## Current Product Notebooks

| Notebook | What it shows | Capability |
| --- | --- | --- |
| `notebooks/src/SGB_Geometry_Tutorials/` | Four public geometries split into one notebook per Route A/B/C contract. | SGB semantic geometry handoff |
| `notebooks/src/public_electrostatic_workflow.py` | Public electrostatic Palace handoff with generated mesh/config artifacts. | Resolve/Results input package |
| `notebooks/src/public_electrostatic_local_workflow.py` | Same electrostatic fixture with direct local `sim.run_local()` controls. | Resolve/Results local run path |
| `notebooks/src/Native_Masked_Surface_EPR/martinis2022_ribbon_native_mask_hpc_handoff.py` | Electrostatic handoff for Palace forks that emit native `Dielectric.Mask` surface outputs. | C-matrix, domain-E, and surface-Q review |
| `notebooks/src/public_driven_workflow.py` | Public Driven run-folder/report pattern. | Secondary Resolve/Results example |
| `notebooks/src/public_eigenmode_workflow.py` | Public Eigenmode run-folder/report pattern and material provenance. | Secondary Resolve/Results example |

## Boundary

- notebooks own public example composition and parameters;
- SGB owns route/topology/terminal/interface sidecars;
- `gsim` owns mesh/config/run/resolve/report behavior;
- `orpen-sc-pdk` owns public fixtures and rendered documentation;
- public notebooks demonstrate those contracts with publication-safe fixtures.

## Related Pages

- [../features/semantic-geometry-builder](../features/semantic-geometry-builder.qmd)
- [../features/gsim-resolve-results](../features/gsim-resolve-results.qmd)
- [../notebooks](../notebooks.qmd)
