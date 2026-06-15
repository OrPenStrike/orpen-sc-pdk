# Public Problem-Type Notebook Coverage

**Repo:** `orpen-sc-pdk`, `gsim`

The public workflow needs one representative notebook or executable example for
each Palace problem type used by private consumers.

Problem:

- private notebooks currently act as workflow contracts for driven, eigenmode,
  and electrostatic simulations;
- those notebooks cannot be published as-is because they may include private
  layouts, saved outputs, run folders, or benchmark evidence;
- upstreamable `gsim` work needs public fixtures to prove each problem type.

Proposed path:

- build a driven CPW or resonator fixture with explicit excitation metadata;
- build an eigenmode resonator fixture that can run a coarse mesh smoke test;
- build an electrostatic capacitor fixture with named terminals and capacitance
  output;
- keep notebooks thin: component metadata, `gsim` call, coarse local Palace
  execution when available, and report loading.

Verified local changes:

- driven now has an executable public fixture in
  `tests/test_gsim_driven_cpw_workflow.py`: it builds the public
  `cpw_straight` cell, uses local `gsim` `DrivenSim` CPW port configuration,
  writes Driven `config.json`, persists `mesh_manifest.json`, persists
  `palace_index_map.json`, and verifies CPW port-surface Power `SurfaceFlux`
  indices map back to `P1`/`P2` port metadata; it also passes
  `get_gsim_material_overlay()` into `gsim` config generation and verifies the
  generated substrate material block uses the public `Si` permittivity and can
  be loaded back through `gsim.palace.load_domain_material_summary()`;
- the same driven fixture now includes an optional local Palace coarse-solve
  smoke test guarded by `ORPEN_RUN_LOCAL_PALACE_SMOKE=1`; it verifies that
  `run_local()` returns public `gsim.palace.SParams`, resolves `o1`/`o2` port
  labels, preserves a non-empty `port-S.csv` result file, and can reload the
  same public output directory through `gsim.palace.load_driven_report()`;
- eigenmode now has an executable public fixture in
  `tests/test_gsim_eigenmode_resonator_workflow.py`: it builds the public
  `resonator` cell, runs local `gsim` `EigenmodeSim` coarse meshing, writes
  Eigenmode `config.json`, persists `mesh_manifest.json`, persists
  `palace_index_map.json`, and verifies the absorbing boundary maps to a Palace
  Power `SurfaceFlux` postprocessing index; it also passes
  `get_gsim_material_overlay()` into `gsim` config generation and verifies the
  generated substrate material block uses the public `Si` permittivity and can
  be loaded back through `gsim.palace.load_domain_material_summary()`;
- the same eigenmode fixture now includes an optional local Palace coarse-solve
  smoke test guarded by `ORPEN_RUN_LOCAL_PALACE_SMOKE=1`; it verifies non-empty
  `eig.csv` and `domain-E.csv` outputs, then loads two positive eigenfrequency
  rows, source visibility, and domain-energy rows through public
  `gsim.palace.load_eigenmode_report()`;
- electrostatic now has an executable public fixture in
  `tests/test_gsim_electrostatic_capacitor_workflow.py`: it builds the public
  same-layer Martinis differential ribbon capacitor fixture, uses local `gsim`
  `ElectrostaticSim` center-selected terminal configuration, writes
  Electrostatic `config.json`, persists `mesh_manifest.json`, persists
  `palace_index_map.json`, and verifies the positive/negative terminal indices
  map back to separate `D0_TOP_M1` physical names; it also passes
  `get_gsim_material_overlay()` into `gsim` config generation and verifies the
  generated substrate material block uses the public `Si` permittivity and can
  be loaded back through `gsim.palace.load_domain_material_summary()`;
- the same electrostatic fixture now includes an optional local Palace
  coarse-solve smoke test guarded by `ORPEN_RUN_LOCAL_PALACE_SMOKE=1`; it can
  run through a local Palace wrapper or direct solver binary and verifies that
  public outputs include non-empty `terminal-C.csv`, `terminal-Cm.csv`, and
  `terminal-Cinv.csv`;
- the optional electrostatic smoke now loads `terminal-C.csv`,
  `terminal-Cm.csv`, and `terminal-Cinv.csv` through public
  `gsim.palace.load_terminal_matrix()` and verifies that terminal labels resolve
  to `positive`/`negative` through `palace_index_map.json`;
- the optional electrostatic smoke now also loads the same real solver
  matrices through public `gsim.palace.load_electrostatic_report()`, keeping the
  composed report path aligned with the primitive matrix loader;
- `notebooks/src/public_simulation_workflows.py` is a publication-safe Jupytext
  notebook source that runs public Driven, Eigenmode, and Electrostatic
  mesh/config/artifact handoffs and displays scrubbed summaries only;
- the public workflow notebook and fixtures intentionally do not add
  material-kind-driven MA/MS/SA interface postprocessing yet; generated public
  mesh fixtures now expose classifiable interface identities, and the public
  alias map covers generated `air`/`silicon` material names; the public PDK
  still has no source-backed default interface preset records or
  default-selection policy for automatic classification;
- the public resonator Eigenmode fixture now proves its real generated
  `air___silicon` interface can be classified with OrPen's public material-kind
  and alias helpers plus a caller-supplied test preset, then joined back through
  `gsim.palace.load_dielectric_interface_summary()`;
- the public simulation workflow notebook now displays that generated
  interface-classification path from a public resonator mesh/config artifact,
  using a notebook-local caller-supplied preset and reusable `gsim` provenance
  loading rather than private notebook parsing or automatic public defaults;
- the public notebook index now links
  `notebooks/public_simulation_workflows` directly as a publication-safe
  Driven/Eigenmode/Electrostatic workflow notebook instead of leaving the
  resonator workflow slot marked private-source pending;
- the public simulation workflow notebook now also writes synthetic public
  Driven, Eigenmode, and Electrostatic report artifacts, loads them through
  reusable `gsim` report bundles, and displays curated S-parameter, port-EPR,
  domain-loss, surface-loss, and loss-budget tables through a notebook-local
  presentation helper;
- the same public simulation workflow notebook now exposes an opt-in local
  Palace smoke cell for Driven, Eigenmode, and Electrostatic public fixtures;
  the default docs path reports a skip reason, while local users can enable the
  coarse solves with `ORPEN_RUN_LOCAL_PALACE_SMOKE=1` plus `PALACE_SIF` or
  `PALACE_EXECUTABLE`;
- `scripts/public_palace_smoke_evidence.py` now regenerates all three public
  problem fixtures under `build/public-palace-smoke-evidence/` and writes
  `public_palace_smoke_evidence.json`; the default dry-run path consumes
  `gsim.palace.load_palace_run_summary()` and records non-empty `palace.msh`,
  `config.json`, `mesh_manifest.json`, `palace_index_map.json`, and
  `palace_material_resolution.json` artifacts for Driven, Eigenmode, and
  Electrostatic fixtures without requiring Palace;
- `gsim` commit `652fcec` adds
  `gsim.palace.load_palace_sweep_summary()`, and the public evidence runner now
  writes `points.json` for the three problem fixtures and records a
  `sweep_summary` built from that reusable API;
- `gsim` commit `f5eb728` extends that reusable sweep summary with
  `point_records`/`to_point_records()`/`to_dataframe()`, and the public evidence
  test now verifies table-ready rows for the three public Driven, Eigenmode, and
  Electrostatic fixtures, including point parameters, artifact counts, runtime
  sidecar status, and compact config/mesh/index/material-resolution counts;
- when the same script is run with `ORPEN_RUN_LOCAL_PALACE_SMOKE=1` plus a
  local Palace SIF or executable, the JSON evidence keeps the same `gsim`
  run-summary bundle and switches from solver skip rows to parsed `gsim`
  Driven/Eigenmode/Electrostatic report summaries; successful local solver
  execution also exposes the sanitized `palace_run_metadata.json` sidecar
  through the same run-summary bundle;
- validation passed with
  `uv run --group ecosystem-dev python -m pytest tests/test_gsim_driven_cpw_workflow.py tests/test_gsim_eigenmode_resonator_workflow.py tests/test_gsim_electrostatic_capacitor_workflow.py -q`;
- optional local Palace validation passed with
  `ORPEN_RUN_LOCAL_PALACE_SMOKE=1 PALACE_EXECUTABLE=/path/to/palace PALACE_EXECUTABLE_MODE=binary uv run --group ecosystem-dev python -m pytest tests/test_gsim_electrostatic_capacitor_workflow.py -q`;
- optional local Driven Palace validation passed with
  `ORPEN_RUN_LOCAL_PALACE_SMOKE=1 PALACE_EXECUTABLE=/path/to/palace PALACE_EXECUTABLE_MODE=binary uv run --group ecosystem-dev python -m pytest tests/test_gsim_driven_cpw_workflow.py -q`;
- optional local Eigenmode Palace validation passed with
  `ORPEN_RUN_LOCAL_PALACE_SMOKE=1 PALACE_EXECUTABLE=/path/to/palace PALACE_EXECUTABLE_MODE=binary uv run --group ecosystem-dev python -m pytest tests/test_gsim_eigenmode_resonator_workflow.py -q`;
- the same optional Eigenmode validation now exercises
  `gsim.palace.load_eigenmode_report()` against real local solver output;
- public synthetic Electrostatic report validation now exercises
  `gsim.palace.load_electrostatic_report()` with terminal matrices,
  domain/surface EPR reports, config/material/interface provenance, separated
  source-index budgets, and explicit-frequency T1 derivation;
- public synthetic Driven report validation now exercises
  `gsim.palace.load_driven_report()` with S-parameters, port-EPR rows,
  config/material provenance, index-map provenance, and source bookkeeping;
- direct macOS development binaries may also require local dynamic-library
  loader variables such as `DYLD_LIBRARY_PATH`; keep those machine-specific
  paths outside public docs and CI defaults;
- Ruff check and format-check passed for all three executable fixtures.
- direct notebook-source execution passed and confirmed the default local
  Palace smoke cell skip path without requiring a local solver.
- `just docs` converts and executes the public simulation workflow notebook as
  part of the docs build.

Remaining slices:

- wire material-kind interface classification into public workflow examples
  only after source-backed public interface preset records and default-selection
  policy exist;
- add a public Magnetostatic fixture only after a public use case is selected;
  current public notebook coverage intentionally proves the private consumer
  problem types that have active Driven/Eigenmode/Electrostatic notebooks;
- keep full sweep orchestration and richer sweep-level physics/performance
  aggregation as later `gsim` workflow slices; this issue now only proves
  explicit point-table artifact, runtime, and provenance records over the public
  problem fixtures;
- keep native masked Surface EPR in the Palace-source/upstream `gsim` lane
  instead of replaying it inside `orpen-sc-pdk`;
- future extensions should stay public-fixture based and keep normal docs
  builds independent of local Palace.
- keep the generated evidence bundle ignored under `build/`; it is local
  review evidence, not a committed public artifact.

Acceptance checks:

- notebooks import `orpen_sc_pdk` and `gsim`, not private layout modules;
- notebooks can run with public fixtures and no private paths;
- saved outputs are scrubbed or synthetic unless cleared for publication;
- tests verify notebook execution or equivalent scripts for all three problem
  types.

Related features:

- {doc}`../features/palace-reporting`
- {doc}`../features/palace-config-generation`
- {doc}`../features/problem-type-notebook-suite`
