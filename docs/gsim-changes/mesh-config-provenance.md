# Mesh and Config Provenance

Mesh and config artifacts need stable names that survive the trip from layout
to Palace output. Without that identity, reports can show numbers but readers
cannot tell which layout region, interface, port, or terminal produced them.

## Why This Was Needed

The public PDK examples need to explain solver artifacts without publishing
private layouts. That means a reader must be able to inspect generated public
artifacts and answer:

- which physical group was generated;
- which Palace index maps back to which physical name;
- which material record was used for a domain or interface;
- which port or terminal a postprocessing row belongs to.

## What gsim Already Had

`gsim` already had Gmsh mesh generation and Palace config writing. The likely
maintainer intent was that mesh/config generation is preparation for running a
solver, not a separately documented provenance system.

The public PDK needs more traceability. The change keeps generation in `gsim`,
but adds explicit artifact sidecars so examples and tests can inspect identity
without reimplementing config assembly in the PDK.

## What Changed

Code pointers:

| Area | Path |
| --- | --- |
| Mesh generation and validation | `../GDSFactory_Community_Workbench/gsim/src/gsim/palace/mesh/generator.py` |
| Physical groups and geometry metadata | `../GDSFactory_Community_Workbench/gsim/src/gsim/palace/mesh/groups.py` |
| Palace config generation | `../GDSFactory_Community_Workbench/gsim/src/gsim/palace/mesh/config_generator.py` |
| Postprocessing config helpers | `../GDSFactory_Community_Workbench/gsim/src/gsim/palace/mesh/postprocessing.py` |
| Material resolution | `../GDSFactory_Community_Workbench/gsim/src/gsim/palace/materials.py` |

Boundary change:

- `gsim` owns mesh manifests, Palace index maps, config generation, and
  material-resolution sidecars.
- `meshwell` remains the owner of CAD/XAO physical-name conventions.
- `orpen-sc-pdk` only supplies public layer/material names and examples that
  consume the generated artifacts.

Related detailed ledgers:

- [../issues/cad-mesh-identity-provenance](../issues/cad-mesh-identity-provenance.md)
- [../issues/palace-config-ownership](../issues/palace-config-ownership.md)
- [../issues/material-schema-boundary](../issues/material-schema-boundary.md)
