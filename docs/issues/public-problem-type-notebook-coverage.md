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
  indices map back to `P1`/`P2` port metadata;
- the same driven fixture now includes an optional local Palace coarse-solve
  smoke test guarded by `ORPEN_RUN_LOCAL_PALACE_SMOKE=1`; it verifies that
  `run_local()` returns public `gsim.palace.SParams`, resolves `o1`/`o2` port
  labels, and preserves a non-empty `port-S.csv` result file;
- eigenmode now has an executable public fixture in
  `tests/test_gsim_eigenmode_resonator_workflow.py`: it builds the public
  `resonator` cell, runs local `gsim` `EigenmodeSim` coarse meshing, writes
  Eigenmode `config.json`, persists `mesh_manifest.json`, persists
  `palace_index_map.json`, and verifies the absorbing boundary maps to a Palace
  Power `SurfaceFlux` postprocessing index;
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
  map back to separate `D0_TOP_M1` physical names;
- the same electrostatic fixture now includes an optional local Palace
  coarse-solve smoke test guarded by `ORPEN_RUN_LOCAL_PALACE_SMOKE=1`; it can
  run through a local Palace wrapper or direct solver binary and verifies that
  public outputs include non-empty `terminal-C.csv`, `terminal-Cm.csv`, and
  `terminal-Cinv.csv`;
- the optional electrostatic smoke now loads `terminal-C.csv`,
  `terminal-Cm.csv`, and `terminal-Cinv.csv` through public
  `gsim.palace.load_terminal_matrix()` and verifies that terminal labels resolve
  to `positive`/`negative` through `palace_index_map.json`;
- `notebooks/src/public_simulation_workflows.py` is a publication-safe Jupytext
  notebook source that runs public Driven, Eigenmode, and Electrostatic
  mesh/config/artifact handoffs and displays scrubbed summaries only;
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
- direct macOS development binaries may also require local dynamic-library
  loader variables such as `DYLD_LIBRARY_PATH`; keep those machine-specific
  paths outside public docs and CI defaults;
- Ruff check and format-check passed for all three executable fixtures.
- `just docs` converts and executes the public simulation workflow notebook as
  part of the docs build.

Remaining slices:

- expose the opt-in solver smoke paths in publication-safe notebook/example
  form without making normal docs builds depend on local Palace;
- extend reusable Eigenmode reporting beyond raw Palace tables only after
  material-loss/T1/gamma ownership is split between `gsim` report schemas and
  PDK material overlays.

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
