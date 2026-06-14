# Palace Analysis/Reporting Contract

**Target:** `gsim`

**Status:** candidate

Reusable Palace electrostatic and EPR report generation should live in `gsim`.
The PDK should provide layer and material metadata that these reports can
consume without depending on private layout repositories.

Acceptance direction:

- report APIs work with public cells and mounted private components;
- reports consume generated Palace config provenance, public layer/material
  identifiers, and solver index maps;
- electrostatic, eigenmode/EPR, driven, and benchmark records use reusable
  schemas instead of notebook-local parsing;
- private layouts can validate the same workflow without publishing layout;
- generated reports avoid private paths and benchmark data from private layouts
  by default.

Related issues:

- {doc}`../issues/palace-report-ownership`
- {doc}`../issues/palace-config-ownership`
- {doc}`../issues/cad-mesh-identity-provenance`
