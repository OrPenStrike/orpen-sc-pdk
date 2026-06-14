# PDK Responsibilities

`orpen-sc-pdk` owns the public SCQ process contract. Private layout repos may
use this contract, but they do not own or redefine it.

The PDK-owned surface includes:

- material records and aliases;
- layer maps and layer views;
- technology and `LAYER_STACK`;
- public CPW cross-sections;
- public reusable layout helpers such as `ETCH = GROUND_MASK - DRAW` and A*
  route strategy wiring;
- public cells and samples, including launcher and interdigital capacitor;
- optional ignored-mount import mechanics for local GF+ preview;
- docs and notebooks that expose workflow shape without private layout/IP.

Reusable solver workflow can live here first when it is needed to keep the
private project usable, then move upstream when the boundary is stable:

- `gsim`: Palace electrostatic, EPR, reporting, benchmarks, material resolver
  adapters, and workflow orchestration reusable across PDKs.
- Palace source fork: solver-side outputs, postprocessing internals, CSV/report
  extensions, and runtime behavior that cannot be implemented cleanly in
  `gsim`.
- `gplugins`: generic GDSFactory plugin integration.
- `Quantum-RF-PDK`: reference and possible contribution target when a feature
  belongs to the public quantum/RF PDK scope.

Private layout/IP belongs in a separate private layout repo. The private repo
may export GF cells and chip assemblies, but the public PDK remains the owner of
layer and process semantics.

See {doc}`ecosystem-workspace` for the local workspace and contribution loop.
