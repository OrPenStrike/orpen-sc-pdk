# Notebooks

This folder contains public Jupyter notebooks for `orpen-sc-pdk`.

## Contributors

Notebook authorities live under `src/`, outside the Python package import
scope. The six Kosen2024 Xmon authorities are Quarto QMD files; their matching
IPYNBs are derived publication artifacts. Notebook families not yet migrated
retain their existing Jupytext `py:percent` authority.

Simulation notebooks are organized by simulation scope, then by the public
thing being simulated:

```text
ComponentSimulation/
  CpwFiniteGround/
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
```

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

OrPen owns components and PDK facts. `scgsim.palace`, `scgsim.aedt`, and
`scgsim.sgb` own model lowering, handoff, execution receipts, resolve, and
reports. Palace notebooks use the `palace-notebooks` dependency group; future
AEDT notebooks use `aedt-notebooks`, so AEDT remains optional.
