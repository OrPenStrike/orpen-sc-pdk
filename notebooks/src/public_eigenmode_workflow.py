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
# # Public Eigenmode resonator workflow
#
# This notebook demonstrates the public OrPen PDK Eigenmode Palace workflow
# using visible `gsim` setup cells. It keeps private layouts out of scope while
# showing mesh/config handoff, dielectric interface classification, convergence,
# loss-budget, and performance display surfaces.

# %%
from __future__ import annotations

import warnings
from datetime import date
from pathlib import Path

from gsim.palace import (
    EigenmodeSim,
    resolve_palace_result,
)
from gsim.palace.mesh import (
    SurfaceFluxSpec,
    build_postprocessing_config_from_manifest,
)
from IPython.display import display

from orpen_sc_pdk.cells import resonator
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
NOTEBOOK_ROOT = PATH.simulation / "notebooks" / "public_eigenmode_workflow"
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
    component = resonator(
        length=1200,
        meanders=2,
        coupling_length=120,
        hanger_straight_length=80,
        cpw_radius=30,
        bend_npoints=8,
    )

    sim = EigenmodeSim()
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
    sim.set_airbox(margin_x=50, margin_y=50, z_above=50, z_below=10)

# %% [markdown]
# ## Mesh

# %%
if NOTEBOOK_PREPARE_RUN_STAGE:
    mesh_result = sim.mesh(
        preset="coarse",
        refined_mesh_size=20,
        max_mesh_size=200,
        margin_x=50,
        margin_y=50,
        planar_conductors=True,
        auto_size=False,
    )

# %% [markdown]
# ## Config

# %%
if NOTEBOOK_PREPARE_RUN_STAGE:
    sim.set_eigenmode(num_modes=2, target=6e9)
    surface_flux_postprocessing = build_postprocessing_config_from_manifest(
        mesh_result.manifest,
        surface_flux=(
            SurfaceFluxSpec(
                role="boundary_surface",
                entry_names=("absorbing",),
                flux_type="Power",
                two_sided=None,
            ),
        ),
    )
    config_path = output_dir / "config.json"

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
PALACE_SBATCH_JOB_NAME = "orpen_public_eigenmode"

if NOTEBOOK_PREPARE_RUN_STAGE:
    run_profile = resolve_public_palace_run_profile(
        PALACE_HPC_PROFILE,
        resource_overrides=PALACE_HPC_RESOURCE_OVERRIDES,
    )
    sim.write_config(
        postprocessing=surface_flux_postprocessing,
        validate_mesh=False,
        material_overlay=get_gsim_material_overlay(),
        hints=run_profile.to_palace_config_hints(),
        prepare_run_folder=True,
    )
    sbatch_handoff = sim.write_slurm_sbatch_handoff(
        run_profile,
        job_name=PALACE_SBATCH_JOB_NAME,
        metadata={
            "component": component.name,
            "problem_type": "Eigenmode",
            "workflow": "public_eigenmode_workflow",
        },
    )
    run_handle = sim.generate_handoff_package(
        write_config=False,
        profile=run_profile,
        script_path=sbatch_handoff.script_path,
        metadata={
            "component": component.name,
            "problem_type": "Eigenmode",
            "workflow": "public_eigenmode_workflow",
            "sbatch_path": sbatch_handoff.script_path.relative_to(output_dir).as_posix(),
        },
    )

# %% [markdown]
# ## Resolve

# %%
analysis_run_root = NOTEBOOK_ANALYSIS_RUN_ROOT
if analysis_run_root is None:
    if "run_handle" not in globals():
        raise ValueError("Set NOTEBOOK_ANALYSIS_RUN_ROOT or enable Run Stage preparation.")
    analysis_run_root = run_handle.run_folder
analysis_run_root = Path(analysis_run_root)

resolved_result = resolve_palace_result(analysis_run_root, problem_type="Eigenmode")
report_bundle = resolved_result.load_report(require_report=NOTEBOOK_REQUIRE_REPORT)
eigenmode_report = (
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
if "run_handle" in globals():
    run_stage_summary.update(
        {
            "problem_type": run_handle.problem_type,
            "hpc_profile": PALACE_HPC_PROFILE,
            "sbatch_path": None
            if run_handle.script_path is None
            else run_handle.script_path.as_posix(),
            "archive_path": None
            if run_handle.archive_path is None
            else run_handle.archive_path.as_posix(),
        }
    )
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
if eigenmode_report is None:
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
            "report_problem_type": eigenmode_report.problem_type,
            "resolved_report_status": report_bundle.report_status,
            "mode_count": int(eigenmode_report.eigenmodes.n_modes),
            "pass_count": int(len(eigenmode_report.pass_summary)),
            "loss_budget_rows": int(len(eigenmode_report.loss_budget)),
            "missing_reports": list(eigenmode_report.missing_reports),
            "benchmark": eigenmode_report.benchmark.to_dataframe().to_dict("records"),
        }
    )
    eigenmode_report.show_all_results()
    display(eigenmode_report.loss.visualize()["loss_budget_bar_plot"])
    display(eigenmode_report.dielectric_interfaces)
