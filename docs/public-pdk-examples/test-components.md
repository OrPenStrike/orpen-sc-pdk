# Test Components Set — source geometry

This CONVERGING set groups seven source-layout inspection families. Its cells
are real GDSFactory geometry, not solver models or native conformity evidence.
Activate OrPen and build a registered factory with no settings:

```python
import gdsfactory as gf
import orpen_sc_pdk

orpen_sc_pdk.activate()
component = gf.get_component("interpolation_spline_strip")
component.write_gds("interpolation_spline_strip.gds")
```

| Family | Source factory / definition | Source scope |
| --- | --- | --- |
| 01 square pad | `square_pad_capacitor()` | Existing 200 um island, 20 um opening gap, nonmetal locator |
| 02 circular disk | `circular_pad_capacitor()` | Existing outer radius100 um, inner radius0 |
| 03 annulus | `circular_pad_capacitor(inner_radius_um=80)` | Inner hole is nonmetal, not Ground |
| 04 curved strip | `straight_to_circular_strip()`, `interpolation_spline_strip()`, `bspline_strip()` | Separate source definitions, no Ground or JJ |
| 05 finite CPW | Existing `notebooks/src/ComponentSimulation/CpwFiniteGround/aedt_hfss_driven_modal.py` coupon section | Notebook-local 500/10/6/80 um; not a registered component factory |
| 06 flip chip | `flip_chip_pad_coupon()` | Default lower square pad, full upper bottom-face plane, four default bumps |
| 07 CPW airbridge | `cpw_airbridge_coupon()` | Positive Al CPW500/10/6/80 with unchanged default airbridge |

## 04B interpolation strip

`interpolation_spline_strip` defines a piecewise cubic Hermite Y(X) graph through
(-200,0), (-100,60), (0,-40), (100,60), (200,0) um. X must increase strictly.
Endpoint slopes are zero; interior slopes use centered secants. The GDS witness
uses32 uniform parameter samples per span plus the final endpoint. This is an
explicit source representation, not a sampling-adequacy or acceptance threshold.

The two boundary curves interpolate the same through-points translated by
plus/minus5 um in Y, and two actual end-cap segments close `TRACE_OUTER`.
SCG's `interpolation_spline` boundary record uses the source through-points;
its native OCC `addSpline` interpolation law does not accept this explicit
Hermite slope definition. Native curve comparison is **UNOBSERVED**. Matching
through-points must not be presented as exact native curve equivalence.

## 04C B-spline strip

`bspline_strip` uses controls (-200,0), (-100,0), (0,150), (100,-30), (200,-30)
um. Controls are not through-points. Degree3, weights(1,1,1,1,1), distinct knots
(0,0.5,1), multiplicities(4,1,4), and active parameter domain[0,1] are explicit
source facts. Homogeneous de Boor evaluation generates64 uniform parameter
samples per knot span plus the final endpoint. No fitting is performed.

Both boundary curves use the supplied rational B-spline definition translated
by plus/minus5 um in Y; the lower boundary reverses controls/weights and reflects
knots to close the ordered source chain with the two end caps. Native comparison
remains **UNOBSERVED**, despite the explicit degree/knots/weights contract.

Both spline factories default to a1000 um square Si footprint and positive Al
DRAW1/0. A full110/0 mask declares no background Ground. Nominal transverse
width10 um means Y separation, **not constant normal width**. Actual endpoint
tangents define outward `o1`/`o2` directions; default tangent pairs are horizontal
and default end caps are perpendicular to them. Source-local `TRACE` owns the
real polygon and its closed boundary chain. Final electrical Nets belong to
the consumer; no implicit circuit, Ground, JJ or native port is assigned.
The current single-die default stack is Al0..0.1 um (100 nm) and Si-500..0 um.

## 06/07 composition ownership

`cells/test_components.py` is the current production source for06/07, migrated
from the prior task-local candidate without physical geometry changes. Prior
task-local files and figures remain historical evidence, not a second current
production authority.

06 retains named `LOWER_PAD_DIE`, `UPPER_GROUND`, `UPPER_SUBSTRATE` and four
`BUMP_*` references at(+/-250,+/-250) um. Children keep local PAD/GROUND and bump
Entities; upper metal declares `UPPER_GROUND` on canonical D1_BOTTOM_M1(2/0),
outward-Z, z8.1..8.2 um. In bumps40/0 span0.1..8.1 um. Existing UBM40/1
footprints remain separate source process detail and simulation-excluded by PDK
policy. The lower child's nonmetal locator is unused and not forwarded.

07 retains local SIGNAL/GROUND_MINUS/GROUND_PLUS and the named AIRBRIDGE child.
The canonical child owns DECK10/0 and PIER_MINUS/PIER_PLUS10/1. Source stack
selection is `get_single_die_layer_stack(include_airbridges=True)`: base Al
0..0.1, piers0.1..3.1, deck3.1..3.4 um. The actual source deck/pier overlap is
12x7 um per pier, not full pier coverage or a reflow-arch redesign. No GF/native
ports or final Nets are invented. Source contact intent is not connectivity
or native conformity proof.

The Human-selected M1 default is now100 nm. Previously delivered source
inspection plates and native evidence with200 nm M1 retain their original
identities; they are not regenerated or relabeled as the new default stack.
XY geometry, the8 um bump gap,3 um airbridge gap and300 nm deck are unchanged.

## Inspection and execution boundary

In GDSFactory+, activate OrPen and Build any registered factory named above with
zero settings. This is the ordinary source discovery path; live viewer operation
has not been observed by this source checkpoint. Exported GDS can also be opened
directly in the Layout Viewer; source metadata is separately bound, not assumed
to survive metadata-free GDS.

Existing pad and CPW notebooks have separate preparation/solver/Resolve/Report
entrypoints. No new runnable simulation notebook is supplied for04B,04C,06 or07;
source registration does not activate Examples or authorize native operations.
The independent Q2D CPW definition uses gap10/ground40, not the3D coupon's
gap6/ground80, and is not an automatic equivalent slice. Exact SCG v2 notebook
migration, native comparisons, solver execution and result claims remain
separate work. This page adds no runtime dependency, schema or scientific Gate.
