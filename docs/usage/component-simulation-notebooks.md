# Public Component Simulation notebook rules

OrPen owns public example source and its layout/material semantics. Obtain
runtime signatures, backend requirements and failure contracts from the
installed SCGSim knowledge bundle. Examples must consume that public runtime;
they must not supply another parser, renderer, lowering implementation or
simulation pipeline. Reading an example does not require a solver or a license.

## Canonical inputs and publication outputs

The six Kosen2024 sources under
`notebooks/src/ComponentSimulation/Kosen2024_Xmon/` are canonical QMD:

- `palace_route_a_electrostatic.qmd` and `palace_route_b_electrostatic.qmd`;
- `palace_route_a_eigenmode.qmd` and `palace_route_b_eigenmode.qmd`;
- `aedt_q3d.qmd`;
- `electrostatic_boundary_alignment.qmd` (analysis-only comparison).

Their derived IPYNBs live at the matching paths under `notebooks/`. Edit QMD,
including its workflow action and receipt selectors, before deriving IPYNB.
Python cells begin with stable `#| id:` options. Pairing includes Markdown,
code, order, IDs and metadata; execution counts and outputs are allowed only
in the IPYNB. Do not hand-patch an IPYNB to diverge from its canonical input.

Other families retain their existing Python/Jupytext sources and IPYNB pairs:
CPW HFSS/Q3D under `ComponentSimulation/CpwFiniteGround`, Q2D under
`CrossSectionSimulation/CpwFiniteGround`, and the read-only geometry viewer
under `Tools`. Preserve their configured pair and existing cell metadata.
The QMD conversion command does not migrate or synchronize Python pairs.

In a source checkout with Quarto and the docs environment installed:

```bash
just check-notebooks
```

This recursively verifies QMD/IPYNB parity without executing code or changing
saved outputs. `just convert-notebooks` explicitly regenerates clean derived
IPYNBs and therefore must not be used over Human-owned executed outputs.
An output-preserving input edit requires coordinated publication ownership.
Existing Python pairs use their configured Jupytext synchronization; inspect
the resulting source/metadata diff before retaining it.

Pages builds verify and render saved notebooks with execution disabled. A clean
checkout must render without raw run folders. See `docs/docs-publishing.md` for
the repository build procedure. Saved outputs and derived evidence do not imply
raw artifact publication. Manual re-analysis requires the exact sealed
artifacts from their custodian and must fail clearly when they are missing.

## Keep the ordinary workflow visible

For a single Palace run, retain the six stage-local sections: Build Component
Coupon, Configure EPR / Problem, Build Mesh, Generate Config, Prepare Handoff
and Analyze. The prepared script is the separate manual execution surface. Keep
true global selectors at the top and each numerical or execution control next
to the operation it governs. The installed SCGSim guide defines exact stage
APIs and ordering. AEDT examples retain their build/assignment/setup/solve,
convergence, results and release structure. Do not merge two backend stage
schemas into one generic notebook.

Use explicit immutable receipt selectors for analysis of an existing run.
`analyze_handoff` must enter only the existing inspect/resolve/report path;
mesh, config, preparation, solver launch and artifact writes remain behind
their separate authoring actions. A fresh preparation requires an intentional
control change, fresh run ID and an empty destination. Do not silently select
the latest run or relabel an old receipt after source/material changes.

The boundary-alignment notebook is analysis-only and the Tools geometry viewer
is a read-only diagnostic. Neither should be forced through the single-run
Palace stage audit. Public example availability does not imply that its selected
run is present in a source checkout.

## Semantic selection and interpretation

Build from the canonical component and structured PDK stack/material records.
Use `validate_interface_preset_records(get_interface_preset_records())` and
select the requested exact record keys immediately before consuming interface
properties. The Kosen literature-central presets are synthetic model
conventions, not measured process data. Values and exclusions remain in record
provenance; do not copy thickness, permittivity or loss tangent into notebooks.

Preserve the component's net, owner, port and material identities. A simulation
boundary can ground conductors without rewriting layout connectivity. Route
choices and mesh controls are explicit consumer settings; examples do not
authorize changing a physical stack or inventing a scientific tolerance.
For Q2D's native cross-section inputs and all other backend-specific geometry
contracts, use the installed SCGSim guide rather than an OrPen solver fixture.

Report trust and execution status before physics. Strict completed resolution
and failed/partial inspection are distinct paths; preserve the actual receipt
status and selected iteration provenance. Runtime, AMR traces, C11, modal
frequencies and participation are evidence with their recorded limitations.
Do not infer convergence, solver agreement, fabrication qualification or
scientific acceptance from the existence of a rendered report.

## Validation without a solver run

Check JSON, unique cell IDs, canonical input parity, Python syntax, source
imports and the appropriate single-run or analysis-only classification. Inspect
action branches before executing any analysis. When re-analysis is authorized,
bind it to existing receipt hashes and verify artifacts remain unchanged. Check
public source and embedded output for absolute user paths, credentials,
unclassified geometry and private metadata. Do not run a solver to validate
formatting or package knowledge. Missing artifacts, unsupported API versions
and invalid identities must remain visible failures.
