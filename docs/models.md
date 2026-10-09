---
orphan: true
---

# Models Namespace

`orpen_sc_pdk.models` is reserved for future public PDK model facts. It is not
an analytical-model or solver runtime surface.

The public PDK owns material records, technology/layer-stack semantics, public
cells, and GF+ package metadata. Reusable simulation models, execution, and
result interpretation belong in `scgsim`.

The `cells_no_model_expected` metadata in `pyproject.toml` names 14 factories;
it is not a blanket classification of all 30 registered cells. The exact list
is the metadata authority. The empty `models` export is a reserved namespace,
not implemented analytical models or solver behavior.
