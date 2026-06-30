"""Q2D conductor assignment boundary for generated AEDT runtimes.

This module reserves assignment of signal lines and reference grounds from
Q2D conductor markers or explicit object patterns. It does not infer missing
terminals or fabricate assignments.
"""

from __future__ import annotations

from typing import Any


def assign_q2d_conductors(*_args: Any, **_kwargs: Any) -> None:
    """Assign Q2D signal and reference conductors.

    Raises:
        NotImplementedError: Q2D conductor assignment has not been implemented.
    """

    raise NotImplementedError("Q2D conductor assignment is not implemented in the AEDT scaffold")


__all__ = ["assign_q2d_conductors"]
