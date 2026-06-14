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
- `gsim` commit `bd0a2bc`: same-layer planar conductor islands can now be
  selected by electrostatic terminal center points, preserving the layer-level
  terminal fallback when no center is provided;
- `gsim` commit `a584079`: `run_local()` can execute either the Palace wrapper
  command or a direct solver binary, so local coarse smokes can use packaged
  wrappers, Apptainer SIFs, or local development binaries without changing PDK
  fixtures;
- public `orpen-sc-pdk` executable fixtures now validate Driven, Eigenmode, and
  Electrostatic mesh/config/artifact handoff through local editable `gsim`.
- the public electrostatic fixture now has an opt-in local Palace coarse solve
  that verifies non-empty terminal capacitance outputs.
- the public driven CPW fixture now has an opt-in local Palace coarse solve that
  verifies generated Driven config and CPW lumped-port metadata can produce
  parsed `SParams` output through local `gsim`.
- the public eigenmode resonator fixture now has an opt-in local Palace coarse
  solve that verifies generated Eigenmode config can produce non-empty
  `eig.csv` and `domain-E.csv` outputs through local `gsim`.

Remaining slices:

- convert executable fixtures into publication-safe notebooks or examples;
- keep normal docs and CI paths independent from local Palace while exposing
  opt-in solver validation commands for local development.

Related features:

- {doc}`../features/palace-reporting`
- {doc}`../features/material-db-overlay`
- {doc}`../features/palace-config-generation`
- {doc}`../features/problem-type-notebook-suite`
