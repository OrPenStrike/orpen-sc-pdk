# Surface-Q Index Mapping

**Target:** `gsim` with `orpen-sc-pdk` metadata

**Status:** candidate

Surface-Q and participation reports need stable mapping from solver surfaces
back to PDK layer semantics.

The PDK should expose public layer/material naming. `gsim` should own the
solver-side mapping and report generation logic.

Required mapping chain:

- public PDK layer/material role;
- meshwell CAD/XAO physical name and interface identity;
- gsim mesh role manifest entry;
- Palace attribute or postprocessing index;
- report row for participation, loss, or surface-Q.

Acceptance direction:

- index maps are generated from solver-side manifests rather than ad hoc report
  parsing;
- the same map supports config generation, EPR reporting, and surface-Q
  reporting;
- private consumers can add layout-specific labels without changing public role
  names.

Related issue:

- {doc}`../issues/cad-mesh-identity-provenance`
