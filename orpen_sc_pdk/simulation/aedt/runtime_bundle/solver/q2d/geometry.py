"""Q2D geometry construction boundary for generated AEDT runtimes.

This module reserves both ``hfss_section`` and ``native_2d`` geometry modes.
The future implementation must either section staged HFSS geometry or build
Q2D rectangles from source metadata, layer mapping, material context, and
conductor markers.
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
