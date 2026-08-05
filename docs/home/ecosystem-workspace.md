# Ecosystem Workspace And Contribution Loop

`orpen-sc-pdk` is the public base PDK for superconducting quantum/RF layout
work. It owns public process semantics, layer views, layer stack, public cells,
and public docs. Private layout projects use it as their base PDK while keeping
Primary Layout, private cells, chip assemblies, notebooks, private layout inputs,
and run evidence private.

## Workspace Shape

Use sibling checkouts so each repo keeps its own ownership boundary:

```text
SCQ_Design/
  orpen_sc_pdk/
  GDSFactory_Community_Workbench/
    gsim/
    gplugins/
    meshwell/
  NCUAS_SC_Qubit_Design/
    KQC/
    scq_layout/
    NCU_AS_SC_Qubit_Design/
  palace/        # optional fork of awslabs/palace for solver-source work
```

:::{list-table}
:widths: 25 75
:header-rows: 1

* - Repo or folder
  - Responsibility
* - `orpen_sc_pdk`
  - Public base PDK checkout for `orpen-sc-pdk`: `LAYER`, `LAYER_STACK`,
    `LAYER_VIEWS`, process/material semantics, public CPW cross-sections, public
    cells, public layout helpers, docs, and examples.
* - `NCU_AS_SC_Qubit_Design`
  - Private GF+ project: Primary Layout, private cells, chip assemblies, private
    parameters, private layout inputs, private notebooks, and private run evidence.
* - `gsim`
  - Reusable solver workflow, Palace/EPR/reporting capability, benchmark surfaces,
    and material workflow adapters.
* - `gplugins`
  - Generic GDSFactory plugin capability that should not be PDK-specific.
* - `meshwell`
  - Upstream mesh workflow fork used for mesh experiments and possible upstream
    contribution.
* - Palace source fork
  - Optional solver-source lane for Palace-side output, postprocessing, or runtime
    behavior that cannot be handled cleanly in `gsim`.
:::

## Private GF+ Project Route

Open `NCU_AS_SC_Qubit_Design` as the active VSCode/GF+ project. Its
`pyproject.toml` should identify the private project and public base PDK:

```toml
[tool.gdsfactoryplus]
name = "ncuas_designs"

[tool.gdsfactoryplus.pdk]
name = "orpen_sc_pdk"
```

With this shape, private cells are GF+ Project cells and `orpen-sc-pdk` is the
Base PDK. The private repo should import public process semantics from
`orpen_sc_pdk`; it should not define its own public `LAYER_STACK`,
`LAYER_VIEWS`, layer map, CPW cross-sections, launcher, or interdigital
capacitor implementation.

## Environment Routes

### 1. GF+ Layout Previewable Only

Use this when the private repo only needs GF+ to list and build private layouts:

```bash
cd SCQ_Design/NCUAS_SC_Qubit_Design/NCU_AS_SC_Qubit_Design
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

## Ownership Boundary

- `orpen-sc-pdk` owns public `LAYER`, `LAYER_VIEWS`, `LAYER_STACK`,
  material/process semantics, public CPW cross-sections, public reusable layout
  helpers, public cells, and public docs.
- `NCU_AS_SC_Qubit_Design` owns private GF cells, chip assemblies, private
  parameters, private-only layout code, private layout inputs, notebooks,
  and private run evidence.
- `gsim` consumes components, public PDK layer stack, and public-safe metadata
  at its solver workflow boundary.
- `gplugins` owns generic plugin capability that is not specific to this PDK.

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
- public cells and publication-safe notebooks;
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
| Public SCQ material records, CPW cross-sections, layout helpers, and public cells | `orpen-sc-pdk` |
| Private cells, Primary Layout factories, private layout inputs | `NCU_AS_SC_Qubit_Design` |
| Private GF+ project setup | `NCU_AS_SC_Qubit_Design` |
| Reusable Palace/EPR/reporting workflow | `gsim` |
| Reusable benchmark and solver cost workflow | `gsim` |
| Palace-side output, postprocessing, CSV/report internals, solver runtime behavior | Palace source fork, then `awslabs/palace` when upstreamable |
| Generic GDSFactory plugin integration | `gplugins` |
