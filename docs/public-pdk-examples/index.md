# Public PDK Examples

These pages explain what the public PDK demonstrates. The examples should show
how a public consumer uses `gsim`; they should not move solver ownership into
`orpen-sc-pdk`.

Start with [component authoring](component-authoring.md) for public layout
factories, then use [Palace HPC handoff](palace-hpc-handoff.md) when a public
notebook needs a portable scheduler package. The existing notebooks, viewer,
and feature pages remain the detailed sources of truth.

## Suggested Review Slices

| Order | Slice | Why it comes here |
| --- | --- | --- |
| 1 | Problem notebooks | This is the user-facing workflow and reveals the API the PDK consumes. |
| 2 | Component authoring | This starts from public registered cells and finishes at the gallery/viewer. |
| 3 | Palace HPC handoff | This selects a public profile and delegates solver packaging to `gsim`. |
| 4 | Simulation layer catalog | This supports the Purcell notebooks without changing `gsim` ownership. |
| 5 | Evidence fixtures | This proves the examples stay public-safe and can trail the main docs. |

- [Problem notebooks](problem-notebooks.md): Driven, Eigenmode, Electrostatic,
  and Purcell workflows with public geometry.
- [Component authoring](component-authoring.md): public registered-cell
  factories, then the existing gallery and browser viewer.
- [Palace HPC handoff](palace-hpc-handoff.md): public F1/Nano4 profile
  selection and the `gsim` handoff boundary.
- [Simulation layer catalog](simulation-layer-catalog.md): public layer names
  and layout-authored solver sheets.
- [Evidence fixtures](evidence-fixtures.md): checks that keep examples
  publication-safe.
