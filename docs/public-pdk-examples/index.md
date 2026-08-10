# Public PDK Examples

These pages explain what the public PDK demonstrates. The examples should show
how a public consumer uses `gsim`; they should not move solver ownership into
`orpen-sc-pdk`.

## Suggested Review Slices

| Order | Slice | Why it comes here |
| --- | --- | --- |
| 1 | Problem notebooks | This is the user-facing workflow and reveals the API the PDK consumes. |
| 2 | Simulation layer catalog | This supports the Purcell notebooks without changing `gsim` ownership. |
| 3 | Evidence fixtures | This proves the examples stay public-safe and can trail the main docs. |

- [Problem notebooks](problem-notebooks.md): Driven, Eigenmode, Electrostatic,
  and Purcell workflows with public geometry.
- [Simulation layer catalog](simulation-layer-catalog.md): public layer names
  and layout-authored solver sheets.
- [Evidence fixtures](evidence-fixtures.md): checks that keep examples
  publication-safe.
