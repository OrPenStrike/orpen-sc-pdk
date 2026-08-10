---
orphan: true
---

# Docs Publishing

The public documentation is part of the PDK contract. It should be buildable
locally and published through GitHub Pages for `OrPenStrike/orpen-sc-pdk`.

## Tooling

The docs stack follows a static public PDK publication pattern:

- Quarto for the searchable documentation site and notebook pages.
- Jupytext `py:percent` notebooks stored in `notebooks/src/`.
- `docs/docs.just` for docs helper commands.
- GitHub Actions for pull request validation and Pages deployment.

The docs intentionally use `orpen-sc-pdk` branding and content. Static assets
should be added only when they are needed for this PDK.

## Local Build

Run:

```bash
uv sync -p 3.12 --group docs --extra dev
just docs
```

`just docs` builds the static site into `docs/_site`. `just serve-docs` starts
the Quarto preview server for local editing.

The generated Just command reference is included below when the docs are built:

```text
just docs
just serve-docs
just clean-docs
```

## CI Contract

The GitHub Pages workflow should:

- build the Quarto HTML site on pull requests and pushes;
- upload the static site artifact for review;
- deploy Pages only from `main`;
- preserve notebook code and saved output in static HTML;
- copy the browser-only layout viewer and its public SVG resources.

Pull requests validate that architecture pages, notebook pages, and API pages
render without requiring private layout repositories.

## Content Checks

Before publishing an architecture change, verify:

```bash
rg -n "/[U]sers/|private[ ]GDS|private[ ]benchmark|run[ ]folders|NCUAS_SC_Qubit_Design" docs README.md
```

Any matches should be intentional. `NCUAS_SC_Qubit_Design` may appear only as
an explicit local workspace example or first-consumer context. Absolute local
paths, GDS inputs from private designs, benchmark values from private layouts,
and private run directories do not belong in public docs or public examples.
