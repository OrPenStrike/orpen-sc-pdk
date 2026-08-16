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
# # Finite-ground CPW — HFSS Eigenmode

# %% [markdown]
# ## Setup and Imports

# %%
from __future__ import annotations

import subprocess
from pathlib import Path

import gdsfactory as gf
from IPython.display import display
from scgsim.aedt import (
    EigenmodeRunControl,
    HfssEigenmodeSpec,
    LayerImport,
    LengthMeshSpec,
    ObjectBinding,
    PdkMaterial,
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
WORKFLOW_ACTION = "prepare_handoff"  # prepare_handoff | run | analyze_handoff
RUN_ID = "cpw_finite_ground_hfss_eigenmode"
OUTPUT_ROOT = Path("notebooks/.artifacts/ComponentSimulation/CpwFiniteGround")
RUN_DIR = OUTPUT_ROOT / RUN_ID
RETURNED_RUN_DIR = RUN_DIR

# %% [markdown]
# ## Create Simulation Component / Coupon

# %%
trace_length_um = 500.0
signal_width_um = 10.0
gap_um = 6.0
ground_width_um = 80.0
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
aedt_version = "2024.2"
project_name = RUN_ID
design_name = "CpwFiniteGroundEigenmode"

# %% [markdown]
# ## Import GDS and Build the HFSS/Q3D/Q2D Model

# %%
layer_imports = (
    LayerImport(1, 0, "D0_TOP_M1", 0.0, 0.0),
    LayerImport(201, 0, "D0_SUBSTRATE", -substrate_thickness_um, 0.0),
)
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
region_padding_um = (100.0, 100.0, 100.0, 100.0, 1000.0, 1000.0)

# %% [markdown]
# ## Ports / Nets / Excitations

# %%
ground_objects = ("D0_TOP_M1_2", "D0_TOP_M1_3")

# %% [markdown]
# ## Simulation Setup

# %%
minimum_frequency_ghz = 3.0
num_modes = 2
maximum_passes = 6
maximum_delta_frequency_percent = 5.0
spec = HfssEigenmodeSpec(
    gds_path=SOURCE_GDS,
    project_name=project_name,
    design_name=design_name,
    materials=materials,
    vacuum_material_id="vacuum",
    layer_imports=layer_imports,
    object_bindings=object_bindings,
    run_control=EigenmodeRunControl(
        "Setup1",
        minimum_frequency_ghz,
        num_modes,
        maximum_passes,
        maximum_delta_frequency_percent,
    ),
    region_padding_um=region_padding_um,
    length_mesh=LengthMeshSpec(("D0_TOP_M1_1",), ground_objects, signal_width_um),
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
