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
# # Finite-ground CPW Cross Section — Q2D Extraction

# %% [markdown]
# ## Setup and Imports

# %%
from __future__ import annotations

import subprocess
from pathlib import Path

from scgsim.aedt import (
    MatrixRunControl,
    PdkMaterial,
    Q2dConductorSpec,
    Q2dRectangleSpec,
    Q2dSpec,
    prepare_handoff,
    resolve_results,
)

import orpen_sc_pdk
from orpen_sc_pdk.materials import get_material_records

orpen_sc_pdk.activate()

# %% [markdown]
# ## Setup and Run Controls

# %%
# Choose prepare_handoff to create files, run to execute, or analyze_handoff to inspect results.
WORKFLOW_ACTION = "prepare_handoff"  # prepare_handoff | run | analyze_handoff
# Use a new unique ID for each prepared run; SCGSim refuses non-empty output directories.
RUN_ID = "cpw_finite_ground_q2d"
# Root directory for prepared geometry and handoff artifacts.
OUTPUT_ROOT = Path("notebooks/.artifacts/CrossSectionSimulation/CpwFiniteGround")
RUN_DIR = OUTPUT_ROOT / RUN_ID
RETURNED_RUN_DIR = RUN_DIR  # Analysis input directory containing returned results.

# %% [markdown]
# ## Create Simulation Component / Coupon

# %%
# Cross-section signal width (um).
signal_width_um = 10.0
# Signal-to-ground gap (um).
gap_um = 10.0
# Ground conductor width (um).
ground_width_um = 40.0
# Substrate width (um).
substrate_width_um = 200.0
# Metal thickness (um).
metal_thickness_um = 0.2
# Substrate thickness (um).
substrate_thickness_um = 500.0

# %% [markdown]
# ## Initialize AEDT Project / App

# %%
# AEDT version used for project generation.
aedt_version = "2024.2"
# AEDT project name.
project_name = RUN_ID
# AEDT design name.
design_name = "CpwFiniteGroundQ2d"

# %% [markdown]
# ## Import GDS and Build the HFSS/Q3D/Q2D Model
#
# Q2D uses SCGSim's native rectangle contract; no GDS file is imported.

# %%
signal_half_width_um = signal_width_um / 2
left_ground_xmin_um = -(signal_half_width_um + gap_um + ground_width_um)
right_ground_xmin_um = signal_half_width_um + gap_um
rectangles = (
    # Each row gives name, lower-left coordinate (um), size (um), and material.
    Q2dRectangleSpec(
        "Substrate",
        (-substrate_width_um / 2, -substrate_thickness_um),
        (substrate_width_um, substrate_thickness_um),
        "Si",
    ),
    Q2dRectangleSpec(
        "Signal",
        (-signal_half_width_um, 0.0),
        (signal_width_um, metal_thickness_um),
        "Nb",
    ),
    Q2dRectangleSpec(
        "GroundLeft",
        (left_ground_xmin_um, 0.0),
        (ground_width_um, metal_thickness_um),
        "Nb",
    ),
    Q2dRectangleSpec(
        "GroundRight",
        (right_ground_xmin_um, 0.0),
        (ground_width_um, metal_thickness_um),
        "Nb",
    ),
)

# %% [markdown]
# ## Geometry Verification

# %%
print(rectangles)

# %% [markdown]
# ## Materials and Boundaries

# %%
material_records = get_material_records()
materials = {
    material_id: PdkMaterial(
        material_id,
        material_records[material_id]["material_kind"],
        material_records[material_id]["is_superconducting"],
        material_records[material_id]["aedt_library_name"],
    )
    for material_id in ("vacuum", "Si", "Nb")
}
# Region padding tuple in -X,+X,-Y,+Y order (um).
region_padding_um = (100.0, 100.0, 1000.0, 100.0)

# %% [markdown]
# ## Ports / Nets / Excitations

# %%
conductors = (
    # Each row gives conductor name, net name, rectangle members, and thickness (um).
    Q2dConductorSpec("Signal", "SignalLine", ("Signal",), metal_thickness_um),
    Q2dConductorSpec(
        "Ground", "ReferenceGround", ("GroundLeft", "GroundRight"), metal_thickness_um
    ),
)

# %% [markdown]
# ## Simulation Setup

# %%
# Matrix solve frequency (GHz).
frequency_ghz = 6.0
# Maximum adaptive passes.
maximum_passes = 3
spec = Q2dSpec(
    project_name=project_name,
    design_name=design_name,
    materials=materials,
    vacuum_material_id="vacuum",
    rectangles=rectangles,
    conductors=conductors,
    run_control=MatrixRunControl("Setup1", frequency_ghz, maximum_passes),
    region_padding_um=region_padding_um,
    aedt_version=aedt_version,
)

# %% [markdown]
# ## Simulation Configuration

# %%
HANDOFF = None
if WORKFLOW_ACTION in {"prepare_handoff", "run"}:
    HANDOFF = prepare_handoff(spec=spec, output_dir=RUN_DIR)
print(HANDOFF)

# %% [markdown]
# ## Solve and Export

# %%
if WORKFLOW_ACTION == "run":
    subprocess.run([str(HANDOFF.script_path)], cwd=HANDOFF.run_dir, check=True)

# %% [markdown]
# ## Adaptive-Pass Convergence / Solver Diagnostics

# %%
RESULT = resolve_results(RETURNED_RUN_DIR) if WORKFLOW_ACTION == "analyze_handoff" else None
print(RESULT)

# %% [markdown]
# ## Results: Plots and Readable Tables
#
# ### Physics Analysis Results

# %%
RESULT.physics_results() if RESULT is not None else None

# %% [markdown]
# ### Simulation Performance / Benchmarks

# %%
RESULT.simulation_benchmark() if RESULT is not None else None

# %% [markdown]
# ## Save and Release AEDT

# %%
print(RESULT.project_path if RESULT is not None else HANDOFF.archive_path)
