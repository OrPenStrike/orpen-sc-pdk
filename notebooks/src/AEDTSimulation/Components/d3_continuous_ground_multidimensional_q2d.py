# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.17.3
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # D3 continuous-ground multidimensional Q2D sweep
#
# This notebook owns the local research workflow for finding regions where
# \(Z_0 \approx Z_c \approx Z_m\) with a continuous upper ground plane.
#
# - \(w,s,d \ge 3\,\mu\mathrm{m}\).
# - Nominal flip-chip height is expected in 7–8 µm.
# - Fabrication-tolerance height samples are 4–9 µm in 0.25 µm steps.
# - The first run is deliberately coarse in \(w,s,d,h\).  It locates a root
#   neighborhood before the complete height-tolerance axis is applied locally.
# - The stable SQLite file caches only validated completed Q2D points.  AEDT
#   Run folders remain the owner of projects, logs, and raw matrix exports.

# %%
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
from IPython.display import display

REPO_ROOT = Path.cwd().resolve()
if not (REPO_ROOT / "orpen_sc_pdk" / "simulation" / "aedt").is_dir():
    raise RuntimeError("Run this notebook from the orpen_sc_pdk repository root.")

SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from d3_continuous_ground_multidimensional_q2d import (  # noqa: E402
    ingest_sweep,
    plot_sweep,
    prepare_sweep,
)

# %% [markdown]
# ## Explicit run controls
#
# Reusing `DATABASE_PATH` prevents a solved physical point from being recomputed
# in a later Run folder.  Change `RUN_ID` for a new attempt; do not move the
# database inside that Run folder.

# %%
SIMULATION_PURPOSE_ID = "d3_continuous_ground_multidimensional_q2d"
RUN_ID = "2026-07-24-Run01"
PHASE_ID = "broad-root-search-v1"

PURPOSE_ROOT = REPO_ROOT / "build" / "simulation" / "aedt" / SIMULATION_PURPOSE_ID
RUN_ROOT = PURPOSE_ROOT / RUN_ID
DATABASE_PATH = PURPOSE_ROOT / "q2d_point_results_v2.sqlite3"

MINIMUM_FEATURE_UM = 3.0
BROAD_W_UM = (3.0, 6.0, 12.0, 24.0)
BROAD_S_UM = (3.0, 6.0, 12.0, 24.0)
BROAD_D_UM = (3.0, 8.0, 24.0)
BROAD_HEIGHT_UM = (4.0, 7.5, 9.0)
TOLERANCE_HEIGHT_UM = tuple(value / 4 for value in range(16, 37))

assert min(BROAD_W_UM + BROAD_S_UM + BROAD_D_UM) >= MINIMUM_FEATURE_UM
assert TOLERANCE_HEIGHT_UM == tuple(4.0 + 0.25 * index for index in range(21))

# %% [markdown]
# ## Prepare the coarse Run folder
#
# The broad stage has 144 coupled-pair points and 48 deduplicated
# single-reference points.  It samples low, nominal, and high flip-chip height
# before spending solver time on all 21 tolerance heights.

# %%
contract = prepare_sweep(
    RUN_ROOT,
    DATABASE_PATH,
    phase_id=PHASE_ID,
    widths_um=BROAD_W_UM,
    gaps_um=BROAD_S_UM,
    center_grounds_um=BROAD_D_UM,
    heights_um=BROAD_HEIGHT_UM,
)
display(contract)

# %% [markdown]
# ## Native AEDT solve
#
# The generated package is point-local and resumable.  Its `scheduled_cases`
# count already excludes cross-run database hits.  Re-running the same command
# skips completed points in this Run folder.

# %%
SOLVE_COMMAND = [
    "/bin/bash",
    "-lc",
    (
        f"UV_CACHE_DIR=/tmp/uv-cache uv run {RUN_ROOT / 'scripts' / 'run_aedt_native.sh'} "
        "--mode solve --max-workers 7 --num-cores 4 --progress stream"
    ),
]
print(SOLVE_COMMAND[-1])

RUN_SOLVER = False
if RUN_SOLVER:
    subprocess.run(SOLVE_COMMAND, cwd=REPO_ROOT, check=True)

# %% [markdown]
# ## Ingest completed points and export high-dimensional CSV
#
# Ingestion is transactional and single-process.  Incomplete or failed points
# never enter the cache.  The joined CSV retains both pair diagonals so
# \(Z_{c1}/Z_{c2}\) asymmetry remains visible instead of being hidden by their
# mean.

# %%
INGEST_SOLVED_RESULTS = False
if INGEST_SOLVED_RESULTS:
    ingest_summary = ingest_sweep(RUN_ROOT, DATABASE_PATH)
    display(ingest_summary)

RESULT_CSV = RUN_ROOT / "results" / "q2d_impedance_sweep.csv"
ROOT_CELL_CSV = RUN_ROOT / "results" / "q2d_root_cells.csv"
if RESULT_CSV.is_file():
    impedance = pd.read_csv(RESULT_CSV)
    display(
        impedance.sort_values("root_score")[
            [
                "w_um",
                "s_um",
                "d_um",
                "h_um",
                "z0_ohm",
                "zc_ohm",
                "zm_ohm",
                "rc",
                "rm",
                "root_score",
                "zc_asymmetry_relative",
            ]
        ].head(20)
    )
if ROOT_CELL_CSV.is_file() and ROOT_CELL_CSV.stat().st_size:
    root_cells = pd.read_csv(ROOT_CELL_CSV)
    display(root_cells.head(20))

# %% [markdown]
# ## Three-row impedance figures
#
# For the broad stage, each height gets one figure:
#
# - rows: \(Z_0, Z_c, Z_m\);
# - x-axis: \(w\);
# - columns: \(s\);
# - colorbar: \(d\).
#
# Once a local refinement contains all 21 heights, the same function switches
# to height on the x-axis and uses line style for \(d\).

# %%
if RESULT_CSV.is_file() and RESULT_CSV.stat().st_size:
    plot_paths = plot_sweep(RUN_ROOT)
    display(plot_paths)

# %% [markdown]
# ## Refinement contract
#
# After reviewing the signed residuals
# \(r_c=(Z_c-Z_0)/Z_0\) and \(r_m=(Z_m-Z_0)/Z_0\), create the next Run folder
# with a small local \(w,s,d\) neighborhood and `TOLERANCE_HEIGHT_UM`.  The same
# `DATABASE_PATH` reuses every already-completed broad point automatically.
# Nominal candidates are ranked within 7–8 µm; 4–9 µm remains tolerance
# evidence rather than an acceptable nominal-height range.
