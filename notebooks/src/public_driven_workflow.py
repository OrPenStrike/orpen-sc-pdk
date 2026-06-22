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
# # Public Driven CPW workflow
#
# This notebook demonstrates the public OrPen PDK Driven Palace workflow using
# the same visible chain as the reusable `gsim` examples: geometry, layer stack,
# mesh, config, solver handoff, report loading, and display views.

# %%
from __future__ import annotations

import warnings
from datetime import date
from pathlib import Path

from gsim.palace import (
    DrivenSim,
    resolve_palace_result,
)
from gsim.palace.mesh import build_postprocessing_config_from_manifest
from IPython.display import display

from orpen_sc_pdk.cells import cpw_straight
from orpen_sc_pdk.config import PATH
from orpen_sc_pdk.materials import get_gsim_material_overlay
from orpen_sc_pdk.pdk import PDK
from orpen_sc_pdk.simulation import resolve_public_palace_run_profile

warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    message="Material model for evaluation at wavelength=.*has unspecified validity range.*",
    module="gsim.palace.materials",
)

PDK.activate()

# User-facing run-folder controls. The root is chosen in the notebook; the run
# id follows the NCUAS date-plus-same-day-index convention.
NOTEBOOK_ROOT = PATH.simulation / "notebooks" / "public_driven_workflow"
NOTEBOOK_RUN_DATE = date.today().isoformat()
NOTEBOOK_RUN_INDEX = 1
NOTEBOOK_RUN_ID = f"{NOTEBOOK_RUN_DATE}-Run{NOTEBOOK_RUN_INDEX:02d}"
NOTEBOOK_RUN_ROOT = NOTEBOOK_ROOT / NOTEBOOK_RUN_ID
# Set this to an existing completed run folder, then rerun Resolve and Report.
NOTEBOOK_ANALYSIS_RUN_ROOT: Path | None = None
NOTEBOOK_PREPARE_RUN_STAGE = NOTEBOOK_ANALYSIS_RUN_ROOT is None
if NOTEBOOK_PREPARE_RUN_STAGE:
    NOTEBOOK_RUN_ROOT.mkdir(parents=True, exist_ok=True)

# %% [markdown]
# ## Geometry

# %%
if NOTEBOOK_PREPARE_RUN_STAGE:
    output_dir = NOTEBOOK_RUN_ROOT
    component = cpw_straight(length=300, signal_width=10, gap=6, ground_width=40)

    sim = DrivenSim()
    sim.set_output_dir(output_dir)
    sim.set_geometry(component)

# %% [markdown]
# ## LayerStack

# %%
if NOTEBOOK_PREPARE_RUN_STAGE:
    sim.set_stack(PDK.get_layer_stack())
    sim.activate_substrate(
        layer="D0_SUBSTRATE",
        die="D0",
        margin_x=500.0,
        margin_y=500.0,
    )
    sim.activate_outer_vacuum(
        margin_x=0.0,
        margin_y=0.0,
        z_above=1000.0,
        z_below=0.0,
    )

# %% [markdown]
# ## Mesh

# %%
if NOTEBOOK_PREPARE_RUN_STAGE:
    sim.add_cpw_port("o1", layer="D0_TOP_M1", s_width=10, gap_width=6, length=10)
    sim.add_cpw_port(
        "o2",
        layer="D0_TOP_M1",
        s_width=10,
        gap_width=6,
        length=10,
        excited=False,
    )
    mesh_result = sim.mesh(
        preset="coarse",
        refined_mesh_size=20,
        max_mesh_size=200,
        planar_conductors=True,
        auto_size=False,
    )

# %% [markdown]
# ## Config

# %%
if NOTEBOOK_PREPARE_RUN_STAGE:
    sim.set_driven(fmin=4e9, fmax=8e9, num_points=3, excitation_port="o1")
    sim.set_palace_version("0.16.0")
    sim.set_refinement(
        max_its=15,
        tol=1e-3,
        update_fraction=0.3,
    )
    sim.set_linear_solver(
        tol=1e-8,
        max_its=2000,
        estimator_mg=True,
    )
    sim.set_output_formats(paraview=True, grid_function=False)
    postprocessing = build_postprocessing_config_from_manifest(mesh_result.manifest)

# %% [markdown]
# ## Run Stage (handoff package)

# %%
PALACE_HPC_PROFILE = "f1:ct112"
PALACE_HPC_RESOURCE_OVERRIDES = {
    "account": "public_alloc",
    "ntasks_per_node": 4,
    "cpus_per_task": 28,
    "wall_time": "12:00:00",
}
PALACE_SBATCH_JOB_NAME = "orpen_public_driven"

if NOTEBOOK_PREPARE_RUN_STAGE:
    run_profile = resolve_public_palace_run_profile(
        PALACE_HPC_PROFILE,
        resource_overrides=PALACE_HPC_RESOURCE_OVERRIDES,
    )
    sim.write_config(
        postprocessing=postprocessing,
        validate_mesh=False,
        material_overlay=get_gsim_material_overlay(),
        hints=run_profile.to_palace_config_hints(),
        prepare_run_folder=True,
        validate_schema=True,
    )
    sbatch_handoff = sim.write_slurm_sbatch_handoff(
        run_profile,
        job_name=PALACE_SBATCH_JOB_NAME,
        metadata={
            "component": component.name,
            "problem_type": "Driven",
            "workflow": "public_driven_workflow",
        },
    )
    sim.generate_handoff_package(
        write_config=False,
        profile=run_profile,
        script_path=sbatch_handoff.script_path,
        metadata={
            "component": component.name,
            "problem_type": "Driven",
            "workflow": "public_driven_workflow",
            "sbatch_path": sbatch_handoff.script_path.relative_to(output_dir).as_posix(),
        },
    )

# %% [markdown]
# ## Resolve

# %%
analysis_run_root = Path(NOTEBOOK_ANALYSIS_RUN_ROOT or NOTEBOOK_RUN_ROOT)
resolved_result = resolve_palace_result(analysis_run_root, problem_type="Driven")
driven_report = resolved_result.load_report(require_report=True).require_report()

# %% [markdown]
# ## Visualize

# %%
driven_report.show_all_results()

# %% [markdown]
# ## Report

# %%
display(
    {
        "analysis_run_folder": analysis_run_root.as_posix(),
        "problem_type": driven_report.problem_type,
    }
)
