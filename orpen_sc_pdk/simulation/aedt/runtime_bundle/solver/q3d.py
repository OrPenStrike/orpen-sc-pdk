"""Q3D extraction workflow contract for the generated PyAEDT runtime.

This module reserves the Q3D extraction path. It owns the future layout import
handoff, Q3D design creation, source/reference or net assignment, matrix solve,
result export, benchmark artifact export, and project-save audit boundary. It
does not implement PyAEDT behavior in the scaffold.
"""

from __future__ import annotations

from . import SolverWorkflow


class Q3DWorkflow(SolverWorkflow):
    """Reservation point for Q3D extraction stage planning."""

    solver_type = "q3d_extraction"


def run_q3d_extraction(context: dict) -> list:
    """Run the Q3D extraction scaffold.

    Raises:
        NotImplementedError: The first reserved solver stage is not implemented.
    """

    return Q3DWorkflow().workflow(context)


__all__ = ["Q3DWorkflow", "run_q3d_extraction"]
