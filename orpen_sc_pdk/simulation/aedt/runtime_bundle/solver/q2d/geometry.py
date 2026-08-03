"""Q2D geometry construction boundary for generated AEDT runtimes.

This module reserves both ``hfss_section`` and ``semantic_cross_section``
geometry modes. The future semantic implementation must build Q2D rectangles
from an explicit Stack/FacePattern cross-section sidecar, not from GDS layout,
CPW case metadata, layer mapping heuristics, or conductor marker ports.
"""

from __future__ import annotations

from typing import Any


def build_q2d_geometry(*_args: Any, **_kwargs: Any) -> None:
    """Build or import Q2D geometry for one recipe.

    Raises:
        NotImplementedError: Q2D geometry construction has not been implemented.
    """

    raise NotImplementedError("Q2D geometry construction is not implemented in the AEDT scaffold")


__all__ = ["build_q2d_geometry"]
