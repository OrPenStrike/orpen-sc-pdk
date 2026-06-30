"""Q2D setup creation boundary for generated AEDT runtimes.

This module reserves creation or repair of CG/RL setup blocks and convergence
settings. It does not silently choose solver defaults outside the manifest.
"""

from __future__ import annotations

from typing import Any


def create_q2d_setup(*_args: Any, **_kwargs: Any) -> None:
    """Create or repair Q2D setup blocks for one recipe.

    Raises:
        NotImplementedError: Q2D setup creation has not been implemented.
    """

    raise NotImplementedError("Q2D setup creation is not implemented in the AEDT scaffold")


__all__ = ["create_q2d_setup"]
