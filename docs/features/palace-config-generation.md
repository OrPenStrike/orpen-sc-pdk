# Palace Config Generation

**Target:** `gsim` with `orpen-sc-pdk` metadata

**Status:** prototype

Automatic Palace configuration generation should live in `gsim`. The PDK
should provide public layer names, material aliases, and example component
metadata; it should not own a separate solver runtime.

Local/implemented capability:

- component metadata can express mesh ports, terminals, lumped ports, wave
  ports, current excitations, and Q2D conductor intent;
- runtime controls can assemble driven, eigenmode, electrostatic, and
  magnetostatic Palace problem definitions;
- material policy can be resolved before writing solver domain materials;
- physical-group tables can be lowered into Palace attributes, boundaries,
  terminals, lumped ports, and postprocessing requests;
- generated run packages can be validated before invoking Palace.

GDSFactory ecosystem mapping:

- `orpen-sc-pdk` owns public PDK layer/material identifiers and public example
  cells that mount simulation intent;
- `gsim` owns the reusable Palace problem models, config writer, material
  overlay evaluation, local/cloud runner integration, and validation helpers;
- `meshwell` supplies mesh/CAD identity that `gsim` consumes through an explicit
  role manifest;
- `gplugins` may expose compatibility wrappers, but should not become the core
  Palace runtime.

Acceptance direction:

- a public `gsim` API can write Palace configs for driven, eigenmode, and
  electrostatic examples using only public PDK metadata;
- generated configs include auditable material, boundary, terminal, and
  postprocessing provenance;
- public PDK material overlays can be passed to `gsim` config generation and
  produce effective `Domains.Materials` values without mutating the source
  layer stack;
- generated material-resolution sidecars can record which stack material,
  matched public material record, model source, validity status, and frequency
  produced each Palace material attribute;
- public evidence can reload generated configs and material sidecars through
  `gsim` report helpers, proving the config writer emitted the expected solver
  block, boundary/postprocessing counts, domain material rows, and material
  provenance for each problem type;
- private consumers can mount their own layouts without changing the public
  config generation contract;
- Palace remains an external executable, not a Python package dependency of the
  PDK.

Related issue:

- {doc}`../issues/palace-config-ownership`
