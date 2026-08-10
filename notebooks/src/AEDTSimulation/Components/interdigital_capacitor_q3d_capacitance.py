# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.3
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Interdigital capacitor Q3D capacitance
#
# This notebook prepares one public IDC coupon, runs its generated native AEDT
# package when requested, and displays the complete Q3D Maxwell result. The
# finite conductor named `ground` is a circuit node, not an ideal GroundNet.

# %% [markdown]
# ## Setup and configuration

# %%
from __future__ import annotations

import subprocess
from pathlib import Path

import orpen_sc_pdk
from orpen_sc_pdk.cells.capacitor import interdigital_capacitor_q3d_coupon
from orpen_sc_pdk.simulation.aedt import (
    load_q3d_capacitance_result,
    prepare_interdigital_capacitor_q3d_simulation,
)
from orpen_sc_pdk.tech import OUTER_VACUUM_THICKNESS_UM

REPO_ROOT = Path(orpen_sc_pdk.__file__).resolve().parent.parent
if not (REPO_ROOT / "orpen_sc_pdk" / "simulation" / "aedt").is_dir():
    raise RuntimeError("The active orpen_sc_pdk package is not a source checkout.")
orpen_sc_pdk.activate()

RUN_ID = "2026-08-10-idc-q3d-v1"
RUN_SOLVER = True
REGION_PADDING_UM = OUTER_VACUUM_THICKNESS_UM

Q3D_SETUP_NAME = "Setup1"
Q3D_MATRIX_PROBLEM_TYPES = ("C",)
Q3D_MATRIX_TYPES = ("Maxwell",)

# %% [markdown]
# ## Geometry

# %%
FINGERS = 20
FINGER_LENGTH_UM = 100.0
FINGER_GAP_UM = 3.3
FINGER_WIDTH_UM = 3.3
TAPER_LENGTH_UM = 150.0
TERMINAL_EXTENSION_LENGTH_UM = 100.0
CAPACITOR_GROUND_GAP_UM = 85.0
TERMINAL_OPEN_CLEARANCE_UM = 25.0
COUPON_MARGIN_UM = 100.0

coupon = interdigital_capacitor_q3d_coupon(
    fingers=FINGERS,
    finger_length=FINGER_LENGTH_UM,
    finger_gap=FINGER_GAP_UM,
    finger_width=FINGER_WIDTH_UM,
    taper_length=TAPER_LENGTH_UM,
    terminal_extension_length_um=TERMINAL_EXTENSION_LENGTH_UM,
    capacitor_ground_gap=CAPACITOR_GROUND_GAP_UM,
    terminal_open_clearance_um=TERMINAL_OPEN_CLEARANCE_UM,
    coupon_margin_um=COUPON_MARGIN_UM,
)
coupon.plot()

# %% [markdown]
# ## Simulation
#
# The prepared recipe assigns `signal_1`, `signal_2`, and the finite `ground`
# conductor as Q3D `SignalNet`s. Q3D therefore exports the full 3x3 Maxwell
# capacitance matrix relative to infinity.

# %%
simulation = prepare_interdigital_capacitor_q3d_simulation(
    coupon=coupon,
    run_root=REPO_ROOT / "build" / "simulation" / "aedt" / "interdigital_capacitor_q3d",
    run_id=RUN_ID,
    region_padding_um=REGION_PADDING_UM,
    setup_name=Q3D_SETUP_NAME,
    matrix_problem_types=Q3D_MATRIX_PROBLEM_TYPES,
    matrix_types=Q3D_MATRIX_TYPES,
)
if RUN_SOLVER:
    subprocess.run(simulation.solve_command, cwd=simulation.package.package_dir, check=True)

# %% [markdown]
# ## Results

# %%
if RUN_SOLVER:
    load_q3d_capacitance_result(simulation).show()
else:
    print("Set RUN_SOLVER = True to generate and display the Q3D result.")
