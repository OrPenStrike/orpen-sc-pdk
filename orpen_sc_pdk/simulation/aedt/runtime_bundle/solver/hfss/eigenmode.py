"""HFSS Eigenmode recipe boundary for generated AEDT runtimes.

This module reserves the path that imports GDS with TECH/XML control into an
AEDB, creates the Eigenmode setup, applies mode-count policy, solves, exports
benchmark artifacts, and saves the project. The scaffold deliberately has no
PyAEDT behavior until those semantics are frozen.
"""

from __future__ import annotations

from .. import SolverWorkflow


class HFSSEigenmodeWorkflow(SolverWorkflow):
    """Reservation point for HFSS Eigenmode stage planning."""

    solver_type = "hfss_eigenmode"


def run_hfss_eigenmode(context: dict) -> list:
    """Run the HFSS Eigenmode scaffold.

    Raises:
        NotImplementedError: The first reserved solver stage is not implemented.
    """

    return HFSSEigenmodeWorkflow().workflow(context)


__all__ = ["HFSSEigenmodeWorkflow", "run_hfss_eigenmode"]
