# Surface-Q Index Mapping

**Target:** `gsim` with `orpen-sc-pdk` metadata

**Status:** candidate

Surface-Q and participation reports need stable mapping from solver surfaces
back to PDK layer semantics.

The PDK should expose public layer/material naming. `gsim` should own the
solver-side mapping and report generation logic.

Required mapping chain:

- public PDK layer/material role;
- meshwell CAD/XAO physical name and interface identity;
- gsim mesh role manifest entry;
- Palace attribute or postprocessing index;
- report row for participation, loss, or surface-Q.

Acceptance direction:

- index maps are generated from solver-side manifests rather than ad hoc report
  parsing;
- the same map supports config generation, EPR reporting, and surface-Q
  reporting;
- private consumers can add layout-specific labels without changing public role
  names.

Current public baseline:

- local `gsim` commit `bbd74fe` adds
  `gsim.palace.resolve.derived.materials.load_dielectric_interface_summary()`,
  which joins
  `Boundaries.Postprocessing.Dielectric` config rows back to
  `palace_index_map.json` physical names;
- composed Eigenmode reports expose those configured interface rows through
  `EigenmodeReport.dielectric_interfaces`;
- local `gsim` commit `f12312c` derives `surface_loss` and `loss_budget`
  tables from `surface-Q.csv`, configured interface metadata, and mode
  frequency, so gamma/T1 columns are available when the Eigenmode frequency is
  known;
- local `gsim` commit `fbb19d1` reuses the same surface-Q/interface mapping in
  the Electrostatic report path reached through
  `resolve_palace_result(...).load_report()`, preserving Electrostatic
  source-index samples and deriving gamma/T1 columns only from an explicit
  caller-provided `frequency_ghz`;
- local `gsim` commit `1da6783` adds material-overlay resolution provenance for
  dielectric interface rows, so surface-loss reports can show whether the
  interface permittivity/loss fields came from a public PDK material record;
- public OrPen evidence and notebook fixtures now exercise the index-map contract
  through
  `gsim.palace.resolve.loaders.index_maps.load_postprocessing_index_map()`,
  showing forward Palace section/index lookup, reverse physical-name lookup,
  and attribute lookup for Driven port surfaces, Eigenmode absorbing/surface
  rows, and Electrostatic terminal rows;
- automatic public interface presets are still not part of the PDK material
  contract.

Related issue:

- [../issues/cad-mesh-identity-provenance](../issues/cad-mesh-identity-provenance.md)
