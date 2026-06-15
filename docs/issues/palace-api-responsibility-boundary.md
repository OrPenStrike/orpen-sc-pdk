# Palace API Responsibility Boundary

**Repo:** `gsim`, `gplugins`, `orpen-sc-pdk`

Palace workflow features should be assigned by responsibility first, then by
public API necessity. A helper belongs in a public import surface only when a
notebook, PDK fixture, or downstream integration is expected to call it
directly. Helper-only lowering details should stay module-local or reachable
only through the higher-level workflow API that owns them.

Problem:

- NCUAS simulation helpers are broad enough to look like a second simulation
  framework if they are copied directly;
- `gsim` already has problem-specific simulation classes, mesh/report
  artifacts, config generation, and result loaders;
- adding every helper or intermediate model to a top-level public import path
  makes future upstream review harder, even when the underlying feature is
  useful;
- `gplugins` compatibility wrappers should not become a second Palace runtime.

Observed `gsim` convention:

- the official/local `docs/api/palace.md` page is manually curated around
  notebook-facing simulation classes, selected workflow methods, mesh
  generation, mesh artifacts/reportability, and reusable report loaders;
- `mkdocstrings` filters private names by default, but package `__init__`
  exports are still a review surface, not automatic proof that a symbol belongs
  in the public API;
- new root-level exports should either appear in the curated API reference or
  have a clear direct notebook/downstream caller; otherwise callers should use
  the deep owning module or a higher-level helper.

Responsibility checklist:

| Change type | Expected home |
|---|---|
| Driven sweep parameters such as field save, adaptive setting, and reference impedance | `DrivenConfig` and `DrivenSim.set_driven()` |
| Eigenmode-specific settings such as mode save, Floquet, and target handling | `EigenmodeConfig` and `EigenmodeSim.set_eigenmode()` |
| Electrostatic capacitance extraction parameters | `ElectrostaticConfig` and `ElectrostaticSim.set_electrostatic()` |
| Common Palace geometry, stack, mesh, material, and cloud workflow behavior | `PalaceSimMixin`, mesh generator, or reusable Palace workflow helpers |
| Port geometry, port extraction, CPW ports, and wave-port behavior | `gsim.palace.ports` or a port config model |
| Palace JSON emission | config generator or `to_palace_config()` |
| Result parsing such as `port-S.csv` to objects | result parser/report loader |

Public API gate:

- treat the curated `gsim` API reference as the public contract to justify new
  root imports, not merely the existence of a symbol in a package `__all__`;
- expose a symbol from `gsim.palace` only when users should import it directly
  in notebooks, public fixtures, or downstream packages;
- keep helper-only dataclasses, lowering helpers, and JSON assembly internals
  private unless they are part of a documented caller contract;
- prefer returning richer `MeshResult`, manifest, index-map, or report objects
  over exposing unrelated mesh-configuration knobs;
- frame mesh-derived visibility as manifest/reportability when it describes
  generated physical groups, attributes, or lookup rows; do not add it to
  `MeshConfig` unless it changes meshing behavior;
- names should be `gsim` native and Palace-compatible, not copied from private
  PDK layer names or NCUAS notebook conventions;
- `orpen-sc-pdk` should expose public PDK records and examples only, not Palace
  solver internals;
- `gplugins` should add only thin compatibility wrappers that delegate to
  `gsim.palace` surfaces when compatibility is needed.

Current review ledger:

| Slice | Review status | Boundary notes |
|---|---|---|
| `gsim` commit `883fb78` multielement magnetostatic current sources | Reviewed, fixed by `gsim` commit `bc78ad4` | Ownership split was mostly right: `CurrentSourceConfig` / `CurrentSourceElementConfig` owns source intent and the config generator owns `SurfaceCurrent` JSON lowering. Review found Palace-contract and API-surface issues: `CoordinateSystem` must be vector-direction only, parent `direction` on multielement sources must not be silently ignored, overlapping element selectors must be rejected, and the JSON helper `palace_direction()` should not be public model API. Local `gsim` commit `bc78ad4` moves direction lowering into a private config-generator helper and adds validation/tests for those cases. |
| `orpen-sc-pdk` commit `e54b677` multielement magnetostatic public fixture/docs | Reviewed, mostly clean with API follow-ups | OrPen remains a consumer of `gsim` source/config/index-map surfaces and does not own Palace attribute mapping. Review found stale notebook-coverage wording, now updated to mention `883fb78`, vector direction, and multielement return-source evidence. API docs now avoid member-expanding raw `tech` records; remaining OrPen API-narrowing follow-ups are top-level `helper`/`logger`/empty `models` and demo-style cells in the PDK registry. |
| OrPen material-permeability provenance slice | Reviewed, API-clean | The slice adds public unit permeability values to material records and displays the generated provenance column through `get_gsim_material_overlay()`, `palace_material_resolution.json`, and `gsim.palace.load_domain_material_summary()`. It does not widen top-level imports, change `MeshConfig`, or move material lowering/report parsing into OrPen. |
| Manifest postprocessing API cleanup slice (`gsim` commit `a736193`) | Reviewed, API-clean | `gsim.palace.mesh.build_postprocessing_config_from_manifest()` now owns omission of empty Palace postprocessing sections, so public OrPen notebook/evidence code avoids importing and reconstructing `PostprocessingConfig` only to preserve Magnetostatic solver-owned `SurfaceFlux` rows. Independent boundary review found no blockers: this remains a mesh artifact/reportability helper, does not widen top-level `gsim.palace`, and does not add `MeshConfig` knobs. |
| Mesh package-root API cleanup slice (`gsim` commit `fa71c4b`) | Reviewed, API-clean | `gsim.palace.mesh.__init__` now stops importing/re-exporting lowering-only symbols: `PostprocessingConfig`, `PostprocessingIndexEntry`, `PostprocessingIndexMap`, terminal/current-source index-map builders, `GeometryData`, and low-level `write_config` remain reachable from their defining deep modules but are no longer `mesh.__all__` exports. `gmsh_utils` is likewise no longer imported or listed by `mesh.__init__`, while Python can still load it as the deep submodule `gsim.palace.mesh.gmsh_utils`. Independent review found no blockers after that Python submodule caveat was documented. The retained package-root surface is the notebook/downstream helper path plus manifest symbols already used by docs and fixture tests. |
| Public API convention capture (`gsim` API doc update) | Reviewed, follow-ups recorded | `gsim` Palace API docs now state that the documented API reference is curated around notebook/downstream-facing entry points. The same page documents `MagnetostaticSim`, `SurfaceFluxSpec`, `SParams`, `load_sparams()`, `load_postprocessing_index_map()`, and `load_terminal_matrix()` because public OrPen fixtures/notebooks use those paths directly. This does not by itself bless every broad `gsim.palace.__all__` export; root-level handoff, sweep, resource-record, broad common/stack/viz/cloud convenience exports, raw config models, port-lowering helpers, low-level result helpers, and advanced manifest builder exports still need a follow-up audit against direct notebook/downstream usage. |
| OrPen handoff/sweep/resource import cleanup | Reviewed, API-clean | OrPen public notebook source and smoke-evidence runner now keep curated simulation classes and problem report/provenance loaders on `gsim.palace`, while importing advanced Slurm/profile/handoff helpers from `gsim.palace.handoff` and runtime/sweep/resource helpers from `gsim.palace.results`. Independent boundary review agreed with moving handoff/profile/archive helpers deep, and recommended treating `load_palace_run_summary()` / `load_palace_sweep_summary()` as runtime/sweep metadata APIs rather than root notebook-facing problem report loaders. This reduces pressure to bless the entire handoff/resource helper set as root public API while preserving public workflow evidence and discoverability through owner-module docs. |
| Runtime helper root API demotion (`gsim` commit `ad52acc`) | Reviewed, API-clean | `gsim.palace.__init__` no longer imports or re-exports the locally added Slurm/profile/handoff/archive helpers or runtime/sweep/resource record helpers. They remain available from `gsim.palace.handoff` and `gsim.palace.results`, and `tests/palace/test_handoff.py` now imports them from those owner modules. Root `gsim.palace` keeps notebook-facing simulation classes, problem report loaders, material/provenance/index loaders, and pre-existing upstream convenience exports for separate review. Independent boundary review found no OrPen blocker and confirmed the owner-module split. |
| Result-detail root API demotion (`gsim` commit `809b881`) | Reviewed, API-clean | Root `gsim.palace` keeps `SParams`, `load_sparams()`, and `load_fields()` because upstream notebooks and OrPen fixtures import those paths directly. Detail-only result helpers and dataclasses now stay in `gsim.palace.results`: `SParam`, `get_port_map()`, `IndexedCsv`, `IndexedCsvColumn`, `Eigenmodes`, `load_indexed_csv()`, eigenmode history loaders, terminal matrix history loaders, `load_port_epr_summary()`, and the matching summary helpers. This matches the notebook-facing API rule and avoids treating parser implementation details as public Palace workflow surface. |
| Source config root API demotion (`gsim` commit `699ff6e`) | Reviewed, API-clean | `CurrentSourceConfig` and `CurrentSourceElementConfig` are no longer imported or re-exported from root `gsim.palace`. They remain in the owner module `gsim.palace.models`, while notebook-facing Magnetostatic workflows use `MagnetostaticSim.add_current_source(...)` with dict/keyword source intent. Independent review found no OrPen/NCUAS root-import dependency, and this avoids making locally added source-intent dataclasses broader public API than the simulation class requires. |
| Port helper root API demotion (`gsim` commit `cf4204d`) | Reviewed, API-clean | `gsim.palace.__init__` no longer imports or re-exports port config/lowering symbols: `CPWPortConfig`, `PortConfig`, `TerminalConfig`, `WavePortConfig`, `PalacePort`, `PortGeometry`, `PortType`, `configure_*_port()`, and `extract_ports()`. Notebook-facing workflows should continue through simulation-class methods such as `add_port()`, `add_cpw_port()`, `add_wave_port()`, and `add_terminal()`. Advanced port authoring remains documented from `gsim.palace.ports` and `gsim.palace.models`, matching the responsibility boundary for port geometry/extraction behavior. Local downstream search found no OrPen/NCUAS direct root-import dependency for these symbols. |

Open API-surface follow-ups:

- demote or explicitly document broad root `gsim.palace` convenience exports
  from `gsim.common`, `gsim.common.stack`, `gsim.viz`, and `gsim.gcloud`
  (`MATERIALS_DB`, `Stack`, `StackLayer`, stack extraction/printing helpers,
  `plot_*`, `print_job_summary`, `run_simulation`) before treating them as
  part of the Palace public API;
- demote raw config/model exports (`DrivenConfig`, `EigenmodeConfig`,
  `ElectrostaticConfig`, `MagnetostaticConfig`, `GeometryConfig`,
  `MaterialConfig`, `NumericalConfig`, `PECBlockConfig`, `PortConfig`,
  `TerminalConfig`, `TransientConfig`, `WavePortConfig`, `SimulationResult`,
  `ValidationResult`) unless notebook users directly construct them rather
  than using the problem-specific `set_*()` helpers;
- finish the remaining `gsim.palace.mesh` surface review for advanced manifest
  fixture symbols (`MeshPhysicalGroup`, `MeshRole`, `build_mesh_manifest`) and
  type aliases that may belong only in `mesh.manifest` / `mesh.postprocessing`;
- keep `gsim` Palace API docs split between mesh generation controls and mesh
  artifacts, manifests, postprocessing index maps, and reportability;
- keep OrPen API docs focused on copy-returning material helpers and avoid
  member-expanding raw mutable `tech.material_properties`,
  `material_alias_records`, and `interface_preset_records`;
- decide whether simulation demo cells should remain public PDK cells or move
  to samples/examples.

Acceptance checks:

- no problem-specific parameter is added to a common mesh/material model;
- no mesh/reportability extension is mislabeled as a mesh generation setting;
- no helper-only symbol is exported from a package-level `__init__.py` without a
  notebook/downstream caller reason;
- generated evidence shows the user-facing helper path, not internal lowering
  details;
- docs name the owner repo for every feature and record remaining boundary
  risks before a local branch is considered PR-ready.

Related issues:

- {doc}`palace-config-ownership`
- {doc}`gplugins-boundary`
- {doc}`material-schema-boundary`
