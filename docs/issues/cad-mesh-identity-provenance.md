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
- `orpen-sc-pdk` local test `tests/test_gsim_driven_cpw_workflow.py`: proves
  CPW port-surface manifest/index-map artifacts on a generated public driven
  mesh, including `P1`/`P2` port metadata and Palace Power `SurfaceFlux`
  indices;
- `orpen-sc-pdk` local test `tests/test_gsim_eigenmode_resonator_workflow.py`:
  proves the manifest/index-map artifacts on a generated public resonator
  eigenmode mesh instead of hand-built physical group dictionaries;
- `orpen-sc-pdk` local test
  `tests/test_gsim_electrostatic_capacitor_workflow.py`: proves electrostatic
  terminal index-map artifacts on a generated public same-layer Martinis
  differential ribbon capacitor mesh;
- validation for `cb052db`: manifest/workflow/curved-meshing tests passed,
  mesh integration tests passed, Ruff check/format passed, and targeted Pyright
  reported no errors.
- validation for `73c8d98`: manifest/workflow tests passed, Ruff
  check/format passed, and targeted Pyright reported no errors.
- validation for `bd0a2bc`: manifest/workflow tests passed, public
  driven/eigenmode/electrostatic fixtures passed, Ruff check/format passed, and
  targeted Pyright passed for the changed model/group surface.

Remaining implementation slices:

- decide whether to cliff-cut `gsim` interface labels from `__` to meshwell's
  `___` delimiter.

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
