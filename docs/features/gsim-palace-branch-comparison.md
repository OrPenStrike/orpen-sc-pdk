# gsim Palace Maintenance Policy

The immediate OrPen Surface-EPR workflow is version-locked to the
OrPen-maintained `gsim` `0.2.0+scq.1` line and Semantic Geometry Builder (SGB).
It is a downstream research integration, not the official `gsim` project and
not a claim that OrPen owns a general solver runtime.

## Exact integrated baseline

| Authority | Exact revision | Role |
| --- | --- | --- |
| `gsim` | `main@8f5dc6c05255d003a9c6d8959537bcf8068379d3`, tree `505a53741953666da17d81b7036eba3ac296cd1a` | Palace mesh/config, handoff, resolve, analysis, and report behavior used by the current workflow |
| SGB | `e74a343154c6b19b6ba32d6fb297e700cfe08ff2` | Semantic geometry and topology identity for Route A/B |

These identities bind the current source lane. They do not by themselves prove
a live Palace solve, numerical EPR result, or convergence.

## Maintenance contract

- Stay on the `0.2.0+scq` line; notebooks and documentation use its native APIs.
- Treat `0.1.0+scq.1` as audit/reference evidence only. It is not a compatibility
  target, and no `0.1` compatibility shim is maintained.
- Do not continuously track or merge upstream `gsim` `main` after this
  stabilization. Evaluate a later upstream release only for a concrete solver
  compatibility need, security issue, critical bug, or clearly valuable
  feature.
- Keep one pinned OrPen downstream branch for the accepted SGB Route A/B,
  Surface-EPR provenance and analysis, exact-net Electrostatic semantics,
  handoff, resolve, and reporting behavior.
- Feed useful findings back to the `gsim` community through public fixtures and
  evidence first. Upstream source contribution is not the default maintenance
  path.

Mature behavior may be described as version-locked, OrPen-affiliated
simulation capability. It must not be presented as replacing official `gsim`.

## Geometry and workflow boundary

SGB remains the geometry/topology authority:

- **Route A** uses zero-thickness face-metal PEC sheets with finite bump shells.
- **Route B** uses the closed exterior boundary shell of a finite construction
  metal volume as PEC while excluding its interior from Palace solution domains
  and volume tetrahedra.

The OrPen-maintained `gsim` line consumes those identities and owns the current
Palace-facing config, handoff, resolve, analysis, and report path. OrPen owns
public PDK fixtures and documentation, not private consumer bindings or solver
results.

See [Palace/Gmsh Notebook Controls](../public-pdk-examples/palace-gmsh-notebook-controls.md),
[Palace HPC Handoff](../public-pdk-examples/palace-hpc-handoff.md), and
[Semantic Geometry Builder](semantic-geometry-builder.qmd) for the reusable
public workflow.

## Separate SCGSim product

`scgsim` is a separately owned downstream product under active development. It
is still **CONVERGING** and has not replaced this immediate
`gsim 0.2.0+scq.1` + SGB workflow. Its roadmap, implementation, and delivery
state must be read from the `scgsim` repository; this page grants it no runtime
or release claim.

## Public-data boundary

This public page intentionally contains no private component identities,
selectors, dimensions, run paths, account or project identifiers, meshes,
configs, receipts, or result artifacts. Sanitization alone does not grant
publication authority.

Related implementation history remains available in Git and in the
[branch-integration issue record](../issues/gsim-palace-branch-integration.md).
