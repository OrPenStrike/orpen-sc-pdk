# OrPen package usage knowledge

OrPen supplies public PDK facts, reusable components and layout authoring,
semantic inspection, and public Component Simulation notebook sources. These
guides describe the package shipped with them. Use the installed distribution
version and resource digests when recording which instructions were consumed;
the current website or a neighboring checkout may describe different bytes.

## Canonical resource inventory

| Resource | Editable source | Scope and status |
| --- | --- | --- |
| Component authoring | `docs/public-pdk-examples/component-authoring.md` | Available: activation, discovery, public geometry, ports, units and preview |
| Semantic inspection | `docs/usage/semantic-inspection.md` | Available: concept versus artifact inspection and reproducible inspection plates |
| Component Simulation notebooks | `docs/usage/component-simulation-notebooks.md` | Available examples; run results retain their individual diagnostic or historical status |
| Publication pairing | `docs/docs-publishing.md` | Available: canonical QMD inputs, derived IPYNB, output-preserving checks |
| Process and material APIs | `orpen_sc_pdk/tech.py`, `orpen_sc_pdk/materials.py`, `orpen_sc_pdk/materials.json` | Canonical source: structured PDK records; see the authoring guide |
| Public examples | `notebooks/src/ComponentSimulation/`, `notebooks/src/CrossSectionSimulation/`, `notebooks/src/Tools/` | Canonical example inputs; never evidence that a new run has succeeded |

The guides and examples are the editable authorities. Offline packaging must
copy or derive resources from these sources, not maintain another editable
instruction set. Raw run folders, executed outputs, credentials and local
environment configuration are not usage resources.

## Prerequisites and boundaries

The public core needs the Python and GDSFactory versions declared by this
distribution. GDSFactory+ is an optional design/editing/viewer integration;
core PDK use does not require the commercial extra. A live viewer and a solver
installation are not prerequisites for reading installed knowledge.

The source-authority chain is:

```text
OrPen material/layer/stack facts + canonical component semantics
-> generic scgsim.sgb
-> SCGSim solver runtime, returned results and reports
```

For simulation API signatures, backend prerequisites, failure behavior and
supported runtime capabilities, read the knowledge bundle belonging to the
installed `scgsim` distribution. If that bundle is unavailable, report that
fact and consult its matching version documentation; do not import a solver
to discover documentation or infer support from an OrPen example. OrPen's
examples show consumer placement, not a second SCGSim API specification.

An optional MCP reader exposes installed resources; OrPen has no MCP runtime
dependency. Knowledge availability does not imply license availability,
numerical convergence, fabrication qualification or scientific acceptance.
