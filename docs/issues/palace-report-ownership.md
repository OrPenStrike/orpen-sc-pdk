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
- `orpen-sc-pdk` now routes the public Eigenmode smoke through
  `load_eigenmodes()` and `load_eigenmode_history()`.

Remaining slices:

- extend the reusable report layer toward material-loss/T1/gamma summaries only
  where that information belongs in public `gsim` schemas or PDK-owned material
  overlays;
- keep native masked Surface EPR as a Palace-source/upstream capability rather
  than a Python replay in the public PDK.

Related features:

- {doc}`../features/palace-reporting`
- {doc}`../features/benchmark-cost-analysis`
