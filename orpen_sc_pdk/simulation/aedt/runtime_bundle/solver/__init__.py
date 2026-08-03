"""Solver workflow contracts for generated AEDT handoff runtimes.

This package reserves the solver-specific Run-side folder structure and shared
stage vocabulary for AEDT recipes. The intended solver ownership is PyAEDT app
choice, geometry method, boundary assignment, setup, solve, export, and audit.

Current v1 status is deliberately conservative: real solver execution still
lives in ``runtime_bundle/run_aedt_native.py``. The modules under
``solver/*`` are fail-fast review boundaries until those implementations are
moved here behind a reviewed contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WorkflowState:
    """Serializable workflow marker for each solver stage."""

    stage: str
    details: dict[str, Any]


class SolverWorkflow:
    """Shared contract for all solver reservations.

    Concrete solver classes must expose the same stage boundary names. Stage methods
    are intentionally fail-fast until runtime-specific logic is implemented.
    """

    solver_type = "solver"

    def workflow_type(self) -> str:
        """Return solver type identifier."""
        return self.solver_type

    def workflow(self, context: dict[str, Any]) -> list[WorkflowState]:
        """Run the full workflow pipeline and return audit states."""
        states = [
            WorkflowState("state", self.state(context)),
            WorkflowState("geometry", self.geometry(context)),
            WorkflowState("assignment", self.assignment(context)),
            WorkflowState("region", self.region(context)),
            WorkflowState("setup", self.setup(context)),
            WorkflowState("solve", self.solve(context)),
            WorkflowState("export", self.export(context)),
            WorkflowState("audit", self.audit(context)),
        ]
        return states

    def state(self, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError(
            f"{self.__class__.__name__} state step is not implemented in V1 scaffold."
        )

    def geometry(self, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError(
            f"{self.__class__.__name__} geometry step is not implemented in V1 scaffold."
        )

    def assignment(self, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError(
            f"{self.__class__.__name__} assignment step is not implemented in V1 scaffold."
        )

    def region(self, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError(
            f"{self.__class__.__name__} region step is not implemented in V1 scaffold."
        )

    def setup(self, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError(
            f"{self.__class__.__name__} setup step is not implemented in V1 scaffold."
        )

    def solve(self, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError(
            f"{self.__class__.__name__} solve step is not implemented in V1 scaffold."
        )

    def export(self, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError(
            f"{self.__class__.__name__} export step is not implemented in V1 scaffold."
        )

    def audit(self, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError(
            f"{self.__class__.__name__} audit step is not implemented in V1 scaffold."
        )


__all__ = [
    "SolverWorkflow",
    "WorkflowState",
]
