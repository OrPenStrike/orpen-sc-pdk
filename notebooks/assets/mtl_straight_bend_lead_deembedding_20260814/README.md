# MTL Straight + Bend Lead De-Embedding Checkpoint

Status: **CONVERGING research checkpoint**. These files are diagnostic evidence,
not the final reusable S-matrix model.

This checkpoint preserves five completed HFSS Driven Terminal runs for equal
lead/de-embedding lengths of 100, 150, 200, 300, and 400 um. Every point uses
W7/S6 CPW, 80 um finite ground, a five-terminal seam with explicit
`g_center`, a 3--8 GHz Fast sweep with 20,000 points, Max Delta S 0.02,
Maximum Delta Zo 1%, 30 cores, and a 45% RAM limit.

## Completed

- Complete raw and native HFSS de-embedded five-port scattering matrices.
- Ideal-short reduction of `g_center` to a four-port network.
- Modal Zpi, propagation constant, adaptive-pass, tetrahedra, matrix-size, and
  solve-time records.
- Per-length reports plus one aggregate comparison report.
- GDSFactory layout images, HFSS geometry images, solved AEDT projects, and GDS
  coupons for all five points.

The aggregate report is at [aggregate/report.md](aggregate/report.md). It shows
that the two physical signal-through paths are already stable, while the full
five-terminal seam basis remains lead-dependent. After ideal-short reduction,
the complete 300 um network differs from the 400 um reference by 0.0020 in
maximum complex absolute S. No acceptance threshold has been declared.

## Next

1. Run the asymmetric `(parallel MTL lead, single-trace lead)` cases
   `(400, 600) um` and `(600, 400) um` using the now-separated component and
   notebook controls.
2. Apply the MTL-side and single-trace-side de-embedding operators separately
   and identify which side dominates the remaining lead dependence.
3. Extend only the unconverged side, then select a practical reference plane
   from the measured stability/cost trade-off.
4. Repeat the accepted procedure for the bend+bend topology before fitting a
   reusable parameterized circuit/S-matrix model.

## Repository placement

The former top-level `artifacts/` directory was an ad-hoc analysis staging
location and is no longer used. This checkpoint lives under `notebooks/assets/`
beside the existing committed CPW convergence dataset. Rebuildable solver work
continues to belong under ignored `build/`; only explicitly selected research
checkpoints belong here.

Some JSON receipts retain the original absolute LTlab paths as provenance.
Those paths are not runtime dependencies.
