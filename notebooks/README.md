# Notebooks

This folder contains public Jupyter notebooks for `orpen-sc-pdk`.

## Contributors

The source for notebooks is the `src/` folder, which contains Jupytext
`py:percent` files. Keep notebook scripts out of the import scope of the Python
package.

Convert one source file with:

```bash
uvx jupytext --to ipynb notebooks/src/public_driven_workflow.py
```

Build the documentation notebook pages and PDF docs with:

```bash
just docs
just docs-latex
just docs-pdf
```

Notebook examples in this public repo must not include private layout/IP, GDS
inputs, private run folders, or private benchmark numbers.

Public Palace HPC profile controls belong in the handoff cell. Use
`orpen_sc_pdk.simulation` for public F1/Nano4 run-profile values, then compose
the explicit `gsim` Run Stage in the notebook with `sim.write_config()`,
`sim.write_slurm_sbatch_handoff()`, and `sim.generate_handoff_package()`.

Local Palace notebooks use the same public fixtures and Resolve/Report cells,
but their Run Stage calls `sim.run_local()`. They default to
`PALACE_RUN_LOCAL = False` so docs builds and fresh checkouts do not require a
local Palace installation. Set `PALACE_RUN_LOCAL = True` after configuring the
local runtime controls such as `PALACE_EXECUTABLE`, `PALACE_EXECUTABLE_MODE`,
and `PALACE_SETUP_COMMANDS`.
