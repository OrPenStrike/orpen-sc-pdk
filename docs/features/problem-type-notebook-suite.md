# Problem-Type Notebook Suite

**Target:** `orpen-sc-pdk` examples using `gsim`

**Status:** prototype

The public PDK should provide a small notebook suite that proves the reusable
simulation workflow works for representative Palace problem types without
copying private notebooks or saved private outputs.

Local/implemented capability:

- driven workflows validate port excitation, terminal sweeps, solver handoff,
  result loading, and performance records;
- eigenmode workflows validate scene construction, sweep staging, mesh/config
  reuse, convergence records, and EPR-ready postprocessing;
- electrostatic workflows validate terminal assignment, capacitance extraction,
  package analysis, and report generation.
- magnetostatic workflows validate current-source ownership, generated
  `SurfaceCurrent` boundaries, vector direction/coordinate-system emission,
  multielement current-source rows, magnetic `SurfaceFlux` index rows, and
  report-loader gap visibility.

Public fixture direction:

- driven: a public CPW or resonator fixture with explicit lumped/terminal
  excitation;
- eigenmode: a public resonator fixture that can run on a coarse mesh and
  later extend to sweep coverage;
- electrostatic: a public capacitor fixture with named terminals and
  capacitance/report outputs.
- magnetostatic: a public CPW fixture with center-selected signal and
  multielement return current sources plus generated config/index-map evidence
  while report loading waits for a confirmed Palace output contract.

Current public notebooks:

- {doc}`../notebooks/public_driven_workflow` runs the public Driven CPW
  mesh/config/artifact handoff with local `gsim` and public `orpen-sc-pdk`
  cells only, writes a Slurm handoff archive, and resolves either the new run
  folder or a user-selected completed run folder through
  `gsim.palace.resolve_palace_result(...).load_report()`;
- {doc}`../notebooks/public_eigenmode_workflow` runs the public resonator
  Eigenmode mesh/config/artifact handoff, proves the generated `air___silicon`
  interface can be classified with caller-supplied public preset values, writes a
  Slurm handoff archive, and resolves either the new run folder or a
  user-selected completed run folder through
  `gsim.palace.resolve_palace_result(...).load_report()`;
- {doc}`../notebooks/public_electrostatic_workflow` runs the public same-layer
  capacitor Electrostatic mesh/config/artifact handoff, shows terminal
  provenance, writes a Slurm handoff archive, and resolves either the new run
  folder or a user-selected completed run folder through
  `gsim.palace.resolve_palace_result(...).load_report()`;
- {doc}`../notebooks/public_driven_local_workflow`,
  {doc}`../notebooks/public_eigenmode_local_workflow`, and
  {doc}`../notebooks/public_electrostatic_local_workflow` use the same public
  fixtures and Resolve/Report path but make the Run Stage call
  `sim.run_local()`. They default to `PALACE_RUN_LOCAL = False` so docs builds
  can render them without local Palace; users set it to `True` after configuring
  local runtime controls such as `PALACE_SETUP_COMMANDS`;
- all three problem-type notebooks display report-owned typed data such as
  `report.domain_materials`, `report.dielectric_interfaces`, `report.sparams`,
  and `report.capacitance` when a completed run folder is selected. Normal
  docs-safe execution displays report status and missing-artifact summaries
  instead of fabricating report rows; primitive provenance loaders stay in their
  Resolve owner modules for tests and evidence generation.
- all three problem-type notebooks keep the main Geometry -> LayerStack -> Mesh
  -> Config -> Run -> Resolve -> Visualize chain visible in the notebook
  source instead of hiding it in script wrappers;
- all three problem-type notebooks configure public Palace HPC handoff in the
  Run cell. The notebook selects `PALACE_HPC_PROFILE`, applies resource
  overrides such as Slurm account, task shape, and wall time, resolves the
  Public PDK run profile, calls `sim.write_config(...)`, writes
  `run_palace.sbatch` through `sim.write_slurm_sbatch_handoff(...)`, and then
  calls `sim.generate_handoff_package(...)` so the `.tar.gz` contains the
  executable Slurm script;
- all three local problem-type notebooks configure direct Palace execution in
  the Run cell. The notebook writes config into the same canonical run folder,
  then calls `sim.run_local(...)` when `PALACE_RUN_LOCAL` is enabled;
- setting `NOTEBOOK_ANALYSIS_RUN_ROOT` points Resolve/Report at an existing run
  folder and disables `NOTEBOOK_PREPARE_RUN_STAGE`, so a clean Run All can
  reopen completed solver outputs without creating a new handoff folder or
  archive;
- public F1 and Nano4 profile values live in
  `orpen_sc_pdk.simulation.palace_hpc`. `gsim` remains the generic owner of
  Slurm schema validation, profile resolution, Palace solver hints, sbatch
  rendering, and archive packaging. Private lab machines such as LTLab stay
  outside the Public PDK profile catalog;
- all three problem-type notebooks are guarded by style tests that reject
  notebook-local function definitions and calls to private `_...()` helpers;
- all three problem-type notebooks keep local Palace smoke execution out of the
  notebook surface. Local solver proof remains in pytest/evidence paths; the
  notebook Run Stage owns handoff-package generation and the Resolve Stage owns
  post-run folder analysis;
- the helper-node coverage matrix remains in
  `scripts/fixtures/public_simulation_helper_nodes.json` and JSON evidence
  bundles rather than being embedded as notebook-local helper logic;
- local `gsim` boundary-review coverage remains a script-level evidence
  sidecar, not a package-root API or a claim that every grouped support commit
  is directly executed by OrPen notebooks;
- Magnetostatic remains a public config/index-map evidence fixture in
  `scripts/public_palace_smoke_evidence.py`; it is intentionally outside the
  report-backed notebook suite until a public Palace report contract is needed,
  and the evidence runner keeps its local solver path disabled even when
  Driven/Eigenmode/Electrostatic local smokes are enabled.

Current executable smoke coverage:

- the public Driven CPW fixture has an opt-in local Palace coarse solve guarded
  by `ORPEN_RUN_LOCAL_PALACE_SMOKE=1`;
- the Driven smoke verifies `gsim.palace.SParams` parsing, `o1`/`o2` port
  labels, non-empty `port-S.csv` output, and the reusable
  `resolve_palace_result(...).load_report().require_report()` bundle over the
  same public output directory;
- the public Eigenmode resonator fixture has an opt-in local Palace coarse
  solve guarded by `ORPEN_RUN_LOCAL_PALACE_SMOKE=1`;
- the Eigenmode smoke verifies non-empty `eig.csv` and `domain-E.csv` outputs
  and reads positive eigenfrequency rows, source visibility, and domain-energy
  rows through
  `resolve_palace_result(...).load_report().require_report()`;
- the Eigenmode local smoke uses the existing `gsim` problem/numerical knobs
  (`EigenmodeSim.set_eigenmode(...)` and `PalaceSimBase.set_numerical(...)`)
  to run a smoke-grade one-mode, first-order solve without changing the
  notebook-facing mesh/config fixture contract;
- the public Electrostatic capacitor fixture has an opt-in local Palace coarse
  solve guarded by `ORPEN_RUN_LOCAL_PALACE_SMOKE=1`;
- the smoke path accepts a Palace SIF (`PALACE_SIF`), a direct local executable
  (`PALACE_EXECUTABLE`), or the selected public run profile's Palace launcher
  setup commands, with `PALACE_EXECUTABLE_MODE=binary` for development binaries
  that do not accept wrapper launcher flags;
- the Spack Palace wrapper path has been replayed locally for all three public
  fixtures with one process and one thread; direct macOS development binaries
  remain supported and may need
  `DYLD_LIBRARY_PATH=<palace-build>/lib:<palace-build>/lib64` when the binary
  carries stale rpaths;
- the Electrostatic smoke verifies both non-empty solver matrix outputs and the
  composed Electrostatic report round trip through
  `resolve_palace_result(...).load_report().require_report()`;
- Driven report loading now has a reusable public bundle that composes final
  S-parameters, optional frequency-sample domain/surface loss rows, index-map
  provenance, config material/interface provenance, and source bookkeeping
  without importing private notebook parsers.
- Eigenmode report loading now has a reusable public bundle that composes final
  modes, AMR history, pass summaries, optional indexed EPR tables, index-map
  provenance, and source bookkeeping without importing private notebook parsers.
- Electrostatic report loading now has a reusable public bundle that composes
  terminal matrices, terminal matrix pass summaries, optional indexed
  domain/surface EPR tables, config/material/interface provenance, source
  bookkeeping, source-indexed loss budgets, and explicit-frequency T1
  derivation without importing private notebook parsers.
- publication-safe notebook output now includes reusable report displays when a
  completed run folder is selected through `NOTEBOOK_ANALYSIS_RUN_ROOT`; default
  docs builds remain independent of local Palace by showing handoff and
  missing-report status instead of synthetic report artifacts.
- publication-safe notebook output now includes generated Eigenmode
  interface-classification provenance with caller-owned preset values.
- publication-safe notebooks no longer include guarded local solver smoke cells;
  local smoke stays in executable tests and evidence scripts.
- `scripts/public_palace_smoke_evidence.py` builds the same public Driven,
  Eigenmode, Electrostatic, and Magnetostatic coarse fixtures into
  `build/public-palace-smoke-evidence/` and writes
  `public_palace_smoke_evidence.json` with a reusable
  `gsim.palace.results.load_palace_run_summary()` bundle for generated artifact status,
  mesh-manifest summaries, Palace index-map summaries, material-resolution
  sidecar presence, and either solver skip reasons or parsed `gsim` report
  summaries.
- the same evidence runner now records `index_map_lookup` rows from
  `gsim.palace.resolve.loaders.index_maps.load_postprocessing_index_map()`,
  proving each public problem fixture can query
  `section/index -> physical name`, reverse physical-name indices, and
  attribute ownership from the generated `palace_index_map.json`.
- the same evidence runner now records `config_generation` rows from generated
  configs and
  `gsim.palace.resolve.derived.materials.load_domain_material_summary()`,
  proving each public problem fixture carries solver block, postprocessing
  count, boundary count, and material provenance evidence.
- the same evidence runner now records the helper-node inventory fixture as
  `helper_node_inventory`, including implemented public fixtures, shared
  material/interface/index/runtime helper nodes, and the Magnetostatic
  config-fixture/report-loader gap.
- the same evidence script uses `gsim.palace.results.write_palace_sweep_points()` to
  write a public `points.json` table for those four fixtures, then consumes
  `gsim.palace.results.load_palace_sweep_summary()` so sweep identity starts from
  explicit point metadata rather than folder scans or PDK-local JSON assembly.
- the public evidence test now checks `gsim` sweep identity validation output:
  the four public problem fixtures have unique point slugs and no sweep
  metadata parse warnings.
- the same sweep summary now exposes table-ready `point_records`, giving each
  public problem fixture a normalized row with point parameters, generated
  artifact status, runtime sidecar status, result-file counts, and compact
  config/mesh/index/material-resolution counts.
- the same evidence path now requests optional `gsim` sweep report metrics; in
  default dry-run mode those rows record missing Driven/Eigenmode/Electrostatic
  report status and skipped Magnetostatic report status without fabricating
  solver outputs, and opt-in local solver replays can fill the same columns
  from supported reusable report loaders.
- the same dry-run evidence path now writes a synthetic public Palace log for
  each problem fixture and consumes
  `gsim.palace.results.write_palace_resource_record_from_log()` so AMR, timing,
  memory, solver-version, wall-time, and model-size records are covered without
  exposing private scheduler or PETSc identity fields.
- the same evidence path now writes a synthetic public Slurm `scontrol`
  snapshot for each problem fixture and passes it to the `gsim` resource-record
  writer, proving sanitized scheduler/allocation fields without retaining raw
  account, user, node, job-name, command, or work-dir values.
- the same evidence path now calls
  `gsim.palace.results.write_palace_sweep_resource_index()` to emit sweep-level point
  records, resource records, and benchmark JSONL indexes under
  `metadata/records/`.
- the same evidence path resolves named public Slurm dry-run profiles from
  `scripts/fixtures/public_slurm_profiles.json` through
  `gsim.palace.handoff.load_palace_slurm_profile_catalog()` and
  `gsim.palace.handoff.resolve_palace_slurm_profile()` for script-level
  coverage. The notebook-facing public site catalog is
  `orpen_sc_pdk.simulation.palace_hpc`, which carries the F1/Nano4 profiles
  used to generate `run_palace.sbatch` inside handoff archives.
- those public profile fixtures now also carry generic launcher hints
  (`command_style`, PETSc options, and `srun_args`) plus solver hints, and the
  generated dry-run scripts prove those hints flow into both single-run and
  sweep-array Slurm handoff output.
- the same evidence path now passes
  `run_profile.to_palace_config_hints()` into public problem-type
  `sim.write_config(...)` calls and verifies generated `config.json` files keep
  `Solver.Device` aligned with the resolved public profile.
- default evidence generation is dry-run and solver-free; setting
  `ORPEN_RUN_LOCAL_PALACE_SMOKE=1` plus `PALACE_SIF` or `PALACE_EXECUTABLE`
  turns the same evidence script into an opt-in local Palace smoke replay,
  including sanitized `gsim` runtime metadata when `run_local()` completes.

Known gaps and non-goals:

- Magnetostatic now has a public config/index-map fixture covering vector
  direction, coordinate-system, and multielement source config, but no public
  report loader yet; the shared helper-node inventory records this as
  `implemented_public_config_fixture_pending_report_loader`.
- Full sweep orchestration and broader cost modeling remain later reusable
  `gsim` workflow slices; the current public baseline is explicit point
  metadata plus table-ready per-point artifact, runtime, provenance, and
  report-status/metrics records.
- Native masked Surface EPR remains a Palace-source or upstream `gsim` lane,
  not a Python replay inside the public PDK notebook suite.

Acceptance direction:

- each notebook uses `gsim` APIs and `orpen-sc-pdk` public metadata only;
- each notebook creates a reviewable Palace handoff package and can resolve a
  user-selected completed run folder through `NOTEBOOK_ANALYSIS_RUN_ROOT`;
- local review can regenerate a durable JSON evidence bundle with
  `uv run --group ecosystem-dev python scripts/public_palace_smoke_evidence.py`;
- saved outputs are scrubbed unless explicitly publication-safe; report fixture
  rows are not generated by the notebooks;
- notebook tests verify the workflow contract without depending on private
  layout modules, private run folders, or private benchmark values.

Related issue:

- {doc}`../issues/public-problem-type-notebook-coverage`
