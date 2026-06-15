# Source-Backed Interface Presets

**Repo:** `orpen-sc-pdk`, `gsim`

Public MA/MS/SA dielectric-interface presets need a source-selection and
default-selection contract before they become PDK data.

Problem:

- private NCUAS workflows already use named MA/MS/SA interface-loss presets and
  automatic assignment helpers;
- the public PDK now validates caller-supplied interface preset records and
  requires explicit source/provenance strings;
- the public PDK intentionally keeps `tech.interface_preset_records` empty
  until source-backed values and default-selection rules are accepted;
- `gsim` already owns reusable `DielectricInterfaceSpec`, assignment,
  material-kind classification, Palace config emission, and report joins, so
  OrPen should not grow a parallel Palace runtime.

Proposed path:

- keep public source review in
  {doc}`../papers/surface-loss-participation`;
- extract candidate values only from public sources, recording whether each
  thickness, permittivity/material, and loss tangent is measured, fitted,
  assumed, or scaled;
- keep public preset records in `orpen-sc-pdk` because they are process and
  material data;
- keep assignment, classification, config generation, material resolution, and
  report loading in `gsim`;
- extend `gsim` only for reusable provenance plumbing: caller-supplied
  `preset_name` and `preset_source` should survive in index maps, sidecars, and
  report summaries without writing non-Palace fields into final `config.json`;
- add public default-selection rules only after the source table states which
  records apply to each material-kind pair and geometry family;
- keep public notebooks caller-supplied until those default-selection rules
  exist.

Verified local changes:

- `orpen-sc-pdk` exposes `tech.interface_preset_records` as an empty-by-default
  public table;
- `validate_interface_preset_records()` rejects caller-supplied records without
  explicit source/provenance strings;
- `get_gsim_dielectric_interface_preset_kwargs()` adapts validated records into
  `gsim.palace.mesh.postprocessing.DielectricInterfaceSpec` keyword arguments
  without importing `gsim` into the base PDK package;
- public tests prove caller-supplied source-backed records can flow through
  exact assignment, material-kind classification, Palace config generation,
  material-overlay resolution, and dielectric-interface report loading;
- local `gsim` now preserves caller-supplied `preset_name` and `preset_source`
  in `palace_index_map.json` and exposes them through
  `load_dielectric_interface_summary()` and surface-loss summaries without
  writing non-Palace fields into final `config.json`;
- `orpen-sc-pdk` now passes validated preset name/source metadata into
  `gsim.palace.mesh.postprocessing.DielectricInterfaceSpec` kwargs and
  verifies the metadata can be loaded back from public interface report rows;
- the surface-loss paper board now lists candidate public sources and extracted
  review rows for CPW `MA`/`MS`/`SA` taxonomy, assumed/scaled Wenner-style
  records, fitted Woods-style interface-loss candidates, transmon validation
  targets, and uncertainty-aware CPW interpretation.
- `scripts/fixtures/public_interface_preset_review_queue.json` mirrors that
  public source-review queue as structured evidence, including source IDs,
  candidate roles, owner repo, `gsim` handoff path, default status, and
  promotion gates without populating `tech.interface_preset_records`;
- the public helper-node inventory and notebook coverage matrix now record the
  source-backed preset promotion gate explicitly: public workflows stay
  caller-supplied until accepted MA/MS/SA preset records, process scope, and
  default-selection rules are approved.
- `notebooks/src/public_simulation_inventory.py` displays the source and
  candidate review tables, so MA/MS/SA promotion status is notebook-visible
  alongside the helper-node, representative-notebook, goal-audit, and `gsim`
  boundary-review evidence.
- `scripts/public_palace_smoke_evidence.py` now builds public thin-film
  conductor-sheet proxy evidence: public `Al` sheet interfaces adjacent to
  public `air` and `silicon` material names generate separate caller-supplied
  `MA` and `MS` dielectric-interface specs through `gsim` material-kind
  classification, config generation, index-map writing, and
  `load_dielectric_interface_summary()` without adding public defaults.

Remaining slices:

- add accepted-candidate tests after the candidate IDs and process scope are
  approved for `tech.interface_preset_records`;
- decide whether any candidate should become a public PDK default or stay
  caller-selected only;
- add a public default-selection map only after candidate records are accepted;
- wire material-kind interface classification into public workflow examples
  only after the public default-selection map exists.

Acceptance checks:

- no private NCUAS preset names or private run evidence appear in public docs;
- public records keep source/provenance visible;
- public defaults are not inferred from private notebook heuristics;
- `gsim` remains the owner of solver-side assignment, config, and reports;
- OrPen remains the owner of public process/material preset data.

Related features:

- {doc}`../features/material-db-overlay`
- {doc}`../features/surface-q-index-mapping`
- {doc}`../features/problem-type-notebook-suite`
