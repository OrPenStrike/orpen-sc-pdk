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
  parsed `SParams` output and a composed `DrivenReport` through local `gsim`.
- the public eigenmode resonator fixture now has an opt-in local Palace coarse
  solve that verifies generated Eigenmode config can produce non-empty
  `eig.csv` and `domain-E.csv` outputs through local `gsim`.
- `gsim` commit `20538ec` and the local `orpen-sc-pdk` material export helper
  establish the public material overlay schema bridge needed before config
  generation accepts PDK material overlays directly.
- `gsim` commit `49be250` adds `material_overlay=` to Palace config generation
  and high-level `write_config()`, with validation preserving the same overlay
  when it regenerates config files.
- public `orpen-sc-pdk` Driven, Eigenmode, and Electrostatic fixtures now pass
  `get_gsim_material_overlay()` into `gsim` config generation and verify that
  public `Si` material data reaches the generated Palace domain material block.
- `gsim` commit `0197b64` exposes the generated effective domain material rows
  through `load_domain_material_summary()`, so config material attributes can
  be joined back to generated domain physical names without PDK-owned report
  parsing.
- `gsim` commit `bbd74fe` exposes generated dielectric interface
  postprocessing rows through `load_dielectric_interface_summary()`, so
  configured interface thickness, permittivity, and loss-tangent values can be
  joined back to generated physical names.
- public `orpen-sc-pdk` material-overlay tests now verify that the generated
  `Si` substrate material row can be loaded back through this `gsim` API for
  Driven, Eigenmode, and Electrostatic artifacts.
- `gsim` commit `61d7d66` writes `palace_material_resolution.json` during
  material-overlay config generation and exposes the same provenance through
  `load_domain_material_summary()`, so generated config artifacts can explain
  which public PDK material source and validity status produced each Palace
  material row.
- `orpen-sc-pdk` now has a dev-only
  `scripts/public_palace_smoke_evidence.py` runner that leaves solver runtime
  and artifact-summary ownership in `gsim`, but records public Driven,
  Eigenmode, and Electrostatic mesh/config/index/material-resolution artifacts
  into an ignored JSON evidence bundle for local review through
  `gsim.palace.load_palace_run_summary()`.
- `gsim` commit `e5e89ef` adds that reusable
  `load_palace_run_summary()` API, including core handoff artifact status,
  result-file status, compact config summaries, mesh-manifest role counts,
  index-map section counts, material-resolution counts, and optional checksums.
- `gsim` commit `4bd1d20` extends successful local `run_local()` executions
  with `palace_run_metadata.json`, recording sanitized launcher information,
  process/thread resources, elapsed seconds, redacted command shape, and output
  file byte counts; the same `load_palace_run_summary()` API exposes the
  sidecar as `runtime`.
- `gsim` commit `00b2777` extends cloud result downloads and legacy
  `run_simulation()` with solver-specific runtime sidecars such as
  `palace_run_metadata.json`, preserving the same
  `load_palace_run_summary().runtime` surface for Palace local and cloud
  execution evidence.

Remaining slices:

- record richer dielectric interface provenance before promoting interface
  presets into public PDK material data;
- keep executable fixtures, publication-safe notebooks, and local evidence
  scripts aligned without moving solver orchestration into the PDK package;
- keep normal docs and CI paths independent from local Palace while exposing
  opt-in solver validation commands for local development.

Related features:

- {doc}`../features/palace-reporting`
- {doc}`../features/material-db-overlay`
- {doc}`../features/palace-config-generation`
- {doc}`../features/problem-type-notebook-suite`
