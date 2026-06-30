"""Runtime manifest and audit I/O boundary for generated AEDT packages.

This module will own manifest loading, package-relative path resolution,
JSON/JSONL audit writes, source hashing, result/log root discovery, and audit
file naming conventions. It does not currently parse runtime payloads because
that behavior belongs to the target-machine implementation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def load_manifest(_path: str | Path) -> dict[str, Any]:
    """Load and validate an AEDT package manifest.

    Raises:
        NotImplementedError: Runtime manifest loading has not been implemented
            in the scaffold boundary.
    """

    raise NotImplementedError("AEDT runtime manifest loading is not implemented")


__all__ = ["load_manifest"]
