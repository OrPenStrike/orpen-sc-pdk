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
  and `domain-E.csv` outputs for a public resonator;
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
  Palace solve, including positive eigenfrequency rows from `eig.csv`.

Remaining implementation slices:

- expose these opt-in solver smokes in publication-safe notebook/example form
  without making normal docs builds depend on local Palace;
- extend report summaries toward material-loss/T1/gamma only after the public
  ownership split between `gsim` result schemas and PDK material overlays is
  explicit.

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
