# Materials And Technology

`orpen-sc-pdk` is the authority for public process facts. Its material database
records material identity, aliases, generic material kind, superconducting
status, Palace numerical properties, and the AEDT library identity where one is
authoritative.

The public copy-returning API is:

- `get_material_records()`;
- `get_material_alias_records()`;
- `get_interface_preset_records()`;
- the corresponding `validate_*` helpers.

The material database `orpen_sc_pdk/materials.json` currently contains six
interface presets, returned as copies by `get_interface_preset_records()`:
`Woods2019_Si_MA`, `Woods2019_Si_MS`, `Woods2019_Si_SA`, and
`LiteratureCentral_MA`, `LiteratureCentral_MS`, `LiteratureCentral_SA`.
Their fields and provenance belong to that database, not the empty legacy
`tech.interface_preset_records` dictionary. These are source-backed model
conventions/candidates, not measured properties for every consumer process or
automatic selection rules. A consumer selects records explicitly and retains
their source identity.

SCGSim consumes these structured records directly. OrPen does not export a
legacy solver-specific overlay and does not own Palace or AEDT lowering.

For AEDT, a declared superconducting record lowers to PEC. A non-superconducting
record uses its explicit AEDT library name. Missing or conflicting backend
identity fails closed. Palace continues to consume the numerical PDK facts
without changing the source material record.

Layer names, z positions, thicknesses, and material references live in the
public `LAYER_STACK`. Solver-specific physical groups, configs, material
assignment, provenance, and reports belong in SCGSim.
