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
# # Martinis 2022 Ribbon Surface EPR Route A HPC Handoff
#
# Demo notebook for the public OrPen PDK Martinis 2022 differential ribbon
# capacitor. The notebook selects one Surface EPR representation and leaves
# mesh lowering, inset partitioning, config rows, and result loading to `gsim`.

# %%
from __future__ import annotations

import json
import math
import os
import warnings
from collections import Counter
from datetime import date
from pathlib import Path

from gsim.palace import ElectrostaticSim, resolve_palace_result
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

SURFACE_EPR_ROUTE = "A"
DEMO_MODE = "hpc_handoff"
PALACE_ORDER = 3
LOCAL_MAX_ITS = 3
HPC_MAX_ITS = 15
PALACE_UPDATE_FRACTION = 0.3

NOTEBOOK_ROOT = (
    PATH.simulation
    / "notebooks"
    / "Inset_Surface_EPR_Demo"
    / "martinis2022_ribbon_route_a_hpc_handoff"
)
NOTEBOOK_RUN_DATE = date.today().isoformat()
NOTEBOOK_RUN_INDEX = int(os.environ.get("NOTEBOOK_RUN_INDEX", "1"))
NOTEBOOK_RUN_ID = f"{NOTEBOOK_RUN_DATE}-Run{NOTEBOOK_RUN_INDEX:02d}"
NOTEBOOK_RUN_ROOT = NOTEBOOK_ROOT / NOTEBOOK_RUN_ID
NOTEBOOK_ANALYSIS_RUN_ROOT: Path | None = None
NOTEBOOK_PREPARE_RUN_STAGE = NOTEBOOK_ANALYSIS_RUN_ROOT is None
if NOTEBOOK_PREPARE_RUN_STAGE:
    NOTEBOOK_RUN_ROOT.mkdir(parents=True, exist_ok=True)

# %% [markdown]
# ## Geometry

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
    {
        "surface_epr_route": SURFACE_EPR_ROUTE,
        "demo_mode": DEMO_MODE,
        "paper_scale_reference_capacitance_fF": round(paper_reference_capacitance_ff, 1),
        "notebook_reference_capacitance_fF": round(notebook_reference_capacitance_ff, 1),
    }
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
# ## Surface EPR Interface Selection

# %%
SURFACE_EPR_INSET_MARGINS_NM = (0, 50, 100, 200, 500, 1000)
SURFACE_EPR_INSET_MARGINS_UM = tuple(margin_nm / 1000 for margin_nm in SURFACE_EPR_INSET_MARGINS_NM)
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
SURFACE_EPR_MA_FACE_KIND = "top" if SURFACE_EPR_ROUTE == "A" else ("top", "sidewall")
SURFACE_EPR_INTERFACE_LABELS = (
    ("MS", "bottom"),
    ("MA", SURFACE_EPR_MA_FACE_KIND),
    ("SA", "top"),
)

display(
    {
        "route": SURFACE_EPR_ROUTE,
        "planar_conductors": SURFACE_EPR_PLANAR_CONDUCTORS,
        "inset_margins_nm": SURFACE_EPR_INSET_MARGINS_NM,
        "active_interface_presets": SURFACE_EPR_ACTIVE_INTERFACE_PRESET_NAMES,
        "interface_labels": SURFACE_EPR_INTERFACE_LABELS,
        "material_policy": "Martinis2022 MS plus public Woods2019 MA/SA across A/B/C",
    }
)

# %% [markdown]
# ## Layer Stack And Mesh

# %%
public_material_overlay = get_gsim_material_overlay()
if NOTEBOOK_PREPARE_RUN_STAGE:
    sim = ElectrostaticSim()
    sim.set_output_dir(output_dir)
    sim.set_geometry(component)
    sim.set_stack(PDK.get_layer_stack())
    sim.activate_substrate("D0_SUBSTRATE", die="D0", margin_x=500.0, margin_y=500.0)
    sim.activate_outer_vacuum(margin_x=0.0, margin_y=0.0, z_above=1000.0, z_below=0.0)
    surface_epr_interface_presets = validate_interface_preset_records(SURFACE_EPR_INTERFACE_PRESETS)
    sim.set_surface_epr(
        representation=SURFACE_EPR_ROUTE,
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
                "face_kind": SURFACE_EPR_MA_FACE_KIND,
            },
            "SA": {
                "preset_name": "Woods2019_Si_SA",
                "preset": surface_epr_interface_presets["Woods2019_Si_SA"],
                "face_kind": "top",
            },
        },
    )
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
    surface_epr_entries = tuple(
        entry
        for entry in mesh_result.manifest.entries
        if entry.metadata.get("surface_epr")
        and entry.metadata.get("representation") == SURFACE_EPR_ROUTE
    )
    surface_epr_child_entries = tuple(
        entry
        for entry in surface_epr_entries
        if entry.metadata.get("surface_epr_summary_kind") != "total"
    )
    physical_group_preview = tuple(
        {
            "name": entry.name,
            "interface_type": entry.metadata.get("interface_type"),
            "face_kind": entry.metadata.get("face_kind"),
            "attrs": entry.attributes,
            "bbox": entry.metadata.get("bbox"),
            "centroid": entry.metadata.get("centroid"),
        }
        for entry in surface_epr_child_entries[:12]
    )
    display(
        {
            "mesh_file": (output_dir / "palace.msh").as_posix(),
            "child_group_counts": Counter(
                (entry.metadata.get("interface_type"), entry.metadata.get("face_kind"))
                for entry in surface_epr_child_entries
            ),
            "physical_group_preview": physical_group_preview,
        }
    )

# %% [markdown]
# ## Palace Config

# %%
if NOTEBOOK_PREPARE_RUN_STAGE:
    sim.set_electrostatic(save_fields=0)
    sim.set_palace_version("0.16.0")
    sim.set_numerical(order=PALACE_ORDER)
    sim.set_refinement(
        max_its=LOCAL_MAX_ITS if DEMO_MODE == "local" else HPC_MAX_ITS,
        tol=1e-3,
        update_fraction=PALACE_UPDATE_FRACTION,
    )
    sim.set_linear_solver(tol=1e-8, max_its=2000, estimator_mg=True)
    sim.set_output_formats(paraview=True, grid_function=False)

    PALACE_HPC_PROFILE = "f1:ct112"
    PALACE_HPC_RESOURCE_OVERRIDES = {
        "account": "public_alloc",
        "ntasks_per_node": 4,
        "cpus_per_task": 28,
        "memory_mb": 524288,
        "wall_time": "12:00:00",
    }
    PALACE_SBATCH_JOB_NAME = f"orpen_epr_{SURFACE_EPR_ROUTE.lower()}"
    run_profile = resolve_public_palace_run_profile(
        PALACE_HPC_PROFILE,
        resource_overrides=PALACE_HPC_RESOURCE_OVERRIDES,
    )
    config_path = sim.write_config(
        validate_mesh=False,
        material_overlay=public_material_overlay,
        hints=run_profile.to_palace_config_hints(),
        prepare_run_folder=True,
        validate_schema=True,
    )
    palace_config = json.loads(config_path.read_text())
    boundary_postprocessing = palace_config.get("Boundaries", {}).get("Postprocessing", {})
    dielectric_rows = boundary_postprocessing.get("Dielectric", ())
    handoff_metadata = {
        "component": component.name,
        "problem_type": "Electrostatic",
        "workflow": f"martinis2022_ribbon_route_{SURFACE_EPR_ROUTE.lower()}_hpc_handoff",
    }
    sbatch_handoff = sim.write_slurm_sbatch_handoff(
        run_profile,
        job_name=PALACE_SBATCH_JOB_NAME,
        metadata=handoff_metadata,
    )
    sbatch_relpath = sbatch_handoff.script_path.relative_to(output_dir).as_posix()
    sim.generate_handoff_package(
        write_config=False,
        profile=run_profile,
        script_path=sbatch_handoff.script_path,
        metadata={
            **handoff_metadata,
            "sbatch_path": sbatch_relpath,
        },
    )
    display(
        {
            "config_file": config_path.relative_to(output_dir).as_posix(),
            "sbatch_file": sbatch_handoff.script_path.relative_to(output_dir).as_posix(),
            "hpc_profile": PALACE_HPC_PROFILE,
            "hpc_max_its": HPC_MAX_ITS,
            "solver_order": PALACE_ORDER,
            "memory_mb": PALACE_HPC_RESOURCE_OVERRIDES["memory_mb"],
            "run_command": f"sbatch {sbatch_relpath}",
            "dielectric_postprocessing_rows": len(dielectric_rows),
            "dielectric_postprocessing_row_counts": dict(
                Counter(row.get("Type") for row in dielectric_rows)
            ),
            "surface_flux_postprocessing_rows": len(boundary_postprocessing.get("SurfaceFlux", ())),
        }
    )

# %% [markdown]
# ## Resolve And Report

# %%
analysis_run_root = Path(NOTEBOOK_ANALYSIS_RUN_ROOT or NOTEBOOK_RUN_ROOT)
try:
    resolved_result = resolve_palace_result(analysis_run_root, problem_type="Electrostatic")
    electrostatic_report = resolved_result.load_report(require_report=True).require_report()
except Exception as exc:
    electrostatic_report = None
    display(
        {"analysis_run_folder": analysis_run_root.as_posix(), "report_status": type(exc).__name__}
    )
else:
    electrostatic_report.show_all_results()
    display(
        {
            "analysis_run_folder": analysis_run_root.as_posix(),
            "problem_type": electrostatic_report.problem_type,
            "paper_scale_reference_capacitance_fF": round(paper_reference_capacitance_ff, 1),
            "notebook_reference_capacitance_fF": round(notebook_reference_capacitance_ff, 1),
        }
    )
