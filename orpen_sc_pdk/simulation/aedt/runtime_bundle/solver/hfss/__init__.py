"""HFSS solver scaffold package for generated AEDT handoff runtimes.

This package owns HFSS-family reservation points. Driven Terminal and Eigenmode
remain separate modules because they use different recipe requirements and
result expectations even while both start from an ``Hfss3dLayout`` import path.
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
