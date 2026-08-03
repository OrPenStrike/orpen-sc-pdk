"""HFSS solver scaffold package for generated AEDT handoff runtimes.

This package reserves HFSS-family Run-side solver boundaries. Driven Terminal
and Eigenmode stay in separate modules because they use different recipe
requirements and result expectations, even though both start from an
``Hfss3dLayout`` import path.

Current v1 HFSS execution still lives in ``runtime_bundle/run_aedt_native.py``.
The files here provide the target structure and fail-fast import surface until
that code is moved behind a reviewed contract.
"""

from __future__ import annotations

from .driven_terminal import HFSSDrivenTerminalWorkflow, run_hfss_driven_terminal
from .eigenmode import HFSSEigenmodeWorkflow, run_hfss_eigenmode

__all__ = [
    "HFSSDrivenTerminalWorkflow",
    "HFSSEigenmodeWorkflow",
    "run_hfss_driven_terminal",
    "run_hfss_eigenmode",
]
