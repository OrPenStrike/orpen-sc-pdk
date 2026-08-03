# Native Masked Surface EPR Handoff

This page owns the public OrPen handoff recipe for the Martinis 2022 ribbon
capacitor when the solver is a Palace fork that supports
`Boundaries.Postprocessing.Dielectric[].Mask`.

It does not promote `Mask` to the upstream `gsim` config model, and it does not
publish private NCUAS run folders or absolute local Palace paths. The notebook
keeps the public OrPen geometry and `gsim` mesh/config pipeline, then applies a
small run-local config patch before packaging the Slurm handoff.

## Contract

- Geometry: `orpen_sc_pdk.cells.martinis2022_differential_ribbon_capacitor`
  with `a_um=50`, `b_um=100`, and `ell_r_um=1391`.
- Solver: Electrostatic Palace, order 2, 20 AMR iterations, `UpdateFraction`
  0.15, and saved adaptive iterations.
- Native Mask rows: `SA`, `MS`, and `MA` interfaces across mask margins
  `0`, `10`, `50`, `100`, `200`, `500`, and `1000` nm.
- Reproduction mode: legacy Run02 material values are explicitly patched into
  the run-local config so a rerun can be compared to the prior convergence
  figure. This is not the default OrPen material policy.

## Known Follow-Up

`gsim` currently validates the official Palace `0.16.0` schema and does not
emit the native `Mask` field. The notebook therefore validates the base config
first, writes the native-mask patch second, and calls
`sim.generate_handoff_package(write_config=False)` so packaging cannot overwrite
the patched config.
