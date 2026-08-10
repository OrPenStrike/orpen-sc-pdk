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

- Root `gsim.palace` keeps the notebook-facing Resolve path:
  `resolve_palace_result(...).load_report().require_report()`. Direct
  problem-specific report loaders are not root public API.
- `gsim.palace.resolve.loaders` owns primitive artifact loaders such as indexed
  CSVs, eigenmode histories, terminal matrices, S-parameters, and
  `palace_index_map.json`.
- `gsim.palace.resolve.derived` owns semantic derived tables such as domain
  material summaries, dielectric interface summaries, participation summaries,
  and loss summaries.
- `gsim.palace.results` owns Typed Data objects and Problem Type Reports, such
  as `SParams`, terminal matrices, loss tables, `DrivenReport`,
  `EigenmodeReport`, and `ElectrostaticReport`.
- Driven reports compose required `port-S.csv`, optional frequency-sample
  `domain-E.csv` and `surface-Q.csv` loss tables, index-map provenance, config
  material/interface provenance, and source bookkeeping.
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

- [../issues/palace-report-ownership](../issues/palace-report-ownership.md)
- [../issues/palace-config-ownership](../issues/palace-config-ownership.md)
- [../issues/cad-mesh-identity-provenance](../issues/cad-mesh-identity-provenance.md)
