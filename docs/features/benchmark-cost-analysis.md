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
- `orpen-sc-pdk` keeps benchmark evidence publication-safe by recording only
  public fixture artifact status and solver skip/runtime summary fields in the
  ignored local smoke-evidence bundle.

Acceptance direction:

- benchmark records distinguish physics outputs from runtime, mesh, memory, and
  execution-cost metadata;
- public fixtures provide normalized records for docs and regression tests;
- private consumers can compare local records against the same schema without
  publishing raw values;
- CAD/mesh performance evidence stays in the mesh/CAD layer, while Palace
  workflow performance lives in `gsim`.

Related issues:

- {doc}`../issues/palace-report-ownership`
- {doc}`../issues/public-problem-type-notebook-coverage`
