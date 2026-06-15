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

Current public baseline:

- local `gsim` exposes `load_postprocessing_index_map()` and
  `load_indexed_csv()` as the first reusable report-loading surface;
- indexed Palace CSV columns can be annotated from `palace_index_map.json`
  without reading private mesh files or notebook-local physical-name maps;
- electrostatic terminal matrices can be loaded through `load_terminal_matrix()`
  with terminal labels resolved from `Boundaries.Terminal` index-map rows;
- electrostatic terminal matrix AMR histories can be summarized through
  `load_terminal_matrix_history()` and `summarize_terminal_matrix_history()`;
- indexed Palace EPR reports can be reshaped into summary frames through
  `load_domain_energy_summary()`, `load_surface_q_summary()`,
  `summarize_surface_q_by_interface()`, and `load_port_epr_summary()`;
- effective Palace domain material rows can be loaded through
  `load_domain_material_summary()` and joined from `config.json` material
  attributes to `palace_index_map.json` domain physical names;
- local `gsim` commit `61d7d66` adds generated
  `palace_material_resolution.json` sidecars and extends domain material
  summaries with stack material, matched material record, model source,
  validity, and resolution-frequency provenance;
- local `gsim` commit `1da6783` extends material-resolution provenance to
  dielectric interface rows, so Palace reports can explain which public
  material overlay entry supplied interface permittivity/loss fields;
- configured dielectric interface postprocessing rows can be loaded through
  `load_dielectric_interface_summary()` and joined from
  `Boundaries.Postprocessing.Dielectric` config rows to index-map physical
  names;
- composed Eigenmode reports expose those rows through
  `EigenmodeReport.domain_materials` and
  `EigenmodeReport.dielectric_interfaces`;
- local `gsim` commit `f12312c` adds `summarize_domain_loss()`,
  `summarize_surface_loss()`, and `summarize_loss_budget()`;
- composed Eigenmode reports now expose derived `domain_loss`,
  `surface_loss`, and `loss_budget` tables, using effective domain material
  loss tangent, Palace `Q_surf`, configured interface metadata, and mode
  frequency for gamma/T1 columns;
- local `gsim` commit `fbb19d1` adds `ElectrostaticReport` and
  `load_electrostatic_report()`, composing terminal capacitance matrices,
  terminal matrix pass summaries, optional indexed `domain-E.csv` and
  `surface-Q.csv` reports, config/material/interface provenance, and
  source bookkeeping;
- Electrostatic report loss budgets preserve Palace `i`/source samples and
  only derive gamma/T1 columns when callers pass an explicit `frequency_ghz`;
- local `gsim` commit `e8632bc` adds `DrivenReport` and
  `load_driven_report()`, composing required `port-S.csv`, optional
  `port-EPR.csv`, index-map provenance, config material/interface provenance,
  and source bookkeeping;
- `orpen-sc-pdk` public notebooks now demonstrate these report bundles with
  synthetic public Driven/Eigenmode/Electrostatic artifacts and curated display
  tables, keeping report parsing in `gsim` and notebook presentation downstream;
- `scripts/public_palace_smoke_evidence.py` can also load real opt-in local
  Palace outputs through the same `gsim` Driven/Eigenmode/Electrostatic report
  bundles when local solver execution is enabled, while its default dry-run
  evidence records generated artifact status through
  `gsim.palace.load_palace_run_summary()` and solver skip reasons; successful
  local solver runs also surface sanitized `gsim` runtime metadata through the
  same summary API;
- local `gsim` commit `f2dbe7f` lets reusable sweep summaries optionally add
  compact report-derived metrics from those same Driven/Eigenmode/Electrostatic
  loaders, so sweep rows can expose physics/report status without moving parser
  ownership into downstream PDK examples;
- `orpen-sc-pdk` remains a consumer that can generate public fixtures and
  examples, not the owner of Palace report parsing.

Related issues:

- {doc}`../issues/palace-report-ownership`
- {doc}`../issues/palace-config-ownership`
- {doc}`../issues/cad-mesh-identity-provenance`
