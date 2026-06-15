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
| Driven, eigenmode, electrostatic, and magnetostatic Palace configuration assembly | `gsim` | Extend existing Palace simulation/config generation APIs instead of creating a PDK-owned solver runtime. |
| Material policy, material aliases, and Palace material translation | `orpen-sc-pdk` and `gsim` | PDK owns public material names, generated-name aliases, and records; `gsim` owns overlays, frequency evaluation, solver translation, and effective Palace domain/interface material report joins; local branches now have a public material overlay export bridge, explicit public material-kind and alias exports for `gsim` interface classification, and `gsim` Palace config/report integration, including generated domain and dielectric-interface material-resolution provenance sidecars. |
| Dielectric interface preset schema for MA/MS/SA-style loss records | `orpen-sc-pdk` schema with `gsim` assignment helpers | Keep public interface preset records validated, explicitly sourced, and JSON-safe in the PDK while `gsim` owns Palace `DielectricInterfaceSpec`, caller-supplied physical-name/interface-pair assignment maps, generic material-kind MA/MS/SA classification, material resolution, config emission, and report joins; OrPen now supplies generic material-name-to-kind input, generated-name aliases, a public surface-loss source-review queue, and candidate Wenner/Woods value rows, while the public preset table remains intentionally empty until source-backed public records and default-selection rules are accepted. |
| CAD/XAO/mesh physical names and solver index provenance | `meshwell` and `gsim` | Build on meshwell physical-name and interface-tag conventions, then expose a Palace role/index manifest in `gsim`. |
| Surface-Q, EPR, capacitance, eigenmode, material, and driven-result report parsing | `gsim` | Keep reusable result loaders and report schemas upstream; local `gsim` now has indexed domain-energy, surface-Q, port-EPR, electrostatic matrix, effective domain material summaries, configured dielectric interface summaries, domain/surface loss budgets, Eigenmode modal/history primitives, and composed Driven/Eigenmode/Electrostatic report bundles. |
| Runtime handoff, local/cloud/HPC execution metadata, and normalized performance records | `gsim` | Keep Palace as an external executable and report sanitized run metadata through reusable records; local `gsim` can now run wrapper-style commands or direct development binaries for opt-in coarse smokes, records sanitized local runtime metadata sidecars for successful `run_local()` executions, writes solver-specific metadata sidecars for cloud result downloads, writes, validates, and summarizes point-local Palace sweeps from explicit `points.json` metadata, emits flat sweep point records/data frames, can optionally attach problem-type report metrics for later physics and performance aggregation, writes/loads dry-run `palace_handoff_metadata.json` sidecars for single runs and sweep points, and renders generic Slurm `run_palace.sbatch` scripts that update the same handoff summary surface without submitting jobs. The remaining NCUAS-style nodes are real site/profile resolution, handoff archive manifests, post-run resource records, and benchmark indexes; these should extend the same `gsim` summary surfaces instead of becoming PDK or `gplugins` runtime code. |
| Public problem-type notebooks for workflow validation | `orpen-sc-pdk` examples using `gsim` | Rebuild driven, eigenmode, and electrostatic notebooks with public fixtures instead of copying private notebooks; local fixtures now have opt-in Palace coarse solves for all three problem types, synthetic public `gsim` report-table displays for Driven S-parameters/port-EPR and Eigenmode/Electrostatic loss budgets, a generated resonator interface-classification display using caller-supplied presets, a docs-safe optional local-solver smoke cell, and an ignored local evidence runner that consumes reusable `gsim` sweep point metadata writing/identity validation, run summaries, dry-run Slurm handoff scripts/summaries, sweep summaries, table-ready sweep point records, and report-metric status rows for all three public problem fixtures. |

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

Provide public driven, eigenmode, and electrostatic notebooks that validate the
same workflow nodes as private consumers without publishing private layouts.
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
