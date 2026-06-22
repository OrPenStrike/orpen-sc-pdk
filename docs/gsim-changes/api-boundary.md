# API Boundary

The first change is not a feature knob. It is the rule that keeps the rest of
the Palace work reviewable: `gsim.palace` should expose notebook-facing entry
points, while helper-only lowering, parser, and runtime details stay in their
owner modules.

## Why This Was Needed

The local Palace branch adds many useful helpers. If every helper is exported
from `gsim.palace`, downstream notebooks get a wide API that looks convenient
but is hard to review or maintain.

The public PDK needs a smaller contract:

- notebooks can import simulation classes and high-level report loaders;
- advanced code can still use deep owner-module imports;
- parser internals, port lowering, config models, and runtime helpers do not
  become public root API by accident.

## What gsim Already Had

`gsim` already had high-level Palace simulation classes and broad convenience
exports. The likely maintainer intent was notebook ergonomics: users could
import common workflow objects from one root package.

That works while the package is small. It becomes noisy when a branch adds
many report, handoff, material, port, and config helpers. The change keeps the
ergonomic imports for user-facing workflows but moves implementation details
back to the modules that own them.

## What Changed

Code pointers:

| Area | Path |
| --- | --- |
| Palace root public surface | `../GDSFactory_Community_Workbench/gsim/src/gsim/palace/__init__.py` |
| Mesh package public surface | `../GDSFactory_Community_Workbench/gsim/src/gsim/palace/mesh/__init__.py` |
| Config/problem models | `../GDSFactory_Community_Workbench/gsim/src/gsim/palace/models/` |
| Port helpers and lowering | `../GDSFactory_Community_Workbench/gsim/src/gsim/palace/ports/` |
| Report typed data | `../GDSFactory_Community_Workbench/gsim/src/gsim/palace/results/` |

Boundary change:

- `gsim.palace` remains the notebook-facing API.
- `gsim.palace.models` owns config/data models.
- `gsim.palace.ports` owns port geometry and lowering.
- `gsim.palace.mesh` owns mesh artifacts and postprocessing helpers.
- `gsim.palace.results` owns typed result objects and report display semantics.

Related detailed ledger: {doc}`../issues/palace-api-responsibility-boundary`.
