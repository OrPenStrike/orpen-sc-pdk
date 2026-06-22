# Simulation Layer Catalog

The public PDK supplies names and public layout layers that examples can use.
`gsim` still owns how those layers become Palace boundaries, ports, terminals,
and sheets.

## Why This Was Needed

Some public examples need solver-only geometry that should not become a normal
fabrication layer. The Purcell demo is the clearest case: its launcher sheets
are authored in layout and then selected as readout lumped-port boundaries.

The PDK needs a public catalog so examples can say which layer means what
without hard-coding private layer names.

## What gsim Already Had

`gsim` already had port and terminal APIs, including generated sheets from
component ports. It did not own OrPen's public layer naming or demo-cell layer
catalog.

The new PDK-side catalog is therefore only metadata. Lowering that metadata to
Palace config remains a `gsim` responsibility.

## What Changed

Code pointers:

| Area | Path |
| --- | --- |
| Public simulation-layer catalog | `orpen_sc_pdk/simulation/palace_layers.py` |
| Simulation package exports | `orpen_sc_pdk/simulation/__init__.py` |
| Purcell public demo notebooks | `notebooks/src/public_purcell_driven_local_workflow.py`, `notebooks/src/public_purcell_eigenmode_local_workflow.py` |
| Style tests | `tests/test_public_problem_notebook_style.py` |

Boundary change:

- `orpen-sc-pdk` owns public layer names and demo-cell intent.
- `gsim` owns `generate_sheet=False`, port lowering, vector directions, and
  Palace boundary emission.
- Private layout projects own private chip layer decisions.

Related pages:

- {doc}`problem-notebooks`
- {doc}`../gsim-changes/mesh-config-provenance`
