# AEDT Native Package

**Target:** `orpen_sc_pdk.simulation.aedt`

**Status:** implemented v1 with transitional solver modules

The public PDK owns a portable AEDT handoff package contract that private
layout repositories can call with their own GDS, TECH/XML, layer mapping,
material sidecars, solver sidecars, and HPC profiles. The PDK does not own
private chip geometry, private machine profiles, local AEDT licenses, or solver
run evidence.

The current implementation keeps the generated PyAEDT runner as a runtime
bundle while the package surface is split into reviewable modules. Public API
users should treat `AedtNativePackageSpec`, `AedtNativeCaseSpec`,
`AedtRecipeSpec`, and `AedtHpcProfileSpec` as the source of truth for package
generation.

## Host Contract

Host-side code runs before the AEDT machine is involved:

- validate package, case, recipe, runtime, material, and HPC models;
- copy source artifacts into a portable package layout;
- write `manifest.yaml`, `run_configs/*.yaml`, `hpc/*.acf`, launcher scripts,
  README, and optional handoff archives;
- fail before package creation when a recipe declares sidecars that cannot
  satisfy the runtime contract, such as missing semantic Q2D cross-section
  metadata.

## Runtime Contract

Target-side code runs inside the generated AEDT package:

- load the manifest and run config;
- create or attach to the AEDT desktop;
- dispatch each recipe to its solver-specific path;
- register materials and assign them to AEDT objects;
- build or import geometry, assign boundaries, create setup/sweeps, solve, and
  export solver outputs;
- write audit files that explain source hashes, geometry decisions, assignment
  summaries, solve status, and exported artifacts.

## Scaffold Layout

`models.py`, `materials.py`, `package.py`, and `templates.py` are the host-side
primitive files. The runtime scaffold modules are intentionally fail-fast: they
define the solver ownership boundaries without pretending those modules are
implemented.

```text
orpen_sc_pdk/simulation/aedt/
  __init__.py
  hpc.py
  constants.py
  models.py
  materials.py
  package.py
  templates.py
  runtime_bundle/
    run_aedt_native.py
    io.py
    materials.py
    session.py
    sweep.py
    solver/
      hfss/driven_terminal.py
      hfss/eigenmode.py
      q3d.py
      q2d/
        workflow.py
        state.py
        geometry.py
        assignment.py
        region.py
        setup.py
        solve.py
        export.py
        audit.py
```

## Solver Boundaries

- HFSS Driven Terminal owns GDS/AEDB import through `Hfss3dLayout`, terminal or
  port selection, setup/sweep creation, solve, layout result export, and project
  save.
- HFSS Eigenmode owns GDS/AEDB import through `Hfss3dLayout`, eigenmode setup,
  mode count, solve, benchmark artifact export, and project save.
- Q3D owns layout import/export handoff, Q3D design creation, source/reference
  or net assignment, C/AC-RL/DC-RL export, and project save.
- Q2D owns stateful cross-section execution. `hfss_section` uses HFSS staging
  and section extraction. `semantic_cross_section` builds explicit
  Stack/FacePattern rectangles directly in Q2D; legacy CPW marker-driven
  `native_2d` geometry is no longer a valid package contract.

Private repositories can add their own profile catalog or artifact discovery
around this API without modifying the public PDK scaffold.
