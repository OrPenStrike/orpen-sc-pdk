# Ecosystem Workspace

Keep each repository focused on one authority:

| Repository | Responsibility |
| --- | --- |
| `orpen-sc-pdk` | Public process layers, layer stack, material records, components, routing/layout helpers, and public simulation notebooks. |
| `scgsim` | In-tree Semantic Geometry Builder Core, Palace/AEDT backends, mesh/config generation, handoff, resolve, and reports. |
| Private layout projects | Private components, chip assemblies, private notebook sources, inputs, and run evidence. |
| `gplugins` | Generic GDSFactory plugin capability. |

The normal consumer route installs `orpen-sc-pdk` and the required SCGSim
backend. A local checkout of a legacy solver-compatibility package or external
Semantic Geometry Builder is not part of the runtime dependency graph.

```bash
uv sync -p 3.12 --group palace-notebooks
uv sync -p 3.12 --group aedt-notebooks
```

OrPen supplies structured PDK facts to SCGSim. SCGSim must preserve those facts
through geometry, mesh/config, handoff, resolve, and reporting rather than
reconstructing semantic identity from names or bounding boxes.

Private layout/IP stays in the private project. Public notebooks in OrPen may
use only publication-safe components and parameters.
