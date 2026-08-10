# OrPen SC PDK

<p align="center">
  <img alt="Status: public PDK" src="https://img.shields.io/badge/status-public%20PDK-0f766e">
  <img alt="Python 3.12+" src="https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white">
  <img alt="GDSFactory 9.43" src="https://img.shields.io/badge/GDSFactory-9.43-4B8BBE">
  <img alt="GDSFactory+ ready" src="https://img.shields.io/badge/GDSFactory%2B-ready-7c3aed">
  <img alt="Docs: GitHub Pages" src="https://img.shields.io/badge/docs-GitHub%20Pages-0f766e">
  <img alt="License" src="https://img.shields.io/github/license/OrPenStrike/orpen-sc-pdk">
</p>

`orpen-sc-pdk` is OrPenStrike's public superconducting quantum/RF base PDK for
[gdsfactory](https://gdsfactory.github.io/gdsfactory/). It provides public
process layers, layer stack semantics, CPW cross-sections, passive layout cells,
flip-chip support geometry, routing helpers, and public simulation layout demos.

The boundary is deliberate: this repository contains reusable public PDK
infrastructure. Private chip designs, private qubit geometry, private parameters,
and notebook run evidence belong in private layout projects that consume this
PDK as their base PDK.

## Highlights

- **Public process contract** — `LAYER`, `LAYER_STACK`, `LAYER_VIEWS`,
  material records, connectivity, and face-aware superconducting process layers.
- **Parametric public cells** — CPW traces, resonators, launchers, tapers,
  indium bumps, dicing edges, capacitors, and benchmark geometries.
- **Flip-chip layout demos** — public resonator-based examples for distance,
  keepout, and 8-direction routing workflows.
- **Simulation metadata** — mesh-port metadata for downstream Palace, Q2D, and
  layout-to-simulation assembly.
- **GDSFactory+ integration** — registered public cells are available through
  the active PDK and can be built from GF+.

## Component Gallery

These previews are generated from the actual public `@gf.cell` factories in
this repo.

### Passive Building Blocks

| CPW Resonator | Interdigital Capacitor | Martinis 2022 Ribbon Capacitor |
| :---: | :---: | :---: |
| `resonator` | `interdigital_capacitor` | `martinis2022_differential_ribbon_capacitor` |
| <img src="docs/_static/images/components/resonator.svg" alt="CPW resonator" width="260"> | <img src="docs/_static/images/components/interdigital_capacitor.svg" alt="Interdigital capacitor" width="260"> | <img src="docs/_static/images/components/martinis2022_differential_ribbon_capacitor.svg" alt="Martinis ribbon capacitor" width="260"> |

| Launcher | Indium Ground Field |
| :---: | :---: |
| `launcher` | `indium_ground` |
| <img src="docs/_static/images/components/launcher.svg" alt="Launcher" width="260"> | <img src="docs/_static/images/components/indium_ground.svg" alt="Indium ground field" width="260"> |

### Public Flip-Chip And Routing Layouts

[QPDK](https://github.com/gdsfactory/quantum-rf-pdk) shows complete
qubit-oriented examples; OrPen SC PDK keeps private qubit IP out of the public
repo and uses public resonator geometry for open routing and flip-chip
demonstrations.

| Flip-Chip Distance | Global Purcell Filter Demo Chip |
| :---: | :---: |
| `sim_flip_chip_distance` | `global_purcell_filter_demo_chip` |
| <img src="docs/_static/images/components/sim_flip_chip_distance.svg" alt="Flip-chip distance layout" width="320"> | <img src="docs/_static/images/components/global_purcell_filter_demo_chip.svg" alt="Global Purcell Filter Demo Chip" width="320"> |

| Resonator Keepout Routing | Global Keepout Routing |
| :---: | :---: |
| `sim_flip_chip_distance_keepout_routing_demo` | `sim_flip_chip_distance_keepout_global_routing_demo` |
| <img src="docs/_static/images/components/sim_flip_chip_distance_keepout_routing_demo.svg" alt="Resonator keepout routing demo" width="320"> | <img src="docs/_static/images/components/sim_flip_chip_distance_keepout_global_routing_demo.svg" alt="Global keepout routing demo" width="320"> |

## Quick Start

Install the public PDK from Git:

```bash
uv init scq-layout-consumer
cd scq-layout-consumer
uv add "orpen-sc-pdk @ git+https://github.com/OrPenStrike/orpen-sc-pdk.git"
```

Activate the PDK and build a public cell:

```python
import gdsfactory as gf
import orpen_sc_pdk

orpen_sc_pdk.activate()

component = gf.get_component("resonator", length=3500)
component.show()
```

Build one of the public flip-chip routing demos:

```python
import gdsfactory as gf
import orpen_sc_pdk

orpen_sc_pdk.activate()

demo = gf.get_component("sim_flip_chip_distance_keepout_global_routing_demo")
demo.show()
```

## Repository Boundaries

| Repository | Owns |
| --- | --- |
| `orpen-sc-pdk` | Public process semantics, public cells, public layout helpers, docs, and base-PDK contracts. |
| Private layout projects | Private cells, private chip assemblies, private layout inputs, notebooks, and run evidence. |
| `gsim` | Reusable Palace/EPR/reporting workflow, benchmarks, and solver orchestration. |
| `gplugins` | Reusable gdsfactory plugin capability. |

Do not put private chip designs directly in this repository.

## Contributor Setup

Use the ecosystem development group when changing `orpen-sc-pdk` and `gsim`
together:

```toml
[dependency-groups]
ecosystem-dev = [
  "gsim",
  "gplugins",
]

[tool.uv.sources]
gsim = { path = "../GDSFactory_Community_Workbench/gsim", editable = true, group = "ecosystem-dev" }
```

For the full local contributor environment:

```bash
uv sync -p 3.12 --all-extras
```

Run the focused validation checks:

```bash
uv run ruff check .
uv run ruff format . --check
uv run pytest
```

## Documentation

Build the static HTML docs:

```bash
just docs
```

The Quarto site includes searchable reference pages, rendered notebook cells
and outputs, and a browser-only interactive viewer for public layout exports.

Serve the built docs locally:

```bash
just serve-docs
```

The default local URL is `http://localhost:8000`. If port 8000 is already in
use, pass another port, for example `just serve-docs 8010`.
