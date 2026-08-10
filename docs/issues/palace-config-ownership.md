# Palace Config Ownership

**Repo:** `gsim`

Reusable Palace config generation should extend `gsim`. The PDK should export
public layer/material metadata and example component intent, but should not own
solver-specific runtime assembly.

Problem:

- private consumers already need automatic Palace config generation for driven,
  eigenmode, electrostatic, and magnetostatic workflows;
- `gsim` already has Palace simulation classes, problem models, material
  overlay evaluation, mesh generation, and config writing;
- duplicating this in the PDK would create two active public runtimes.

Proposed path:

- extend `gsim` config generation around role-aware mesh manifests,
  postprocessing requests, and public material overlays;
- keep `orpen-sc-pdk` exports limited to public PDK data and example component
  metadata;
- keep `gplugins` as a compatibility façade unless it delegates to `gsim`;
- validate with public driven, eigenmode, electrostatic, and magnetostatic
  config fixtures before using private layouts as local consumers.

Verified local changes:

- `gsim` commit `73c8d98`: high-level `write_config()` now persists terminal
  index-map rows for electrostatic configs, so generated capacitance terminal
  indices can be traced back to manifest physical names;
- `gsim` commit `bd0a2bc`: same-layer planar conductor islands can now be
  selected by electrostatic terminal center points, preserving the layer-level
  terminal fallback when no center is provided;
- `gsim` commit `a584079`: `run_local()` can execute either the Palace wrapper
  command or a direct solver binary, so local coarse smokes can use packaged
  wrappers, Apptainer SIFs, or local development binaries without changing PDK
  fixtures;
- public `orpen-sc-pdk` executable fixtures now validate Driven, Eigenmode,
  Electrostatic, and Magnetostatic mesh/config/artifact handoff through local
  editable `gsim`.
- the public electrostatic fixture now has an opt-in local Palace coarse solve
  that verifies non-empty terminal capacitance outputs.
- the public driven CPW fixture now has an opt-in local Palace coarse solve that
  verifies generated Driven config and CPW lumped-port metadata can produce
  parsed `SParams` output and a composed `DrivenReport` through local `gsim`.
- the public eigenmode resonator fixture now has an opt-in local Palace coarse
  solve that verifies generated Eigenmode config can produce non-empty
  `eig.csv` and `domain-E.csv` outputs through local `gsim`.
- `gsim` commit `20538ec` and the local `orpen-sc-pdk` material export helper
  establish the public material overlay schema bridge needed before config
  generation accepts PDK material overlays directly.
- `gsim` commit `49be250` adds `material_overlay=` to Palace config generation
  and high-level `write_config()`, with validation preserving the same overlay
  when it regenerates config files.
- public `orpen-sc-pdk` Driven, Eigenmode, and Electrostatic fixtures now pass
  `get_gsim_material_overlay()` into `gsim` config generation and verify that
  public `Si` material data reaches the generated Palace domain material block.
- `gsim` commit `0197b64` exposes the generated effective domain material rows
  through `load_domain_material_summary()`, so config material attributes can
  be joined back to generated domain physical names without PDK-owned report
  parsing.
- `gsim` commit `bbd74fe` exposes generated dielectric interface
  postprocessing rows through `load_dielectric_interface_summary()`, so
  configured interface thickness, permittivity, and loss-tangent values can be
  joined back to generated physical names.
- public `orpen-sc-pdk` material-overlay tests now verify that the generated
  `Si` substrate material row can be loaded back through this `gsim` API for
  Driven, Eigenmode, and Electrostatic artifacts.
- `gsim` commit `61d7d66` writes `palace_material_resolution.json` during
  material-overlay config generation and exposes the same provenance through
  `load_domain_material_summary()`, so generated config artifacts can explain
  which public PDK material source and validity status produced each Palace
  material row.
- `orpen-sc-pdk` now has a dev-only
  `scripts/public_palace_smoke_evidence.py` runner that leaves solver runtime
  and artifact-summary ownership in `gsim`, but records public Driven,
  Eigenmode, and Electrostatic mesh/config/index/material-resolution artifacts
  into an ignored JSON evidence bundle for local review through
  `gsim.palace.resolve.load_palace_run_summary()`.
- `gsim` commit `e5e89ef` adds that reusable
  `load_palace_run_summary()` API, including core handoff artifact status,
  result-file status, compact config summaries, mesh-manifest role counts,
  index-map section counts, material-resolution counts, and optional checksums.
- `gsim` commit `4bd1d20` extends successful local `run_local()` executions
  with `palace_run_metadata.json`, recording sanitized launcher information,
  process/thread resources, elapsed seconds, redacted command shape, and output
  file byte counts; the same `load_palace_run_summary()` API exposes the
  sidecar as `runtime`.
- `gsim` commit `00b2777` extends cloud result downloads and legacy
  `run_simulation()` with solver-specific runtime sidecars such as
  `palace_run_metadata.json`, preserving the same
  `load_palace_run_summary().runtime` surface for Palace local and cloud
  execution evidence.
- `gsim` commit `652fcec` adds
  `load_palace_sweep_summary()` for point-local sweep folders with explicit
  `points.json`, keeping sweep identity and per-point artifact summaries in
  `gsim` instead of moving them into `orpen-sc-pdk`.
- `gsim` commit `1d9390f` adds `PalaceSweepPointSpec` and
  `write_palace_sweep_points()`, so the explicit sweep metadata schema is
  written and read by `gsim` instead of hand-assembled by `orpen-sc-pdk`.
- `gsim` commit `ac62a4a` keeps point identity validation in `gsim` by
  rejecting duplicate generated point slugs and exposing duplicate slug and
  parse-warning summaries when existing `points.json` files are loaded.
- `gsim` commit `f5eb728` extends those sweep summaries with table-ready
  point records/data frames, keeping sweep-level artifact, runtime, result, and
  provenance aggregation reusable in `gsim` while `orpen-sc-pdk` remains only a
  public fixture/evidence consumer.
- `gsim` commit `f2dbe7f` adds opt-in report-derived metrics to those sweep
  records, reusing `gsim` Driven/Eigenmode/Electrostatic report loaders instead
  of adding problem-type report parsing to `orpen-sc-pdk`.
- current OrPen local evidence records a `config_generation` section for each
  public problem fixture, proving generated `config.json` files contain the
  expected solver problem block, `Solver.Device` hint, linear-solver block,
  boundary/postprocessing counts, domain material counts, and material-resolution
  sidecar summary without moving config assembly into the PDK package.
- the public problem-type notebooks display the same generated config/material
  provenance as table output through
  `gsim.palace.load_domain_material_summary()`, so notebook review can inspect
  how PDK material overlay values enter Palace `Domains.Materials`.
- public OrPen material records now expose unit permeability for nonmagnetic
  vacuum/dielectric records, and local evidence verifies that `gsim` lowers
  those common material values into Palace `Domains.Materials` without adding
  solver-specific material parsing to the PDK.
- `gsim` commit `c72f0d3` adds first-class Magnetostatic config-surface support
  in the same Palace ownership boundary: public
  `MagnetostaticSim.add_current_source(...)` source intent, generated
  `Problem.Type == "Magnetostatic"`, `Solver.Magnetostatic`,
  `Boundaries.SurfaceCurrent`, `Boundaries.PMC`, magnetic `SurfaceFlux`, and
  source-name rows in `palace_index_map.json`.
- `gsim` commit `883fb78` extends the same Magnetostatic source boundary with
  vector `Direction`, optional `CoordinateSystem`, and selector-based
  multielement `SurfaceCurrent.Elements`, matching the NCUAS/Palace helper
  shape without moving raw physical-group IDs or source geometry into
  `orpen-sc-pdk`.
- `gsim` commit `bc78ad4` closes the responsibility-boundary review findings
  for that source slice: `CoordinateSystem` now requires vector directions,
  parent direction is rejected for multielement sources, overlapping element
  selectors are rejected before misleading index maps can be written, and the
  Palace direction lowering helper is private to config generation.
- current OrPen local evidence and notebook output now share a helper-node
  inventory fixture that records Driven/Eigenmode/Electrostatic as implemented
  public fixtures and Magnetostatic as an implemented public config fixture
  with report loading intentionally pending.

Remaining slices:

- add a public Magnetostatic report loader only after the exact Palace
  Magnetostatic CSV/output contract is confirmed;
- define layout-authored solver-boundary sheet ingestion in `gsim`/meshwell
  before any public fixture depends on drawn boundary-sheet polygons; OrPen
  should not grow runtime parsing for Palace sheet ingestion;
- extend public London-depth provenance only after those records have a
  source-backed public schema;
- record richer dielectric interface provenance before promoting interface
  presets into public PDK material data;
- split NCUAS-style Slurm/Sbatch handoff, profile/resource resolution,
  archives, and run/sweep resource records into the `gsim` handoff/resource
  issue instead of adding those controls to `orpen-sc-pdk` fixtures;
- keep executable fixtures, publication-safe notebooks, and local evidence
  scripts aligned without moving solver orchestration into the PDK package;
- keep normal docs and CI paths independent from local Palace while exposing
  opt-in solver validation commands for local development.

Related features:

- [../features/palace-reporting](../features/palace-reporting.md)
- [../features/material-db-overlay](../features/material-db-overlay.md)
- [../features/palace-config-generation](../features/palace-config-generation.md)
- [../features/problem-type-notebook-suite](../features/problem-type-notebook-suite.md)
- [../features/gsim-palace-branch-comparison](../features/gsim-palace-branch-comparison.md)

Related issue:

- [palace-hpc-handoff-records](palace-hpc-handoff-records.md)
- [palace-api-responsibility-boundary](palace-api-responsibility-boundary.md)
- [gsim-palace-branch-integration](gsim-palace-branch-integration.md)
