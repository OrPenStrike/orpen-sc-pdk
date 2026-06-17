# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.17.3
# ---

# %% [markdown]
# # Public Electrostatic capacitor local workflow
#
# This notebook demonstrates the public OrPen PDK Electrostatic Palace workflow
# using local `sim.run_local()` execution. It shows same-layer terminal selection
# and writes raw Palace outputs into the run folder for Resolve/Report review.

# %%
from __future__ import annotations

import os
import warnings
from datetime import date
from pathlib import Path

from gsim.palace import (
    ElectrostaticSim,
    resolve_palace_result,
)
from gsim.palace.mesh import build_postprocessing_config_from_manifest
from IPython.display import display

from orpen_sc_pdk.cells import martinis2022_differential_ribbon_capacitor
from orpen_sc_pdk.config import PATH
from orpen_sc_pdk.materials import get_gsim_material_overlay
from orpen_sc_pdk.pdk import PDK

warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    message="Material model for evaluation at wavelength=.*has unspecified validity range.*",
    module="gsim.palace.materials",
)

PDK.activate()

# User-facing run-folder controls. The root is chosen in the notebook; the run
# id follows the NCUAS date-plus-same-day-index convention.
NOTEBOOK_ROOT = PATH.simulation / "notebooks" / "public_electrostatic_local_workflow"
NOTEBOOK_RUN_DATE = date.today().isoformat()
NOTEBOOK_RUN_INDEX = 1
NOTEBOOK_RUN_ID = f"{NOTEBOOK_RUN_DATE}-Run{NOTEBOOK_RUN_INDEX:02d}"
NOTEBOOK_RUN_ROOT = NOTEBOOK_ROOT / NOTEBOOK_RUN_ID
# Set this to an existing completed run folder, then rerun Resolve and Report.
NOTEBOOK_ANALYSIS_RUN_ROOT: Path | None = None
NOTEBOOK_PREPARE_RUN_STAGE = NOTEBOOK_ANALYSIS_RUN_ROOT is None
NOTEBOOK_REQUIRE_REPORT = False
if NOTEBOOK_PREPARE_RUN_STAGE:
    NOTEBOOK_RUN_ROOT.mkdir(parents=True, exist_ok=True)

# %% [markdown]
# ## Geometry

# %%
if NOTEBOOK_PREPARE_RUN_STAGE:
    output_dir = NOTEBOOK_RUN_ROOT
    component = martinis2022_differential_ribbon_capacitor(
        a_um=20,
        b_um=35,
        ell_r_um=160,
    )
    positive_port = component.ports["o_mesh_positive_electrode"]
    negative_port = component.ports["o_mesh_negative_electrode"]
    positive_center = tuple(float(value) for value in positive_port.center)
    negative_center = tuple(float(value) for value in negative_port.center)

    sim = ElectrostaticSim()
    sim.set_output_dir(output_dir)
    sim.set_geometry(component)

# %% [markdown]
# ## LayerStack

# %%
if NOTEBOOK_PREPARE_RUN_STAGE:
    sim.set_stack(
        include_substrate=True,
        substrate_thickness=20,
        add_oxide_dielectric=False,
        add_passivation_dielectric=False,
    )
    sim.set_airbox(margin_x=40, margin_y=40, z_above=50, z_below=10)

# %% [markdown]
# ## Mesh

# %%
if NOTEBOOK_PREPARE_RUN_STAGE:
    sim.add_terminal("positive", layer="D0_TOP_M1", center=positive_center)
    sim.add_terminal("negative", layer="D0_TOP_M1", center=negative_center)
    mesh_result = sim.mesh(
        preset="coarse",
        refined_mesh_size=20,
        max_mesh_size=200,
        margin_x=40,
        margin_y=40,
        planar_conductors=True,
        auto_size=False,
    )

# %% [markdown]
# ## Config

# %%
if NOTEBOOK_PREPARE_RUN_STAGE:
    sim.set_electrostatic(save_fields=0)
    postprocessing = build_postprocessing_config_from_manifest(mesh_result.manifest)
    config_path = output_dir / "config.json"

# %% [markdown]
# ## Run Stage (run_local)

# %%
PALACE_RUN_LOCAL = False
PALACE_USE_APPTAINER = False
PALACE_SIF_PATH = os.environ.get("PALACE_SIF")
PALACE_EXECUTABLE = os.environ.get("PALACE_EXECUTABLE", "palace")
PALACE_EXECUTABLE_MODE = os.environ.get("PALACE_EXECUTABLE_MODE", "wrapper")
PALACE_SETUP_COMMANDS = ("spack load palace",)
PALACE_NUM_PROCESSES = int(os.environ.get("PALACE_NP", "1"))
PALACE_NUM_THREADS = int(os.environ.get("PALACE_NT", "1"))
PALACE_SERIAL = os.environ.get("PALACE_SERIAL", "0") == "1"

if NOTEBOOK_PREPARE_RUN_STAGE:
    sim.write_config(
        postprocessing=postprocessing,
        validate_mesh=False,
        material_overlay=get_gsim_material_overlay(),
        prepare_run_folder=True,
    )
    local_run_summary = {
        "problem_type": "Electrostatic",
        "run_local": "skipped",
        "run_folder": output_dir.as_posix(),
        "config_path": config_path.as_posix(),
        "setup_commands": list(PALACE_SETUP_COMMANDS),
    }
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
        local_results = sim.run_local(**local_run_kwargs)
        local_run_summary.update(
            {
                "run_local": "completed",
                "result_type": type(local_results).__name__,
            }
        )

# %% [markdown]
# ## Resolve

# %%
analysis_run_root = NOTEBOOK_ANALYSIS_RUN_ROOT
if analysis_run_root is None:
    if "output_dir" not in globals():
        raise ValueError("Set NOTEBOOK_ANALYSIS_RUN_ROOT or enable Run Stage preparation.")
    analysis_run_root = output_dir
analysis_run_root = Path(analysis_run_root)

resolved_result = resolve_palace_result(analysis_run_root, problem_type="Electrostatic")
report_bundle = resolved_result.load_report(
    frequency_ghz=5.0, require_report=NOTEBOOK_REQUIRE_REPORT
)
electrostatic_report = (
    report_bundle.require_report() if NOTEBOOK_REQUIRE_REPORT else report_bundle.report
)

# %% [markdown]
# ## Visualize

# %%
run_stage_summary = {
    "analysis_run_folder": analysis_run_root.as_posix(),
    "resolved_problem_type": resolved_result.problem_type,
    "resolved_result_names": list(resolved_result.artifacts.result_names),
    "missing_artifacts": list(resolved_result.artifacts.missing_artifacts),
    "report_status": report_bundle.report_status,
    "report_message": report_bundle.report_message,
}
if "local_run_summary" in globals():
    run_stage_summary.update(local_run_summary)
if "component" in globals():
    run_stage_summary["component"] = component.name
if "config_path" in globals() and config_path.exists():
    run_stage_summary["config_path"] = config_path.as_posix()
if "mesh_result" in globals():
    run_stage_summary["mesh_path"] = mesh_result.mesh_path.as_posix()

display(run_stage_summary)


# %% [markdown]
# ## Report

# %%
if electrostatic_report is None:
    display(
        {
            "report_status": report_bundle.report_status,
            "report_message": report_bundle.report_message,
            "analysis_run_folder": analysis_run_root.as_posix(),
        }
    )
else:
    display(
        {
            "report_problem_type": electrostatic_report.problem_type,
            "resolved_report_status": report_bundle.report_status,
            "terminal_names": list(electrostatic_report.capacitance.terminal_names),
            "capacitance_shape": list(electrostatic_report.capacitance.dataframe.shape),
            "pass_count": int(len(electrostatic_report.terminal_c_pass_summary)),
            "loss_budget_rows": int(len(electrostatic_report.loss_budget)),
            "missing_reports": list(electrostatic_report.missing_reports),
            "benchmark": electrostatic_report.benchmark.to_dataframe().to_dict("records"),
        }
    )
    electrostatic_report.show_all_results()
    display(electrostatic_report.capacitance.visualize()["terminal_C_heatmap"])
    display(electrostatic_report.loss.visualize()["loss_budget_bar_plot"])
