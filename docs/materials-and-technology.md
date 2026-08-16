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

SCGSim consumes these structured records directly. OrPen does not export a
legacy solver-specific overlay and does not own Palace or AEDT lowering.

For AEDT, a declared superconducting record lowers to PEC. A non-superconducting
record uses its explicit AEDT library name. Missing or conflicting backend
identity fails closed. Palace continues to consume the numerical PDK facts
without changing the source material record.

Layer names, z positions, thicknesses, and material references live in the
public `LAYER_STACK`. Solver-specific physical groups, configs, material
assignment, provenance, and reports belong in SCGSim.
