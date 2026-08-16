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

import gdsfactory as gf
from IPython.display import display
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
WORKFLOW_ACTION = "prepare_handoff"  # prepare_handoff | run | analyze_handoff
RUN_ID = "cpw_finite_ground_q2d"
OUTPUT_ROOT = Path("notebooks/.artifacts/CrossSectionSimulation/CpwFiniteGround")
RUN_DIR = OUTPUT_ROOT / RUN_ID
RETURNED_RUN_DIR = RUN_DIR

# %% [markdown]
# ## Create Simulation Component / Coupon

# %%
signal_width_um = 10.0
gap_um = 10.0
ground_width_um = 40.0
metal_thickness_um = 0.2
substrate_thickness_um = 500.0
cross_section = gf.Component()
cross_section.add_polygon(
    [(-100.0, -500.0), (100.0, -500.0), (100.0, 0.0), (-100.0, 0.0)],
    layer=(201, 0),
)
cross_section.add_polygon([(-5.0, 0.0), (5.0, 0.0), (5.0, 0.2), (-5.0, 0.2)], layer=(1, 0))
cross_section.add_polygon([(-55.0, 0.0), (-15.0, 0.0), (-15.0, 0.2), (-55.0, 0.2)], layer=(2, 0))
cross_section.add_polygon([(15.0, 0.0), (55.0, 0.0), (55.0, 0.2), (15.0, 0.2)], layer=(2, 0))
cross_section.plot()

# %% [markdown]
# ## Initialize AEDT Project / App

# %%
aedt_version = "2024.2"
project_name = RUN_ID
design_name = "CpwFiniteGroundQ2d"

# %% [markdown]
# ## Import GDS and Build the HFSS/Q3D/Q2D Model

# %%
rectangles = (
    Q2dRectangleSpec("Substrate", (-100.0, -substrate_thickness_um), (200.0, 500.0), "Si"),
    Q2dRectangleSpec("Signal", (-signal_width_um / 2, 0.0), (signal_width_um, 0.2), "Nb"),
    Q2dRectangleSpec("GroundLeft", (-55.0, 0.0), (ground_width_um, 0.2), "Nb"),
    Q2dRectangleSpec("GroundRight", (15.0, 0.0), (ground_width_um, 0.2), "Nb"),
)

# %% [markdown]
# ## Geometry Verification

# %%
display(cross_section)

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
region_padding_um = (100.0, 100.0, 1000.0, 100.0)

# %% [markdown]
# ## Ports / Nets / Excitations

# %%
conductors = (
    Q2dConductorSpec("Signal", "SignalLine", ("Signal",), metal_thickness_um),
    Q2dConductorSpec(
        "Ground", "ReferenceGround", ("GroundLeft", "GroundRight"), metal_thickness_um
    ),
)

# %% [markdown]
# ## Simulation Setup

# %%
frequency_ghz = 6.0
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
