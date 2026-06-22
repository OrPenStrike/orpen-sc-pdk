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
    build_dielectric_interface_specs_from_material_kinds,
    build_postprocessing_config_from_manifest,
)
from IPython.display import display

from orpen_sc_pdk.cells import resonator
from orpen_sc_pdk.config import PATH
from orpen_sc_pdk.materials import (
    get_gsim_material_kind_alias_map,
    get_gsim_material_kind_map,
    get_gsim_material_overlay,
    get_interface_preset_records,
    validate_interface_preset_records,
)
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
    mesh_result = sim.mesh(
        preset="coarse",
        refined_mesh_size=20,
        max_mesh_size=200,
        planar_conductors=True,
        auto_size=False,
    )

# %% [markdown]
# ## Material Database Overlay
#
# This resonator workflow demonstrates the PDK-owned `materials.json` path:
# OrPen exports material records and source-backed interface presets, then
# `gsim` resolves those records while writing Palace `config.json`.

# %%
public_material_overlay = get_gsim_material_overlay()
public_interface_presets = validate_interface_preset_records(get_interface_preset_records())
RESONATOR_INTERFACE_PRESET_BY_TYPE = {"SA": "Woods2019_Si_SA"}

display(
    {
        "material_database": "orpen_sc_pdk/materials.json",
        "overlay_materials_used": {
            name: public_material_overlay["materials"][name]
            for name in ("Si", "vacuum", "Woods2019_Si_SA_effective")
        },
        "interface_presets_used": {
            name: public_interface_presets[name]
            for name in RESONATOR_INTERFACE_PRESET_BY_TYPE.values()
        },
    }
)

# %% [markdown]
# ## Config

# %%
if NOTEBOOK_PREPARE_RUN_STAGE:
    sim.set_eigenmode(num_modes=2, target=6e9)
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
    resonator_interface_specs = build_dielectric_interface_specs_from_material_kinds(
        mesh_result.manifest,
        material_kind_by_name=get_gsim_material_kind_map(),
        material_name_aliases=get_gsim_material_kind_alias_map(),
        presets=public_interface_presets,
        preset_by_interface_type=RESONATOR_INTERFACE_PRESET_BY_TYPE,
        interface_types_by_kind_pair={("dielectric", "vacuum"): "SA"},
    )
    postprocessing = build_postprocessing_config_from_manifest(
        mesh_result.manifest,
        dielectric_interfaces=resonator_interface_specs,
    )
    display(
        {
            "dielectric_interface_specs": len(resonator_interface_specs),
            "preset_by_interface_type": RESONATOR_INTERFACE_PRESET_BY_TYPE,
        }
    )

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
        postprocessing=postprocessing,
        validate_mesh=False,
        material_overlay=public_material_overlay,
        hints=run_profile.to_palace_config_hints(),
        prepare_run_folder=True,
        validate_schema=True,
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
    sim.generate_handoff_package(
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
