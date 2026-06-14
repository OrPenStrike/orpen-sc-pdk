"""Optional ignored private layout mount for local GF+ preview."""

from __future__ import annotations

import importlib
import os
import sys
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any

from gdsfactory.cross_section import get_cross_sections

PRIVATE_CELL_MOUNT = Path(__file__).resolve().parent / "privates"
PRIVATE_LAYOUT_REPO_NAME = os.environ.get("ORPEN_SC_PDK_PRIVATE_LAYOUT_REPO", "")
PRIVATE_LAYOUT_CELLS_PACKAGE = os.environ.get("ORPEN_SC_PDK_PRIVATE_LAYOUT_CELLS", "")
PRIVATE_LAYOUT_XSECTIONS_PACKAGE = os.environ.get("ORPEN_SC_PDK_PRIVATE_LAYOUT_XSECTIONS", "")


def load_private_cells(
    namespace: MutableMapping[str, Any] | None = None,
    *,
    mount_root: Path | str | None = None,
    repo_name: str = PRIVATE_LAYOUT_REPO_NAME,
    cells_package: str = PRIVATE_LAYOUT_CELLS_PACKAGE,
) -> tuple[str, ...]:
    """Load private GF cell factories from an ignored repo-local mount."""

    namespace = globals() if namespace is None else namespace
    module = _import_mounted_package(
        cells_package,
        mount_root=mount_root,
        repo_name=repo_name,
    )
    if module is None:
        return ()

    registered: list[str] = []
    for name in _public_export_names(module):
        value = getattr(module, name)
        if callable(value):
            namespace[name] = value
            registered.append(name)
    return tuple(registered)


def load_private_cross_sections(
    *,
    mount_root: Path | str | None = None,
    repo_name: str = PRIVATE_LAYOUT_REPO_NAME,
    xsections_package: str = PRIVATE_LAYOUT_XSECTIONS_PACKAGE,
) -> dict[str, Any]:
    """Load private cross-section factories needed by mounted private cells."""

    module = _import_mounted_package(
        xsections_package,
        mount_root=mount_root,
        repo_name=repo_name,
    )
    if module is None:
        return {}
    return dict(get_cross_sections(module))


def _import_mounted_package(
    package: str,
    *,
    mount_root: Path | str | None,
    repo_name: str,
) -> Any | None:
    if not repo_name or not package:
        return None

    repo_root, src_root = _mounted_repo_paths(mount_root=mount_root, repo_name=repo_name)
    if not src_root.exists():
        return None

    src_path = str(src_root)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    try:
        importlib.invalidate_caches()
        return importlib.import_module(package)
    except Exception as error:
        raise RuntimeError(
            f"Private layout mount at {repo_root} is present but could not import "
            f"{package!r}. Check that the mounted private repo has a valid src layout "
            "and compatible orpen-sc-pdk dependency."
        ) from error


def _mounted_repo_paths(
    *,
    mount_root: Path | str | None,
    repo_name: str,
) -> tuple[Path, Path]:
    root = Path(mount_root) if mount_root is not None else PRIVATE_CELL_MOUNT
    repo_root = root / repo_name
    return repo_root, repo_root / "src"


def _public_export_names(module: Any) -> tuple[str, ...]:
    exported = getattr(module, "__all__", None)
    if exported is None:
        exported = tuple(name for name in vars(module) if not name.startswith("_"))
    return tuple(str(name) for name in exported if not str(name).startswith("_"))


PRIVATE_MOUNTED_CELLS = load_private_cells()
PRIVATE_MOUNTED_CROSS_SECTIONS = load_private_cross_sections()

__all__ = [
    *PRIVATE_MOUNTED_CELLS,
]
