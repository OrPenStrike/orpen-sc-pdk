# gsim Palace Branch Integration

**Repo:** `gsim`

**Related features:** FEAT-006, FEAT-009

The local Palace personal branch extends upstream `gsim` substantially. The
public PDK needs those capabilities, but it should not treat branch-only or
working-tree-only code as accepted upstream design.

Current evidence after pulling upstream:

- upstream `main` was fetched and merged into
  `feature/gsim-palace-postprocessing-roles`;
- merge commit: `2f2a471`;
- upstream baseline after pull: `4a3c067`;
- branch distance after merge: `0` upstream commits behind and `71` local
  commits ahead;
- the latest upstream-only commits mainly touch Meep interactive visualization,
  samples, and notebook cloud-run updates;
- the local branch owns the Palace config/report/runtime direction;
- additional uncommitted Palace config-schema validation, authored-sheet, and
  port-lowering edits remain in the `gsim` working tree.

## Problem

The branch contains several reusable Palace capabilities that are useful for
public PDK simulation workflows, but they cross multiple review concerns:

- public API narrowing and helper demotion;
- mesh manifest and physical-name provenance;
- Palace config generation and schema validation;
- material overlays and dielectric-interface provenance;
- result loaders and typed report bundles;
- local/cloud/HPC run metadata;
- sweep, benchmark, and resource records;
- layout-authored solver-boundary sheets.

If OrPen copies these behaviors into the PDK, it creates a second Palace
runtime. If OrPen documents them as accepted upstream behavior too early, the
docs become stronger than the reviewed `gsim` API.

## Proposed Slicing

Use `gsim` as the implementation home and split the branch into reviewable
upstream slices:

1. Public API and module responsibility cleanup.
2. Mesh manifest, Palace index-map, and meshwell handoff contract.
3. Material overlay, alias, domain-material, and dielectric-interface
   provenance.
4. Result loaders and Driven/Eigenmode/Electrostatic report bundles.
5. Local run folders, handoff packages, Slurm scripts, sweep summaries, and
   sanitized resource records.
6. Versioned Palace config schema validation, typed solver/refinement models,
   and target-version metadata.
7. Layout-authored solver sheet selection through PDK-supplied simulation
   layers.

Each slice should include focused `gsim` tests and only then be reflected in
OrPen fixtures or notebooks as a public consumer workflow.

## Public PDK Rule

Until the relevant `gsim` slice is accepted or deliberately pinned as an
editable contributor dependency:

- OrPen docs may list the capability as prototype or issue-tracked work;
- OrPen examples may use public fixtures to show the intended consumption path;
- OrPen package code should not own Palace config assembly, schema validation,
  result parsing, run handoff, or resource-record logic;
- untracked run archives and local solver outputs should stay out of public
  docs and committed PDK artifacts.

## Open Review Questions

- Should Palace config schemas be vendored in `gsim`, loaded from Palace
  releases, or generated during development?
- Which result/report helpers should remain root-level notebook APIs, and which
  should stay under `gsim.palace.resolve` or `gsim.palace.results`?
- Is `generate_sheet=False` with PDK-declared simulation layers the right public
  API for layout-authored solver sheets?
- Which resource records are safe to standardize publicly without leaking
  site, account, node, command, or private work-directory details?

Related feature:

- {doc}`../features/gsim-palace-branch-comparison`
