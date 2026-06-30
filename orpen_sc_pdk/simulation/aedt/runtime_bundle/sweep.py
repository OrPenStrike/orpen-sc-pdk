"""Point-local sweep orchestration boundary for generated AEDT packages.

This module will own skip/retry/recovery policy, worker project isolation,
progress reporting, per-point result/log routing, and completion aggregation.
It does not run workers or synthesize sweep results in the scaffold.
"""

from __future__ import annotations

from typing import Any


def run_point_local_sweep(*_args: Any, **_kwargs: Any) -> None:
    """Run a point-local AEDT sweep.

    Raises:
        NotImplementedError: Runtime sweep orchestration has not been
            implemented in the scaffold boundary.
    """

    raise NotImplementedError("AEDT point-local sweep orchestration is not implemented")


__all__ = ["run_point_local_sweep"]
