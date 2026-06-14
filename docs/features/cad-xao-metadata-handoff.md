# CAD/XAO Metadata Handoff

**Target:** `meshwell` and `gsim`

**Status:** prototype

Simulation reports need a stable identity chain from public PDK layer semantics
to CAD/XAO entities, mesh physical groups, Palace attributes, and
postprocessing indices.

Local/implemented capability:

- CAD and mesh stages can preserve physical names for volumes, conductor
  surfaces, ports, exterior boundaries, and interfaces;
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
- `gsim.palace.mesh` exposes a `PostprocessingIndexMap` that can resolve Palace
  postprocessing section/index values back to physical names and attributes;
- both the mesh manifest and Palace index map can be written as JSON artifacts.

Acceptance direction:

- every Palace-relevant mesh physical group has a stable public role, name,
  entity-tag list, and metadata dictionary;
- index maps can answer `Palace index -> physical group name -> PDK layer or
  material role`;
- surface-Q and EPR reports can use the same index map as Palace config
  generation;
- the implementation builds on meshwell physical-name and interface-tag
  conventions rather than copying private CAD/XAO code.

Related issue:

- {doc}`../issues/cad-mesh-identity-provenance`
