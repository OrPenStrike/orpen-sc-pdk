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
# ## Setup and Imports

# %%
from __future__ import annotations

import subprocess
from pathlib import Path

import gdsfactory as gf
from IPython.display import display
from scgsim.aedt import (
    LayerImport,
    MatrixRunControl,
    ObjectBinding,
    PdkMaterial,
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
RUN_ID = "cpw_finite_ground_q3d"
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
coupon << gf.get_component(
    "cpw_straight",
    length=trace_length_um,
    signal_width=signal_width_um,
    gap=gap_um,
    ground_width=ground_width_um,
)
coupon << gf.components.rectangle(
    size=(trace_length_um, signal_width_um + 2 * (gap_um + ground_width_um)),
    centered=True,
    layer=LAYER.D0_SUBSTRATE_AREA,
)
SOURCE_GDS = OUTPUT_ROOT / "geometry" / f"{RUN_ID}.gds"
SOURCE_GDS.parent.mkdir(parents=True, exist_ok=True)
coupon.write_gds(SOURCE_GDS, with_metadata=False)
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
# GDS layer number/datatype, AEDT name, bottom z and thickness (um).
layer_imports = (
    LayerImport(1, 0, "D0_TOP_M1", 0.0, metal_thickness_um),
    LayerImport(201, 0, "D0_SUBSTRATE", -substrate_thickness_um, 0.0),
)
# Imported object name, source layer, semantic role, and material ID.
object_bindings = (
    ObjectBinding("D0_TOP_M1_1", 1, "signal", "Nb"),
    ObjectBinding("D0_TOP_M1_2", 1, "ground", "Nb"),
    ObjectBinding("D0_TOP_M1_3", 1, "ground", "Nb"),
    ObjectBinding("D0_SUBSTRATE_4", 201, "substrate", "Si"),
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
    Q3dNetSpec("Signal", "Signal", ("D0_TOP_M1_1",), "D0_TOP_M1_1", "-X", "D0_TOP_M1_1", "+X"),
    Q3dNetSpec("GroundLeft", "Ground", ("D0_TOP_M1_2",)),
    Q3dNetSpec("GroundRight", "Ground", ("D0_TOP_M1_3",)),
)

# %% [markdown]
# ## Simulation Setup

# %%
# Matrix solve frequency (GHz).
frequency_ghz = 6.0
# Maximum adaptive passes.
maximum_passes = 3
spec = Q3dSpec(
    gds_path=SOURCE_GDS,
    project_name=project_name,
    design_name=design_name,
    materials=materials,
    vacuum_material_id="vacuum",
    layer_imports=layer_imports,
    object_bindings=object_bindings,
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
