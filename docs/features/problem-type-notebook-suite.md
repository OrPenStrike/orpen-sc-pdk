# Problem-Type Notebook Suite

**Target:** `orpen-sc-pdk` examples using `gsim`

**Status:** prototype

The public PDK should provide a small notebook suite that proves the reusable
simulation workflow works for representative Palace problem types without
copying private notebooks or saved private outputs.

Local/implemented capability:

- driven workflows validate port excitation, terminal sweeps, solver handoff,
  result loading, and performance records;
- eigenmode workflows validate scene construction, sweep staging, mesh/config
  reuse, convergence records, and EPR-ready postprocessing;
- electrostatic workflows validate terminal assignment, capacitance extraction,
  package analysis, and report generation.

Public fixture direction:

- driven: a public CPW or resonator fixture with explicit lumped/terminal
  excitation;
- eigenmode: a public resonator fixture that can run on a coarse mesh and
  later extend to sweep coverage;
- electrostatic: a public capacitor fixture with named terminals and
  capacitance/report outputs.

Current public notebook:

- {doc}`../notebooks/public_simulation_workflows` runs public Driven,
  Eigenmode, and Electrostatic mesh/config/artifact handoffs with local `gsim`
  and public `orpen-sc-pdk` cells only.

Current executable smoke coverage:

- the public Electrostatic capacitor fixture has an opt-in local Palace coarse
  solve guarded by `ORPEN_RUN_LOCAL_PALACE_SMOKE=1`;
- the smoke path accepts either a Palace SIF (`PALACE_SIF`) or a direct local
  executable (`PALACE_EXECUTABLE`), with `PALACE_EXECUTABLE_MODE=binary` for
  development binaries that do not accept wrapper launcher flags;
- Driven and Eigenmode still need equivalent opt-in solver smokes.

Acceptance direction:

- each notebook uses `gsim` APIs and `orpen-sc-pdk` public metadata only;
- each notebook can run a coarse local Palace smoke test when Palace is
  available;
- saved outputs are scrubbed or synthetic unless explicitly publication-safe;
- notebook tests verify the workflow contract without depending on private
  layout modules, private run folders, or private benchmark values.

Related issue:

- {doc}`../issues/public-problem-type-notebook-coverage`

```{toctree}
:hidden:

../notebooks/public_simulation_workflows
```
