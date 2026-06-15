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
- local `gsim` commit `1d9390f` adds `PalaceSweepPointSpec` and
  `write_palace_sweep_points()`, making `gsim` the writer as well as the
  reader for explicit sweep point metadata;
- local `gsim` commit `ac62a4a` validates sweep point identity by rejecting
  duplicate point slugs in generated metadata and surfacing duplicate slugs plus
  parse warnings when loading existing `points.json` files;
- local `gsim` commit `f5eb728` extends those sweep summaries with
  `to_point_records()` and `to_dataframe()`, producing flat records that carry
  sweep/point identity, public point parameters, artifact counts/bytes,
  runtime sidecar status, result-file counts, and compact config,
  mesh-manifest, index-map, and material-resolution counts;
- local `gsim` commit `f2dbe7f` adds opt-in report-derived sweep point metrics,
  reusing the existing Driven, Eigenmode, and Electrostatic report loaders to
  add compact physics/report rows when solver result artifacts are present,
  while recording missing report status for dry-run or partial sweeps;
- local `gsim` commit `8879248` adds dry-run Palace handoff sidecars through
  `write_palace_handoff_metadata()` and exposes them through
  `load_palace_run_summary().handoff` plus table-ready sweep point handoff
  fields;
- local `gsim` commit `d4f226a` adds a generic Slurm/Sbatch dry-run handoff
  renderer, `write_palace_slurm_sbatch_handoff()`, which writes
  `run_palace.sbatch` and updates the same `palace_handoff_metadata.json`
  summary surface without submitting jobs or resolving private profile
  catalogs;
- local `gsim` commit `c2c5383` adds a generic Slurm array dry-run handoff
  renderer, `write_palace_slurm_sweep_array_handoff()`, which derives
  `points.csv` from existing `points.json`, writes `run_sweep_array.sbatch`,
  and exposes sweep-level handoff status through
  `load_palace_sweep_summary().handoff`;
- local `gsim` commit `0ab7628` adds generated handoff archive manifests
  through `write_palace_run_handoff_archive_manifest()` and
  `write_palace_sweep_handoff_archive_manifest()`. These writers record the
  reviewable files that would be packaged for a single run or sweep, expose the
  manifest through the existing handoff summary `archive.manifest_path`, and do
  not create archives or submit jobs;
- local `gsim` commit `7febb33` adds a generic post-run
  `palace_resource_record.json` sidecar through
  `write_palace_resource_record()`, exposes compact resource status through
  `load_palace_run_summary().resource`, and flattens sweep point resource
  fields such as wall time, core-hours, allocation shape, peak HWM memory, and
  global unknowns without parsing private scheduler logs;
- local `gsim` commit `452b3d4` adds
  `parse_palace_resource_log()` and `write_palace_resource_record_from_log()`,
  writing public-safe AMR pass, stage timing, and stage memory CSV sidecars
  while omitting PETSc node, user, and executable path fields from the
  structured record;
- local `gsim` commit `19e35fd` adds `parse_slurm_scontrol_job()` and optional
  `scontrol_path` support in `write_palace_resource_record_from_log()`, merging
  sanitized Slurm scheduler/allocation evidence into the same resource record
  without retaining raw account, user, node, job-name, command, stdout/stderr,
  or work-dir fields;
- local `gsim` commit `bfcc45a` adds
  `write_palace_sweep_resource_index()`, which writes
  `metadata/records/sweep_point_records.csv`,
  `metadata/records/sweep_resource_records.csv`,
  `metadata/records/sweep_benchmark_index.jsonl`, and
  `metadata/records/sweep_resource_index.json` from the same explicit
  `points.json` sweep summary;
- local `gsim` commit `d93830f` adds
  `resolve_palace_slurm_profile()` plus `PalaceSlurmProfileSpec`, resolving
  caller-supplied named Slurm profiles into `PalaceSlurmResourceSpec` with
  validated resource overrides while keeping bundled private site catalogs and
  submission out of `gsim`;
- local `gsim` commit `ba04d9d` adds
  `load_palace_slurm_profile_catalog()`, loading caller-owned JSON Slurm
  profile catalogs before feeding the same resolver and handoff sidecar path;
- local `gsim` commit `5ff58b6` extends caller-owned Slurm profiles with
  generic launcher hints (`palace_executable`, command style, setup commands,
  PETSc options, and `srun` arguments) plus solver hints (`device` and
  `backend`), so NCUAS-style profile controls can flow into public dry-run
  scripts without publishing private site catalogs;
- `orpen-sc-pdk` keeps benchmark evidence publication-safe by recording only
  public fixture artifact status, solver skip/runtime/handoff summary fields,
  generated handoff archive manifest status, synthetic public log-derived
  resource-record status, sanitized synthetic Slurm scheduler fields, table
  sidecars, resolved public Slurm dry-run profiles loaded from
  `scripts/fixtures/public_slurm_profiles.json` including launcher/solver
  hints, a public problem-type
  sweep-summary smoke, and generated sweep-level resource/benchmark index files
  in the ignored local evidence bundle.
- the public evidence bundle can now be replayed with local direct-binary
  Palace execution for Driven, Eigenmode, and Electrostatic fixtures; each
  point records sanitized command shape, return code, elapsed seconds, output
  counts, and report-loader status through the same `gsim` run-summary schema.
- NCUAS already has a richer private run-stage layer for Slurm/Sbatch handoff,
  handoff archives, site/profile resources, and post-run records; the public
  migration path is to extend the same `gsim` run-summary and sweep-summary
  schemas with optional handoff/archive/resource/profile sidecars, not to expose
  private benchmark values or duplicate runtime code in the PDK.

Acceptance direction:

- benchmark records distinguish physics outputs from runtime, mesh, memory, and
  execution-cost metadata;
- sweep summaries start from reusable explicit point metadata writing/loading
  with identity validation, per-point run summaries, table-ready point records,
  and reusable report-derived metrics before adding broader handoff,
  orchestration and cost modeling;
- public fixtures provide normalized records for docs and regression tests;
- private consumers can compare local records against the same schema without
  publishing raw values;
- CAD/mesh performance evidence stays in the mesh/CAD layer, while Palace
  workflow performance lives in `gsim`.

Related issues:

- {doc}`../issues/palace-report-ownership`
- {doc}`../issues/public-problem-type-notebook-coverage`
- {doc}`../issues/palace-hpc-handoff-records`
