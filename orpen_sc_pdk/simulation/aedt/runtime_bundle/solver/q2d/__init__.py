"""Q2D solver stage package for generated AEDT handoff runtimes.

This package reserves the target stateful Q2D cross-section boundary. Each
module maps to one reviewable workflow stage: state, geometry, assignment,
region, setup, solve, export, and audit.

Current v1 Q2D execution still lives in ``runtime_bundle/run_aedt_native.py``.
The files here fail fast until that implementation is moved into these stage
modules behind a reviewed contract.
"""

from __future__ import annotations

from .assignment import assign_q2d_conductors
from .audit import write_q2d_audit
from .export import export_q2d_results
from .geometry import build_q2d_geometry
from .region import create_q2d_region
from .setup import create_q2d_setup
from .solve import solve_q2d
from .state import validate_q2d_state
from .workflow import Q2DWorkflow, run_q2d_workflow

__all__ = [
    "Q2DWorkflow",
    "assign_q2d_conductors",
    "build_q2d_geometry",
    "create_q2d_region",
    "create_q2d_setup",
    "export_q2d_results",
    "run_q2d_workflow",
    "solve_q2d",
    "validate_q2d_state",
    "write_q2d_audit",
]
