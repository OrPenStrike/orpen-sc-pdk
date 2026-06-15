# Benchmark And Cost Analysis

**Target:** `gsim`

**Status:** candidate

Solver workflows need performance records that make runtime, memory, mesh size,
and cloud/HPC cost visible.

Benchmark reporting must avoid exposing private geometry, private run
directories, or benchmark values from private layouts unless explicitly cleared
for publication.

Current public baseline:

- local `gsim` writes sanitized `palace_run_metadata.json` sidecars for
  successful local Palace runs and exposes them through
  `gsim.palace.load_palace_run_summary().runtime`;
- local `gsim` commit `00b2777` writes solver-specific runtime metadata
  sidecars for GDSFactory+ cloud result downloads, including Palace
  `palace_run_metadata.json`, so local and cloud executions can share the same
  summary surface;
- local `gsim` commit `652fcec` adds
  `gsim.palace.load_palace_sweep_summary()` for explicit `points.json`
  point-local Palace sweep folders, reusing the same per-point run summaries
  without inferring point identity from folder names;
- local `gsim` commit `f5eb728` extends those sweep summaries with
  `to_point_records()` and `to_dataframe()`, producing flat records that carry
  sweep/point identity, public point parameters, artifact counts/bytes,
  runtime sidecar status, result-file counts, and compact config,
  mesh-manifest, index-map, and material-resolution counts;
- `orpen-sc-pdk` keeps benchmark evidence publication-safe by recording only
  public fixture artifact status, solver skip/runtime summary fields, and a
  public problem-type sweep-summary smoke in the ignored local evidence bundle.

Acceptance direction:

- benchmark records distinguish physics outputs from runtime, mesh, memory, and
  execution-cost metadata;
- sweep summaries start from explicit point metadata, per-point reusable run
  summaries, and table-ready point records before adding richer
  physics/performance aggregation;
- public fixtures provide normalized records for docs and regression tests;
- private consumers can compare local records against the same schema without
  publishing raw values;
- CAD/mesh performance evidence stays in the mesh/CAD layer, while Palace
  workflow performance lives in `gsim`.

Related issues:

- {doc}`../issues/palace-report-ownership`
- {doc}`../issues/public-problem-type-notebook-coverage`
