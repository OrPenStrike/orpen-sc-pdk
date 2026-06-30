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
# # Public Surface EPR ribbon capacitor representation C workflow
#
# This notebook demonstrates Surface EPR representation C on the public OrPen
# PDK Martinis 2022 differential ribbon capacitor. It keeps notebook
# responsibility to public example/profile selection while `gsim` owns interface
# discovery, inset partitioning, and Palace postprocessing through
# `sim.set_surface_epr(...)`. This C-route notebook validates generated
# MS/MA/SA child inset physical groups and logical total postprocessing rows.

# %%
from __future__ import annotations

import math
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
NOTEBOOK_ROOT = (
    PATH.simulation
    / "notebooks"
    / ("public_surface_epr_ribbon_capacitor_representation_c_workflow")
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
# %% [markdown]
# ## Surface EPR interface selection
#
# `gsim` owns Surface EPR interface discovery, inset partitioning, and Palace
# postprocessing. This notebook selects representation C, validates the
# generated MS/MA/SA child physical groups, and activates public MS/MA/SA
# presets for Surface EPR postprocessing. `TOTAL` rows are logical aggregates
# built by `gsim`, not overlapping mesh physical groups.

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
SURFACE_EPR_RETAIN_3D_METAL_VOLUME = True
SURFACE_EPR_PLANAR_CONDUCTORS = False

display(
    {
        "surface_epr_representation": "C",
        "retains_3d_metal_volume": SURFACE_EPR_RETAIN_3D_METAL_VOLUME,
        "planar_conductors": SURFACE_EPR_PLANAR_CONDUCTORS,
        "gsim_generated_inset_nm": SURFACE_EPR_INSET_NM,
        "gsim_generated_inset_margins_nm": SURFACE_EPR_INSET_MARGINS_NM,
        "validated_mesh_interface_types": ("MA", "MS", "SA"),
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
# Surface EPR channel parameters use the Martinis Table 2 MS ribbon value and
# public Woods2019 MA/SA candidate presets from the PDK material database. The
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
        representation="C",
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
    sim.add_terminal(
        "positive",
        layer="D0_TOP_M1",
        port_name="o_mesh_positive_electrode",
        physical_label="positive",
    )
    sim.add_terminal(
        "negative",
        layer="D0_TOP_M1",
        port_name="o_mesh_negative_electrode",
        physical_label="negative",
    )
    mesh_result = sim.mesh(
        preset="coarse",
        refined_mesh_size=20,
        max_mesh_size=200,
        planar_conductors=SURFACE_EPR_PLANAR_CONDUCTORS,
        auto_size=False,
    )
    route_c_generated_group_examples = tuple(
        entry.name
        for entry in mesh_result.manifest.entries
        if entry.metadata.get("surface_epr")
        and entry.metadata.get("representation") == "C"
        and entry.metadata.get("surface_epr_summary_kind") != "total"
    )[:8]
    display(
        {
            "surface_epr_representation": "C",
            "terminal_labels": {
                "positive": "o_mesh_positive_electrode",
                "negative": "o_mesh_negative_electrode",
            },
            "validated_mesh_interface_types": ("MA", "MS", "SA"),
            "generated_child_physical_group_examples": route_c_generated_group_examples,
            "mesh_file": (output_dir / "palace.msh").relative_to(output_dir).as_posix(),
        }
    )

# %% [markdown]
# ## Config

# %%
if NOTEBOOK_PREPARE_RUN_STAGE:
    sim.set_electrostatic(save_fields=0)
    sim.set_palace_version("0.16.0")
    sim.set_numerical(order=3)
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
        if entry.metadata.get("surface_epr")
        and entry.metadata.get("representation") == "C"
        and entry.metadata.get("surface_epr_summary_kind") == "total"
    )
    surface_epr_child_entry_names = tuple(
        entry.name
        for entry in mesh_result.manifest.entries
        if entry.metadata.get("surface_epr")
        and entry.metadata.get("representation") == "C"
        and entry.metadata.get("surface_epr_summary_kind") != "total"
    )
    display(
        {
            "surface_epr_interfaces": ("MS bottom", "MA top", "MA sidewall", "SA top"),
            "logical_total_surface_epr_entries": surface_epr_manifest_entry_names,
            "child_surface_epr_entry_count": len(surface_epr_child_entry_names),
            "solver_order": 3,
            "active_loss_channels": ("MA", "MS", "SA"),
            "validated_mesh_interface_types": ("MA", "MS", "SA"),
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
    "memory_mb": 524288,
    "wall_time": "12:00:00",
}
PALACE_SBATCH_JOB_NAME = "orpen_public_surface_epr"

if NOTEBOOK_PREPARE_RUN_STAGE:
    run_profile = resolve_public_palace_run_profile(
        PALACE_HPC_PROFILE,
        resource_overrides=PALACE_HPC_RESOURCE_OVERRIDES,
    )
    palace_config_file = sim.write_config(
        validate_mesh=False,
        material_overlay=public_material_overlay,
        hints=run_profile.to_palace_config_hints(),
        prepare_run_folder=True,
        validate_schema=True,
    )
    handoff_metadata = {
        "component": component.name,
        "problem_type": "Electrostatic",
        "workflow": "public_surface_epr_ribbon_capacitor_representation_c_workflow",
    }
    sbatch_handoff = sim.write_slurm_sbatch_handoff(
        run_profile,
        job_name=PALACE_SBATCH_JOB_NAME,
        metadata=handoff_metadata,
    )
    sim.generate_handoff_package(
        write_config=False,
        profile=run_profile,
        script_path=sbatch_handoff.script_path,
        metadata={
            **handoff_metadata,
            "sbatch_path": sbatch_handoff.script_path.relative_to(output_dir).as_posix(),
        },
    )
    display(
        {
            "palace_config_file": palace_config_file.relative_to(output_dir).as_posix(),
            "palace_handoff_script": sbatch_handoff.script_path.relative_to(output_dir).as_posix(),
            "palace_run_command": (
                f"sbatch {sbatch_handoff.script_path.relative_to(output_dir).as_posix()}"
            ),
        }
    )

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
