# Palace HPC Handoff And Resource Records

**Repo:** `gsim`

NCUAS already has a post-config workflow layer for Palace run staging, HPC
handoff, archives, and resource records. The public ecosystem should absorb
the reusable parts into `gsim` without moving private layout assumptions or a
second solver runtime into `orpen-sc-pdk` or `gplugins`.

Problem:

- private workflows need more than `config.json` and local `run_local()`: they
  also need runtime-stage controls, handoff packaging, Slurm scripts, site
  profiles, resource overrides, post-run resource records, and benchmark
  indexes;
- a read-only NCUAS inventory found this as a helper chain rather than a single
  utility: `prepare_simulation_runtime_stage(...)`,
  `build_*_runtime_config(...)`, `prepare_palace_sbatch_handoff(...)`,
  `run_or_show_palace_stage(...)`, Palace handoff validation/log diagnostics,
  sbatch/package helpers, HPC profile resolution, sweep runtime staging,
  package analysis, result archives, and run/sweep record builders;
- local `gsim` already owns Palace config generation, local/cloud execution
  metadata, run summaries, report loaders, point-local sweep summaries,
  Slurm/Sbatch dry-run handoff sidecars, archive manifests, resource-record
  sidecars, sanitized Palace log-derived resource tables, and sanitized Slurm
  scheduler/allocation parsing, and caller-supplied profile resolution, but it
  does not yet ship real site catalogs or model full benchmark campaign costs;
- `gplugins` still has older direct Palace helpers, but extending those into
  cluster handoff would create a second public Palace runtime.

Proposed path:

- keep `gsim.palace` as the owner of reusable Palace run-stage metadata,
  handoff manifests, profile/resource schemas, and result/resource record
  loaders;
- start artifact-first: add optional handoff/resource sidecars beside the
  existing `config.json`, `palace.msh`, `mesh_manifest.json`,
  `palace_index_map.json`, `palace_material_resolution.json`, and
  `palace_run_metadata.json`;
- extend `load_palace_run_summary()` and `load_palace_sweep_summary()` so
  existing public fixture and private consumer evidence can report the same
  handoff/resource status without parsing scheduler files in notebooks;
- model scheduler/profile data generically in `gsim`, while keeping
  site-specific profile catalogs caller-supplied or project-owned until a
  public source for those profiles exists;
- build sweep handoff on the existing `PalaceSweepPointSpec` and
  `points.json` identity model before adding heavier campaign orchestration;
- treat handoff archives as generated review artifacts with a manifest, not as
  source files to commit by default;
- keep `orpen-sc-pdk` limited to public fixtures and evidence consumers, and
  keep `gplugins` compatibility wrappers thin if they are needed at all.

Current local evidence:

- `gsim` has reusable local/cloud runtime sidecars and summary readers;
- local `gsim` commit `8879248` adds the first artifact-level handoff
  contract: `write_palace_handoff_metadata()`, optional
  `palace_handoff_metadata.json` discovery in `load_palace_run_summary()`,
  `PalaceSweepPointSpec.handoff_metadata_path`, and flat sweep point handoff
  fields for status, profile, script presence, and archive presence;
- local `gsim` adds Slurm resource/profile models and the notebook-facing
  `sim.write_slurm_sbatch_handoff(...)` Run Stage method for generic
  Slurm/Sbatch dry-run script rendering. The API accepts explicit
  caller-supplied resources/profile metadata, writes `run_palace.sbatch`, and
  updates `palace_handoff_metadata.json`; it does not submit jobs, package
  archives, or resolve private site profiles;
- local `gsim` commit `c2c5383` adds `PalaceSlurmSweepArraySpec`,
  `write_palace_slurm_sweep_array_handoff()`, generated `points.csv`,
  `run_sweep_array.sbatch`, and `palace_sweep_handoff_metadata.json` for
  sweep-level Slurm array dry-runs. `load_palace_sweep_summary()` now exposes
  this as `summary.handoff` while point-local handoffs remain under each
  point's `run_summary.handoff`;
- local `gsim` commit `0ab7628` adds `PalaceHandoffArchiveManifestResult`,
  `write_palace_run_handoff_archive_manifest()`, and
  `write_palace_sweep_handoff_archive_manifest()`. These writers generate
  JSON manifests for the files that would be packaged for a single run or
  sweep, update the existing handoff sidecar with
  `archive.manifest_path`, and keep archive creation/submission out of
  `gsim`;
- local `gsim` commit `7febb33` adds `write_palace_resource_record()`,
  `palace_resource_record.json` discovery, `load_palace_run_summary().resource`,
  `PalaceSweepPointSpec.resource_record_path`, sweep-level
  `resource_present_count`, and flat point fields for resource status,
  wall-time, core-hours, allocation shape, peak HWM memory, and global
  unknowns. This is the public post-run resource sidecar surface; it does not
  parse Palace logs or Slurm snapshots yet;
- local `gsim` commit `452b3d4` adds `parse_palace_resource_log()` and
  `write_palace_resource_record_from_log()`, including public-safe AMR pass,
  stage timing, and stage memory CSV sidecars plus solver version, PETSc
  version, wall-time, memory, and model-size fields. The parser intentionally
  omits PETSc node, user, and executable path fields from the structured
  record;
- local `gsim` commit `19e35fd` adds `parse_slurm_scontrol_job()` and optional
  `scontrol_path` support in `write_palace_resource_record_from_log()`. The
  parser keeps sanitized Slurm job state, partition, time, allocation, and
  requested-memory fields while omitting raw scheduler text, account, user,
  node, job-name, command, stdout/stderr, and work-dir values;
- local `gsim` commit `bfcc45a` adds
  `write_palace_sweep_resource_index()`, generating sweep-level
  point-record CSV, resource-record CSV, benchmark JSONL, and compact index
  JSON files from explicit `points.json` metadata and the existing
  `load_palace_sweep_summary()` surface;
- local `gsim` commit `d93830f` adds `PalaceSlurmProfileSpec` and
  `resolve_palace_slurm_profile()`, resolving caller-supplied named Slurm
  profiles into `PalaceSlurmResourceSpec` plus handoff-ready profile metadata.
  Resource overrides are validated against the public resource spec; private
  site catalogs and submission remain caller-owned;
- local `gsim` commit `ba04d9d` adds
  `load_palace_slurm_profile_catalog()`, which loads caller-owned JSON catalog
  files with `schema_version: 1` plus a `profiles` mapping, or a direct profile
  mapping, and returns normalized `PalaceSlurmProfileSpec` objects;
- local `gsim` commit `5ff58b6` adds `PalaceSlurmLauncherSpec` and extends
  `PalaceSlurmProfileSpec`/`PalaceSlurmProfileResolution` with generic
  launcher hints (`palace_executable`, command style, setup commands, PETSc
  options, and `srun` arguments) plus solver hints (`device` and `backend`).
  This captures the reusable NCUAS-style runtime controls while keeping real
  site catalogs, private setup commands, and submission policy caller-owned;
- local `gsim` commit `0f401c5` adds
  `PalaceSlurmProfileResolution.to_palace_config_hints()` and deep-merged
  high-level `sim.write_config(hints=...)`, so profile solver hints can update
  generated Palace `Solver.Device` and optional `Solver.Backend` without
  dropping generated `Solver.Linear` or problem-type solver settings;
- public OrPen evidence now writes dry-run handoff sidecars for Driven,
  Eigenmode, and Electrostatic fixtures plus a sweep-level Slurm array script
  plus generated archive manifests and handoff archives, and synthetic public
  log-derived resource-record sidecars plus sanitized synthetic Slurm snapshot sidecars
  through the `gsim` renderers, loads
  `scripts/fixtures/public_slurm_profiles.json`, resolves named public dry-run
  profiles through the `gsim` profile resolver, forwards launcher hints into
  generated single-run and sweep-array scripts, forwards solver hints into
  generated `config.json` files, then reads the sidecars back through the
  normal run/sweep summary surfaces and writes reusable sweep-level
  resource/benchmark index files;
- `gsim` has point-local sweep summary readers/writers, dry-run Slurm script
  renderers, generated archive manifests, handoff archive packaging, and a
  generic post-run resource sidecar, but no cluster campaign submission;
- `gplugins` has direct Palace wrapper functions that generate config, call a
  `palace` executable from `PATH`, and parse raw CSV output, but those helpers
  do not expose the richer `gsim` run-summary/report surfaces;
- the public OrPen problem-type evidence bundle now proves the
  `palace_handoff_metadata.json` path for Driven, Eigenmode, and
  Electrostatic in cluster-free dry-runs, while the existing opt-in local
  Palace run path still reports `palace_run_metadata.json` through the same
  summary schema.

Remaining slices:

- add private site catalog content in private consumers and validate those
  profiles against the generic `gsim` Slurm handoff API on real Slurm/HPC runs;
- add richer benchmark campaign and cost-modeling helpers without committing
  private archives or private benchmark values;
- only after dry-run schemas are stable, add local private-layout validation on
  NCUAS personal branches against real Slurm/HPC runs.

Acceptance checks:

- `gsim` remains the only reusable Palace runtime owner;
- `gplugins` does not grow duplicated Palace handoff/config/report logic;
- public docs and fixtures do not include private run directories, scheduler
  accounts, private benchmark values, or private layout names;
- single-run and sweep summaries can report missing, dry-run, or completed
  handoff/resource records through the same public schema;
- private consumers can mount site-specific profile catalogs without changing
  public `gsim` APIs.

Related features:

- [../features/benchmark-cost-analysis](../features/benchmark-cost-analysis.md)
- [../features/palace-config-generation](../features/palace-config-generation.md)
- [../features/problem-type-notebook-suite](../features/problem-type-notebook-suite.md)
