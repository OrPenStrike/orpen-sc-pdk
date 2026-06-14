# Palace Config Ownership

**Repo:** `gsim`

Reusable Palace config generation should extend `gsim`. The PDK should export
public layer/material metadata and example component intent, but should not own
solver-specific runtime assembly.

Problem:

- private consumers already need automatic Palace config generation for driven,
  eigenmode, electrostatic, and magnetostatic workflows;
- `gsim` already has Palace simulation classes, problem models, material
  overlay evaluation, mesh generation, and config writing;
- duplicating this in the PDK would create two active public runtimes.

Proposed path:

- extend `gsim` config generation around role-aware mesh manifests,
  postprocessing requests, and public material overlays;
- keep `orpen-sc-pdk` exports limited to public PDK data and example component
  metadata;
- keep `gplugins` as a compatibility façade unless it delegates to `gsim`;
- validate with public driven, eigenmode, and electrostatic fixtures before
  using private layouts as local consumers.

Verified local changes:

- `gsim` commit `73c8d98`: high-level `write_config()` now persists terminal
  index-map rows for electrostatic configs, so generated capacitance terminal
  indices can be traced back to manifest physical names;
- public `orpen-sc-pdk` executable fixtures now validate Driven, Eigenmode, and
  Electrostatic mesh/config/artifact handoff through local editable `gsim`.

Remaining slices:

- extend `gsim` terminal selection beyond layer-level terminals for same-layer
  differential capacitors;
- convert executable fixtures into publication-safe notebooks or examples;
- add optional local Palace coarse-solve smoke checks when available.

Related features:

- {doc}`../features/palace-reporting`
- {doc}`../features/material-db-overlay`
- {doc}`../features/palace-config-generation`
- {doc}`../features/problem-type-notebook-suite`
