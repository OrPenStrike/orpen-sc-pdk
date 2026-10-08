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
# # Finite-ground CPW — Q3D Extraction

# %% [markdown]
# Source-only SCGSim v2 alignment, CONVERGING / LOCAL CANDIDATE; not executed.
# In a separate consumer environment with this OrPen checkout installed:
# `python -m pip install "scgsim[aedt] @ git+https://github.com/OrPenStrike/scgsim.git@cc1424c84ffe9d295a57dbabb3c2ab6431110f6c"`
# The ordinary project pin remains 2eed1eb; uv sync does not select this v2 cohort.
# Historical native results retain their original run/runtime identities.
# No native preparation, solve, Resolve or Report is claimed for this source.
#
# ## Setup and Imports

# %%
from __future__ import annotations

import subprocess
from pathlib import Path

import gdsfactory as gf
from IPython.display import display
from scgsim.aedt import (
    MatrixRunControl,
    PdkMaterial,
    Q3dBodySpec,
    Q3dNetSpec,
    Q3dSpec,
    prepare_handoff,
    resolve_results,
)

import orpen_sc_pdk
from orpen_sc_pdk.materials import get_material_records
from orpen_sc_pdk.tech import LAYER

orpen_sc_pdk.activate()

# %% [markdown]
# ## Setup and Run Controls

# %%
# Choose prepare_handoff to create files, run to execute, or analyze_handoff to inspect results.
WORKFLOW_ACTION = "prepare_handoff"  # prepare_handoff | run | analyze_handoff
# Use a new unique ID for each prepared run; SCGSim refuses non-empty output directories.
RUN_ID = "cpw_finite_ground_q3d_v2_20261009_01"
# Root directory for prepared geometry and handoff artifacts.
OUTPUT_ROOT = Path("notebooks/.artifacts/ComponentSimulation/CpwFiniteGround")
RUN_DIR = OUTPUT_ROOT / RUN_ID
RETURNED_RUN_DIR = RUN_DIR  # Analysis input directory containing returned results.

# %% [markdown]
# ## Create Simulation Component / Coupon

# %%
# CPW trace length along X (um).
trace_length_um = 500.0
# Signal conductor width (um).
signal_width_um = 10.0
# Gap from signal to each ground conductor (um).
gap_um = 6.0
# Width of each ground conductor (um).
ground_width_um = 80.0
# Metal thickness (um).
metal_thickness_um = 0.2
# Substrate thickness below the metal (um).
substrate_thickness_um = 500.0
coupon = gf.Component()
coupon << gf.components.rectangle(
    size=(trace_length_um, signal_width_um),
    centered=True,
    layer=LAYER.D0_TOP_M1_DRAW,
)
top_ground = coupon << gf.components.rectangle(
    size=(trace_length_um, ground_width_um), centered=True, layer=LAYER.D0_TOP_M1_DRAW
)
top_ground.movey((signal_width_um + ground_width_um) / 2 + gap_um)
bottom_ground = coupon << gf.components.rectangle(
    size=(trace_length_um, ground_width_um), centered=True, layer=LAYER.D0_TOP_M1_DRAW
)
bottom_ground.movey(-((signal_width_um + ground_width_um) / 2 + gap_um))
coupon << gf.components.rectangle(
    size=(trace_length_um, signal_width_um + 2 * (gap_um + ground_width_um)),
    centered=True,
    layer=LAYER.D0_SUBSTRATE_AREA,
)
SOURCE_GDS = OUTPUT_ROOT / "geometry" / f"{RUN_ID}.gds"
if WORKFLOW_ACTION in {"prepare_handoff", "run"}:
    SOURCE_GDS.parent.mkdir(parents=True, exist_ok=True)
    with SOURCE_GDS.open("xb") as stream:
        coupon.write_gds(stream.name, with_metadata=False)
coupon.plot()

# %% [markdown]
# ## Initialize AEDT Project / App

# %%
# AEDT version used for project generation.
aedt_version = "2024.2"
# AEDT project name.
project_name = RUN_ID
# AEDT design name.
design_name = "CpwFiniteGroundQ3d"

# %% [markdown]
# ## Import GDS and Build the HFSS/Q3D/Q2D Model

# %%
# Source-free body-v3 records mirror the four GDSFactory rectangles exactly.
# Body IDs are authored identities, not guesses about native imported names.
x = trace_length_um / 2
s = signal_width_um / 2
g = s + gap_um
w = ground_width_um
bodies = (
    Q3dBodySpec("SignalBody", ((-x, -s), (x, -s), (x, s), (-x, s)), (),
                0.0, metal_thickness_um, "Nb", "signal", "Signal"),
    Q3dBodySpec("GroundLeftBody", ((-x, g), (x, g), (x, g+w), (-x, g+w)), (),
                0.0, metal_thickness_um, "Nb", "ground", "GroundLeft"),
    Q3dBodySpec("GroundRightBody", ((-x, -g-w), (x, -g-w), (x, -g), (-x, -g)), (),
                0.0, metal_thickness_um, "Nb", "ground", "GroundRight"),
    Q3dBodySpec("SubstrateBody", ((-x, -g-w), (x, -g-w), (x, g+w), (-x, g+w)), (),
                -substrate_thickness_um, 0.0, "Si", "substrate", None),
)

# %% [markdown]
# ## Geometry Verification

# %%
display(coupon)

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
# Padding around the model in -X, +X, -Y, +Y, -Z, +Z directions (um).
region_padding_um = (0.0, 0.0, 100.0, 100.0, 1000.0, 1000.0)

# %% [markdown]
# ## Ports / Nets / Excitations

# %%
# Net names, roles, object members, and terminal directions define Q3D excitations.
nets = (
    # Net name, net role, member objects, and optional terminal object/directions.
    Q3dNetSpec("Signal", "Signal", ("SignalBody",), "SignalBody", "-X", "SignalBody", "+X"),
    Q3dNetSpec("GroundLeft", "Ground", ("GroundLeftBody",)),
    Q3dNetSpec("GroundRight", "Ground", ("GroundRightBody",)),
)

# %% [markdown]
# ## Simulation Setup

# %%
# Matrix solve frequency (GHz).
frequency_ghz = 6.0
# Maximum adaptive passes.
maximum_passes = 3
spec = Q3dSpec(
    project_name=project_name,
    design_name=design_name,
    materials=materials,
    vacuum_material_id="vacuum",
    bodies=bodies,
    nets=nets,
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
display(HANDOFF)

# %% [markdown]
# ## Solve and Export

# %%
if WORKFLOW_ACTION == "run":
    subprocess.run([str(HANDOFF.script_path)], cwd=HANDOFF.run_dir, check=True)

# %% [markdown]
# ## Adaptive-Pass Convergence / Solver Diagnostics

# %%
RESULT = resolve_results(RETURNED_RUN_DIR) if WORKFLOW_ACTION == "analyze_handoff" else None
display(RESULT)

# %% [markdown]
# ## Results: Plots and Readable Tables
#
# ### Physics Analysis Results

# %%
if RESULT is not None:
    display(RESULT.physics_results())

# %% [markdown]
# ### Simulation Performance / Benchmarks

# %%
if RESULT is not None:
    display(RESULT.simulation_benchmark())

# %% [markdown]
# ## Save and Release AEDT

# %%
display(RESULT.project_path if RESULT is not None else HANDOFF.archive_path)
