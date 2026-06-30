"""Q2D workflow boundary for generated AEDT runtimes.

This module reserves the stateful Q2D extraction pipeline. It coordinates the
named stage modules for state, geometry, assignment, region, setup, solve,
export, and audit once runtime behavior is implemented.
"""

from __future__ import annotations

from .. import SolverWorkflow


class Q2DWorkflow(SolverWorkflow):
    """Reservation point for Q2D extraction stage planning."""

    solver_type = "q2d_extraction"


def run_q2d_workflow(context: dict) -> list:
    """Run the Q2D workflow scaffold.

    Raises:
        NotImplementedError: The first reserved solver stage is not implemented.
    """

    return Q2DWorkflow().workflow(context)


__all__ = ["Q2DWorkflow", "run_q2d_workflow"]
