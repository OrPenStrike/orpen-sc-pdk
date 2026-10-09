# Cell organization and discovery tags

The current cell source separates reusable layout construction from public
simulation and inspection coupons. Both use the same OrPen PDK; these folders
do not select a solver or change geometry, defaults, layers or semantics.

| Previous deep module | Current deep module |
| --- | --- |
| `cells.{primitives,taper,cpw,airbridge,indium,dicing,junction,capacitor,martinis,purcell,qubit,resonator,resonator_hanger,resonator_meander}` | `cells.layout.{same_module}` |
| `cells.{simple_pad,spline_strip,test_components}` | `cells.simulation.{same_module}` |
| `cells.chips.small_airbridge_chip` | `cells.simulation.small_airbridge_chip` |
| `cells.chips.resonator_with_indium_bumps` | `cells.simulation.resonator_with_indium_bumps` |

All module paths in this table are relative to `orpen_sc_pdk`. Old deep modules
are removed, without compatibility shims. Prefer the stable public imports,
for example `from orpen_sc_pdk.cells import resonator`. Public exports, factory
names, active-PDK keys, cross-section keys and sample discovery keys are unchanged.
The two sample-only chip assemblies remain outside the PDK cell registry.

Tags are flat snake_case metadata for discovery, not process qualification or
simulation support claims. Each public factory has one purpose tag (`layout`
or `simulation`), a singular object tag and meaningful family/feature tags:

| Factories/family | Tags |
| --- | --- |
| Layout straight, taper, Euler bend | `layout`, `primitive`, respectively `straight`, `taper`, `bend_euler` |
| Circular bend | `layout`, `primitive`, `bend_circular`, `circular_arc` |
| CPW factories | `layout`, `cpw`; coupling sections also `coupling_segment` |
| Resonator; hanger; meander | `layout`, `resonator`; `hanger` and/or `meander` according to factory |
| Intrinsic Purcell resonator | `layout`, `resonator`, `intrinsic_purcell` |
| Manhattan junction | `layout`, `junction`, `manhattan` |
| Interdigital capacitor; Martinis capacitor | `layout`, `capacitor`; respectively `interdigital` and `martinis2022` |
| Kosen qubit | `layout`, `qubit`, `kosen2024`, `flip_chip` |
| Indium; airbridge; dicing | `layout`, respectively `bump` + `indium`, `airbridge`, `dicing` |
| Square pad | `simulation`, `capacitor`, `simple_pad`, `single_die` |
| Circular pad | `simulation`, `capacitor`, `circular_pad`, `single_die`, `circular_arc` |
| Arc strip | `simulation`, `primitive`, `curved_strip`, `single_die`, `circular_arc` |
| Interpolation/B-spline strip | `simulation`, `primitive`, `curved_strip`, `single_die`, respectively `interpolation_spline` or `bspline` |
| Flip-chip pad coupon | `simulation`, `chip`, `simple_pad`, `flip_chip`, `bump` |
| CPW airbridge coupon | `simulation`, `cpw`, `single_die`, `airbridge` |
| Small airbridge chip | `simulation`, `chip`, `cpw`, `small_airbridge_chip` |
| Bump resonator assembly | `simulation`, `chip`, `resonator`, `resonator_with_indium_bumps`, `bump` |

Circular pads do not have an unconditional hole tag: the default is a disk.
The small chip's optional airbridges and the bump resonator's same-die assembly
do not imply unconditional `airbridge` or `flip_chip` tags.

For the unchanged VS Code project and by-name build workflow, see the
[GDSFactory+ guide](../features/gdsfactoryplus-discovery.md).
