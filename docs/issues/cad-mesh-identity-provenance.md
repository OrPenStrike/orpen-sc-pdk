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

Remaining implementation slices:

- decide whether to cliff-cut `gsim` interface labels from `__` to meshwell's
  `___` delimiter;
- wire postprocessing config and index-map artifact writing through the
  high-level `PalaceSimMixin.write_config()` workflow;
- add public problem-type fixtures that prove the manifest/index map with
  generated meshes instead of hand-built group dictionaries.

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
