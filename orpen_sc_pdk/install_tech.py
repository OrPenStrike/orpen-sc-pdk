"""Install the bundled KLayout technology assets."""

from __future__ import annotations

import shutil
from pathlib import Path

from gdsfactory.install import get_klayout_path

from orpen_sc_pdk.config import PATH
from orpen_sc_pdk.logger import logger

TECH_NAME = "orpen_sc_pdk"


def install_tech(*, overwrite: bool = False, use_symlink: bool = True) -> Path:
    """Install or link this PDK's KLayout technology directory."""

    destination = get_klayout_path() / "tech" / TECH_NAME
    source = PATH.klayout
    if not source.exists():
        raise FileNotFoundError(f"KLayout technology source does not exist: {source}")
    if destination.exists() or destination.is_symlink():
        if not overwrite:
            logger.info("KLayout technology already exists at %s", destination)
            return destination
        if destination.is_symlink() or destination.is_file():
            destination.unlink()
        else:
            shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if use_symlink:
        destination.symlink_to(source, target_is_directory=True)
    else:
        shutil.copytree(source, destination)
    logger.info("Installed KLayout technology at %s", destination)
    return destination


if __name__ == "__main__":
    install_tech(overwrite=True)
