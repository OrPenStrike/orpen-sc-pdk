"""HFSS Driven Terminal recipe boundary for generated AEDT runtimes.

This module reserves the path that imports GDS with TECH/XML control into an
AEDB, creates the Driven Terminal setup and frequency sweep, resolves terminal
or port patterns, solves, exports layout results, and saves the project. The
scaffold deliberately has no PyAEDT behavior until those semantics are frozen.
"""

from __future__ import annotations

from .. import SolverWorkflow


class HFSSDrivenTerminalWorkflow(SolverWorkflow):
    """Reservation point for HFSS Driven Terminal stage planning."""

    solver_type = "hfss_driven_terminal"


def run_hfss_driven_terminal(context: dict) -> list:
    """Run the HFSS Driven Terminal scaffold.

    Raises:
        NotImplementedError: The first reserved solver stage is not implemented.
    """

    return HFSSDrivenTerminalWorkflow().workflow(context)


__all__ = ["HFSSDrivenTerminalWorkflow", "run_hfss_driven_terminal"]
