# Evidence Fixtures

Evidence fixtures are not user workflow pages. They exist so public examples
can be checked without publishing private layouts or private solver outputs.

## Why This Was Needed

The public docs need to make claims about `gsim` integration, mesh identity,
material provenance, and runtime records. Those claims need tests. The tests
cannot depend on private layouts or real HPC runs.

The evidence path gives the repo a public, repeatable check for the workflow
shape.

## What gsim Already Had

`gsim` provides reusable APIs for mesh artifacts, run summaries, reports,
sweeps, and resource records. It does not own OrPen's public audit matrix or
the question "does this public PDK example cover the intended workflow?"

That review surface belongs in the PDK as evidence, while the reusable logic
stays in `gsim`.

## What Changed

Code pointers:

| Area | Path |
| --- | --- |
| Evidence runner | `scripts/public_palace_smoke_evidence.py` |
| gsim branch cross-check fixture | `scripts/fixtures/public_gsim_boundary_review_crosscheck.json` |
| Evidence tests | `tests/test_public_palace_smoke_evidence.py` |
| Workflow fixture tests | `tests/test_gsim_driven_cpw_workflow.py`, `tests/test_gsim_eigenmode_resonator_workflow.py`, `tests/test_gsim_electrostatic_capacitor_workflow.py` |
| Notebook style policy | `tests/test_public_problem_notebook_style.py` |

Boundary change:

- `orpen-sc-pdk` owns public evidence and publication-safety tests.
- `gsim` owns reusable implementation behavior.
- Evidence generated under `build/` remains ignored local review output, not a
  committed public artifact.

Related detailed ledger: {doc}`../issues/public-problem-type-notebook-coverage`.
