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
- eigenmode now has an executable public fixture in
  `tests/test_gsim_eigenmode_resonator_workflow.py`: it builds the public
  `resonator` cell, runs local `gsim` `EigenmodeSim` coarse meshing, writes
  Eigenmode `config.json`, persists `mesh_manifest.json`, persists
  `palace_index_map.json`, and verifies the absorbing boundary maps to a Palace
  Power `SurfaceFlux` postprocessing index;
- electrostatic now has an executable public fixture in
  `tests/test_gsim_electrostatic_capacitor_workflow.py`: it builds the public
  same-layer Martinis differential ribbon capacitor fixture, uses local `gsim`
  `ElectrostaticSim` center-selected terminal configuration, writes
  Electrostatic `config.json`, persists `mesh_manifest.json`, persists
  `palace_index_map.json`, and verifies the positive/negative terminal indices
  map back to separate `D0_TOP_M1` physical names;
- validation passed with
  `uv run --group ecosystem-dev python -m pytest tests/test_gsim_driven_cpw_workflow.py tests/test_gsim_eigenmode_resonator_workflow.py tests/test_gsim_electrostatic_capacitor_workflow.py -q`;
- Ruff check and format-check passed for all three executable fixtures.

Remaining slices:

- convert the executable driven fixture into a publication-safe notebook or
  notebook-equivalent example page;
- convert the executable eigenmode fixture into a publication-safe notebook or
  notebook-equivalent example page;
- convert the executable electrostatic fixture into a publication-safe notebook
  or notebook-equivalent example page;
- add optional local Palace coarse-solve smoke checks when a Palace binary is
  available.

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
