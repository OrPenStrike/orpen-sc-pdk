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

Current public notebook:

- {doc}`../notebooks/public_simulation_workflows` runs public Driven,
  Eigenmode, Electrostatic, and Magnetostatic mesh/config/artifact handoffs
  with local `gsim` and public `orpen-sc-pdk` cells only;
- the same notebook now displays a helper-node coverage matrix loaded from
  `scripts/fixtures/public_simulation_helper_nodes.json`, showing why each
  private helper node exists, which private notebook/helper anchors motivated
  the row, which GDSFactory ecosystem repo should own the public equivalent,
  which `gsim`/OrPen API or artifact currently covers it, and which issue owns
  the next slice; rows now also show the promotion gate and missing evidence
  that must be resolved before a pending helper becomes a public default or
  report-backed workflow;
- the same notebook loads synthetic public Driven, Eigenmode, and Electrostatic
  Palace report bundles through `gsim.palace.load_driven_report()`,
  `gsim.palace.load_eigenmode_report()`, and
  `gsim.palace.load_electrostatic_report()`, then displays curated S-parameter,
  port-EPR, domain-loss, surface-loss, and loss-budget tables through a
  notebook-local presentation helper instead of raw report displays;
- the notebook does not add automatic MA/MS/SA interface postprocessing yet:
  generated interface identities and material-kind classification are available
  as manifest-level helpers, and generated `air`/`silicon` material names can
  classify through the public alias map; public problem-type examples still
  wait for source-backed public preset records and default-selection policy;
- the public resonator Eigenmode fixture now proves the generated
  `air___silicon` interface can be classified with OrPen's public
  material-kind and alias helpers when the caller supplies an explicit test
  preset;
- the same notebook now displays the generated `air___silicon`
  interface-classification path and reloads the configured interface
  provenance through `gsim`, keeping automatic public defaults out of the
  notebook;
- the same notebook exposes an opt-in local Palace smoke cell for Driven,
  Eigenmode, and Electrostatic public fixtures; normal docs builds display a
  skip reason unless `ORPEN_RUN_LOCAL_PALACE_SMOKE=1` and a Palace SIF or
  executable path is configured.
- the same notebook displays a Magnetostatic CPW config fixture with a
  vector-direction `signal` source and a multielement `return` source,
  generated `SurfaceCurrent`, `PMC`, and magnetic `SurfaceFlux` boundary
  sections, plus source-name, coordinate-system, and element-count lookup rows
  from `palace_index_map.json`; report parsing remains intentionally pending.
- the same notebook displays the public Slurm profile catalog, resolved
  resource overrides, generic launcher/solver hints, generated Palace
  `Solver` config hints, and a generated dry-run `run_palace.sbatch` preview
  loaded back through
  `gsim.palace.results.load_palace_run_summary()`.
- the same notebook now displays `PostprocessingIndexMap` lookup tables loaded
  through `gsim.palace.load_postprocessing_index_map()`, so public Driven,
  Eigenmode, interface, and Electrostatic cells show how generated Palace
  section/index rows map back to physical names and reverse lookup indices.
- the same notebook now displays generated domain-material provenance tables
  loaded through `gsim.palace.load_domain_material_summary()`, so public problem
  cells show how `get_gsim_material_overlay()` becomes Palace material attributes
  and material-resolution rows, including public material permeability where the
  overlay supplies it.

Current executable smoke coverage:

- the public Driven CPW fixture has an opt-in local Palace coarse solve guarded
  by `ORPEN_RUN_LOCAL_PALACE_SMOKE=1`;
- the Driven smoke verifies `gsim.palace.SParams` parsing, `o1`/`o2` port
  labels, non-empty `port-S.csv` output, and the reusable
  `gsim.palace.load_driven_report()` bundle over the same public output
  directory;
- the public Eigenmode resonator fixture has an opt-in local Palace coarse
  solve guarded by `ORPEN_RUN_LOCAL_PALACE_SMOKE=1`;
- the Eigenmode smoke verifies non-empty `eig.csv` and `domain-E.csv` outputs
  and reads positive eigenfrequency rows, source visibility, and domain-energy
  rows through `gsim.palace.load_eigenmode_report()`;
- the public Electrostatic capacitor fixture has an opt-in local Palace coarse
  solve guarded by `ORPEN_RUN_LOCAL_PALACE_SMOKE=1`;
- the smoke path accepts either a Palace SIF (`PALACE_SIF`) or a direct local
  executable (`PALACE_EXECUTABLE`), with `PALACE_EXECUTABLE_MODE=binary` for
  development binaries that do not accept wrapper launcher flags;
- the direct-binary path has been replayed locally for all three public
  fixtures with one process and one thread; macOS development builds may also
  need `DYLD_LIBRARY_PATH=<palace-build>/lib:<palace-build>/lib64` when the
  binary carries stale rpaths;
- the Electrostatic smoke verifies both non-empty solver matrix outputs and the
  `gsim.palace.load_terminal_matrix()` report-loader round trip through
  `palace_index_map.json`;
- Driven report loading now has a reusable public bundle that composes final
  S-parameters, optional indexed port-EPR rows, index-map provenance, config
  material/interface provenance, and source bookkeeping without importing
  private notebook parsers.
- Eigenmode report loading now has a reusable public bundle that composes final
  modes, AMR history, pass summaries, optional indexed EPR tables, index-map
  provenance, and source bookkeeping without importing private notebook parsers.
- Electrostatic report loading now has a reusable public bundle that composes
  terminal matrices, terminal matrix pass summaries, optional indexed
  domain/surface EPR tables, config/material/interface provenance, source
  bookkeeping, source-indexed loss budgets, and explicit-frequency T1
  derivation without importing private notebook parsers.
- publication-safe notebook output now includes reusable Driven S-parameter and
  port-EPR displays plus Eigenmode and Electrostatic loss-budget table displays
  from synthetic public artifacts, keeping normal docs builds independent of
  local Palace.
- publication-safe notebook output now includes generated Eigenmode
  interface-classification provenance with caller-owned preset values.
- publication-safe notebook output now includes a guarded local solver smoke
  entrypoint that reuses the public fixture builders and keeps normal docs
  builds independent of local Palace.
- `scripts/public_palace_smoke_evidence.py` builds the same public Driven,
  Eigenmode, Electrostatic, and Magnetostatic coarse fixtures into
  `build/public-palace-smoke-evidence/` and writes
  `public_palace_smoke_evidence.json` with a reusable
  `gsim.palace.results.load_palace_run_summary()` bundle for generated artifact status,
  mesh-manifest summaries, Palace index-map summaries, material-resolution
  sidecar presence, and either solver skip reasons or parsed `gsim` report
  summaries.
- the same evidence runner now records `index_map_lookup` rows from
  `gsim.palace.load_postprocessing_index_map()`, proving each public problem
  fixture can query `section/index -> physical name`, reverse physical-name
  indices, and attribute ownership from the generated `palace_index_map.json`.
- the same evidence runner now records `config_generation` rows from generated
  configs and `gsim.palace.load_domain_material_summary()`, proving each public
  problem fixture carries solver block, postprocessing count, boundary count, and
  material provenance evidence.
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
- the same evidence path now resolves named public Slurm dry-run profiles
  from `scripts/fixtures/public_slurm_profiles.json` through
  `gsim.palace.handoff.load_palace_slurm_profile_catalog()` and
  `gsim.palace.handoff.resolve_palace_slurm_profile()`, keeping profile/resource
  normalization in `gsim` while leaving real site catalog content outside the
  public PDK fixture.
- those public profile fixtures now also carry generic launcher hints
  (`command_style`, PETSc options, and `srun_args`) plus solver hints, and the
  generated dry-run scripts prove those hints flow into both single-run and
  sweep-array Slurm handoff output.
- the same evidence path now passes
  `slurm_profile.to_palace_config_hints()` into public problem-type
  `sim.write_config(...)` calls and verifies generated `config.json` files keep
  `Solver.Device` aligned with the resolved public profile.
- default evidence generation is dry-run and solver-free; setting
  `ORPEN_RUN_LOCAL_PALACE_SMOKE=1` plus `PALACE_SIF` or `PALACE_EXECUTABLE`
  turns the same script into an opt-in local Palace smoke replay, including
  sanitized `gsim` runtime metadata when `run_local()` completes.

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
- each notebook can run a coarse local Palace smoke test when Palace is
  available;
- local review can regenerate a durable JSON evidence bundle with
  `uv run --group ecosystem-dev python scripts/public_palace_smoke_evidence.py`;
- saved outputs are scrubbed or synthetic unless explicitly publication-safe;
- notebook tests verify the workflow contract without depending on private
  layout modules, private run folders, or private benchmark values.

Related issue:

- {doc}`../issues/public-problem-type-notebook-coverage`
