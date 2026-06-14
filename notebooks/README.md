# Notebooks

This folder contains public Jupyter notebooks for `orpen-sc-pdk`.

## Contributors

The source for notebooks is the `src/` folder, which contains Jupytext
`py:percent` files. Keep notebook scripts out of the import scope of the Python
package.

Convert one source file with:

```bash
uvx jupytext --to ipynb notebooks/src/public_pdk_quickstart.py
```

Build the documentation notebook pages and PDF docs with:

```bash
just docs
just docs-latex
just docs-pdf
```

Notebook examples in this public repo must not include private layout/IP, GDS
inputs, private run folders, or private benchmark numbers.
