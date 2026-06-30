"""AEDT material registration boundary for generated runtime packages.

This module will own creation of AEDT project materials, object/material
binding, unsupported-property audit records, and material assignment summaries.
It does not create PyAEDT material objects in the scaffold.
"""

from __future__ import annotations

from typing import Any


def register_aedt_materials(*_args: Any, **_kwargs: Any) -> None:
    """Register package material context in an AEDT project.

    Raises:
        NotImplementedError: Runtime material registration has not been
            implemented in the scaffold boundary.
    """

    raise NotImplementedError("AEDT material registration is not implemented")


__all__ = ["register_aedt_materials"]
