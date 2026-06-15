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

Public fixture direction:

- driven: a public CPW or resonator fixture with explicit lumped/terminal
  excitation;
- eigenmode: a public resonator fixture that can run on a coarse mesh and
  later extend to sweep coverage;
- electrostatic: a public capacitor fixture with named terminals and
  capacitance/report outputs.

Current public notebook:

- {doc}`../notebooks/public_simulation_workflows` runs public Driven,
  Eigenmode, and Electrostatic mesh/config/artifact handoffs with local `gsim`
  and public `orpen-sc-pdk` cells only;
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
  Eigenmode, and Electrostatic coarse fixtures into
  `build/public-palace-smoke-evidence/` and writes
  `public_palace_smoke_evidence.json` with a reusable
  `gsim.palace.load_palace_run_summary()` bundle for generated artifact status,
  mesh-manifest summaries, Palace index-map summaries, material-resolution
  sidecar presence, and either solver skip reasons or parsed `gsim` report
  summaries.
- the same evidence script writes a public `points.json` table for those three
  fixtures and consumes `gsim.palace.load_palace_sweep_summary()` so sweep
  identity starts from explicit point metadata rather than folder scans.
- the same sweep summary now exposes table-ready `point_records`, giving each
  public problem fixture a normalized row with point parameters, generated
  artifact status, runtime sidecar status, result-file counts, and compact
  config/mesh/index/material-resolution counts.
- default evidence generation is dry-run and solver-free; setting
  `ORPEN_RUN_LOCAL_PALACE_SMOKE=1` plus `PALACE_SIF` or `PALACE_EXECUTABLE`
  turns the same script into an opt-in local Palace smoke replay, including
  sanitized `gsim` runtime metadata when `run_local()` completes.

Known gaps and non-goals:

- Magnetostatic is acknowledged as a private helper/test surface, but it has no
  public OrPen fixture or notebook equivalent yet.
- Full sweep orchestration and richer sweep-level physics/performance
  aggregation remain later reusable `gsim` workflow slices; the current public
  baseline is explicit point metadata plus table-ready per-point artifact,
  runtime, and provenance records.
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
