"""Runtime bundle scaffold copied into generated AEDT handoff packages.

This package owns target-machine runtime boundaries: manifest I/O, AEDT session
creation, material registration, sweep orchestration, and solver dispatch. The
current scaffold reserves those interfaces and fails loudly until PyAEDT runtime
semantics are approved.
"""

from __future__ import annotations

from .io import load_manifest
from .materials import register_aedt_materials
from .session import create_aedt_session
from .solver import SolverWorkflow
from .solver.hfss.driven_terminal import HFSSDrivenTerminalWorkflow, run_hfss_driven_terminal
from .solver.hfss.eigenmode import HFSSEigenmodeWorkflow, run_hfss_eigenmode
from .solver.q2d.workflow import Q2DWorkflow, run_q2d_workflow
from .solver.q3d import Q3DWorkflow, run_q3d_extraction
from .sweep import run_point_local_sweep

__all__ = [
    "HFSSDrivenTerminalWorkflow",
    "HFSSEigenmodeWorkflow",
    "Q2DWorkflow",
    "Q3DWorkflow",
    "SolverWorkflow",
    "create_aedt_session",
    "load_manifest",
    "register_aedt_materials",
    "run_hfss_driven_terminal",
    "run_hfss_eigenmode",
    "run_point_local_sweep",
    "run_q2d_workflow",
    "run_q3d_extraction",
]
