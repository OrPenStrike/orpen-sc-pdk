# Notebooks

This folder contains public Jupyter notebooks for `orpen-sc-pdk`.

## Contributors

Notebook authorities live under `src/`, outside the Python package import
scope. The Pages × Notebook suite and six Kosen2024 Xmon authorities are Quarto
QMD files; matching IPYNBs are derived publication artifacts, not independent
editable sources. Families not yet migrated retain their existing Jupytext
`py:percent` authority. Historical Xmon outputs and evidence retain their
original identity and are not execution of a revised source.

Pages explain user/tool requirements; notebooks own concrete case settings and
real SCGSim calls. The current suite is source-only and CONVERGING. It includes
SimplePad/CircularPad, finite-CPW Palace and AEDT cases, the shared 17-bridge
RLC/Lumped/Wave family, three GeometrySemantics observations and Q2D. Native
modeling, meshing, solving and returned-run analysis are distinct explicit
stages. The body-first Driven Modal interface is unavailable at the selected
checkpoint; its QMD is a nonexecutable historical authoring note, not a usable
replacement. The earlier finite-CPW Terminal entry remains historical.

Simulation notebooks are organized by simulation scope, then by the public
thing being simulated:

```text
ComponentSimulation/
  SimplePad/
  CircularPad/
  GeometrySemantics/
    geometry_source_ownership.ipynb
    geometry_curves_holes_transforms.ipynb
    geometry_multilevel_contacts.ipynb
  CpwMeanderAirbridge/
    aedt_hfss_eigenmode_rlc.ipynb
    aedt_hfss_driven_terminal_lumped.ipynb
    aedt_hfss_driven_terminal_wave.ipynb
  CpwFiniteGround/
    palace_eigenmode.ipynb
    aedt_hfss_driven_modal.ipynb
    aedt_hfss_driven_terminal.ipynb
    aedt_hfss_eigenmode.ipynb
    aedt_q3d.ipynb
  Kosen2024_Xmon/
    palace_route_a_eigenmode.ipynb
    palace_route_a_electrostatic.ipynb
    palace_route_b_eigenmode.ipynb
    palace_route_b_electrostatic.ipynb
CrossSectionSimulation/
  CpwFiniteGround/
    aedt_q2d.ipynb
Research/
  FieldCalculator/
    aedt_hfss_eigenmode_mask_integrals.ipynb
```

The FieldCalculator research notebook is a canonical QMD under
`src/Research/FieldCalculator/` with a clean derived IPYNB. It studies native
HFSS masked surface integrals on a public generic PEC vacuum cavity, without
GDS/PDK/SGB geometry or device-loss claims. Its explicit actions separate one
adaptive solve, postprocessing a copied sealed project, and AEDT-free plotting
of hash-verified saved measurements. Local evidence stays in that notebook
family's `.artifacts/` directory; this research scope remains `CONVERGING`.

Future `ChipSimulation`, `CrossSectionSimulation`, and `CircuitSimulation`
folders use the same pattern. Solver/backend identity belongs in notebook
filenames, not in a top-level `AEDTSimulation` or SGB tutorial folder.

Regenerate all QMD-backed publication notebooks after editing their sources:

```bash
just convert-notebooks
```

Generation is explicit and produces clean IPYNBs. `just check-notebooks`
instead renders every QMD to a temporary notebook and compares Markdown, code,
order, metadata, and stable cell identities without executing or overwriting
the tracked IPYNBs. Pages uses the check-only path, so saved publication
outputs may exist only in the derived IPYNB.

Build the Quarto documentation and notebook pages with:

```bash
just docs
```

Notebook examples in this public repo must not include private layout/IP, GDS
inputs, private run folders, or private benchmark numbers.

OrPen owns components, PDK facts and notebook case meaning. `scgsim.geometry`
owns the source geometry boundary; `scgsim.palace` and `scgsim.aedt` own backend
lowering, handoff, execution receipts, Resolve and Report. The current suite
authors against [SCGSim v2 RC1](https://github.com/OrPenStrike/scgsim/tree/85d8bedb733b1e17737d935029618351b30ea5de)
in a separate consumer environment; the ordinary environment and pins are
unchanged. Follow each source's environment instructions. AEDT remains optional.

The current PDK base film is 0.1 µm. Q2D retains its explicitly authored Nb
0.2 µm section with 10 µm gap and 40 µm grounds, not an inferred 3D slice.
Use the [suite catalog](../docs/simulation/notebooks.qmd) for requirement links
and local canonical-source/derived-notebook downloads.
