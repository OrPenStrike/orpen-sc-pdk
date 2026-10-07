# CircularPad: source layout and returned eigenmode

This public synthetic electrical model has a 100 µm circular Al pad,
20 µm radial gap, 1000 µm die, 0.2 µm Al and 500 µm Si. A 2 µm-wide
non-metal junction locator defines a linear 10 nH inductive branch; no added
capacitive branch is used. These are not measured-device parameters.

![Existing disk GDS: full die and circular pad detail.](source_layout.png)

Blue shows the actual layer 1/0 electrode polygons from the existing public
disk GDS. Brown shows its layer 202/1 non-metal junction locator; it is
not an added metal bridge. This is a source-layout view, not a native mesh or
field plot.

## Returned result

![Mode-1 frequency and native error indicator across five snapshots.](frequency_amr.png)

The `_05` run completed four refinement operations and five solve/estimate
snapshots. Mode 1 changes from 5.309160520909 to 5.571696800247 GHz.
The final indicator is 0.1200141096788 versus the configured 0.02, with the
four-refinement maximum reached. Native postprocessing/projection PCG
warnings include 10000 iterations without convergence (logged final relative
residuals 2.471e-6 and 2.058e-5). Native completion and strict result resolution
do not remove those warnings or establish mesh convergence.

Final metadata records 825454 DOF and 111039 elements, using 8 MPI processes
and 1 OpenMP thread. Ordinary final VTU output across eight rank pieces
contains 10-node Lagrange tetrahedra (VTK 71) and 6-node Lagrange triangles
(VTK 69). This observes quadratic serialization after AMR. Shared-node motion,
continuous-circle fidelity and interior nodal state beyond those saved
outputs remain unmeasured; no geometric-accuracy claim follows.

[Frequency/indicator CSV](frequency_amr.csv) preserves the five snapshots.
[Typed EPR CSV](typed_epr.csv) preserves nine surface, two bulk and one
junction participation row from the structured result. Electric normalization
is 4.169884754072e-12 J. Surface values are unmasked, zero-inset baselines with
synthetic LiteratureCentral MA/MS/SA interface inputs. The raw signed Palace
junction participation -0.9948331481454 (`signed_palace=true`) is not
absolute-valued or asserted to be negative physical energy. No Q/T1,
accuracy, cross-solver equivalence or convergence conclusion is made.

## Provenance and use

[run_set.json](run_set.json) binds the opaque source, input, returned receipt,
executed analysis and derived-file hashes without publishing raw logs or
machine-local paths. The layout is read from the existing public disk GDS;
frequency and indicators are selected from the original native CSVs. Typed
EPR and saved-cell observations come from the existing terminal summary and
clean-kernel analysis, not a rerun of the later presentation revision.

The corrected Palace source
`4e9e1b7232b4c8ca8b964be7e70f1848f578de37` is required for the observed
curved-port Uniform area/length normalization path. That surrogate is not an
exact equipotential curved-terminal voltage or measured inductance. Use an
actual MPI wrapper with `resources["command_style"] = "wrapper"`; a direct
ELF does not implement the generated `-np 8 -nt 1` command interface.

The original `_03` preparation supplied the unchanged mesh/config copied to
`_05`; no remesh or repeated HighOrder optimization was performed. The `_04`
attempt failed during port geometry verification and remains separate. The
successful `_05` result and its executed analysis precede this presentation
update. The canonical QMD and derived source-only IPYNB default to read-only
analysis with the retained handoff ID; raw returned artifacts must already
exist locally and are not distributed here. New preparation requires a fresh
run ID.
