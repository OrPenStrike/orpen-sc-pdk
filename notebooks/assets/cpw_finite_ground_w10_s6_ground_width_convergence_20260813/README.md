# W10/S6 CPW finite-ground HFSS convergence

This package preserves the 2026-08-13 five-point HFSS Driven Terminal study of
a 500 um W10/S6 CPW coupon with 10, 20, 40, 80, and 160 um ground width per
side.

## Current design use

The Human selected **80 um per side** as the current working finite-ground
width for this W10/S6 geometry. Across 3--8 GHz, the maximum change in mean
modal `Port Zo` is 0.1992 ohm from 40 to 80 um and 0.03973 ohm from 80 to
160 um. The 80 um point keeps the smaller layout footprint and required 126.6
seconds of solve time in this run.

This is a geometry-specific design choice, not a universal convergence gate.
The two individual port impedances retain a numerical asymmetry; the study
uses their mean only for the ground-width convergence comparison.

## Quantity authority

- Characteristic impedance: HFSS **Modal Solution Data**, quantity category
  `Port Zo`, reported separately as `Zo(o1)` and `Zo(o2)`.
- Scattering response: HFSS Driven Terminal **Terminal Solution Data**,
  `St(o1,o1)` and `St(o2,o1)`.
- The four-panel PNG shows their mean Port Zo, port-to-port Port Zo difference,
  terminal reflection, and terminal transmission at the nearest sampled point
  to 5.5 GHz (5.49987499375 GHz).

## Simulation identity

- HFSS/PyAEDT: 2024 R2 / 1.3.0
- Conductors: PEC sheets; both finite grounds are Wave Port references
- Boundary: no Radiation or PML
- Adaptive solve: three completed passes at every point
- Frequency sweep: Fast, 3--8 GHz, 20,000 points
- Mesh: 10 um Length-Based operation on signal and both grounds, with at most
  1,000,000 additional elements; ground Surface Approximation level 9
- ACF: 30 cores, 45% memory

## Contents

- `cpw_finite_ground_w10_s6_ground_width_convergence.csv`: plotted values,
  full-band adjacent-width comparison, adaptive passes, and solve time.
- `cpw_finite_ground_w10_s6_ground_width_convergence.png`: four-panel summary.
- `aedt/`: one setup-ready AEDT project per ground width.
- `raw/`: complete 20,000-point Modal Port Zo and Terminal S diagnostics.
- `receipts/`: per-point metadata and solve timing.

The large generated `.aedtresults` solver caches are intentionally excluded;
the committed AEDT projects, raw numerical exports, and receipts are the
portable evidence package.
