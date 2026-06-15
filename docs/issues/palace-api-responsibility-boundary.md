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

Open API-surface follow-ups:

- review `gsim.palace.mesh.__all__` for low-level manifest/index-map builders
  that may be advanced submodule APIs rather than top-level notebook APIs;
- split `gsim` Palace API docs so mesh generation controls are separate from
  mesh artifacts, manifests, postprocessing index maps, and reportability;
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
