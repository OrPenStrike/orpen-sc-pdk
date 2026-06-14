---
orphan: true
---

# Models Namespace

`orpen_sc_pdk.models` is reserved for future public model contracts. It is not
an active analytical-model or solver API surface in this milestone.

The public PDK owns material records, technology/layer stack semantics, public
cells, samples, and static GF+ import mechanics. Reusable solver
implementations remain upstream-oriented:

- Palace electrostatic/EPR/reporting workflow belongs in `gsim` when it is
  reusable beyond this PDK.
- GDSFactory plugin integration belongs in `gplugins` when it is generic.
- `Quantum-RF-PDK` remains a reference and contribution target when the feature
  belongs to that public RF/quantum PDK scope.

GDSFactory+ metadata marks current public cells as intentionally lacking models.
That is a statement of scope for this architecture slice, not a placeholder
implementation.
