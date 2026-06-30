"""Q2D solve boundary for generated AEDT runtimes.

This module reserves the ACF/HPC-controlled solve step. It must eventually
enforce that explicit ACF files and runtime resource overrides do not silently
disagree.
"""

from __future__ import annotations

from typing import Any


def solve_q2d(*_args: Any, **_kwargs: Any) -> None:
    """Solve one Q2D recipe.

    Raises:
        NotImplementedError: Q2D solve behavior has not been implemented.
    """

    raise NotImplementedError("Q2D solve behavior is not implemented in the AEDT scaffold")


__all__ = ["solve_q2d"]
