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

Related features:

- {doc}`../features/palace-reporting`
- {doc}`../features/material-db-overlay`
- {doc}`../features/palace-config-generation`
- {doc}`../features/problem-type-notebook-suite`
