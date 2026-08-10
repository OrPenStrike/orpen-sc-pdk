# CAD/XAO Metadata Handoff

**Target:** `meshwell` and `gsim`

**Status:** prototype

Simulation reports need a stable identity chain from public PDK layer semantics
to CAD/XAO entities, mesh physical groups, Palace attributes, and
postprocessing indices.

Local/implemented capability:

- CAD and mesh stages can preserve physical names for volumes, conductor
  surfaces, ports, exterior boundaries, and interfaces;
- generated interface and exterior names can follow meshwell-style `___` and
  `___None` delimiters while older `gsim` artifacts remain parseable;
- physical-group tables can map names to entity tags and solver attributes;
- surface registries can map postprocessing rows back to surface roles and
  material/layer semantics;
- run manifests can keep solver indices separate from private run evidence.

GDSFactory ecosystem mapping:

- `meshwell` owns solver-agnostic physical names, interface naming, XAO/CAD
  export, thin-film geometry semantics, and backend equivalence tests;
- `gsim` owns Palace-specific role manifests, index maps, postprocessing
  requests, and reporting lookups;
- `orpen-sc-pdk` owns public layer/material labels that appear in reports;
- private consumers may add layout-specific names, but those names must not be
  required by the public contract.

Current prototype baseline:

- `gsim.palace.mesh` exposes a `MeshManifest` built from mesh physical groups;
- manifest entries preserve role, physical names, entity tags, inferred
  dimension, source, and parsed interface/exterior identity;
- `gsim.palace.resolve.loaders.index_maps.load_postprocessing_index_map()`
  reloads
  `palace_index_map.json` into the reusable
  `gsim.palace.mesh.postprocessing.PostprocessingIndexMap` schema, which can
  resolve Palace postprocessing section/index values back to physical names and
  attributes;
- both the mesh manifest and Palace index map can be written as JSON artifacts;
- public OrPen evidence fixtures now reload `palace_index_map.json` through
  `gsim.palace.resolve.loaders.index_maps.load_postprocessing_index_map()` and
  display forward
  `section/index -> physical name`, reverse `physical name -> indices`, and
  attribute lookup rows for Driven, Eigenmode, and Electrostatic workflows.
- `public_cad_mesh_identity_handoff_evidence.json` records the same
  publication-safe CAD/mesh identity audit for the Driven, Eigenmode, and
  Electrostatic fixtures: manifest role coverage, generated interface physical
  names, index-map sections, port metadata, terminal metadata, and config
  material joins. This is OrPen consumer evidence; meshwell still owns the
  physical-name/interface-tag grammar and backend equivalence contract.
- `public_meshwell_handoff_contract_gate_evidence.json` now records the
  upstream handoff gate separately from OrPen consumer evidence: local meshwell
  source/tests expose `___` interface names, `___None` exterior names, multiple
  physical-name equivalence, interface/exterior refinement behavior, formal
  physical-name contract text, and backend equivalence across CAD/XAO routes,
  while local `gsim` manifest, index-map, result-loader, integration tests, and
  a meshwell-generated MSH consumer fixture consume those names as
  interface/exterior rows.
- generated public example meshes now prove domain, conductor, port, terminal,
  absorbing-boundary, refinement, and non-exterior interface identities through
  the same manifest path; interface-loss classification remains a separate
  material/preset policy step.

Acceptance direction:

- every Palace-relevant mesh physical group has a stable public role, name,
  entity-tag list, and metadata dictionary;
- index maps can answer `Palace index -> physical group name -> PDK layer or
  material role`;
- surface-Q and EPR reports can use the same index map as Palace config
  generation;
- material-kind interface classification consumes generated manifest interface
  identities when the caller supplies public material-kind aliases and
  source-backed presets; the current public alias map covers generated
  `air`/`silicon` names, while preset defaults remain a later PDK contract;
- the implementation builds on meshwell physical-name and interface-tag
  conventions rather than copying private CAD/XAO code.

Related issue:

- [../issues/cad-mesh-identity-provenance](../issues/cad-mesh-identity-provenance.md)
