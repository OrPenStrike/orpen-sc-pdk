# Source-Backed Interface Presets

**Repo:** `orpen-sc-pdk`, `gsim`

Public MA/MS/SA dielectric-interface presets may be PDK material data when
they are source-backed. Automatic default selection still needs an explicit
policy before notebooks or helpers infer presets for users.

Problem:

- private NCUAS workflows already use named MA/MS/SA interface-loss presets and
  automatic assignment helpers;
- the public PDK now exposes source-backed interface preset records from
  `orpen_sc_pdk/materials.json` and validates explicit source/provenance
  strings;
- the public PDK still does not infer default MA/MS/SA assignment rules from
  private workflow heuristics;
- `gsim` already owns reusable `DielectricInterfaceSpec`, assignment,
  material-kind classification, Palace config emission, and report joins, so
  OrPen should not grow a parallel Palace runtime.

Proposed path:

- keep public source review in
  [../papers/surface-loss-participation](../papers/surface-loss-participation.md);
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
- add broader public default-selection rules only after the source table states
  which records apply to each material-kind pair and geometry family;
- keep public notebooks explicitly selected until those default-selection rules
  exist.

Verified local changes:

- `orpen-sc-pdk` exposes source-backed interface preset records through
  `get_interface_preset_records()` from `orpen_sc_pdk/materials.json`;
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
  promotion gates without enabling automatic default selection;
- the public helper-node inventory and notebook coverage matrix now record the
  source-backed preset promotion gate explicitly: public workflows stay
  explicitly selected until broader MA/MS/SA process scope and
  default-selection rules are approved.
- `notebooks/src/public_simulation_inventory.py` displays the source and
  candidate review tables, so MA/MS/SA promotion status is notebook-visible
  alongside the helper-node, representative-notebook, goal-audit, and `gsim`
  boundary-review evidence.
- `scripts/public_palace_smoke_evidence.py` now writes
  `public_interface_preset_promotion_gate_evidence.json`, which records
  candidate readiness, missing acceptance decisions, default-selection status,
  and the OrPen/`gsim` owner boundary before any source-backed row can become
  an inferred public default.
- `notebooks/src/public_simulation_inventory.py` displays the same promotion
  gate table, keeping accepted-candidate ID, process scope, default-selection
  rule, and public-default decision gaps visible in notebook review.
- `scripts/public_palace_smoke_evidence.py` now builds public thin-film
  conductor-sheet proxy evidence: public `Al` sheet interfaces adjacent to
  public `air` and `silicon` material names generate separate caller-supplied
  `MA` and `MS` dielectric-interface specs through `gsim` material-kind
  classification, config generation, index-map writing, and
  `load_dielectric_interface_summary()` without adding public defaults.

Remaining slices:

- add accepted-candidate tests after candidate IDs and process scope are
  approved for automatic default selection;
- decide whether any candidate should become a public PDK default or stay
  caller-selected only; the promotion gate currently records every interface
  candidate as `awaiting_public_policy`;
- add a public default-selection map only after candidate records are accepted;
- broaden material-kind interface classification beyond the resonator example
  only after the public default-selection map exists.

Acceptance checks:

- no private NCUAS preset names or private run evidence appear in public docs;
- public records keep source/provenance visible;
- public defaults are not inferred from private notebook heuristics;
- `gsim` remains the owner of solver-side assignment, config, and reports;
- OrPen remains the owner of public process/material preset data.

Related features:

- [../features/material-db-overlay](../features/material-db-overlay.md)
- [../features/surface-q-index-mapping](../features/surface-q-index-mapping.md)
- [../features/problem-type-notebook-suite](../features/problem-type-notebook-suite.md)
