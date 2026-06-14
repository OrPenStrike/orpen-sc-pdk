# orpen-sc-pdk

`orpen-sc-pdk` is OrPenStrike's public superconducting quantum/RF PDK for
GDSFactory. It is the public side of a split architecture: private layout/IP
stays in private layout packages, while public process semantics, examples,
docs, and ecosystem contribution surfaces stay reviewable here.

The PDK owns `LAYER`, `LAYER_STACK`, `LAYER_VIEWS`, material/process semantics,
public cells, public docs, and the base-PDK contract used by private GF+
projects. Private projects own private cells, chip assemblies, parameters, GDS
dependencies from private designs, notebooks, and private run evidence.

## Usage Workflow

Normal users should install the public PDK through a package manager route:
released packages, Git URLs, or a private package index.

```bash
uv init scq-layout-consumer
cd scq-layout-consumer
uv add "orpen-sc-pdk @ git+https://github.com/OrPenStrike/orpen-sc-pdk.git"
uv sync -p 3.12
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
PDK.

```python
import ncuas_designs
from ncuas_designs.cells import as_resonator

ncuas_designs.PDK.activate()
component = as_resonator()
component.show()
```

For GF+ preview, open the private repo as the active VSCode/GF+ project. In that
shape, private cells are Project cells and `orpen-sc-pdk` is the base PDK.

An ignored public-PDK mount remains available only as a local bridge experiment:

```text
orpen-sc-pdk/
  orpen_sc_pdk/
    cells/
      privates/
        ncuas-sc-qubit-design/   # ignored local clone
```

This is not a submodule and not a public dependency contract. The mount only
makes private source available to the local GF+ server for static cell
discovery when the local environment explicitly points to it:

```bash
export ORPEN_SC_PDK_PRIVATE_LAYOUT_REPO=ncuas-sc-qubit-design
export ORPEN_SC_PDK_PRIVATE_LAYOUT_CELLS=ncuas_designs.cells
export ORPEN_SC_PDK_PRIVATE_LAYOUT_XSECTIONS=ncuas_designs.cells.xsections
```

Public CI and public docs must not require it.

## Contribution Workflow

Use editable sibling checkouts when changing `orpen-sc-pdk`, `gsim`, `gplugins`,
or the private layout project together. Keep `quantum-rf-pdk` as an optional
adjacent PDK lane, not part of the normal NCUAS private layout flow.

```toml
[dependency-groups]
ecosystem-dev = [
  "gsim",
  "gplugins",
]
adjacent-pdk-dev = [
  "qpdk",
]

[tool.uv.sources]
orpen-sc-pdk = { path = "../../GDSFactory_Community_Workbench/repos/orpen-sc-pdk", editable = true }
gsim = { path = "../../GDSFactory_Community_Workbench/repos/gsim", editable = true, group = "ecosystem-dev" }
gplugins = { path = "../../GDSFactory_Community_Workbench/repos/gplugins", editable = true, group = "ecosystem-dev" }
qpdk = { path = "../../GDSFactory_Community_Workbench/repos/quantum-rf-pdk", editable = true, group = "adjacent-pdk-dev" }
```

The checkout folder is `quantum-rf-pdk`, but the Python distribution name is
`qpdk`; use it only for adjacent PDK work.

```bash
cd SCQ_Design/NCUAS_SC_Qubit_Design/ncuas-sc-qubit-design
uv sync -p 3.12 --extra gdsfactoryplus --group ecosystem-dev
```

Open `ncuas-sc-qubit-design` as the active VSCode/GF+ folder and select
`ncuas-sc-qubit-design/.venv/bin/python3`.

## Static Private Mount Boundary

The GF+ route is intentionally static:

- private repo exports cells through explicit imports and `__all__`;
- private GF+ project uses `orpen-sc-pdk` as its base PDK;
- optional public ignored mount imports from `orpen_sc_pdk/cells/privates/*`
  only when that local bridge exists;
- `orpen-sc-pdk` owns layer/process/material semantics and the public PDK
  registry;
- `gsim`, `gplugins`, and GF+ do not depend on private repo internals.

Do not put private chip designs directly in this repository.

## Repository Boundaries

- `orpen-sc-pdk`: public process, material records, technology/layerstack,
  public cells, optional GF+ private mount hook, and public examples.
- private layout project: private cells, design factories, layout parameters,
  GDS dependencies from private designs, notebooks, and private run evidence.
- `gsim`: reusable Palace/EPR/reporting workflow, benchmarks, and solver
  orchestration.
- `gplugins`: reusable GDSFactory plugin capability.
- `quantum-rf-pdk`: optional adjacent PDK contribution target, not the upstream
  of `orpen-sc-pdk` and not part of the normal NCUAS private layout flow.

## Documentation

Build the docs locally with:

```bash
uv sync -p 3.12 --group docs --extra dev
just docs
```
