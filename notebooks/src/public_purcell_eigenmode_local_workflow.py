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
# # Public Purcell Filter Eigenmode local workflow
#
# This notebook demonstrates the same layout-authored readout launcher sheets in
# an Eigenmode setup. The sheets are passive LumpedPort boundaries; mesh marker
# ports remain layout metadata and do not become Palace port sheets.

# %%
from __future__ import annotations

import os
import warnings
from datetime import date
from pathlib import Path

from gsim.palace import (
    EigenmodeSim,
    resolve_palace_result,
)
from gsim.palace.mesh import build_postprocessing_config_from_manifest
from IPython.display import display

from orpen_sc_pdk.config import PATH
from orpen_sc_pdk.materials import get_gsim_material_overlay
from orpen_sc_pdk.pdk import PDK
from orpen_sc_pdk.samples.simulation_demos import global_purcell_filter_demo_chip
from orpen_sc_pdk.simulation import get_gsim_palace_simulation_layer_catalog

warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    message="Material model for evaluation at wavelength=.*has unspecified validity range.*",
    module="gsim.palace.materials",
)

PDK.activate()

READOUT_PORT_NAMES = ("o_lumped_readout_in", "o_lumped_readout_out")

# User-facing run-folder controls. The root is chosen in the notebook; the run
# id follows the NCUAS date-plus-same-day-index convention.
NOTEBOOK_ROOT = PATH.simulation / "notebooks" / "public_purcell_eigenmode_local_workflow"
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
    component = global_purcell_filter_demo_chip()

    sim = EigenmodeSim()
    sim.set_output_dir(output_dir)
    sim.set_geometry(component)
    sim.set_simulation_layers(get_gsim_palace_simulation_layer_catalog())

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
    sim.add_port(
        "o_lumped_readout_in",
        layer="D0_TOP_M1",
        length=1.0,
        direction=component.ports["o_lumped_readout_in"].info.get(
            "palace_lumped_port_direction",
            "+X",
        ),
        excited=False,
        generate_sheet=False,
    )
    sim.add_port(
        "o_lumped_readout_out",
        layer="D0_TOP_M1",
        length=1.0,
        direction=component.ports["o_lumped_readout_out"].info.get(
            "palace_lumped_port_direction",
            "+X",
        ),
        excited=False,
        generate_sheet=False,
    )
    mesh_result = sim.mesh(
        preset="coarse",
        refined_mesh_size=50,
        max_mesh_size=1000,
        planar_conductors=True,
        auto_size=False,
    )
    port_sheet_entries = mesh_result.manifest.entries_for_role("port_surface")
    port_sheet_physical_names = tuple(entry.name for entry in port_sheet_entries)
    if len(port_sheet_physical_names) != len(READOUT_PORT_NAMES):
        raise ValueError(
            "Expected one Palace port sheet for each readout port, got "
            f"{port_sheet_physical_names!r}."
        )
    port_sheet_sources = {
        entry.name: entry.metadata.get("sheet_source") for entry in port_sheet_entries
    }
    if any(source != "layout-authored" for source in port_sheet_sources.values()):
        raise ValueError(f"Expected layout-authored sheets, got {port_sheet_sources!r}.")

# %% [markdown]
# ## Config

# %%
if NOTEBOOK_PREPARE_RUN_STAGE:
    sim.set_eigenmode(num_modes=1, target=6e9)
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
# ## Run Stage (run_local)

# %%
PALACE_RUN_LOCAL = False
PALACE_USE_APPTAINER = False
PALACE_SIF_PATH = os.environ.get("PALACE_SIF")
PALACE_EXECUTABLE = os.environ.get("PALACE_EXECUTABLE", "palace")
PALACE_EXECUTABLE_MODE = os.environ.get("PALACE_EXECUTABLE_MODE", "wrapper")
PALACE_SETUP_COMMANDS = ('eval "$(spack load --sh palace)"',)
PALACE_NUM_PROCESSES = int(os.environ.get("PALACE_NP", "1"))
PALACE_NUM_THREADS = int(os.environ.get("PALACE_NT", "1"))
PALACE_SERIAL = os.environ.get("PALACE_SERIAL", "0") == "1"

if NOTEBOOK_PREPARE_RUN_STAGE:
    sim.write_config(
        postprocessing=postprocessing,
        validate_mesh=False,
        material_overlay=get_gsim_material_overlay(),
        prepare_run_folder=True,
        validate_schema=True,
    )
    if PALACE_RUN_LOCAL:
        if PALACE_EXECUTABLE_MODE not in {"wrapper", "binary"}:
            raise ValueError("PALACE_EXECUTABLE_MODE must be 'wrapper' or 'binary'")
        local_run_kwargs = {
            "use_apptainer": PALACE_USE_APPTAINER,
            "num_processes": PALACE_NUM_PROCESSES,
            "num_threads": PALACE_NUM_THREADS,
            "verbose": True,
        }
        if PALACE_USE_APPTAINER:
            local_run_kwargs["palace_sif_path"] = PALACE_SIF_PATH
        else:
            local_run_kwargs["palace_executable"] = PALACE_EXECUTABLE
            local_run_kwargs["executable_mode"] = PALACE_EXECUTABLE_MODE
            local_run_kwargs["serial"] = PALACE_SERIAL
            local_run_kwargs["setup_commands"] = PALACE_SETUP_COMMANDS
        sim.run_local(**local_run_kwargs)

# %% [markdown]
# ## Resolve

# %%
analysis_run_root = Path(NOTEBOOK_ANALYSIS_RUN_ROOT or NOTEBOOK_RUN_ROOT)
resolved_result = resolve_palace_result(analysis_run_root, problem_type="Eigenmode")
eigenmode_report = resolved_result.load_report(require_report=True).require_report()

# %% [markdown]
# ## Visualize

# %%
eigenmode_report.show_all_results()

# %% [markdown]
# ## Report

# %%
display(
    {
        "analysis_run_folder": analysis_run_root.as_posix(),
        "problem_type": eigenmode_report.problem_type,
    }
)
