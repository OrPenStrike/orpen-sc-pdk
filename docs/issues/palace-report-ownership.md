# Palace Report Ownership

**Repo:** `gsim`

Reusable Palace report generation should live upstream instead of in a private
layout repo or inside the PDK core.

Problem:

- private notebooks already parse Palace indexed reports such as
  `domain-E.csv`, `surface-Q.csv`, and `port-EPR.csv` back to physical names;
- those mappings must come from generated solver artifacts, not notebook-local
  physical-name scans or private layout naming rules;
- the PDK should not own a parallel report framework when `gsim` already owns
  Palace result loading.

Proposed path:

- extend `gsim.palace.results` so reusable report loaders can consume
  `palace_index_map.json`;
- keep public PDK examples focused on producing solver artifacts and reading
  public-safe reports through `gsim`;
- keep richer report tables and presentation layers downstream of a reusable
  `gsim` result schema.

Verified local changes:

- `gsim` commit `5caa2db`: adds `load_postprocessing_index_map()` and
  `load_indexed_csv()` to the public `gsim.palace` surface;
- `load_indexed_csv()` can load indexed Palace CSV files, infer standard
  sections for `domain-E.csv`, `surface-Q.csv`, and `port-EPR.csv`, rename
  indexed columns with physical names from `palace_index_map.json`, and expose
  JSON-friendly column provenance rows;
- focused `gsim` tests cover directory sources, results-dict sources,
  domain-energy mapping, surface-Q mapping, unmapped index preservation, Ruff,
  and targeted Pyright.
- `gsim` commit `38787ff`: adds `TerminalMatrix` and
  `load_terminal_matrix()` to the public `gsim.palace` surface;
- `load_terminal_matrix()` can load `terminal-C.csv`, `terminal-Cm.csv`, and
  `terminal-Cinv.csv`, label rows/columns from `Boundaries.Terminal` rows in
  `palace_index_map.json`, preserve SI values, expose display-scaled matrices,
  and emit long-form terminal-pair rows for report tables.
- `gsim` commit `3c0dad9`: adds `load_terminal_matrix_history()` and
  `summarize_terminal_matrix_history()` so electrostatic AMR pass matrices can
  be loaded, final-pass duplicates can be dropped, and convergence deltas can be
  summarized without notebook-local parsing.
- `gsim` commit `76b383a`: adds indexed EPR summary helpers on top of
  `load_indexed_csv()`;
- `load_domain_energy_summary()`, `load_surface_q_summary()`,
  `summarize_surface_q_by_interface()`, and `load_port_epr_summary()` reshape
  `domain-E.csv`, `surface-Q.csv`, and `port-EPR.csv` into public-safe report
  frames with index-map provenance, interface totals, and port participation
  fractions.
- `orpen-sc-pdk` now validates `load_terminal_matrix()` against a real optional
  local Palace Electrostatic coarse solve, so the public fixture proves
  generated terminal matrix CSVs can be loaded back with `positive`/`negative`
  labels from `palace_index_map.json`.
- `orpen-sc-pdk` now validates the public Driven CPW fixture against a real
  optional local Palace coarse solve, proving `port-S.csv` loads through
  `gsim.palace.SParams` with `o1`/`o2` port labels.
- `orpen-sc-pdk` now validates the public Eigenmode resonator fixture against a
  real optional local Palace coarse solve, proving `eig.csv` and `domain-E.csv`
  are produced for a public resonator.
- `gsim` now exposes `load_eigenmodes()`, `load_eigenmode_history()`, and
  `summarize_eigenmode_history()` so Eigenmode `eig.csv` outputs have stable
  normalized fields, notebook-facing aliases, source visibility, and
  HFSS-style pass summaries instead of notebook-local parsing.
- `gsim` commit `ca471b4`: adds `EigenmodeReport` and
  `load_eigenmode_report()` as a thin composition layer over final
  `eig.csv`, AMR history, pass summaries, `palace_index_map.json`,
  `domain-E.csv`, `surface-Q.csv`, and `port-EPR.csv`;
- optional EPR report families load independently and missing optional reports
  are recorded in the report `sources`/`missing_reports` table rather than
  forcing every Eigenmode run to emit all EPR outputs;
- `orpen-sc-pdk` now routes the public Eigenmode smoke through
  `load_eigenmode_report()`, proving a real local resonator solve can read
  positive modal rows, final-source visibility, and domain-energy rows through
  the public report bundle.
- optional local Eigenmode Palace validation passed after the report-bundle
  wiring with `ORPEN_RUN_LOCAL_PALACE_SMOKE=1`, a direct local Palace binary,
  and `gsim.palace.load_eigenmode_report()`.
- `gsim` commit `0197b64`: adds `load_domain_material_summary()` and
  `EigenmodeReport.domain_materials`, so effective Palace `Domains.Materials`
  rows can be loaded from `config.json` and joined to domain physical names
  through `palace_index_map.json`.
- `gsim` commit `bbd74fe`: adds `load_dielectric_interface_summary()` and
  `EigenmodeReport.dielectric_interfaces`, so configured dielectric
  postprocessing interface rows can be loaded from `config.json` and joined to
  index-map physical names without PDK-owned report parsing.
- `gsim` commit `f12312c`: adds reusable loss-budget interpretation through
  `summarize_domain_loss()`, `summarize_surface_loss()`,
  `summarize_loss_budget()`, and composed Eigenmode report fields for
  `domain_loss`, `surface_loss`, and `loss_budget`.
- `orpen-sc-pdk` public material-overlay fixtures now verify the generated
  public `Si` substrate material row can be read back through this reusable
  `gsim` report/index-map surface for Driven, Eigenmode, and Electrostatic
  artifact handoffs.
- `orpen-sc-pdk` public material-overlay fixtures now verify that a synthetic
  public Eigenmode artifact bundle can derive inverse-Q, equivalent Q, gamma,
  and T1-ready loss budget rows through `gsim.palace.load_eigenmode_report()`.
- `gsim` commit `61d7d66` extends generated config/report provenance with
  `palace_material_resolution.json` and domain material summary columns for
  stack material name, matched material record, model source, validity status,
  and resolution frequency; `orpen-sc-pdk` material-overlay fixtures verify the
  public `Si` model source is visible through the reusable report loader.
- `gsim` commit `fbb19d1`: adds `ElectrostaticReport` and
  `load_electrostatic_report()` as a thin composition layer over terminal
  capacitance matrices, terminal matrix history/pass summaries,
  `palace_index_map.json`, `config.json`, `domain-E.csv`, and `surface-Q.csv`.
- Electrostatic domain/surface loss reports now reuse the same effective
  domain material and configured interface provenance as Eigenmode reports;
  source-indexed Palace samples remain separate, and gamma/T1 columns are
  derived only when callers pass an explicit `frequency_ghz`.
- `orpen-sc-pdk` public material-overlay fixtures now verify that a synthetic
  public Electrostatic artifact bundle can derive inverse-Q, equivalent Q, and
  optional frequency-gated T1-ready loss budgets through
  `gsim.palace.load_electrostatic_report()`.
- The optional public Electrostatic local-Palace smoke now also reloads real
  solver terminal matrices through `gsim.palace.load_electrostatic_report()`
  instead of only the primitive terminal-matrix loader.
- `gsim` commit `1da6783`: adds dielectric-interface material-reference
  resolution and report provenance, so `Boundaries.Postprocessing.Dielectric`
  rows can be populated from a public material overlay and loaded back with
  material source, validity, and frequency metadata.
- `orpen-sc-pdk` public material-overlay fixtures now verify
  `AlOx_native_generic` can reach a Palace dielectric interface row through the
  reusable `gsim` interface material path without making MA/MS/SA defaults part
  of the PDK contract.
- `orpen-sc-pdk` public simulation notebooks now load synthetic public
  Eigenmode/Electrostatic report bundles through `gsim` and display curated
  domain-loss, surface-loss, and loss-budget tables without importing private
  runs or moving report parsing into the PDK.

Remaining slices:

- add a public preset schema before treating MA/MS/SA thickness, loss tangent,
  or automatic interface selection as part of the PDK contract;
- keep native masked Surface EPR as a Palace-source/upstream capability rather
  than a Python replay in the public PDK.

Related features:

- {doc}`../features/palace-reporting`
- {doc}`../features/benchmark-cost-analysis`
