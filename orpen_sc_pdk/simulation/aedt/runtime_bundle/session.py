"""AEDT Desktop session boundary for generated runtime packages.

This module will own AEDT version selection, gRPC settings, Desktop lifecycle,
solver app construction, save/close policy, and AEDT message collection. It
does not instantiate Desktop or PyAEDT apps in the scaffold.
"""

from __future__ import annotations

from typing import Any


def create_aedt_session(*_args: Any, **_kwargs: Any) -> Any:
    """Create the target-machine AEDT runtime session.

    Raises:
        NotImplementedError: Runtime AEDT session creation has not been
            implemented in the scaffold boundary.
    """

    raise NotImplementedError("AEDT runtime session creation is not implemented")


__all__ = ["create_aedt_session"]
