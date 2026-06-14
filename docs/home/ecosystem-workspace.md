# Ecosystem Workspace And Contribution Loop

`orpen-sc-pdk` is the public base PDK for superconducting quantum/RF layout
work. It owns public process semantics, layer views, layer stack, public cells,
and public docs. Private layout projects use it as their base PDK while keeping
Primary Layout, private cells, chip assemblies, notebooks, GDS dependencies,
and run evidence private.

## Workspace Shape

Use sibling checkouts so each repo keeps its own ownership boundary:

```text
SCQ_Design/
  GDSFactory_Community_Workbench/
    repos/
      orpen-sc-pdk/
        orpen_sc_pdk/
          cells/
            privates/
              ncuas-sc-qubit-design/   # optional ignored local mount
      gsim/
      gplugins/
      quantum-rf-pdk/
  NCUAS_SC_Qubit_Design/
    ncuas-sc-qubit-design/
    palace/        # optional fork of awslabs/palace for solver-source work
```

| Repo or folder | Responsibility |
| --- | --- |
| `orpen-sc-pdk` | Public base PDK: `LAYER`, `LAYER_STACK`, `LAYER_VIEWS`, process/material semantics, public CPW cross-sections, public cells, public layout helpers, docs, and optional ignored-mount import hook. |
| `ncuas-sc-qubit-design` | Private GF+ project: Primary Layout, private cells, chip assemblies, private parameters, GDS dependencies from private designs, private notebooks, and private run evidence. |
| `gsim` | Reusable solver workflow, Palace/EPR/reporting capability, benchmark surfaces, and material workflow adapters. |
| `gplugins` | Generic GDSFactory plugin capability that should not be PDK-specific. |
| `quantum-rf-pdk` | Optional adjacent public PDK contribution target; it is not upstream of `orpen-sc-pdk` and not part of the normal NCUAS private layout flow. |
| Palace source fork | Optional solver-source lane for Palace-side output, postprocessing, or runtime behavior that cannot be handled cleanly in `gsim`. |

## Private GF+ Project Route

Open `ncuas-sc-qubit-design` as the active VSCode/GF+ project. Its
`pyproject.toml` should identify the private project and public base PDK:

```toml
[tool.gdsfactoryplus]
name = "ncuas_designs"

[tool.gdsfactoryplus.pdk]
name = "orpen_sc_pdk"
```

With this shape, private cells are GF+ Project cells and `orpen-sc-pdk` is the
base PDK. The private repo should import public process semantics from
`orpen_sc_pdk`; it should not define its own public `LAYER_STACK`,
`LAYER_VIEWS`, layer map, CPW cross-sections, launcher, or interdigital
capacitor implementation.

## Environment Routes

### 1. GF+ Layout Previewable Only

Use this when the private repo only needs GF+ to list and build private layouts:

```bash
cd SCQ_Design/NCUAS_SC_Qubit_Design/ncuas-sc-qubit-design
uv sync -p 3.12 --extra gdsfactoryplus
```

This installs the private project, editable `orpen-sc-pdk`, and GDSFactory+.

### 2. GF+ Preview With Package-Manager `gsim` / `gplugins`

Use this when simulation/plugin packages should come from released packages,
Git sources, or a private index:

```bash
uv sync -p 3.12 --extra gdsfactoryplus --extra ecosystem --no-sources
```

This is the package-manager route. It requires `orpen-sc-pdk`, `gsim`, and
`gplugins` to be resolvable without local editable source overrides.

### 3. GF+ Preview With Editable `gsim` / `gplugins`

Use this only for contribution or cross-repo development:

```bash
uv sync -p 3.12 --extra gdsfactoryplus --group ecosystem-dev
```

Editable `gsim` and `gplugins` are contribution tools, not part of the minimal
layout preview environment.

### 4. Optional Adjacent PDK Development

Use `quantum-rf-pdk` only when explicitly contributing to or comparing with that
PDK:

```bash
uv sync -p 3.12 --extra gdsfactoryplus --group ecosystem-dev --group adjacent-pdk-dev
```

The checkout folder is `quantum-rf-pdk`, but the Python package metadata name is
`qpdk`.

## Optional Public-PDK Mount

The primary GF+ preview route is the private project route above. A local
ignored mount under the public PDK can still be used for experiments that need
private source below the active public PDK checkout:

```bash
cd SCQ_Design/GDSFactory_Community_Workbench/repos/orpen-sc-pdk
mkdir -p orpen_sc_pdk/cells/privates
git clone git@github.com:OrPenStrike/NCUAS_SC_Qubit_Design.git \
  orpen_sc_pdk/cells/privates/ncuas-sc-qubit-design

export ORPEN_SC_PDK_PRIVATE_LAYOUT_REPO=ncuas-sc-qubit-design
export ORPEN_SC_PDK_PRIVATE_LAYOUT_CELLS=ncuas_designs.cells
export ORPEN_SC_PDK_PRIVATE_LAYOUT_XSECTIONS=ncuas_designs.cells.xsections
```

`orpen_sc_pdk/cells/privates/*` is ignored. This mount is not a submodule, not a
public dependency contract, and not required for public CI. Public docs and CI
must remain valid without access to private source.

## Ownership Boundary

- `orpen-sc-pdk` owns public `LAYER`, `LAYER_VIEWS`, `LAYER_STACK`,
  material/process semantics, public CPW cross-sections, public reusable layout
  helpers, public cells, public docs, and public samples.
- `ncuas-sc-qubit-design` owns private GF cells, chip assemblies, private
  parameters, private-only cross-sections, GDS dependencies from private
  designs, notebooks, and private run evidence.
- `gsim` consumes components, public PDK layer stack, and public-safe metadata
  at its solver workflow boundary.
- `gplugins` owns generic plugin capability that is not specific to this PDK.
- `quantum-rf-pdk` remains an optional adjacent PDK lane.

Do not move private layout/IP into `orpen-sc-pdk`. Do not move public process
semantics back into the private repo.

## Personal Branches And PR Branches

Use a long-lived personal branch as the prototype log:

```bash
git fetch origin
git switch -c i-li-chiu origin/main
```

Keep commits topical and cherry-pickable. A useful prototype commit should be
able to move into a public PR branch without private layout/IP, private
parameters, private notebooks, or private run evidence.

When a public slice is ready, create a clean PR branch from the target upstream
base:

```bash
# In ecosystem forks that track an upstream project:
git fetch upstream
git switch -c features/<topic> upstream/main

# In self-owned repos without an upstream remote:
git fetch origin
git switch -c features/<topic> origin/main

git cherry-pick -x <accepted-public-commit>
```

Use `features/<topic>` or `integration/<topic>` for PR branches. These branches
should contain only public implementation, tests, docs, and public-safe evidence
that reviewers can inspect without access to the private layout repo.

## Public/Private Checklist

Public docs, tests, and examples may include:

- public process and layer semantics;
- public material records and aliases;
- optional ignored-mount import mechanics;
- public cells, public samples, and publication-safe notebooks;
- upstream contribution instructions and public benchmark methodology.

They must not include:

- private qubit or resonator geometry;
- private layout parameters;
- GDS inputs from private designs;
- private notebooks or private run evidence;
- benchmark values from private layouts unless explicitly cleared for
  publication;
- lab-specific implementation details that reveal private layout/IP.

## Where Changes Belong

| Change | Destination |
| --- | --- |
| Layer names, layer views, layer stack, process semantics | `orpen-sc-pdk` |
| Public SCQ material records, CPW cross-sections, layout helpers, and static import hook | `orpen-sc-pdk` |
| Private cells, Primary Layout factories, GDS dependencies from private designs | `ncuas-sc-qubit-design` |
| Private GF+ project setup | `ncuas-sc-qubit-design` |
| Reusable Palace/EPR/reporting workflow | `gsim` |
| Reusable benchmark and solver cost workflow | `gsim` |
| Palace-side output, postprocessing, CSV/report internals, solver runtime behavior | Palace source fork, then `awslabs/palace` when upstreamable |
| Generic GDSFactory plugin integration | `gplugins` |
| Adjacent public PDK comparison/contribution | `quantum-rf-pdk`, when explicitly needed |
