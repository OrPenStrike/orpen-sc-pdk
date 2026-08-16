# Developing Features

The active cross-repository boundary is intentionally small:

- OrPen develops public components, layer-stack and material facts, semantic
  annotations, and public notebook sources.
- SCGSim develops the Semantic Geometry Builder Core plus Palace and AEDT
  execution, handoff, resolve, and report APIs.
- A private consumer may validate those public contracts without becoming a
  second implementation authority.

See [SCGSim integration](features/scgsim-integration.md) for the dependency and
data flow, and [Notebooks](notebooks.qmd) for the current public consumers.
