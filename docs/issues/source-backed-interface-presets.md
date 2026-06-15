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
  `gsim.palace.mesh.DielectricInterfaceSpec` keyword arguments without importing
  `gsim` into the base PDK package;
- public tests prove caller-supplied source-backed records can flow through
  exact assignment, material-kind classification, Palace config generation,
  material-overlay resolution, and dielectric-interface report loading;
- local `gsim` now preserves caller-supplied `preset_name` and `preset_source`
  in `palace_index_map.json` and exposes them through
  `load_dielectric_interface_summary()` and surface-loss summaries without
  writing non-Palace fields into final `config.json`;
- `orpen-sc-pdk` now passes validated preset name/source metadata into
  `gsim.palace.mesh.DielectricInterfaceSpec` kwargs and verifies the metadata
  can be loaded back from public interface report rows;
- the surface-loss paper board now lists candidate public sources for CPW
  `MA`/`MS`/`SA` taxonomy, extracted interface-loss values, transmon
  validation targets, and uncertainty-aware CPW interpretation.

Remaining slices:

- extract a public candidate-value table from the selected sources, with one
  row per role/source/process assumption;
- add tests that accept only records with explicit source strings and public
  material names or explicit permittivity;
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
