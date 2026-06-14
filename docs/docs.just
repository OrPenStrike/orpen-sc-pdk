# Documentation helper targets, following the Quantum-RF-PDK docs workflow style.

docs_source := "docs"
docs_build := "docs/_build"
docs_notebooks := "docs/notebooks"
notebook_source := "notebooks/src"
latex_main := "orpen-sc-pdk.tex"

# Write a generated command reference for docs pages.
[group('docs')]
write-justfile-help:
    @just --list > {{docs_source}}/justfile_help.txt

# Convert Jupytext notebook sources to ipynb artifacts for local inspection.
[group('docs')]
convert-notebooks:
    @bash .github/convert-notebooks.sh {{notebook_source}} notebooks

# Copy converted notebooks into the Sphinx source tree.
[group('docs')]
copy-notebooks:
    @mkdir -p {{docs_notebooks}}
    @bash .github/convert-notebooks.sh {{notebook_source}} {{docs_notebooks}}

# Prepare generated documentation inputs.
[group('docs')]
docs-prerequisites: write-justfile-help convert-notebooks copy-notebooks

# Build HTML documentation.
[group('docs')]
docs: docs-prerequisites
    uv run --group docs python -m sphinx.cmd.build -b html {{docs_source}} {{docs_build}}/html

# Build and serve HTML documentation locally.
[group('docs')]
serve-docs port="8000": docs
    @echo "Serving docs at http://localhost:{{port}}"
    uv run --group docs python -m http.server "{{port}}" -d {{docs_build}}/html

# Build LaTeX documentation sources.
[group('docs')]
docs-latex: docs-prerequisites
    uv run --group docs python -m sphinx.cmd.build -b latex {{docs_source}} {{docs_build}}/latex

# Build PDF documentation from LaTeX sources.
[group('docs')]
docs-pdf: docs-latex
    cd {{docs_build}}/latex && latexmk -pdf -xelatex -interaction=nonstopmode -file-line-error {{latex_main}}

# Remove generated documentation output.
[group('docs')]
clean-docs:
    rm -rf {{docs_build}} {{docs_notebooks}} {{docs_source}}/justfile_help.txt notebooks/*.ipynb
