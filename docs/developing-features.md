# Developing Features

This page is a public feature board for capability that this project needs from
the GDSFactory ecosystem. Each item should stay reviewable without private
layout/IP.

Feature status labels:

- `candidate`: useful direction, not yet prototyped.
- `prototype`: being explored on a personal branch.
- `integration`: mature enough to slice into an upstream-review branch.
- `accepted`: merged or otherwise adopted by the target public repo.

## PR Extraction Roadmap

Conclusion: rebuild review branches from clean upstream baselines. The current
personal branches are useful staging areas, not PR branches. Breakpoint PRs come
first because later PDK notebooks only become meaningful after those contracts
exist in the owner repo.

Baseline used for this roadmap:

| Repo | Baseline | Current personal branch signal |
|---|---|---|
| `gsim` | `upstream/main` | 71 local commits plus active Palace WIP |
| `meshwell` | `upstream/main` | 1 physical-name contract commit plus thin-film WIP |
| `orpen-sc-pdk` | `origin/main` | public docs/notebooks/material/Purcell WIP |

Priority order:

| Priority | PR slice | Repo | Size | Breakpoint | Result to show first | Waits for |
|---|---|---|---|---|---|---|
| P0 | Palace API boundary cleanup | `gsim` | M | Yes | smaller public imports; owner modules for mesh, material, run, resolve, display | none |
| P1 | Mesh physical-name and index-map contract | `meshwell` then `gsim` | M | Yes | raw mesh physical names round-trip to manifest/index-map lookups | P0 |
| P2 | Material overlay and provenance | `gsim` | M | Yes | PDK material overlay changes generated Palace material rows and report provenance | P0 |
| P3 | Typed Resolve/report backbone | `gsim` | L | Yes | Driven, Eigenmode, and Electrostatic reports load real Palace outputs through one report path | P1, P2 |
| P4 | ThinMetal Surface EPR MS geometry/config helper | `gsim` | M | Yes | two source sheets produce 50 nm, 100 nm, 200 nm, 500 nm, 1 um MS groups plus core groups without overlapping original PEC groups | P1, P3 |
| P5 | Public material overlay demo | `orpen-sc-pdk` | S | No | resonator notebook shows PDK material JSON reaching `gsim` config/report rows | P2, P3 |
| P6 | Public problem notebooks | `orpen-sc-pdk` | M | No | Driven, Eigenmode, and Electrostatic notebooks use public layouts and `report.show_all_results()` | P3 |
| P7 | Martinis ribbon Surface EPR MS notebook | `orpen-sc-pdk` | S | No | handoff/local notebooks show MS-only ThinMetal groups and config rows | P4 |
| P8 | Runtime handoff and benchmark records | `gsim` then `orpen-sc-pdk` | L | No | Slurm handoff, run metadata, wall time, memory, and benchmark tables are reproducible from public fixtures | P3 |
| P9 | Purcell public notebooks | `orpen-sc-pdk` | M | No | layout-authored readout sheets drive public Purcell examples | P1, P3 |

Not first-wave PRs:

| Slice | Why it waits |
|---|---|
| Surface EPR result presentation and loss-budget visualization | Current geometry/config path is useful, but final report presentation is not done. Do not claim Surface EPR analysis complete until report tables and plots are reviewable. |
| MA/SA and general 3D interface banding | The MS ThinMetal path is the small working slice. MA/SA and volume/interface banding need a separate mesh/API design. |
| Branch-review ledgers and long comparison docs | Useful locally, but not a public feature unless the PR itself is documentation infrastructure. |

## Fast Review Conclusions

| Current result | Benefit | Public notebook evidence | Scope boundary |
|---|---|---|---|
| ThinMetal source-aware Surface EPR margin groups, MS-only | Splits each original PEC/source sheet into 50 nm, 100 nm, 200 nm, 500 nm, and 1 um edge bands plus a core group, so mesh review can check convergence by source sheet without overlapping the original PEC physical group. | `notebooks/src/public_surface_epr_ribbon_capacitor_workflow.py` and `notebooks/src/public_surface_epr_ribbon_capacitor_local_workflow.py` | MA/SA and general 3D interface banding are deferred; this slice only proves thin-film sheet MS postprocessing. |
| PDK material overlay into `gsim` | Keeps public SCQ material values in `orpen_sc_pdk/materials.json` while `gsim` owns Palace material resolution and report joins. | `notebooks/src/public_eigenmode_workflow.py` and `notebooks/src/public_eigenmode_local_workflow.py` | The PDK exports records and aliases; `gsim` resolves solver material values. |
| Report-backed public problem notebooks | Shows the reusable Geometry -> LayerStack -> Mesh -> Config -> Run -> Resolve -> Visualize chain on public layouts. | Driven, Eigenmode, Electrostatic, and Surface EPR notebooks under `notebooks/src/` | Notebooks compose examples; they do not parse Palace outputs or hide workflow logic in scripts. |

## Local/Implemented Feature Inventory

The private simulation workflow already exercises these reusable capabilities.
They should be mapped into the GDSFactory ecosystem without publishing private
layout/IP, private run folders, or private benchmark evidence.

| Implemented capability | Public ecosystem home | Direction |
|---|---|---|
| Simulation intent attached to GDSFactory ports and component metadata | `gsim`, with public examples in `orpen-sc-pdk` | Keep component authorship in GDSFactory terms; let `gsim` translate port and terminal intent into solver inputs. |
| Driven, eigenmode, electrostatic, and magnetostatic Palace configuration assembly | `gsim` | Extend existing Palace simulation/config generation APIs instead of creating a PDK-owned solver runtime; public evidence now records generated config counts, solver problem blocks, domain-material counts, postprocessing counts, and boundary ownership for Driven, Eigenmode, Electrostatic, and Magnetostatic fixtures through reusable `gsim` output artifacts. Magnetostatic source config now covers vector `Direction`, `CoordinateSystem`, and selector-based multielement `SurfaceCurrent.Elements` in `gsim`, with OrPen only exercising the public fixture. Lumped-port `Direction` vectors and generated sheets from GDSFactory port orientation belong in `gsim`; layout-authored solver-boundary sheet ingestion remains next-round `gsim`/meshwell work, not OrPen runtime code. |
| Material policy, material aliases, and Palace material translation | `orpen-sc-pdk` and `gsim` | PDK owns public material names, generated-name aliases, and records; `gsim` owns overlay loading, alias expansion, frequency evaluation, solver translation, and effective Palace domain/interface material report joins. Local branches now have a public material overlay export bridge, explicit public material-kind and alias exports for `gsim` interface classification, `material_aliases` metadata for `gsim` overlay resolution, and `gsim` Palace config/report integration, including generated domain and dielectric-interface material-resolution provenance sidecars. Public evidence and report-backed notebook cells now show domain-material provenance through report-owned `domain_materials` and the `gsim.palace.resolve.derived.materials.load_domain_material_summary()` owner path, including stack material, matched material, model source, validity, frequency, permittivity, permeability, loss, and conductivity rows from generated configs. |
| Dielectric interface preset schema for source-backed loss records | `orpen-sc-pdk` schema with `gsim` assignment helpers | Keep public interface preset records validated, explicitly sourced, and JSON-safe in the PDK while `gsim` owns Palace `DielectricInterfaceSpec`, caller-supplied physical-name/interface-pair assignment maps, material-kind classification, material resolution, config emission, and report joins. The current notebook-backed slice is ThinMetal MS-only; MA/SA promotion and automatic default-selection rules remain deferred until source-backed public process scope is accepted. |
| CAD/XAO/mesh physical names and solver index provenance | `meshwell` and `gsim` | Build on meshwell physical-name and interface-tag conventions, then expose a Palace role/index manifest in `gsim`; local public evidence and notebook outputs now load `mesh_manifest.json`, `palace_index_map.json`, and `config.json` for Driven, Eigenmode, and Electrostatic fixtures, demonstrating manifest role/physical-name coverage, `section/index -> physical name`, `physical name -> indices`, attribute-to-entry lookup, port metadata, terminal metadata, and config material joins without making OrPen own the CAD/XAO grammar. The public inventory now also shows a meshwell-to-`gsim` handoff contract gate: local meshwell source/tests, formal meshwell physical-name contract text, meshwell backend-equivalence tests, `gsim` manifest/index-map consumers, and a `gsim` consumer fixture backed by a meshwell-generated MSH artifact are aligned on meshwell-style `___`/`___None` names. |
| Surface-Q, EPR, capacitance, eigenmode, material, and driven-result report parsing | `gsim` | Keep reusable result loaders and report schemas upstream; local `gsim` now has indexed domain-energy, surface-Q, Eigenmode port-EPR, electrostatic matrix, effective domain material summaries, configured dielectric interface summaries, domain/surface loss budgets, Eigenmode modal/history primitives, and composed Driven/Eigenmode/Electrostatic report bundles. Root `gsim.palace` stays notebook-facing for simulation classes and `resolve_palace_result(...).load_report().require_report()`, while primitive loaders and derived provenance tables stay under their Resolve owner modules and typed report/data semantics stay under `gsim.palace.results`. |
| Runtime handoff, local/cloud/HPC execution metadata, and normalized performance records | `gsim` | Keep Palace as an external executable and report sanitized run metadata through reusable records; local `gsim` can now run wrapper-style commands or direct development binaries for opt-in coarse smokes, records sanitized local runtime metadata sidecars for successful `run_local()` executions, writes solver-specific metadata sidecars for cloud result downloads, writes, validates, and summarizes point-local Palace sweeps from explicit `points.json` metadata, emits flat sweep point records/data frames, can optionally attach problem-type report metrics for later physics and performance aggregation, writes/loads dry-run `palace_handoff_metadata.json` sidecars for single runs and sweep points, renders generic Slurm `run_palace.sbatch` scripts, renders generic Slurm array `run_sweep_array.sbatch` scripts with sweep-level `palace_sweep_handoff_metadata.json`, writes generated handoff archive manifests without packaging private archives, writes/loads public `palace_resource_record.json` sidecars for post-run resource evidence, parses sanitized Palace logs into AMR, stage-timing, stage-memory, solver-version, memory, wall-time, and model-size records, parses sanitized Slurm `scontrol show job` snapshots into scheduler/allocation fields without raw account, user, node, job-name, command, or work-dir values, writes sweep-level point/resource CSVs plus benchmark JSONL indexes from the same explicit sweep summary, loads caller-owned JSON Slurm profile catalogs before resolving validated resource overrides, carries generic launcher/solver hints from those catalogs into Slurm script rendering, and can map profile solver hints into generated Palace `Solver.Device`/`Solver.Backend` config keys. The remaining NCUAS-style nodes are private site catalog content, richer campaign/cost modeling, and private-HPC validation; these should extend the same `gsim` summary surfaces instead of becoming PDK or `gplugins` runtime code. |
| Public problem-type notebooks for workflow validation | `orpen-sc-pdk` examples using `gsim` | Rebuild Driven, Eigenmode, and Electrostatic report-backed notebooks with public fixtures instead of copying private notebooks; local fixtures now have opt-in Palace coarse solves for the report-backed Driven/Eigenmode/Electrostatic problem types, and public notebooks now load completed solver outputs through `resolve_palace_result(...).load_report(require_report=True).require_report()` before displaying report-owned typed-data visualizations. The docs build converts and renders these notebooks but does not execute the result cells because tracked public docs do not carry solver-produced report CSVs. The public simulation inventory notebook displays the helper-node matrix, representative NCUAS notebook cross-check, goal-level audit, source-review queue, local `gsim` boundary-review coverage, and thin-film sheet proxy MA/MS evidence from public helpers/fixtures, including opt-in solver replay, user-deferred Magnetostatic/HPC scope, and owner-pending AEDT/Q2D work rather than treating every row as complete Palace workflow coverage. Magnetostatic remains a JSON evidence/config fixture with vector-direction signal source, multielement return source, generated coordinate-system and element-count lookup evidence, and report-metric skipped status until a report contract is needed. The ignored local evidence runner consumes reusable `gsim` sweep point metadata writing/identity validation, run summaries, dry-run single-run and sweep-array Slurm handoff scripts/summaries, generated handoff archive manifests, synthetic log-derived resource-record summaries, sweep summaries, table-ready sweep point records, helper-node inventory evidence with promotion gates and missing-evidence fields, problem-notebook cross-check evidence, goal-audit evidence, local `gsim` boundary-review coverage evidence, interface preset source-review evidence, thin-film sheet proxy evidence, config/material provenance evidence, index-map lookup evidence, and report-metric status rows for all four public problem fixtures. |

::::{grid} 1 1 2 3
:gutter: 3

:::{grid-item-card} FEAT-001 Palace analysis/reporting contract
:link: features/palace-reporting
:link-type: doc

**Target:** `gsim`

**Status:** candidate

Define reusable electrostatic and EPR report surfaces that can consume public
PDK layer/material metadata without depending on private layout repos.
:::

:::{grid-item-card} FEAT-002 Surface-Q index mapping
:link: features/surface-q-index-mapping
:link-type: doc

**Target:** `gsim` with `orpen-sc-pdk` metadata

**Status:** candidate

Map simulation surfaces back to PDK layer semantics so reports can identify
participation, loss, and surface-Q contributors in a publication-safe way.
:::

:::{grid-item-card} FEAT-003 Material database overlay
:link: features/material-db-overlay
:link-type: doc

**Target:** `orpen-sc-pdk` and `gsim`

**Status:** prototype

Keep SCQ material records in the PDK while adapting them into `gsim` material
resolver overlays for Palace config generation and other solver workflows.
:::

:::{grid-item-card} FEAT-004 Benchmark and cost analysis
:link: features/benchmark-cost-analysis
:link-type: doc

**Target:** `gsim`

**Status:** candidate

Provide solver performance records that help estimate runtime, memory, mesh
cost, and cloud/HPC spend without exposing private geometry or private runs.
:::

:::{grid-item-card} FEAT-005 GDSFactory+ PDK discovery
:link: features/gdsfactoryplus-discovery
:link-type: doc

**Target:** `orpen-sc-pdk`

**Status:** prototype

Keep the PDK in a flat package layout with public `cells/`, reserved `models/`,
and GDSFactory+ metadata so VSCode preview works on the active repo.
:::

:::{grid-item-card} FEAT-006 Palace config generation
:link: features/palace-config-generation
:link-type: doc

**Target:** `gsim` with `orpen-sc-pdk` metadata

**Status:** prototype

Generate Palace configuration from public PDK layer/material metadata,
component-mounted simulation intent, and mesh role manifests.
:::

:::{grid-item-card} FEAT-007 CAD/XAO metadata handoff
:link: features/cad-xao-metadata-handoff
:link-type: doc

**Target:** `meshwell` and `gsim`

**Status:** prototype

Preserve physical names, interface identities, mesh roles, and solver indices
from CAD/XAO generation through Palace postprocessing.
:::

:::{grid-item-card} FEAT-008 Problem-type notebook suite
:link: features/problem-type-notebook-suite
:link-type: doc

**Target:** `orpen-sc-pdk` examples using `gsim`

**Status:** prototype

Provide public Driven, Eigenmode, and Electrostatic report-backed notebooks
that validate the same workflow nodes as private consumers without publishing
private layouts.
:::

:::{grid-item-card} FEAT-009 gsim Palace branch comparison
:link: features/gsim-palace-branch-comparison
:link-type: doc

**Target:** `gsim`

**Status:** prototype

Track how the local Palace personal branch differs from upstream `gsim` so the
public PDK can consume only reusable, reviewable solver capabilities.
:::

::::

```{toctree}
:hidden:

features/palace-reporting
features/surface-q-index-mapping
features/material-db-overlay
features/benchmark-cost-analysis
features/gdsfactoryplus-discovery
features/palace-config-generation
features/cad-xao-metadata-handoff
features/problem-type-notebook-suite
features/gsim-palace-branch-comparison
```
