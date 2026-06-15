# CAD/Mesh Identity Provenance

**Repo:** `meshwell`, `gsim`

Physical names, interface identities, mesh roles, Palace attributes, and
postprocessing indices need one public handoff contract.

Problem:

- report rows and Palace postprocessing outputs are only useful when they map
  back to public PDK layer/material semantics;
- private consumers already rely on physical-name and index provenance across
  CAD, mesh, config generation, and analysis;
- copying private CAD/XAO helpers into public repos would bypass meshwell's
  existing naming and backend model.

Proposed path:

- keep CAD/XAO naming, interface identity, thin-film semantics, and backend
  equivalence in `meshwell`;
- expose a Palace role manifest and index map in `gsim`;
- make config generation and reports consume the same manifest;
- keep `orpen-sc-pdk` responsible only for public layer/material labels that
  appear in those maps.

Local prototype status:

- first `gsim` slice is implemented on the local Palace postprocessing roles
  branch: role-aware mesh manifest, Palace postprocessing index map, JSON
  artifact writers, and config merge points;
- tests cover role classification, physical-name provenance, interface/exterior
  parsing for both current `gsim` and meshwell-style delimiters, config
  postprocessing merges, index-map lookup, and JSON serialization.
- second `gsim` slice wires the typed postprocessing config through
  `PalaceSimMixin.write_config()`: high-level simulations can merge Palace
  domain/boundary postprocessing fragments into `config.json`, persist
  `mesh_manifest.json`, persist `palace_index_map.json`, and reuse the last
  explicit postprocessing config when upload/run code regenerates the config.
- third `gsim` CAD identity slice cliff-cuts generated interface and exterior
  physical names to meshwell-style `___` and `___None` labels while preserving
  legacy parser support for older generated meshes.
- fourth `gsim` results slice lets Palace indexed CSV loaders consume
  `palace_index_map.json` so report columns can be annotated without re-reading
  private mesh physical-name helpers.
- fifth `gsim` results slice lets electrostatic terminal matrix loaders consume
  `Boundaries.Terminal` rows from `palace_index_map.json`.
- sixth `gsim` results slice builds electrostatic terminal matrix history and
  convergence summaries on top of the same indexed terminal labels.
- seventh `gsim` results slice builds indexed domain-energy, surface-Q, and
  port-EPR summary frames on top of the same `palace_index_map.json` artifact.
- eighth `gsim` results slice composes Eigenmode final modes, AMR history,
  pass summaries, optional EPR report tables, index-map provenance, and source
  bookkeeping into one public report bundle.
- ninth `gsim` results slice loads configured dielectric interface
  postprocessing rows from `config.json` and joins them to the same
  `palace_index_map.json` physical-name provenance used by surface-Q reports.
- tenth `gsim` results slice derives domain/surface loss budgets from the
  same report, material, interface, and index-map artifacts without introducing
  PDK-owned report parsing.
- eleventh `gsim` config/results slice writes
  `palace_material_resolution.json` and joins it into domain material reports,
  so material attributes can be traced to stack material names, matched public
  material records, model sources, validity status, and resolution frequency.
- `gsim` commit `21f84a2` preserves generated non-exterior interface physical
  groups in the role manifest, so public mesh artifacts can expose
  classifiable `interface_of` rows such as `air___silicon` instead of limiting
  manifests to domain, conductor, port, terminal, absorbing-boundary, and
  refinement identities.
- current OrPen local evidence/notebook slice reloads generated
  `palace_index_map.json` artifacts through
  `gsim.palace.load_postprocessing_index_map()` and records forward
  `section/index -> physical name`, reverse `physical name -> indices`, and
  attribute-to-entry lookup rows for the public Driven, Eigenmode, and
  Electrostatic fixtures.
- current OrPen local evidence/notebook slice also writes
  `public_cad_mesh_identity_handoff_evidence.json`, a consumer-side audit of
  the generated Driven, Eigenmode, and Electrostatic `mesh_manifest.json`,
  `palace_index_map.json`, and `config.json` artifacts. The audit records
  manifest role coverage, physical-name coverage, generated interface names,
  index-map sections, port metadata, terminal metadata, and config material
  joins while keeping physical-name grammar and backend equivalence in
  `meshwell`.
- current OrPen local evidence/notebook slice also writes
  `public_meshwell_handoff_contract_gate_evidence.json`, a source-alignment and
  consumer-fixture gate for the upstream contract: meshwell `cad_gmsh`, `mesh`,
  and XAO writer source, formal meshwell physical-name contract text, meshwell
  multiple-physical-name/interface/exterior and backend equivalence tests,
  `gsim` manifest/index-map consumer code/tests, and a meshwell-generated MSH
  fixture all expose meshwell-style `___` and `___None` names.

Verified local changes:

- `gsim` commit `2ab16d7`: added role-aware mesh manifest, Palace
  postprocessing index map, config merge points, and unit coverage;
- `gsim` commit `cb052db`: added high-level `write_config(postprocessing=...)`
  wiring and artifact persistence;
- `gsim` commit `73c8d98`: writes `Boundaries.Terminal` rows into
  `palace_index_map.json` for electrostatic configs, linking terminal indices
  to manifest physical names;
- `gsim` commit `bd0a2bc`: splits same-layer planar PEC islands into separate
  physical groups and lets electrostatic terminals select one island by XY
  center while preserving layer-level terminal selection when no center is
  provided;
- `gsim` commit `3541ace`: generated interface and exterior physical names now
  use meshwell-style `___` and `___None` delimiters; mesh manifest and group
  consumers still parse legacy `__` labels for old artifacts;
- `gsim` commit `21f84a2`: generated non-exterior interface physical groups
  are now preserved as `boundary_surface` manifest entries with physical name,
  entity-tag, and `interface_of` provenance, while exterior groups still feed
  the absorbing boundary behavior;
- `gsim` commit `5caa2db`: adds public result loaders that read
  `palace_index_map.json` and annotate indexed Palace CSV columns such as
  `domain-E.csv` and `surface-Q.csv` with physical-name provenance;
- `gsim` commit `38787ff`: adds public electrostatic terminal matrix loaders
  for `terminal-C.csv`, `terminal-Cm.csv`, and `terminal-Cinv.csv`, with row and
  column labels resolved from `Boundaries.Terminal` index-map rows;
- `gsim` commit `3c0dad9`: adds public terminal matrix AMR history and summary
  helpers that reuse the indexed terminal labels and emit convergence deltas;
- `gsim` commit `76b383a`: adds public indexed EPR report summary helpers for
  `domain-E.csv`, `surface-Q.csv`, and `port-EPR.csv`, including surface
  interface totals and port participation fractions;
- `gsim` commit `a584079`: adds a direct-binary mode for local Palace execution
  so development builds can run the same public fixtures without wrapper-only
  launcher assumptions;
- `gsim` commit `ca471b4`: adds the public root
  `load_eigenmode_report()` entrypoint and the
  `gsim.palace.results.EigenmodeReport` return model, so notebooks can load
  final modal rows, AMR history, pass summaries, indexed EPR tables, index-map
  rows, and source bookkeeping through one public loader while keeping the
  report bundle class in the result owner module;
- `gsim` commit `bbd74fe`: adds
  `load_dielectric_interface_summary()` and
  `EigenmodeReport.dielectric_interfaces`, proving configured dielectric
  interface rows can use the same index-map physical-name provenance;
- `gsim` commit `f12312c`: adds
  `gsim.palace.results.summarize_domain_loss()`,
  `gsim.palace.results.summarize_surface_loss()`, and
  `gsim.palace.results.summarize_loss_budget()`, proving derived loss rows
  reuse the same domain and interface physical-name provenance;
- `gsim` commit `61d7d66`: adds generated material-resolution sidecars and
  domain material provenance columns, proving the material/attribute side of
  the config/report chain can be audited without embedding non-Palace keys in
  `config.json`;
- `orpen-sc-pdk` local test `tests/test_gsim_driven_cpw_workflow.py`: proves
  CPW port-surface manifest/index-map artifacts on a generated public driven
  mesh, including `P1`/`P2` port metadata and Palace Power `SurfaceFlux`
  indices;
- the same driven fixture now has an opt-in local Palace coarse-solve smoke
  path that confirms the generated mesh/config can produce a non-empty
  `port-S.csv` and parse it back through public `gsim.palace.SParams` with
  `o1`/`o2` port labels;
- `orpen-sc-pdk` local test `tests/test_gsim_eigenmode_resonator_workflow.py`:
  proves the manifest/index-map artifacts on a generated public resonator
  eigenmode mesh instead of hand-built physical group dictionaries;
- the same eigenmode fixture now has an opt-in local Palace coarse-solve smoke
  path that confirms the generated mesh/config can produce non-empty `eig.csv`
  and `domain-E.csv` outputs for a public resonator and load them through public
  `gsim.palace.load_eigenmode_report()`;
- `orpen-sc-pdk` local test
  `tests/test_gsim_electrostatic_capacitor_workflow.py`: proves electrostatic
  terminal index-map artifacts on a generated public same-layer Martinis
  differential ribbon capacitor mesh;
- the same electrostatic fixture now has an opt-in local Palace coarse-solve
  smoke path that confirms the generated mesh/config can produce non-empty
  terminal capacitance matrices through public `gsim` execution;
- the optional Electrostatic smoke also reloads those matrices through
  `gsim.palace.load_terminal_matrix()`, proving the solver indices map back to
  `positive`/`negative` terminal names from the generated index map;
- the public evidence runner and notebook now also load the generated index map
  as a `gsim` `PostprocessingIndexMap`, proving reusable helper calls can resolve
  forward Palace indices, reverse physical-name lookups, and attribute ownership
  for public Driven, Eigenmode, and Electrostatic fixture outputs;
- validation for `cb052db`: manifest/workflow/curved-meshing tests passed,
  mesh integration tests passed, Ruff check/format passed, and targeted Pyright
  reported no errors.
- validation for `73c8d98`: manifest/workflow tests passed, Ruff
  check/format passed, and targeted Pyright reported no errors.
- validation for `bd0a2bc`: manifest/workflow tests passed, public
  driven/eigenmode/electrostatic fixtures passed, Ruff check/format passed, and
  targeted Pyright passed for the changed model/group surface.
- validation for `3541ace`: mesh manifest, integration, workflow, and
  curved-meshing tests passed; public driven/eigenmode/electrostatic fixtures
  passed through editable `gsim`; Ruff check/format passed; targeted Pyright
  passed for the changed mesh/group parsing surface.
- validation for `5caa2db`: `gsim` result, manifest, and workflow tests
  passed; public driven/eigenmode/electrostatic fixtures passed through
  editable `gsim`; Ruff check/format passed; targeted Pyright passed for the
  changed results public surface.
- validation for `38787ff`: `gsim` result, manifest, and workflow tests
  passed; public driven/eigenmode/electrostatic fixtures passed through
  editable `gsim`; Ruff check/format passed; targeted Pyright passed for the
  changed results public surface.
- validation for `3c0dad9`: `gsim` result, manifest, and workflow tests passed;
  public driven/eigenmode/electrostatic fixtures passed through editable
  `gsim`; Ruff check/format passed; targeted Pyright passed for the changed
  results public surface.
- validation for `76b383a`: `gsim` result, manifest, and workflow tests passed;
  Ruff check/format passed; targeted Pyright passed for the changed results
  public surface.
- validation for `a584079`: `gsim` result, manifest, and workflow tests passed;
  Ruff check/format passed; targeted Pyright passed for the changed local
  execution surface; the public electrostatic fixture passed an opt-in local
  Palace coarse solve against a direct development binary.
- validation after the report-loader smoke extension: the public electrostatic
  fixture passed both the default skip path and the opt-in local Palace solve,
  including terminal matrix loading through `palace_index_map.json`.
- validation after the Driven smoke extension: the public driven CPW fixture
  passed both the default skip path and the opt-in local Palace solve,
  including S-parameter parsing through `gsim.palace.SParams`.
- validation after the Eigenmode smoke extension: the public resonator
  eigenmode fixture passed both the default skip path and the opt-in local
  Palace solve, including positive eigenfrequency rows and final-source
  visibility from the public Eigenmode loader.
- validation after the direct-binary local replay: Driven, Eigenmode, and
  Electrostatic public fixtures all passed opt-in local Palace coarse solves
  against `palace-arm64.bin` with corrected dynamic-library loader paths,
  proving the generated mesh manifest, index map, and config artifacts can feed
  real solver output without copying private CAD/XAO helpers.
- validation after the Eigenmode report bundle slice: `gsim` result, manifest,
  and workflow tests passed; Ruff check/format passed; targeted Pyright passed
  for the changed results public surface.
- validation after the effective material summary slice: generated
  `Domains.Materials` rows can be joined from `config.json` attributes to
  domain physical names through `gsim.palace.load_domain_material_summary()`
  and `palace_index_map.json`.
- validation after the dielectric interface summary slice: generated
  `Boundaries.Postprocessing.Dielectric` rows can be joined from `config.json`
  to interface physical names through
  `gsim.palace.load_dielectric_interface_summary()` and
  `palace_index_map.json`.
- validation after the loss-budget slice: domain/surface loss rows and
  per-mode loss budgets can be derived from public synthetic Palace artifacts
  through `gsim.palace.load_eigenmode_report()`.
- validation after the material-resolution provenance slice: generated public
  Palace configs write `palace_material_resolution.json`, and
  `gsim.palace.load_domain_material_summary()` can join public PDK material
  source and validity metadata back to Palace material attributes.
- validation after the Electrostatic report slice: public synthetic
  Electrostatic artifacts preserve terminal, domain, surface, material, and
  interface provenance through `gsim.palace.load_electrostatic_report()`, and
  source-indexed loss budgets remain separated instead of being collapsed into
  one mode-like row.
- validation after the dielectric-interface material provenance slice:
  `gsim.palace` resolves interface material references through public material
  overlays, strips transient handoff keys from Palace `config.json`, records
  interface material source/validity/frequency in
  `palace_material_resolution.json`, and loads that provenance back through
  `load_dielectric_interface_summary()`.
- validation after the public notebook smoke-exposure slice: the public
  simulation workflow notebook reuses the same Driven, Eigenmode, and
  Electrostatic fixture builders for mesh/config summaries and opt-in local
  Palace smoke execution, while normal docs builds display a skip reason
  instead of invoking a local solver.
- validation after the generated-interface classification slice: the public
  resonator Eigenmode fixture now uses its real generated
  `mesh_manifest.json` interface row, OrPen's public material-kind map,
  OrPen's generated-name alias map, and a caller-supplied public test preset
  to emit a configured `SA` dielectric interface row and load the joined
  material provenance through `gsim.palace.load_dielectric_interface_summary()`.
- validation after the notebook exposure slice:
  `notebooks/src/public_eigenmode_workflow.py` displays the same generated
  resonator interface-classification path with a caller-supplied preset, so the
  docs-visible workflow now shows generated physical names, Palace config
  generation, index-map joining, and material provenance without adopting
  automatic public defaults.
- validation after the CAD/mesh identity audit slice: the public inventory
  notebook displays `public_cad_mesh_identity_handoff_table()`, and the smoke
  evidence bundle embeds a Driven/Eigenmode/Electrostatic-only audit proving
  manifest role/physical-name coverage, generated `air___silicon` interface
  identity, index-map forward/reverse/attribute lookups, Driven port metadata,
  Electrostatic terminal metadata, and config material joins through public
  `gsim` artifacts.
- validation after the meshwell handoff contract-gate slice: the public
  inventory notebook displays `public_meshwell_handoff_contract_gate_table()`,
  and the smoke evidence bundle embeds source-alignment rows for meshwell
  `cad_gmsh` naming docs, delimiter defaults, XAO writer source,
  multiple-physical-name equivalence tests, interface/exterior refinement
  tests, formal meshwell physical-name contract text, meshwell
  backend-equivalence tests, `gsim` manifest/index-map consumer coverage, and a
  `gsim` consumer fixture backed by a meshwell-generated MSH artifact.

Remaining implementation slices:

- wire generated mesh interface classification into public workflows only
  after source-backed public interface presets and default-selection rules are
  accepted; the public alias map already lets `air`/`silicon`-style `gsim`
  volume names classify through public `vacuum`/`Si` material records without
  private lookup tables, and the real generated resonator manifest is now
  tested with caller-supplied presets;
- add richer dielectric-interface provenance and source-backed preset
  validation before making MA/MS/SA defaults part of public PDK material data;
- keep the committed `gsim` meshwell-generated MSH handoff fixture as the
  current cross-repo consumer gate, and regenerate or extend it only if the
  upstream meshwell physical-name contract expands.

Acceptance checks:

- every Palace-relevant physical group has a stable role, name, entity tags,
  and metadata;
- generated index maps support config generation, EPR, surface-Q, and reporting;
- tests cover interface/exterior names, multi-physical-name entities, ports,
  conductors, dielectrics, and boundaries using public fixtures.

Related features:

- {doc}`../features/surface-q-index-mapping`
- {doc}`../features/palace-config-generation`
- {doc}`../features/cad-xao-metadata-handoff`
