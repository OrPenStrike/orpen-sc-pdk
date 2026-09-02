# Documentation helper targets for the public OrPen PDK docs workflow.

docs_source := "docs"
notebook_source := "notebooks/src"

# Write a generated command reference for docs pages.
[group('docs')]
write-justfile-help:
    @just --list > {{docs_source}}/justfile_help.txt

# Generate derived publication notebooks from canonical QMD sources.
[group('docs')]
convert-notebooks:
    @bash .github/convert-notebooks.sh {{notebook_source}} notebooks --generate

# Verify derived notebook inputs without executing or overwriting saved outputs.
[group('docs')]
check-notebooks:
    @bash .github/convert-notebooks.sh {{notebook_source}} notebooks --check

# Prepare generated documentation inputs.
[group('docs')]
docs-prerequisites: write-justfile-help check-notebooks

# Build HTML documentation.
[group('docs')]
docs: docs-prerequisites
    quarto render {{docs_source}}

# Build and serve HTML documentation locally.
[group('docs')]
serve-docs port="8000": docs-prerequisites
    quarto preview {{docs_source}} --host 127.0.0.1 --port "{{port}}"

# Remove generated documentation output.
[group('docs')]
clean-docs:
    rm -rf {{docs_source}}/.quarto {{docs_source}}/_freeze {{docs_source}}/_site {{docs_source}}/reference {{docs_source}}/justfile_help.txt notebooks/*.ipynb
