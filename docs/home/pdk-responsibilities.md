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
- public cells including launcher and interdigital capacitor;
- docs and notebooks that expose workflow shape without private layout/IP.

Reusable simulation behavior does not live here:

- `scgsim` owns the Semantic Geometry Builder Core, Palace and AEDT backends,
  mesh/config generation, handoff, run resolution, and reports;
- `orpen-sc-pdk` supplies components, layer-stack facts, material records,
  semantic annotations, and public notebooks that consume that API;
- `gplugins` owns generic GDSFactory plugin integration.

Private layout/IP belongs in a separate private layout repo. The private repo
may export GF cells and chip assemblies, but the public PDK remains the owner of
layer and process semantics.

See [ecosystem-workspace](ecosystem-workspace.md) for the local workspace and
contribution loop.
