# ---
# jupyter:
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
#   language_info:
#     name: python
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.17.3
# ---

# %% [markdown]
# # Martinis 2022 Ribbon SGB Route B Native Mask Handoff
#
# This notebook uses Semantic Geometry Builder Route B for geometry and semantic
# physical-group sidecars, then patches the Palace fork `config.json` with
# native `Dielectric.Mask` postprocessing rows for SA, MS, and MA.

# %%
from __future__ import annotations

import sys
from pathlib import Path


def _repo_root() -> Path:
    for candidate in (Path.cwd(), *Path.cwd().parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "orpen_sc_pdk").is_dir():
            return candidate
    return Path.cwd()


NOTEBOOK_SOURCE_DIR = _repo_root() / "notebooks" / "src" / "Native_Masked_Surface_EPR"
if NOTEBOOK_SOURCE_DIR.as_posix() not in sys.path:
    sys.path.insert(0, NOTEBOOK_SOURCE_DIR.as_posix())

from sgb_native_mask_handoff_common import run_sgb_native_mask_handoff  # noqa: E402

ANALYSIS_RUN_ROOT: Path | None = None
# ANALYSIS_RUN_ROOT = Path("/path/to/handoff/run/folder")

run_sgb_native_mask_handoff("B", analysis_run_root=ANALYSIS_RUN_ROOT)
