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
- the same notebook loads synthetic public Eigenmode and Electrostatic Palace
  report bundles through `gsim.palace.load_eigenmode_report()` and
  `gsim.palace.load_electrostatic_report()`, then displays curated
  domain-loss, surface-loss, and loss-budget tables through a notebook-local
  presentation helper instead of raw report displays;
- the notebook does not add automatic MA/MS/SA interface postprocessing yet:
  generated interface identities and material-kind classification are available
  as manifest-level helpers, while public problem-type examples wait for
  source-backed public preset records and material-name alias policy;
- the same notebook exposes an opt-in local Palace smoke cell for Driven,
  Eigenmode, and Electrostatic public fixtures; normal docs builds display a
  skip reason unless `ORPEN_RUN_LOCAL_PALACE_SMOKE=1` and a Palace SIF or
  executable path is configured.

Current executable smoke coverage:

- the public Driven CPW fixture has an opt-in local Palace coarse solve guarded
  by `ORPEN_RUN_LOCAL_PALACE_SMOKE=1`;
- the Driven smoke verifies `gsim.palace.SParams` parsing, `o1`/`o2` port
  labels, and non-empty `port-S.csv` output;
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
- Eigenmode report loading now has a reusable public bundle that composes final
  modes, AMR history, pass summaries, optional indexed EPR tables, index-map
  provenance, and source bookkeeping without importing private notebook parsers.
- Electrostatic report loading now has a reusable public bundle that composes
  terminal matrices, terminal matrix pass summaries, optional indexed
  domain/surface EPR tables, config/material/interface provenance, source
  bookkeeping, source-indexed loss budgets, and explicit-frequency T1
  derivation without importing private notebook parsers.
- publication-safe notebook output now includes reusable Eigenmode and
  Electrostatic loss-budget table displays from synthetic public artifacts,
  keeping normal docs builds independent of local Palace.
- publication-safe notebook output now includes a guarded local solver smoke
  entrypoint that reuses the public fixture builders and keeps normal docs
  builds independent of local Palace.

Acceptance direction:

- each notebook uses `gsim` APIs and `orpen-sc-pdk` public metadata only;
- each notebook can run a coarse local Palace smoke test when Palace is
  available;
- saved outputs are scrubbed or synthetic unless explicitly publication-safe;
- notebook tests verify the workflow contract without depending on private
  layout modules, private run folders, or private benchmark values.

Related issue:

- {doc}`../issues/public-problem-type-notebook-coverage`

```{toctree}
:hidden:

../notebooks/public_simulation_workflows
```
