# Palace Analysis/Reporting Contract

**Target:** `gsim`

**Status:** candidate

Reusable Palace electrostatic and EPR report generation should live in `gsim`.
The PDK should provide layer and material metadata that these reports can
consume without depending on private layout repositories.

Acceptance direction:

- report APIs work with public cells and mounted private components;
- reports consume generated Palace config provenance, public layer/material
  identifiers, and solver index maps;
- electrostatic, eigenmode/EPR, driven, and benchmark records use reusable
  schemas instead of notebook-local parsing;
- private layouts can validate the same workflow without publishing layout;
- generated reports avoid private paths and benchmark data from private layouts
  by default.

Current implemented baseline:

- `gsim.palace.load_postprocessing_index_map()` is the root public loader for
  generated `palace_index_map.json` artifacts used directly by public notebooks
  and smoke evidence.
- Lower-level indexed CSV, eigenmode pass-history, terminal matrix history,
  port-EPR, interface aggregation, and loss-summary helpers live in
  `gsim.palace.results`, for example `load_indexed_csv()`,
  `load_eigenmodes()`, `load_eigenmode_history()`,
  `load_terminal_matrix_history()`, `load_port_epr_summary()`, and
  `summarize_surface_q_by_interface()`, `summarize_domain_loss()`,
  `summarize_surface_loss()`, and `summarize_loss_budget()`.
- Root `gsim.palace` keeps notebook-facing report and provenance loaders:
  `load_driven_report()`, `load_eigenmode_report()`,
  `load_electrostatic_report()`, `load_terminal_matrix()`,
  `load_domain_material_summary()`,
  and `load_dielectric_interface_summary()`.
- Driven reports compose required `port-S.csv`, optional `port-EPR.csv`,
  index-map provenance, config material/interface provenance, and source
  bookkeeping.
- Eigenmode reports compose final `eig.csv`, AMR history, pass summaries,
  `palace_index_map.json`, optional EPR report families, material/interface
  provenance, and loss-budget tables.
- Electrostatic reports compose terminal capacitance matrices, terminal matrix
  pass summaries, optional indexed `domain-E.csv` and `surface-Q.csv` reports,
  material/interface provenance, and frequency-gated loss-budget rows.
- Runtime summaries, sweep records, resource records, and handoff evidence are
  reusable workflow APIs under `gsim.palace.results` or
  `gsim.palace.handoff`, not root problem-report APIs.
- `orpen-sc-pdk` remains a consumer that generates public fixtures, notebooks,
  and display tables; it does not own Palace report parsing.

Related issues:

- {doc}`../issues/palace-report-ownership`
- {doc}`../issues/palace-config-ownership`
- {doc}`../issues/cad-mesh-identity-provenance`
