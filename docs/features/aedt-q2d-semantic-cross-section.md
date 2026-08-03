# AEDT Q2D Semantic Cross-Section

Q2D geometry must be authored as an explicit cross-section contract, not inferred
from GDS layout, CPW helper names, layer mapping rows, or conductor marker
sidecars. The source artifact is a JSON sidecar with schema
`q2d-semantic-cross-section.v1`.

## Geometry Contract

The stack is written bottom-to-top:

```python
Stack(
    elements=(
        Air(height_um=100),
        Die(id="D0", thickness_um=500, material="Silicon"),
        DieGap(height_um=8),
        Die(id="D1", thickness_um=500, material="Silicon"),
        Air(height_um=100),
    )
)
```

`Air` only expands the final AEDT `Vacuum` Region. `DieGap` is physical empty
spacing between dies. Neither becomes a rectangle. Only `Die`, `Ground`, and
`Trace` become geometry objects.

Each die face owns an explicit left-to-right metal sequence:

```python
FacePattern(
    die="D0",
    face="top",
    metal_thickness_um=0.2,
    segments=(
        Ground(width_um=50),
        Gap(width_um=6),
        Trace("T1", width_um=7),
        Gap(width_um=6),
        Ground(width_um=8),
        Gap(width_um=6),
        Trace("T2", width_um=7),
        Gap(width_um=6),
        Ground(width_um=50),
    ),
)
```

`Gap` advances the lateral cursor only. It is not emitted as an air rectangle.
`Trace.name` becomes a signal assignment. `Ground` segments on the same face are
assigned to the reference ground group unless a later compiler adds an explicit
ground assignment override.

## Same-Face Purcell Contracts

The intrinsic-Purcell Q2D route is a same-face model, not the earlier
opposing-face two-trace example:

- `T1` and `T2` are both on `D0/top`.
- `D1` remains in `Stack` as a substrate body.
- `D1/bottom` retains reference-ground metal except for one local opening.
- `upper_ground_clearance_width_um` is the explicit width of that opening.

Use the focused constructor rather than moving `T2` to D1:

```python
from orpen_sc_pdk.simulation.aedt.q2d import (
    make_q2d_same_face_two_trace_cross_section,
)

cross_section = make_q2d_same_face_two_trace_cross_section(
    trace_width_um=trace_width_um,
    trace_gap_um=trace_gap_um,
    inter_trace_ground_width_um=inter_trace_ground_width_um,
    upper_ground_clearance_width_um=upper_ground_clearance_width_um,
    flip_chip_gap_height_um=flip_chip_gap_height_um,
    die_thickness_um=die_thickness_um,
    air_height_um=air_height_um,
    ground_width_um=ground_width_um,
    metal_thickness_um=metal_thickness_um,
)
```

The serialized D1 pattern is `Ground`,
`Gap(role="upper_ground_clearance")`, `Ground`. The runtime still lowers the
gap by advancing the lateral cursor without creating metal. The role prevents a
generic CPW spacing from being misidentified as the reviewed upper-ground
clearance. All numeric values remain caller-owned; this public contract does not
publish private design dimensions.

The isolated-CPW reference uses the same D0/D1 stack and local D1 clearance,
but has exactly one signal conductor on `D0/top`:

```python
from orpen_sc_pdk.simulation.aedt.q2d import (
    make_q2d_same_face_single_trace_cross_section,
)

reference = make_q2d_same_face_single_trace_cross_section(
    trace_width_um=trace_width_um,
    trace_gap_um=trace_gap_um,
    upper_ground_clearance_width_um=upper_ground_clearance_width_um,
    flip_chip_gap_height_um=flip_chip_gap_height_um,
    die_thickness_um=die_thickness_um,
    air_height_um=air_height_um,
    ground_width_um=ground_width_um,
    metal_thickness_um=metal_thickness_um,
)
```

Its validator requires the exact D0 sequence
`Ground-Gap-T1-Gap-Ground`, retained D1 substrate, and a centered tagged
clearance between D1 reference-ground segments. This is a distinct
`single_reference` result role; it must not be combined with `coupled_pair`
cases in one exported artifact.

## Public D3 Ground-Clearance Package

The Workbench handoff is generated with an explicit run root:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python \
  scripts/build_d3_same_face_ground_clearance_q2d_package.py \
  --run-root build/simulation/aedt/d3_same_face_ground_clearance_q2d/2026-07-20-Run01
```

The package contains exactly twelve point-local Q2D cases: nine
`coupled_pair` cases over inter-trace ground widths `3.8`, `4.65`, and `5.5`
µm crossed with D1 clearances `60`, `120`, and `240` µm, plus three
`single_reference` cases over the same clearances. Every case records the
public `w=5` µm, `s=7.5` µm CPW values; 7 µm flip gap; two 500 µm Silicon
substrates; 200 µm exterior air on each side; 150 µm side ground; 0.2 µm
metal; and 6 GHz adaptive frequency in both point ledgers.

Generation writes only semantic inputs, the AEDT package, point ledgers, and a
hash-backed package audit. It does not create matrices or claim solver
completion. A pre-existing run root fails unless `--overwrite` is explicit;
compatible overwrite refreshes package metadata while preserving existing
`results/`, `logs/`, and point-local `points/` files.

## Sweep Presentation

Notebook sweeps should present the parameter space first:

```python
space = ParameterSpace(
    Axis("trace_width_um", (5.0, 7.0, 9.0), default=7.0),
    Axis("trace_gap_um", (4.0, 6.0, 8.0), default=6.0),
    Axis("flip_chip_gap_height_um", (6.0, 8.0, 10.0), default=8.0),
    Axis("upper_ground_clearance_width_um", public_clearance_widths_um),
)

space.point()
space.line("trace_width_um", trace_gap_um=6.0)
space.plane("trace_width_um", "trace_gap_um", flip_chip_gap_height_um=8.0)
```

Axis names are notebook-defined, but should match builder keyword arguments so
each point can feed either direct Q2D geometry or a GDSFactory component:

```python
cross_section = make_q2d_cross_section(**point.coords)
component = make_gds_component(**point.coords)
```

After that, the notebook should show:

1. Cross-section controls: stack, materials, and face patterns.
2. Sweep axes: values such as trace width, gap width, die gap, metal thickness,
   face pattern variants, and horizontal origin.
3. Point grid: one row per point with `point_slug`, flattened `parameter_*`
   columns, and a compact stack/pattern summary.
4. AEDT recipe and runtime controls.
5. Handoff package creation.
6. Run command.
7. Matrix readback and derived physics metrics.
8. Runtime performance and solve evidence.

Every sweep point must serialize the full semantic cross-section. Parameter
columns are provenance and filtering aids; they are not allowed to be the only
geometry source.

## Analysis Contract

Readback should parse Q2D matrix CSVs into long-form rows before deriving
metrics. A row should include point id, recipe id, matrix type, quantity,
row terminal, column terminal, raw value, unit, and SI value when supported.

Strict readback should fail on missing matrix files, zero-byte exports, parse
errors, or inconsistent terminal names. Non-strict readback may return partial
data only when it also reports missing sources and parse warnings.

Derived metrics such as self impedance or mutual impedance are formulas over
parsed matrix entries. They must not fabricate missing values.

## Purcell Maxwell L/C Export

`scripts/export_orpen_q2d_intrinsic_purcell_cases.py` has no built-in run or
dimension defaults. Each case must be named explicitly with `--case-id` after a
compatible AEDT solve has completed:

```bash
uv run python scripts/export_orpen_q2d_intrinsic_purcell_cases.py \
  --run-root PATH_TO_COMPLETED_RUN \
  --case-id SAME_FACE_CASE_ID \
  --output PATH_TO_MAXWELL_LC_ARTIFACT
```

The exporter validates the cross-section before loading matrices, so an
opposing-face case cannot be reused as same-face evidence. Missing case
selection, solver completion, matrix exports, or solver-version evidence raises
`PendingQ2dArtifactError` before the output path is written.

A selection must be homogeneous: `coupled_pair` produces 2×2 Maxwell L/C,
while `single_reference` produces 1×1 Maxwell L/C. A completed artifact
records:

- conductor row/column order and the `Ground` reference group;
- voltage relative to `Ground`, positive current in `+z`, and the Q2D XY-plane
  propagation convention;
- distributed Maxwell per-unit-length matrix representation and extraction
  frequency;
- `R` and `G` as unavailable and explicitly `assumed_zero_for_v1`;
- AEDT, PyAEDT, run, project, recipe, and selected-case provenance; and
- SHA-256 plus byte size for every source sidecar, solver ledger, and matrix
  export used by the artifact.
