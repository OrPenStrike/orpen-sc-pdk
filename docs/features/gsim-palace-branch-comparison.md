# gsim Palace Branch Comparison

**Target:** `gsim`

**Status:** prototype

This page records the public, reviewable delta between upstream `gsim` and the
local Palace personal branch used by the public PDK simulation work. The PDK
should treat this as an integration map, not as PDK-owned solver runtime.

Comparison snapshot:

- **Date:** 2026-06-19
- **Upstream baseline:** `upstream/main` at `4a3c067`
- **Local branch:** `feature/gsim-palace-postprocessing-roles` at `2f2a471`
- **Pull status:** upstream `main` is merged into the local branch
- **Branch distance after merge:** `0` upstream commits behind, `71` local
  commits ahead
- **Working tree:** additional uncommitted Palace config, port-lowering,
  simulation-layer, and validation edits are present

## Upstream Design Baseline

Current upstream `gsim` is organized as an electromagnetic simulation package
for GDSFactory layouts. Its public design emphasizes:

- layer-stack extraction from the active PDK;
- port configuration from GDSFactory ports into solver-compatible definitions;
- Gmsh mesh generation for Palace;
- cloud execution through `gsim.gcloud`;
- visualization helpers shared across solver workflows;
- high-level Palace classes such as `DrivenSim`, `EigenmodeSim`, and
  `ElectrostaticSim`;
- notebook examples that call the high-level simulation API and run through the
  public cloud path where appropriate.

The upstream changes pulled into this branch on 2026-06-19 were primarily
Meep/visualization and notebook-execution updates: interactive FDTD plotting,
shared visualization helpers, a taper sample, and Palace notebook cloud-run
updates. They did not add a new Palace responsibility-layer architecture.

## Local Branch Delta

| Area | Upstream design | Local Palace branch delta | Public PDK boundary |
|---|---|---|---|
| Public Palace API | High-level simulation classes and broad helper exports. | Narrows root `gsim.palace` exports and demotes helper internals into owner modules such as `mesh`, `resolve`, `results`, and `run`. | OrPen examples should call stable high-level APIs only. |
| Mesh and identity | Mesh generation and port surfaces are solver-prep details. | Adds mesh manifests, Palace index maps, postprocessing config artifacts, and meshwell physical-name handoff tests. | OrPen can provide public fixtures and inspect generated artifacts, but mesh identity ownership remains `gsim`/meshwell. |
| Config generation | Palace config writing exists behind simulation classes. | Extends role-aware config generation for driven, eigenmode, electrostatic, and magnetostatic problem surfaces, including material overlays and generated provenance sidecars. | OrPen exports public layer/material metadata and component intent; it does not assemble Palace JSON itself. |
| Materials and interfaces | Layer-stack/material handling is basic reusable simulation input. | Adds material aliases, generated domain-material summaries, dielectric-interface summaries, interface classification, and source/provenance rows. | OrPen owns public material records and aliases; `gsim` owns solver evaluation and report joins. |
| Results and reports | Results are returned from run workflows and notebooks. | Adds `resolve/` loaders, typed report/data surfaces, domain and surface loss summaries, EPR and terminal matrix loaders, and composed Driven/Eigenmode/Electrostatic reports. | OrPen notebooks may display report tables through `gsim`; parsing stays upstream. |
| Runtime and handoff | Cloud execution is the public happy path. | Adds local wrapper/direct-binary runs, canonical run folders, handoff packages, Slurm single and array scripts, resource metadata, sweep summaries, and benchmark records. | OrPen may keep opt-in public smoke evidence; execution orchestration belongs in `gsim`. |
| Tests and review surface | Upstream tests focus on public solver, notebook, and visualization behavior. | Adds Palace handoff, mesh manifest, meshwell handoff contract, display, result-loader, run-folder, and workflow tests. | Public PDK tests should verify consumption, not duplicate upstream solver tests. |

## Working-Tree-Only Delta

The current local checkout also contains uncommitted Palace work. Treat these
as draft slices until committed and validated in `gsim`:

- vendored Palace config schemas for `0.15.0` and `0.16.0`;
- `validate_palace_config(...)` for last-mile schema validation before
  solver execution or handoff packaging;
- explicit Palace config-version targeting through `set_palace_version(...)`;
- typed `Solver.Linear` and `Model.Refinement` models for advanced solver
  settings;
- a PDK-supplied simulation-layer catalog for layout-authored solver sheets;
- `generate_sheet=False` port flows that select authored horizontal sheet
  polygons from registered simulation-only layers;
- port-lowering refactors that move metadata extraction into
  `gsim.palace.ports.lowering`;
- vector `Direction` lowering for lumped and CPW port elements;
- focused config-validation, mesh, workflow, and simulation-class tests.

## Integration Direction

Keep the public PDK as a consumer and evidence host:

- OrPen owns public layer names, material records, public fixture cells, and
  docs/notebook evidence.
- `gsim` owns Palace-specific lowering, schema validation, config assembly,
  run folders, handoff, result parsing, reports, sweeps, and resource records.
- meshwell owns CAD/XAO physical-name and mesh identity conventions consumed by
  `gsim`.
- `gplugins` should remain a compatibility/plugin layer and should not grow a
  second Palace runtime.

Before treating any branch-only capability as public contract, slice it into
reviewable `gsim` changes, run focused `gsim` validation, then update OrPen
docs and fixtures to consume the accepted API surface.

Related issue:

- [../issues/gsim-palace-branch-integration](../issues/gsim-palace-branch-integration.md)
