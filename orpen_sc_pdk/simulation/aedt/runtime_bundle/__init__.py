"""Run-side runtime package copied into each AEDT handoff package.

``runtime_bundle`` is the code that actually travels to the AEDT machine. It is
copied into ``scripts/runtime_bundle`` by the Notebook-side package writer, then
loaded by ``scripts/run_aedt_native.py`` without importing the source notebook
repository or the OrPen checkout.

Run-side pipeline ownership:
1. ``run_aedt_native.py`` is the copied CLI entrypoint and transitional
   dispatcher.
2. ``io.py`` owns manifest/run-config loading, package paths, hashes, and audit
   file writes.
3. ``sweep.py`` owns one-script parallel parent orchestration, worker commands,
   progress, resume decisions, result/log routing, and the shared manifest
   selection helpers used by serial and parallel paths.
4. ``session.py`` owns AEDT version selection, gRPC/Desktop lifecycle, PyAEDT
   app registration, modeler units, save/release, messages, and lifecycle audit.
5. ``materials.py`` owns run-side AEDT material creation and object/material
   binding from the compiled material context.
6. ``solver/*`` owns the target folder structure and fail-fast stage vocabulary
   for solver-specific implementations. Current solver execution still lives in
   ``run_aedt_native.py`` until each solver path is moved behind a reviewed v1
   module boundary.

Importing this package must not open AEDT Desktop, mutate projects, launch
workers, or solve recipes.
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
