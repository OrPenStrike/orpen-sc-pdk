# Notebooks

This folder contains public Jupyter notebooks for `orpen-sc-pdk`.

## Contributors

The source for notebooks is the `src/` folder, which contains Jupytext
`py:percent` files. Keep notebook scripts out of the import scope of the Python
package.

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

Convert one source file with:

```bash
uvx jupytext --to ipynb notebooks/src/ComponentSimulation/Kosen2024_Xmon/palace_route_a_eigenmode.py
```

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
