# Developing Features

This page is a public feature board for capability that this project needs from
the GDSFactory ecosystem. Each item should stay reviewable without private
layout/IP.

Feature status labels:

- `candidate`: useful direction, not yet prototyped.
- `prototype`: being explored on a personal branch.
- `integration`: mature enough to slice into an upstream-review branch.
- `accepted`: merged or otherwise adopted by the target public repo.

## Local/Implemented Feature Inventory

The private simulation workflow already exercises these reusable capabilities.
They should be mapped into the GDSFactory ecosystem without publishing private
layout/IP, private run folders, or private benchmark evidence.

| Implemented capability | Public ecosystem home | Direction |
|---|---|---|
| Simulation intent attached to GDSFactory ports and component metadata | `gsim`, with public examples in `orpen-sc-pdk` | Keep component authorship in GDSFactory terms; let `gsim` translate port and terminal intent into solver inputs. |
| Driven, eigenmode, electrostatic, and magnetostatic Palace configuration assembly | `gsim` | Extend existing Palace simulation/config generation APIs instead of creating a PDK-owned solver runtime; public evidence now records generated config counts, solver problem blocks, domain-material counts, postprocessing counts, and boundary ownership for Driven, Eigenmode, Electrostatic, and Magnetostatic fixtures through reusable `gsim` output artifacts. Magnetostatic source config now covers vector `Direction`, `CoordinateSystem`, and selector-based multielement `SurfaceCurrent.Elements` in `gsim`, with OrPen only exercising the public fixture. |
| Material policy, material aliases, and Palace material translation | `orpen-sc-pdk` and `gsim` | PDK owns public material names, generated-name aliases, and records; `gsim` owns overlay loading, alias expansion, frequency evaluation, solver translation, and effective Palace domain/interface material report joins. Local branches now have a public material overlay export bridge, explicit public material-kind and alias exports for `gsim` interface classification, `material_aliases` metadata for `gsim` overlay resolution, and `gsim` Palace config/report integration, including generated domain and dielectric-interface material-resolution provenance sidecars. Public evidence and notebook cells now load domain-material provenance with `gsim.palace.load_domain_material_summary()`, showing stack material, matched material, model source, validity, frequency, permittivity, permeability, loss, and conductivity rows from generated configs. |
| Dielectric interface preset schema for MA/MS/SA-style loss records | `orpen-sc-pdk` schema with `gsim` assignment helpers | Keep public interface preset records validated, explicitly sourced, and JSON-safe in the PDK while `gsim` owns Palace `DielectricInterfaceSpec`, caller-supplied physical-name/interface-pair assignment maps, generic material-kind MA/MS/SA classification, material resolution, config emission, and report joins; OrPen now supplies generic material-name-to-kind input, generated-name aliases, a public surface-loss source-review queue, and candidate Wenner/Woods value rows, while the public preset table remains intentionally empty until source-backed public records and default-selection rules are accepted. |
| CAD/XAO/mesh physical names and solver index provenance | `meshwell` and `gsim` | Build on meshwell physical-name and interface-tag conventions, then expose a Palace role/index manifest in `gsim`; local public evidence and notebook outputs now load `palace_index_map.json` through `gsim.palace.load_postprocessing_index_map()` and demonstrate `section/index -> physical name`, `physical name -> indices`, and attribute-to-entry lookup for Driven, Eigenmode, Electrostatic, and Magnetostatic fixtures. |
| Surface-Q, EPR, capacitance, eigenmode, material, and driven-result report parsing | `gsim` | Keep reusable result loaders and report schemas upstream; local `gsim` now has indexed domain-energy, surface-Q, port-EPR, electrostatic matrix, effective domain material summaries, configured dielectric interface summaries, domain/surface loss budgets, Eigenmode modal/history primitives, and composed Driven/Eigenmode/Electrostatic report bundles. Root `gsim.palace` stays notebook-facing for report bundles and public provenance loaders, while detail loaders such as indexed CSV parsing, eigenmode/terminal pass histories, port-EPR summaries, and parser dataclasses belong under `gsim.palace.results`. |
| Runtime handoff, local/cloud/HPC execution metadata, and normalized performance records | `gsim` | Keep Palace as an external executable and report sanitized run metadata through reusable records; local `gsim` can now run wrapper-style commands or direct development binaries for opt-in coarse smokes, records sanitized local runtime metadata sidecars for successful `run_local()` executions, writes solver-specific metadata sidecars for cloud result downloads, writes, validates, and summarizes point-local Palace sweeps from explicit `points.json` metadata, emits flat sweep point records/data frames, can optionally attach problem-type report metrics for later physics and performance aggregation, writes/loads dry-run `palace_handoff_metadata.json` sidecars for single runs and sweep points, renders generic Slurm `run_palace.sbatch` scripts, renders generic Slurm array `run_sweep_array.sbatch` scripts with sweep-level `palace_sweep_handoff_metadata.json`, writes generated handoff archive manifests without packaging private archives, writes/loads public `palace_resource_record.json` sidecars for post-run resource evidence, parses sanitized Palace logs into AMR, stage-timing, stage-memory, solver-version, memory, wall-time, and model-size records, parses sanitized Slurm `scontrol show job` snapshots into scheduler/allocation fields without raw account, user, node, job-name, command, or work-dir values, writes sweep-level point/resource CSVs plus benchmark JSONL indexes from the same explicit sweep summary, loads caller-owned JSON Slurm profile catalogs before resolving validated resource overrides, carries generic launcher/solver hints from those catalogs into Slurm script rendering, and can map profile solver hints into generated Palace `Solver.Device`/`Solver.Backend` config keys. The remaining NCUAS-style nodes are private site catalog content, richer campaign/cost modeling, and private-HPC validation; these should extend the same `gsim` summary surfaces instead of becoming PDK or `gplugins` runtime code. |
| Public problem-type notebooks for workflow validation | `orpen-sc-pdk` examples using `gsim` | Rebuild driven, eigenmode, electrostatic, and magnetostatic config notebooks with public fixtures instead of copying private notebooks; local fixtures now have opt-in Palace coarse solves for the report-backed Driven/Eigenmode/Electrostatic problem types, a Magnetostatic config/index-map fixture with vector-direction signal source, multielement return source, generated coordinate-system and element-count lookup evidence, synthetic public `gsim` report-table displays for Driven S-parameters/port-EPR and Eigenmode/Electrostatic loss budgets, a generated resonator interface-classification display using caller-supplied presets, docs-safe Slurm profile catalog, solver-config-hint, handoff-preview cells, a helper-node coverage matrix loaded from the same fixture as local JSON evidence, generated config/material provenance tables backed by `gsim.palace.load_domain_material_summary()` including material permeability where supplied by the public overlay, index-map lookup tables backed by `gsim.palace.load_postprocessing_index_map()`, a docs-safe optional local-solver smoke cell, and an ignored local evidence runner that consumes reusable `gsim` sweep point metadata writing/identity validation, run summaries, dry-run single-run and sweep-array Slurm handoff scripts/summaries, generated handoff archive manifests, synthetic log-derived resource-record summaries, sweep summaries, table-ready sweep point records, helper-node inventory evidence with promotion gates and missing-evidence fields, config/material provenance evidence, index-map lookup evidence, and report-metric status rows for all four public problem fixtures. |

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

Provide public driven, eigenmode, electrostatic, and magnetostatic config
notebooks that validate the same workflow nodes as private consumers without
publishing private layouts.
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
```
