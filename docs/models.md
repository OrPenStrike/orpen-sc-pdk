---
orphan: true
---

# Models Namespace

`orpen_sc_pdk.models` is reserved for future public PDK model facts. It is not
an analytical-model or solver runtime surface.

The public PDK owns material records, technology/layer-stack semantics, public
cells, and GF+ package metadata. Reusable simulation models, execution, and
result interpretation belong in `scgsim`; generic GDSFactory plugin integration
belongs in `gplugins`.

GDSFactory+ metadata marks current public cells as intentionally lacking models.
That is a statement of scope for this architecture slice, not a placeholder
implementation.
