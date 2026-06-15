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
  sidecars, and sanitized Palace log-derived resource tables, but it does not
  yet resolve real site/profile catalogs or parse scheduler snapshots;
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
- local `gsim` commit `d4f226a` adds `PalaceSlurmResourceSpec`,
  `PalaceSlurmSbatchSpec`, and `write_palace_slurm_sbatch_handoff()` for
  generic Slurm/Sbatch dry-run script rendering. The API accepts explicit
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
- public OrPen evidence now writes dry-run handoff sidecars for Driven,
  Eigenmode, and Electrostatic fixtures plus a sweep-level Slurm array script
  plus generated archive manifests and synthetic public log-derived
  resource-record sidecars through the `gsim` renderers, then reads them back
  through the normal run/sweep summary surfaces;
- `gsim` has point-local sweep summary readers/writers, dry-run Slurm script
  renderers, generated archive manifests, and a generic post-run resource
  sidecar, but no cluster campaign submission or archive packaging;
- `gplugins` has direct Palace wrapper functions that generate config, call a
  `palace` executable from `PATH`, and parse raw CSV output, but those helpers
  do not expose the richer `gsim` run-summary/report surfaces;
- the public OrPen problem-type evidence bundle now proves the
  `palace_handoff_metadata.json` path for Driven, Eigenmode, and
  Electrostatic in cluster-free dry-runs, while the existing opt-in local
  Palace run path still reports `palace_run_metadata.json` through the same
  summary schema.

Remaining slices:

- resolve real site/profile resources outside public fixture code, then feed
  the resolved resources into the generic `gsim` Slurm handoff API;
- add sanitized scheduler/scontrol parsing without public raw accounts,
  user IDs, node names, private job names, or absolute work paths;
- add sweep-level resource record builders and benchmark indexes without
  committing private archives or private benchmark values;
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

- {doc}`../features/benchmark-cost-analysis`
- {doc}`../features/palace-config-generation`
- {doc}`../features/problem-type-notebook-suite`
