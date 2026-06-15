# Public Problem-Type Notebook Coverage

**Repo:** `orpen-sc-pdk`, `gsim`

The public workflow needs one representative notebook or executable example for
each Palace problem type used by private consumers.

Problem:

- private notebooks and helpers currently act as workflow contracts for driven,
  eigenmode, electrostatic, and magnetostatic simulations;
- those notebooks cannot be published as-is because they may include private
  layouts, saved outputs, run folders, or benchmark evidence;
- upstreamable `gsim` work needs public fixtures to prove each problem type.

Proposed path:

- build a driven CPW or resonator fixture with explicit excitation metadata;
- build an eigenmode resonator fixture that can run a coarse mesh smoke test;
- build an electrostatic capacitor fixture with named terminals and capacitance
  output;
- build a magnetostatic CPW fixture with named current sources and generated
  config/index-map evidence while report parsing remains pending;
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
  notebook source that runs public Driven, Eigenmode, Electrostatic, and
  Magnetostatic mesh/config/artifact handoffs and displays scrubbed summaries
  only;
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
  Driven/Eigenmode/Electrostatic/Magnetostatic workflow notebook instead of
  leaving the resonator workflow slot marked private-source pending;
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
- `gsim` commit `c72f0d3` adds first-class Magnetostatic config-surface support:
  public `MagnetostaticSim`, center-selected `CurrentSourceConfig` sources,
  `Problem.Type == "Magnetostatic"`, `Solver.Magnetostatic`,
  `Boundaries.SurfaceCurrent`, `Boundaries.PMC`, magnetic `SurfaceFlux`, and
  source-name rows in `palace_index_map.json`;
- `gsim` commit `883fb78` extends the same Magnetostatic source surface with
  vector `Direction`, optional `CoordinateSystem`, and selector-based
  multielement `SurfaceCurrent.Elements`; the public fixture uses a vector
  `signal` source and a multielement `return` source so the notebook and JSON
  evidence can review generated element-count, direction, and coordinate-system
  lookup rows without owning Palace attribute mapping in OrPen;
- the public simulation workflow notebook now displays a Magnetostatic CPW
  config fixture with vector-direction `signal` and multielement `return`
  current sources, generated `SurfaceCurrent`/magnetic `SurfaceFlux` rows,
  `PMC` attributes, domain material provenance, and source-name/index-map
  lookup rows;
- `scripts/public_palace_smoke_evidence.py` now regenerates four public
  problem fixtures under `build/public-palace-smoke-evidence/` and writes
  `public_palace_smoke_evidence.json`; the default dry-run path consumes
  `gsim.palace.load_palace_run_summary()` and records non-empty `palace.msh`,
  `config.json`, `mesh_manifest.json`, `palace_index_map.json`, and
  `palace_material_resolution.json` artifacts for Driven, Eigenmode,
  Electrostatic, and Magnetostatic fixtures without requiring Palace;
- the same evidence runner now records reusable
  `gsim.palace.load_postprocessing_index_map()` lookup evidence for each public
  problem fixture, including forward `section/index -> physical name`, reverse
  `physical name -> indices`, and attribute-to-entry checks;
- the same evidence runner now records generated config/material provenance for
  each public problem fixture, including solver problem block, solver-device
  hint, linear-solver presence, boundary/postprocessing counts, material sidecar
  counts, and domain-material rows loaded through
  `gsim.palace.load_domain_material_summary()`;
- the public simulation workflow notebook now displays those same lookup
  concepts as table outputs for Driven CPW, Eigenmode resonator, caller-supplied
  Eigenmode interface classification, and Electrostatic same-layer capacitor
  cells;
- the public simulation workflow notebook now also displays generated
  domain-material provenance tables for those public problem cells, making the
  material overlay usage visible in docs-safe outputs;
- the public simulation workflow notebook now displays a helper-node coverage
  matrix from `scripts/fixtures/public_simulation_helper_nodes.json`, tying
  private helper capability shapes and private anchors to their intended
  ecosystem home, current public `gsim`/OrPen API or artifact, and owning issue;
- the public evidence runner now embeds the same helper-node inventory as
  `helper_node_inventory`, so local JSON evidence and notebook output agree on
  implemented public fixtures, shared material/interface/index/runtime nodes,
  and the Magnetostatic config-fixture/report-loader gap;
- `gsim` commit `652fcec` adds
  `gsim.palace.load_palace_sweep_summary()`, and the public evidence runner now
  writes `points.json` for the four problem fixtures and records a
  `sweep_summary` built from that reusable API;
- `gsim` commit `1d9390f` adds `write_palace_sweep_points()`, and the public
  evidence runner now delegates `points.json` generation to that reusable
  `gsim` writer instead of hand-assembling the sweep metadata schema in
  `orpen-sc-pdk`;
- `gsim` commit `ac62a4a` adds sweep point identity validation, and the public
  evidence test now verifies the four public problem fixtures have unique
  point slugs and no sweep metadata parse warnings;
- `gsim` commit `f5eb728` extends that reusable sweep summary with
  `point_records`/`to_point_records()`/`to_dataframe()`, and the public evidence
  test now verifies table-ready rows for the four public fixtures, including
  point parameters, artifact counts, runtime sidecar status, and compact
  config/mesh/index/material-resolution counts;
- `gsim` commit `f2dbe7f` adds opt-in report-derived metrics to reusable sweep
  point records, and the public evidence runner now requests those metrics; the
  dry-run test verifies Driven/Eigenmode/Electrostatic rows report missing
  solver reports and Magnetostatic reports as skipped until a report loader is
  added, instead of fabricating physics outputs; local solver replay can fill
  the same columns from supported `gsim` report loaders;
- the public helper-node inventory now exposes promotion gates and missing
  evidence in both the notebook matrix and JSON evidence, so Magnetostatic
  remains visibly blocked on an exact Palace output contract instead of being
  marked as a report-backed workflow prematurely;
- `gsim` commit `452b3d4` adds sanitized Palace log parsing into reusable
  resource records, and the public evidence runner now uses a synthetic public
  Palace log fixture per problem type to write AMR pass, stage timing, stage
  memory, solver-version, wall-time, memory, and model-size records without
  exposing PETSc node, user, or executable path fields;
- `gsim` commit `19e35fd` adds sanitized Slurm `scontrol show job` parsing,
  and the public evidence runner now writes a synthetic public scheduler
  snapshot per problem type to exercise scheduler/allocation fields without
  exposing account, user, node, job-name, command, stdout/stderr, or work-dir
  values in the reusable resource summary;
- `gsim` commit `bfcc45a` adds sweep-level resource/benchmark index writing,
  and the public evidence runner now emits
  `metadata/records/sweep_point_records.csv`,
  `metadata/records/sweep_resource_records.csv`,
  `metadata/records/sweep_benchmark_index.jsonl`, and
  `metadata/records/sweep_resource_index.json` from the same four public
  problem fixtures;
- `gsim` commit `d93830f` adds caller-supplied Slurm profile resolution, and
  the public evidence runner now resolves the run and sweep dry-run profiles
  through that public `gsim` API instead of constructing resource specs inline;
- `gsim` commit `ba04d9d` adds JSON Slurm profile catalog loading, and the
  public evidence runner now loads its dry-run profiles from
  `scripts/fixtures/public_slurm_profiles.json` before resolving them through
  the same `gsim` profile API;
- `gsim` commit `5ff58b6` adds generic Slurm profile launcher/solver hints,
  and the public evidence runner now carries public dry-run `srun_args`,
  command style, PETSc option, and solver-device metadata from the catalog into
  generated single-run and sweep-array scripts;
- `gsim` commit `0f401c5` adds profile-to-config solver hints and
  high-level `sim.write_config(hints=...)`, and the public evidence runner now
  verifies generated Driven, Eigenmode, Electrostatic, and Magnetostatic
  `config.json` files carry the resolved public profile `Solver.Device`;
- the public simulation workflow notebook now displays the same catalog
  loading, profile resolution, launcher/solver metadata, generated `Solver`
  config hints, and generated `run_palace.sbatch` preview through executable
  cells before the problem-type workflow cells;
- when the same script is run with `ORPEN_RUN_LOCAL_PALACE_SMOKE=1` plus a
  local Palace SIF or executable, the JSON evidence keeps the same `gsim`
  run-summary bundle and switches from solver skip rows to parsed `gsim`
  Driven/Eigenmode/Electrostatic report summaries; successful local solver
  execution also exposes the sanitized `palace_run_metadata.json` sidecar
  through the same run-summary bundle;
- validation passed with
  `uv run --group ecosystem-dev python -m pytest tests/test_gsim_driven_cpw_workflow.py tests/test_gsim_eigenmode_resonator_workflow.py tests/test_gsim_electrostatic_capacitor_workflow.py -q`;
- optional local Palace validation passed on the public fixtures with a direct
  macOS development binary using
  `ORPEN_RUN_LOCAL_PALACE_SMOKE=1 PALACE_EXECUTABLE=<palace-build>/bin/palace-arm64.bin PALACE_EXECUTABLE_MODE=binary PALACE_NP=1 PALACE_NT=1 DYLD_LIBRARY_PATH=<palace-build>/lib:<palace-build>/lib64 uv run --group ecosystem-dev python -m pytest <workflow-test> -q`;
- the direct binary path was required for this local build: the wrapper launcher
  reached `mpirun` and failed to resolve `@rpath/libceed.dylib` because the
  binary still carried stale build rpaths, while `palace-arm64.bin --version`
  succeeded with the corrected loader path;
- optional local Electrostatic Palace validation passed with
  `tests/test_gsim_electrostatic_capacitor_workflow.py -q`
  (`2 passed`, public material validity-range warnings only);
- optional local Driven Palace validation passed with
  `tests/test_gsim_driven_cpw_workflow.py -q`
  (`2 passed`, public material validity-range warnings only);
- optional local Eigenmode Palace validation passed with
  `tests/test_gsim_eigenmode_resonator_workflow.py -q`
  (`3 passed`, public material validity-range warnings only);
- the unified local evidence runner also passed with the same direct-binary
  environment and wrote the ignored
  `build/public-palace-smoke-evidence/public_palace_smoke_evidence.json`
  bundle; the bundle reports loaded Driven, Eigenmode, and Electrostatic
  `gsim` report summaries plus sanitized `palace_run_metadata.json` sidecars;
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
- Ruff check and format-check passed for the executable fixtures.
- direct notebook-source execution passed and confirmed the default local
  Palace smoke cell skip path without requiring a local solver.
- `just docs` converts and executes the public simulation workflow notebook as
  part of the docs build.

Remaining slices:

- wire material-kind interface classification into public workflow examples
  only after source-backed public interface preset records and default-selection
  policy exist;
- add a public Magnetostatic report loader only after the exact Palace
  Magnetostatic CSV/output contract is confirmed; the current fixture proves
  config generation, source ownership, magnetic `SurfaceFlux`, `PMC`, and
  index-map provenance only;
- extend public material provenance for Magnetostatic-specific superconducting
  fields only when London-depth records and any non-unit magnetic parameters
  have a source-backed public schema;
- keep full sweep orchestration and broader cost modeling as later `gsim`
  workflow slices; this issue now proves explicit point-table artifact,
  runtime, provenance, resource, scheduler, benchmark-index, and report-metric
  status records over the public problem fixtures;
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
- tests verify notebook execution or equivalent scripts for all four public
  problem fixtures.

Related features:

- {doc}`../features/palace-reporting`
- {doc}`../features/palace-config-generation`
- {doc}`../features/problem-type-notebook-suite`
