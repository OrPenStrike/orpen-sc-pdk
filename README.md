# orpen-sc-pdk

`orpen-sc-pdk` is OrPenStrike's public superconducting quantum/RF base PDK for
GDSFactory. It keeps public process semantics, reusable public cells, docs, and
ecosystem contribution surfaces reviewable while private layout/IP stays in a
private GF+ project.

The PDK owns `LAYER`, `LAYER_STACK`, `LAYER_VIEWS`, material/process semantics,
public CPW cross-sections, public cells, public docs, and the base-PDK contract
used by private GF+ projects. Private projects own private cells, chip
assemblies, parameters, private layout inputs, notebooks, and private run
evidence.

## Usage Workflow

Normal users should install the public PDK through a package manager route:
released packages, Git URLs, or a private package index.

```bash
uv init scq-layout-consumer
cd scq-layout-consumer
uv add "orpen-sc-pdk @ git+https://github.com/OrPenStrike/orpen-sc-pdk.git"
```

Activate the public PDK and build a public component:

```python
import orpen_sc_pdk
from orpen_sc_pdk.cells import cpw_straight

orpen_sc_pdk.activate()

component = cpw_straight(length=500, signal_width=10, gap=6)
component.show()
```

Private layouts should live in a private GF+ project, such as
`OrPenStrike/NCUAS_SC_Qubit_Design`, with `orpen-sc-pdk` installed as its base
PDK. For GF+ preview, open the private repo as the active VSCode/GF+ project;
private cells are Project cells and `orpen-sc-pdk` is the Base PDK.

## Contribution Workflow

Use editable sibling checkouts only when changing `orpen-sc-pdk`, `gsim`,
`gplugins`, or the private layout project together:

```toml
[dependency-groups]
ecosystem-dev = [
  "gsim",
  "gplugins",
]

[tool.uv.sources]
orpen-sc-pdk = { path = "../../orpen_sc_pdk", editable = true }
gsim = { path = "../../GDSFactory_Community_Workbench/gsim", editable = true, group = "ecosystem-dev" }
gplugins = { path = "../../GDSFactory_Community_Workbench/gplugins", editable = true, group = "ecosystem-dev" }
```

```bash
cd SCQ_Design/NCUAS_SC_Qubit_Design/NCU_AS_SC_Qubit_Design
uv sync -p 3.12 --extra <extra> --group <group>
```

Available extras and groups:

| Kind | Name | Purpose |
| --- | --- | --- |
| extra | `dev` | Test and lint tooling such as `pytest` and `ruff`. |
| extra | `gdsfactoryplus` | GF+ local development and preview dependencies. |
| group | `docs` | Sphinx, MyST-NB, Jupytext, notebook conversion, and docs build tooling. |
| group | `ecosystem-dev` | Editable sibling checkouts for `gsim` and `gplugins`. |

For the full local contributor environment, install the development, GF+,
documentation, and ecosystem dependencies together. Do not run separate sync
commands for docs and GF+ work; each `uv sync` should include every extra and
group the active environment needs:

```bash
uv sync -p 3.12 --extra dev --extra gdsfactoryplus --group docs --group ecosystem-dev
```

Open `NCU_AS_SC_Qubit_Design` as the active VSCode/GF+ folder and select
`NCU_AS_SC_Qubit_Design/.venv/bin/python3`.

## Repository Boundaries

- `orpen-sc-pdk`: public process, material records, technology/layerstack,
  public CPW cross-sections, public cells, public layout helpers, docs, and
  examples.
- private layout project: private cells, design factories, layout parameters,
  private layout inputs, notebooks, and private run evidence.
- `gsim`: reusable Palace/EPR/reporting workflow, benchmarks, and solver
  orchestration.
- `gplugins`: reusable GDSFactory plugin capability.

Do not put private chip designs directly in this repository.

## Documentation

Build the static HTML docs with:

```bash
just docs
```

Serve the built docs locally with:

```bash
just serve-docs
```

The default local URL is:

```text
http://localhost:8000
```

If port 8000 is already in use, pass a different port:

```bash
just serve-docs 8010
```

The `serve-docs` target builds the docs first, then serves
`docs/_build/html` with Python's built-in HTTP server.
