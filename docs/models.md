---
orphan: true
---

# Models Namespace

`orpen_sc_pdk.models` is reserved for future public model contracts. It is not
an active analytical-model or solver API surface in this milestone.

The public PDK owns material records, technology/layer stack semantics, public
cells, and GF+ package metadata. Reusable solver implementations
remain upstream-oriented:

- Palace electrostatic/EPR/reporting workflow belongs in `gsim` when it is
  reusable beyond this PDK.
- GDSFactory plugin integration belongs in `gplugins` when it is generic.
- Separate public PDK repos remain reference material when a feature belongs
  outside the OrPen/NCUAS workflow.

GDSFactory+ metadata marks current public cells as intentionally lacking models.
That is a statement of scope for this architecture slice, not a placeholder
implementation.
