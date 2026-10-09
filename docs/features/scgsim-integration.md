# SCGSim Integration

SCGSim is the sole reusable simulation runtime for OrPen notebooks.

```text
OrPen component + layer stack + material/annotation records
                         |
                         v
        SCGSim SGB Core -> Palace or AEDT backend
                         |
                         v
              handoff -> run -> resolve -> report
```

OrPen owns source design intent and public Notebook UX. Layout ports are named
locators plus sheet geometry; they do not carry Palace L/C/R, mesh profiles, or
AEDT assignment labels. SCGSim owns semantic geometry/topology after layout
ingestion, backend lowering, solver execution contracts, returned-run identity,
and reports. Structured IDs and provenance must survive the complete path;
physical names are labels rather than semantic authority.

Palace configs from `write_config()` always include
`Model.Refinement.Nonconformal`. SCGSim defaults it to `false`. Notebooks may
opt into nonconformal AMR with `set_numerical(amr_nonconformal=True)`. Do not
omit the key or rely on Palace's default `true`.

`prepare_handoff()` generates `run_palace.sh` or `run_palace.sbatch` from
`direct-local`, `slurm-single-node`, or `slurm-multi-node`. Slurm stdout/stderr
go to `logs/palace-%j.log` only; the scheduler does not also write
`slurm-%j.out`.

`resolve_palace_result(...).show_run_trustworthiness()` is the first Analyze
view: run identity, AMR numerical evidence, and simulation cost. Physics-result
figures are a later layer. If the parent `results/palace` folder is incomplete,
`inspect_run_trustworthiness(run_dir)` still reads `iterationNN` snapshots.

The dependency groups are backend-specific so users without AEDT do not need
its optional runtime:

```bash
uv sync -p 3.12 --group palace-notebooks
uv sync -p 3.12 --group aedt-notebooks
```

No legacy solver-compatibility package or external geometry-builder checkout is
required by an OrPen consumer.

## Nominal airbridge stack (CONVERGING)

`get_single_die_layer_stack(*, include_airbridges=False)` retains the existing
D0 substrate, top metal and locator levels. Opting in adds detached copies of
`D0_TOP_AIRBRIDGE_VIA` and `D0_TOP_AIRBRIDGE`; it does not add an upper die or
interdie host cavity. The default Al base metal is 0.1 µm (100 nm) thick. The nominal
underside gap above that metal is 3 µm (also the pier height), and the Al deck
film is separately 0.3 µm thick:

| D0 top part | z range (µm) | Material |
| --- | --- | --- |
| Base metal | 0–0.1 | Al |
| Landing piers | 0.1–3.1 | Al |
| Bridge deck | 3.1–3.4 | Al |

Earlier source plates and native runs that used the 200 nm M1 default retain
their original stack and provenance. Changing this default does not regenerate
those artifacts or change an explicitly fixed notebook-local metal model.

The full face-aware stack uses the same nominal heights along each face's
outward direction. `AIRBRIDGE_VIA_THICKNESS_UM` denotes the 3 µm pier height,
not a separate 0.1 µm contact film; `AIRBRIDGE_THICKNESS_UM` denotes the deck
film. Each airbridge level carries structured `info["airbridge_process"]`
provenance and `airbridge_part` identity. These are Human-selected nominal
rectangular-prism electrostatic facts, not reflow-profile metrology or process
certification. [Chen et al. (2014)](https://doi.org/10.1063/1.4863745) describe
the 3 µm scaffold and 300 nm Al film; the
[supplement, section III](https://web.physics.ucsb.edu/~martinisgroup/papers/Chen2013supp.pdf)
uses 3 µm separation. Placement above the base-metal top is the selected model
convention, not a claim that the paper fixes that coordinate reference.

The registered `airbridge()` retains its 84 × 12 µm deck and two 14 µm-square
endpoint footprints, with unchanged XY polygons and no route ports. Canonical
same-face layer pairs declare local `DECK`, `PIER_MINUS` and `PIER_PLUS`
Entities using `component_semantics` v2 and authoritative stack-level names.
Custom or mixed layer pairs remain layout-only; they do not invent stack
physics. The existing footprint is not asserted to replicate the paper.
The consumer owns electrical Net assignment; the PDK declares no net or Group.

The levels use the existing typed `part_role` values `airbridge_deck` and
`airbridge_post`; the PDK does not relabel these parts as bumps or face metal.
The public [SCGSim develop checkpoint
`1e278492ce06f857e0926c2b2d2ed8e2f351ac55`](https://github.com/OrPenStrike/scgsim/tree/1e278492ce06f857e0926c2b2d2ed8e2f351ac55)
(`1.2.0.dev1`, not a stable release) provides
`scgsim.aedt.prepare_q3d_from_geometry(plan.prepare(), ...)`. It consumes a
`GeometryPlan` snapshot of role-neutral finite source geometry with explicit
PDK materials and caller-assigned final Nets. For C/G-only preparation, it
internally exports distinct generated numeric import layers while tracing
each piece back to its original Entity, occurrence, polygon, canonical
layer/datatype, z bounds, material and final Net. The canonical deck `(10, 0)`
and piers `(10, 1)` remain unchanged; no PDK layer remapping is needed.

That helper supports terminal-free all-Signal C/G inputs, including a physical
ground Net whose native type is Signal; physical ground role and native Net
type are independent. It returns the ordinary SCGSim handoff for native
execution and existing resolve/report interfaces. Native import, material and
Net readback, solve/export and returned results remain consumer observations,
not consequences of source preparation. This documentation does not change
the OrPen dependency pin or claim native success, scientific acceptance or
Palace Route A/B airbridge support.

The legacy explicit `Q3dSpec`/`LayerImport` input path still requires distinct
numeric GDS import layers; merely passing canonical deck and pier datatypes
as two mappings on layer 10 is not that contract. Use the traced public helper
for finite planar source preparation rather than a notebook-local workaround.
Its generic geometry path is C/G-only, not arbitrary 3D CAD or curved-source
lowering; direct AC/RL inputs still require real terminals.
