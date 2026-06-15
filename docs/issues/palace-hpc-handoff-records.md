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
  metadata, run summaries, report loaders, and point-local sweep summaries, but
  it has no first-class Slurm/Sbatch/HPC handoff or resource-record schema yet;
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

- `gsim` has reusable local/cloud runtime sidecars and summary readers, but no
  Slurm/Sbatch/HPC profile model;
- `gsim` has point-local sweep summary readers/writers, but no Slurm array
  script or cluster campaign handoff;
- `gplugins` has direct Palace wrapper functions that generate config, call a
  `palace` executable from `PATH`, and parse raw CSV output, but those helpers
  do not expose the richer `gsim` run-summary/report surfaces;
- the public OrPen problem-type evidence bundle now proves the local
  `palace_run_metadata.json` path for Driven, Eigenmode, and Electrostatic, so
  the next step can extend the same summary schema instead of introducing a new
  evidence channel.

Remaining slices:

- define the minimal `gsim` sidecar schema for single-run handoff metadata:
  launcher kind, profile name, script path, archive path, requested resources,
  resolved resources, and redacted scheduler command shape;
- add dry-run writers/readers that produce summaries without requiring a live
  cluster or submitting jobs;
- extend sweep summaries with optional handoff/archive/resource fields for each
  point and for the sweep-level array handoff;
- add public OrPen fixture tests that prove the dry-run sidecars are readable
  through `gsim` summary APIs while normal docs builds remain cluster-free;
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
