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
# # Public Surface EPR ribbon capacitor representation B local workflow
#
# This notebook demonstrates the public OrPen PDK Surface EPR workflow on the
# Martinis 2022 differential ribbon capacitor. It exercises the Route B
# finite-metal shell path and exposes a direct `sim.run_local()` Run Stage. The
# notebook selects MS/MA/SA presets while `gsim` owns shell lowering, SA seed
# splitting, cumulative inset postprocessing, and report rendering.

# %%
from __future__ import annotations

import math
import os
import warnings
from datetime import date
from pathlib import Path

from gsim.palace import (
    ElectrostaticSim,
    resolve_palace_result,
)
from IPython.display import display

from orpen_sc_pdk.cells import martinis2022_differential_ribbon_capacitor
from orpen_sc_pdk.config import PATH
from orpen_sc_pdk.materials import (
    get_gsim_material_overlay,
    get_interface_preset_records,
    validate_interface_preset_records,
)
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
NOTEBOOK_ROOT = (
    PATH.simulation
    / "notebooks"
    / ("public_surface_epr_ribbon_capacitor_representation_b_local_workflow")
)
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
#
# The geometry uses the public PDK's Martinis 2022 differential ribbon
# capacitor. The paper-scale comparison below follows Martinis 2022,
# "Surface loss calculations and design of a superconducting transmon qubit
# with tapered wiring" ([DOI: 10.1038/s41534-022-00530-6](https://doi.org/10.1038/s41534-022-00530-6)).

# %%
MARTINIS_RIBBON_A_UM = 50.0
MARTINIS_RIBBON_B_UM = 100.0
MARTINIS_PAPER_LENGTH_UM = 1300.0
MARTINIS_NOTEBOOK_LENGTH_UM = 1391.0
SILICON_RELATIVE_PERMITTIVITY = 11.7
VACUUM_PERMITTIVITY_F_PER_UM = 8.8541878128e-18

ribbon_k_ratio = MARTINIS_RIBBON_A_UM / MARTINIS_RIBBON_B_UM
ribbon_ck_approx = (
    math.log(2.0 * (1.0 + math.sqrt(ribbon_k_ratio)) / (1.0 - math.sqrt(ribbon_k_ratio))) / math.pi
)
ribbon_effective_permittivity = (1.0 + SILICON_RELATIVE_PERMITTIVITY) / 2.0
paper_reference_capacitance_ff = (
    ribbon_effective_permittivity
    * VACUUM_PERMITTIVITY_F_PER_UM
    * MARTINIS_PAPER_LENGTH_UM
    / ribbon_ck_approx
    * 1e15
)
notebook_reference_capacitance_ff = (
    ribbon_effective_permittivity
    * VACUUM_PERMITTIVITY_F_PER_UM
    * MARTINIS_NOTEBOOK_LENGTH_UM
    / ribbon_ck_approx
    * 1e15
)

display(
    [
        {
            "reference": "Martinis 2022 paper-scale ribbon",
            "a_um": MARTINIS_RIBBON_A_UM,
            "b_um": MARTINIS_RIBBON_B_UM,
            "ell_r_um": MARTINIS_PAPER_LENGTH_UM,
            "approx_capacitance_fF": round(paper_reference_capacitance_ff, 1),
        },
        {
            "reference": "Notebook geometry, same approximation",
            "a_um": MARTINIS_RIBBON_A_UM,
            "b_um": MARTINIS_RIBBON_B_UM,
            "ell_r_um": MARTINIS_NOTEBOOK_LENGTH_UM,
            "approx_capacitance_fF": round(notebook_reference_capacitance_ff, 1),
        },
    ]
)

# %%
if NOTEBOOK_PREPARE_RUN_STAGE:
    output_dir = NOTEBOOK_RUN_ROOT
    component = martinis2022_differential_ribbon_capacitor(
        a_um=MARTINIS_RIBBON_A_UM,
        b_um=MARTINIS_RIBBON_B_UM,
        ell_r_um=MARTINIS_NOTEBOOK_LENGTH_UM,
    ).copy()
    positive_port = component.ports["o_mesh_positive_electrode"]
    negative_port = component.ports["o_mesh_negative_electrode"]
    positive_center = tuple(float(value) for value in positive_port.center)
    negative_center = tuple(float(value) for value in negative_port.center)

# %% [markdown]
# ## Surface EPR interface selection
#
# `gsim` owns full 3D interface discovery, Route B finite-metal shell lowering,
# SA seed splitting, and inset partitioning. This notebook only selects the
# public MS/MA/SA material presets for local postprocessing.

# %%
SURFACE_EPR_INSET_NM = 50
SURFACE_EPR_INSET_MARGINS_NM = (0, 50, 100, 200, 500, 1000)
SURFACE_EPR_INSET_MARGINS_UM = tuple(margin_nm / 1000 for margin_nm in SURFACE_EPR_INSET_MARGINS_NM)
MARTINIS2022_RIBBON_MS_REFERENCE_PARTICIPATION = 1.42e-4
PUBLIC_INTERFACE_PRESET_RECORDS = get_interface_preset_records()
SURFACE_EPR_INTERFACE_PRESETS = {
    "martinis2022_ms": {
        "interface_type": "MS",
        "thickness": 0.002,
        "permittivity": 9.8,
        "loss_tangent": 0.005,
        "source": "Martinis 2022 Table 2 ribbon example",
    },
    "Woods2019_Si_MA": PUBLIC_INTERFACE_PRESET_RECORDS["Woods2019_Si_MA"],
    "Woods2019_Si_SA": PUBLIC_INTERFACE_PRESET_RECORDS["Woods2019_Si_SA"],
}
SURFACE_EPR_ACTIVE_INTERFACE_PRESET_NAMES = (
    "martinis2022_ms",
    "Woods2019_Si_MA",
    "Woods2019_Si_SA",
)
SURFACE_EPR_PLANAR_CONDUCTORS = False

display(
    {
        "gsim_generated_inset_nm": SURFACE_EPR_INSET_NM,
        "gsim_generated_inset_margins_nm": SURFACE_EPR_INSET_MARGINS_NM,
        "metal_model": "finite_shell_route_b",
        "planar_conductors": SURFACE_EPR_PLANAR_CONDUCTORS,
        "active_interface_presets": SURFACE_EPR_ACTIVE_INTERFACE_PRESET_NAMES,
        "active_loss_channels": ("MA", "MS", "SA"),
        "table_2_ribbon_ms_reference_participation": (
            MARTINIS2022_RIBBON_MS_REFERENCE_PARTICIPATION
        ),
    }
)

# %% [markdown]
# ## Material bridge
#
# Surface EPR channel parameters in this Martinis ribbon notebook are filled
# from Martinis 2022 Table 2 for MS and public Woods2019 presets for MA/SA. The
# PDK material overlay below is still passed to `gsim` for bulk stack material
# resolution.

# %%
public_material_overlay = get_gsim_material_overlay()
public_materials = public_material_overlay["materials"]
display(
    {
        "overlay_materials_used": {name: public_materials[name] for name in ("Si", "vacuum")},
        "overlay_material_aliases": public_material_overlay["material_aliases"],
        "surface_epr_interface_presets": SURFACE_EPR_INTERFACE_PRESETS,
    }
)

# %% [markdown]
# ## LayerStack

# %%
if NOTEBOOK_PREPARE_RUN_STAGE:
    sim = ElectrostaticSim()
    sim.set_output_dir(output_dir)
    sim.set_geometry(component)
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
    surface_epr_interface_presets = validate_interface_preset_records(SURFACE_EPR_INTERFACE_PRESETS)
    sim.set_surface_epr(
        representation="B",
        inset_margins_um=SURFACE_EPR_INSET_MARGINS_UM,
        interfaces={
            "MS": {
                "preset_name": "martinis2022_ms",
                "preset": surface_epr_interface_presets["martinis2022_ms"],
                "face_kind": "bottom",
            },
            "MA": {
                "preset_name": "Woods2019_Si_MA",
                "preset": surface_epr_interface_presets["Woods2019_Si_MA"],
                "face_kind": ("top", "sidewall"),
            },
            "SA": {
                "preset_name": "Woods2019_Si_SA",
                "preset": surface_epr_interface_presets["Woods2019_Si_SA"],
                "face_kind": "top",
            },
        },
    )

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
        planar_conductors=SURFACE_EPR_PLANAR_CONDUCTORS,
        auto_size=False,
    )

# %% [markdown]
# ## Config

# %%
if NOTEBOOK_PREPARE_RUN_STAGE:
    sim.set_electrostatic(save_fields=0)
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
    surface_epr_manifest_entry_names = tuple(
        entry.name
        for entry in mesh_result.manifest.entries
        if entry.metadata.get("surface_epr") and entry.metadata.get("representation") == "B"
    )
    display(
        {
            "surface_epr_interfaces": ("MS bottom", "MA top", "MA sidewall", "SA top"),
            "mesh_manifest_surface_epr_entries": surface_epr_manifest_entry_names,
            "active_loss_channels": ("MA", "MS", "SA"),
        }
    )

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
        validate_mesh=False,
        material_overlay=public_material_overlay,
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
resolved_result = resolve_palace_result(analysis_run_root, problem_type="Electrostatic")
electrostatic_report = resolved_result.load_report(require_report=True).require_report()

# %% [markdown]
# ## Visualize

# %%
electrostatic_report.show_all_results()

# %% [markdown]
# ## Report

# %%
display(
    {
        "analysis_run_folder": analysis_run_root.as_posix(),
        "problem_type": electrostatic_report.problem_type,
        "paper_scale_reference_capacitance_fF": round(paper_reference_capacitance_ff, 1),
        "notebook_reference_capacitance_fF": round(notebook_reference_capacitance_ff, 1),
    }
)
