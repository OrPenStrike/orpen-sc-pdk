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
# # Martinis 2022 Ribbon Native Mask Surface EPR Handoff
#
# This notebook prepares the public OrPen Martinis 2022 differential ribbon
# capacitor for a Palace fork that supports native `Dielectric.Mask`
# postprocessing. `gsim` owns mesh generation, base Palace config generation,
# Slurm script rendering, archive packaging, and report loading. This notebook
# owns only the run-local native-mask config patch and the result-side
# convergence view.

# %%
from __future__ import annotations

import csv
import json
import math
import re
import shutil
import warnings
from collections import defaultdict
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
from gsim.palace import ElectrostaticSim, resolve_palace_result
from gsim.palace.handoff import PalaceSlurmLauncherSpec
from gsim.palace.mesh import build_postprocessing_config_from_manifest
from IPython.display import display

from orpen_sc_pdk.cells import martinis2022_differential_ribbon_capacitor
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

DEMO_MODE = "hpc_handoff"
PALACE_ORDER = 2
HPC_MAX_ITS = 20
PALACE_UPDATE_FRACTION = 0.15
PALACE_REFINEMENT_TOL = 1e-12
PALACE_LINEAR_TOL = 1e-6

NATIVE_MASK_MARGINS_L0_UNITS = (0.0, 0.01, 0.05, 0.1, 0.2, 0.5, 1.0)
NATIVE_MASK_MARGINS_NM = tuple(int(round(value * 1000)) for value in NATIVE_MASK_MARGINS_L0_UNITS)
NATIVE_MASK_SOURCE_INDEX = 1
NATIVE_MASK_VISIBLE_MARGINS_NM = (0, 10, 50, 100, 200, 500, 1000)
NATIVE_MASK_CONFIG_SCHEMA = "palace_fork_dielectric_mask"

LEGACY_RUN02_SUBSTRATE_PERMITTIVITY = 11.7
LEGACY_RUN02_SUBSTRATE_CONDUCTIVITY = 0.0
LEGACY_RUN02_INTERFACE_PARAMS = {
    "SA": {"thickness": 0.002, "permittivity": 3.8, "loss_tangent": 0.0017},
    "MS": {"thickness": 0.002, "permittivity": 9.8, "loss_tangent": 0.00048},
    "MA": {"thickness": 0.002, "permittivity": 9.8, "loss_tangent": 0.0033},
}

NOTEBOOK_ROOT = (
    PATH.simulation
    / "notebooks"
    / "Native_Masked_Surface_EPR"
    / "martinis2022_ribbon_native_mask_hpc_handoff"
)
NOTEBOOK_RUN_DATE = date.today().isoformat()
NOTEBOOK_RUN_INDEX = 1
NOTEBOOK_RUN_ID = f"{NOTEBOOK_RUN_DATE}-Run{NOTEBOOK_RUN_INDEX:02d}"
NOTEBOOK_RUN_ROOT = NOTEBOOK_ROOT / NOTEBOOK_RUN_ID
NOTEBOOK_ANALYSIS_RUN_ROOT: Path | None = None  # Default: None
# NOTEBOOK_ANALYSIS_RUN_ROOT = Path("/path/to/handoff/run/folder")
NOTEBOOK_PREPARE_RUN_STAGE = NOTEBOOK_ANALYSIS_RUN_ROOT is None
DEFAULT_PALACE_NATIVE_MASK_SOURCE_EXECUTABLE = (
    PATH.simulation.parents[2] / "palace" / "build" / "bin" / "palace-x86_64.bin"
)
PALACE_HPC_PROFILE = "f1:ct112"
PALACE_HPC_RESOURCE_OVERRIDES = {
    "account": "public_alloc",
    "partition": "ltlab-workstation1",
    "nodes": 1,
    "ntasks_per_node": 2,
    "cpus_per_task": 16,
    "memory_mb": 480000,
    "wall_time": "12:00:00",
}
PALACE_NATIVE_MASK_EXECUTABLE = "palace"
PALACE_NATIVE_MASK_COMMAND_STYLE = "binary"
PALACE_NATIVE_MASK_SETUP_COMMANDS: tuple[str, ...] = ()
PALACE_NATIVE_MASK_BUNDLE_EXECUTABLE = True
PALACE_NATIVE_MASK_SOURCE_EXECUTABLE = DEFAULT_PALACE_NATIVE_MASK_SOURCE_EXECUTABLE
PALACE_SBATCH_JOB_NAME = "orpen_native_mask_epr"
if NOTEBOOK_PREPARE_RUN_STAGE:
    NOTEBOOK_RUN_ROOT.mkdir(parents=True, exist_ok=True)


def _as_int_tuple(value: Any) -> tuple[int, ...]:
    if value is None:
        return ()
    if isinstance(value, bool):
        return ()
    if isinstance(value, int):
        return (value,)
    if isinstance(value, str):
        return (int(value),)
    if isinstance(value, list | tuple | set):
        return tuple(sorted({int(item) for item in value}))
    return ()


def _read_manifest_boundary_surface_names(
    mesh_manifest: dict[str, Any],
) -> dict[int, list[str]]:
    names_by_attr: dict[int, set[str]] = defaultdict(set)
    for entry in mesh_manifest.get("entries", ()):
        if entry.get("role") != "boundary_surface":
            continue
        physical_name = entry.get("name")
        if not physical_name:
            continue
        for attribute in _as_int_tuple(entry.get("attributes", ())):
            names_by_attr[attribute].add(str(physical_name))
    return {attribute: sorted(names) for attribute, names in names_by_attr.items()}


def _update_palace_index_map(
    *,
    index_map_path: Path,
    dielectric_rows: list[dict[str, Any]],
    manifest_attr_names: dict[int, list[str]],
) -> None:
    if not index_map_path.is_file():
        raise FileNotFoundError(f"Missing palace_index_map.json: {index_map_path}")

    index_map = json.loads(index_map_path.read_text())
    entries = list(index_map.get("entries", ()))
    if not isinstance(entries, list):
        raise TypeError("palace_index_map.json entries must be a JSON array")

    non_dielectric_entries = [
        entry
        for entry in entries
        if str(entry.get("section")) != "Boundaries.Postprocessing.Dielectric"
    ]
    dielectric_entries: list[dict[str, Any]] = []
    for row in dielectric_rows:
        attrs = _as_int_tuple(row.get("Attributes", ()))
        if not attrs:
            continue
        interface_type = str(row.get("Type", ""))
        if not interface_type:
            continue
        mask_margin_nm = int(round(float(row["Mask"]["Margin"]) * 1000))
        physical_names = sorted(
            {name for attribute in attrs for name in manifest_attr_names.get(attribute, ())}
        )
        dielectric_entry: dict[str, Any] = {
            "section": "Boundaries.Postprocessing.Dielectric",
            "index": int(row["Index"]),
            "entry_name": (
                f"native_mask_dielectric_{interface_type.lower()}_"
                f"{mask_margin_nm}nm_{row['Index']:03d}"
            ),
            "role": "boundary_surface",
            "attributes": list(attrs),
            "physical_names": physical_names,
            "dimension": 2,
            "Type": interface_type,
            "metadata": {
                "interface_type": interface_type,
                "mask_margin_nm": mask_margin_nm,
                "attributes": list(attrs),
            },
        }
        if row.get("terminal") is not None:
            dielectric_entry["metadata"]["terminal_name"] = row["terminal"]
        if row.get("terminal_index") is not None:
            dielectric_entry["metadata"]["terminal_index"] = row["terminal_index"]
        dielectric_entries.append(dielectric_entry)
    if not dielectric_entries:
        raise RuntimeError("No dielectric index-map entries were generated.")

    index_map["schema_version"] = int(index_map.get("schema_version", 1))
    index_map["entries"] = sorted(
        [*non_dielectric_entries, *dielectric_entries],
        key=lambda entry: (str(entry.get("section")), int(entry.get("index", -1))),
    )
    index_map_path.write_text(json.dumps(index_map, indent=2) + "\n")


def _ensure_native_mask_dielectric_index_map(analysis_run_root: Path) -> None:
    metadata_dir = analysis_run_root / "metadata"
    index_map_path = metadata_dir / "palace_index_map.json"
    native_mask_path = metadata_dir / "native_mask_postprocessing.json"
    mesh_manifest_path = metadata_dir / "mesh_manifest.json"
    if (
        not index_map_path.is_file()
        or not native_mask_path.is_file()
        or not mesh_manifest_path.is_file()
    ):
        return

    index_map = json.loads(index_map_path.read_text())
    if any(
        entry.get("section") == "Boundaries.Postprocessing.Dielectric"
        for entry in index_map.get("entries", ())
    ):
        return

    native_mask = json.loads(native_mask_path.read_text())
    mesh_manifest = json.loads(mesh_manifest_path.read_text())
    _update_palace_index_map(
        index_map_path=index_map_path,
        dielectric_rows=list(native_mask.get("dielectric_rows", ())),
        manifest_attr_names=_read_manifest_boundary_surface_names(mesh_manifest),
    )


def _palace_log_run_status(analysis_run_root: Path) -> str:
    log_text = "\n".join(
        path.read_text(errors="replace")[-20_000:]
        for path in sorted((analysis_run_root / "logs").glob("*"))
        if path.is_file()
    ).lower()
    if "due to time limit" in log_text:
        return "cancelled_time_limit"
    if "out of memory" in log_text or "oom" in log_text:
        return "oom_killed"
    return "completed"


def _handoff_requested_allocation(analysis_run_root: Path) -> dict[str, Any]:
    handoff_path = analysis_run_root / "metadata" / "palace_handoff_metadata.json"
    if not handoff_path.is_file():
        return {}
    handoff = json.loads(handoff_path.read_text())
    return dict(handoff.get("resources", {}).get("requested", {}))


# %% [markdown]
# ## Geometry

# %%
MARTINIS_RIBBON_A_UM = 50.0
MARTINIS_RIBBON_B_UM = 100.0
MARTINIS_PAPER_LENGTH_UM = 1300.0
MARTINIS_NOTEBOOK_LENGTH_UM = 1391.0
SILICON_RELATIVE_PERMITTIVITY = LEGACY_RUN02_SUBSTRATE_PERMITTIVITY
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
        "demo_mode": DEMO_MODE,
        "native_mask_schema": NATIVE_MASK_CONFIG_SCHEMA,
        "mask_margins_nm": NATIVE_MASK_MARGINS_NM,
        "source_index_for_plot": NATIVE_MASK_SOURCE_INDEX,
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
    positive_center = tuple(
        float(value) for value in component.ports["o_mesh_positive_electrode"].center
    )
    negative_center = tuple(
        float(value) for value in component.ports["o_mesh_negative_electrode"].center
    )

# %% [markdown]
# ## Mesh

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
        z_above=500.0,
        z_below=0.0,
    )
    sim.add_terminal("positive", layer="D0_TOP_M1", center=positive_center)
    sim.add_terminal("negative", layer="D0_TOP_M1", center=negative_center)
    mesh_result = sim.mesh(
        preset="coarse",
        refined_mesh_size=20,
        max_mesh_size=200,
        planar_conductors=True,
        auto_size=False,
    )
    display(
        {
            "mesh_file": (output_dir / "palace.msh").as_posix(),
            "mesh_manifest_entries": len(mesh_result.manifest.entries),
            "planar_conductors": True,
        }
    )

# %% [markdown]
# ## Base Palace Config

# %%
if NOTEBOOK_PREPARE_RUN_STAGE:
    sim.set_electrostatic(save_fields=1)
    sim.set_palace_version("0.16.0")
    sim.set_numerical(order=PALACE_ORDER)
    sim.set_refinement(
        max_its=HPC_MAX_ITS,
        tol=PALACE_REFINEMENT_TOL,
        update_fraction=PALACE_UPDATE_FRACTION,
        save_adapt_iterations=True,
        save_adapt_mesh=True,
    )
    sim.set_linear_solver(
        tol=PALACE_LINEAR_TOL,
        max_its=2000,
        estimator_mg=True,
    )
    sim.set_output_formats(paraview=False, grid_function=False)
    postprocessing = build_postprocessing_config_from_manifest(mesh_result.manifest)

# %% [markdown]
# ## Native Mask Config Patch

# %%
if NOTEBOOK_PREPARE_RUN_STAGE:
    if PALACE_NATIVE_MASK_BUNDLE_EXECUTABLE:
        source_executable = PALACE_NATIVE_MASK_SOURCE_EXECUTABLE
        if not source_executable.is_file():
            raise FileNotFoundError(source_executable)
        bundled_executable = output_dir / source_executable.name
        shutil.copy2(source_executable, bundled_executable)
        bundled_executable.chmod(bundled_executable.stat().st_mode | 0o755)
        PALACE_NATIVE_MASK_EXECUTABLE = f"./{bundled_executable.name}"

    run_profile = resolve_public_palace_run_profile(
        PALACE_HPC_PROFILE,
        resource_overrides=PALACE_HPC_RESOURCE_OVERRIDES,
    )
    native_mask_launcher = PalaceSlurmLauncherSpec(
        palace_executable=PALACE_NATIVE_MASK_EXECUTABLE,
        command_style=PALACE_NATIVE_MASK_COMMAND_STYLE,
        setup_commands=PALACE_NATIVE_MASK_SETUP_COMMANDS,
    )
    native_mask_profile_metadata = {
        **dict(run_profile.profile),
        "launcher": native_mask_launcher.to_dict(),
        "metadata": {
            **dict(run_profile.profile.get("metadata", {})),
            "palace_requirement": "native Dielectric.Mask fork",
        },
    }
    run_profile = replace(
        run_profile,
        launcher=native_mask_launcher,
        profile=native_mask_profile_metadata,
    )
    config_path = sim.write_config(
        postprocessing=postprocessing,
        validate_mesh=False,
        material_overlay=get_gsim_material_overlay(),
        hints=run_profile.to_palace_config_hints(),
        prepare_run_folder=True,
        validate_schema=True,
    )

    palace_config = json.loads(config_path.read_text())
    palace_config["Problem"]["Verbose"] = 2
    palace_config["Model"]["L0"] = 1e-6
    substrate_attrs = tuple(palace_config["Domains"]["Materials"][0]["Attributes"])
    if not substrate_attrs:
        raise RuntimeError("Substrate material attributes are empty; cannot patch legacy material.")
    palace_config["Domains"]["Materials"][0] = {
        "Attributes": list(substrate_attrs),
        "Permittivity": LEGACY_RUN02_SUBSTRATE_PERMITTIVITY,
        "Permeability": 1.0,
        "Conductivity": LEGACY_RUN02_SUBSTRATE_CONDUCTIVITY,
        "LossTan": 0.0,
    }

    manifest_path = output_dir / "metadata" / "mesh_manifest.json"
    mesh_manifest = json.loads(manifest_path.read_text())
    sa_entries = [
        entry
        for entry in mesh_manifest["entries"]
        if entry["name"] == "D0_SUBSTRATE___OUTER_VACUUM" and entry["role"] == "boundary_surface"
    ]
    if len(sa_entries) != 1:
        raise RuntimeError("Expected one D0 substrate-to-vacuum boundary surface.")
    sa_attributes = tuple(sa_entries[0]["attributes"])
    terminal_rows = sorted(
        palace_config["Boundaries"]["Terminal"],
        key=lambda row: row["Index"],
    )
    if len(terminal_rows) != 2 or any(not row["Attributes"] for row in terminal_rows):
        raise RuntimeError("Native mask patch requires two non-empty terminal attribute sets.")

    native_mask_dielectric_rows = []
    native_mask_groups = []
    next_index = 1
    for margin_l0, margin_nm in zip(
        NATIVE_MASK_MARGINS_L0_UNITS,
        NATIVE_MASK_MARGINS_NM,
        strict=True,
    ):
        params = LEGACY_RUN02_INTERFACE_PARAMS["SA"]
        native_mask_dielectric_rows.append(
            {
                "Index": next_index,
                "Attributes": list(sa_attributes),
                "Type": "SA",
                "Thickness": params["thickness"],
                "Permittivity": params["permittivity"],
                "LossTan": params["loss_tangent"],
                "Mask": {"Type": "Inset", "Margin": margin_l0},
            }
        )
        native_mask_groups.append(
            {
                "interface_type": "SA",
                "mask_margin_nm": margin_nm,
                "row_indices": [next_index],
            }
        )
        next_index += 1

    for terminal_row in terminal_rows:
        terminal_name = "positive" if terminal_row["Index"] == 1 else "negative"
        for interface_type in ("MS", "MA"):
            params = LEGACY_RUN02_INTERFACE_PARAMS[interface_type]
            for margin_l0, margin_nm in zip(
                NATIVE_MASK_MARGINS_L0_UNITS,
                NATIVE_MASK_MARGINS_NM,
                strict=True,
            ):
                native_mask_dielectric_rows.append(
                    {
                        "Index": next_index,
                        "Attributes": list(terminal_row["Attributes"]),
                        "Type": interface_type,
                        "Thickness": params["thickness"],
                        "Permittivity": params["permittivity"],
                        "LossTan": params["loss_tangent"],
                        "Mask": {"Type": "Inset", "Margin": margin_l0},
                        "terminal": terminal_name,
                        "terminal_index": terminal_row["Index"],
                    }
                )
                native_mask_groups.append(
                    {
                        "interface_type": interface_type,
                        "terminal": terminal_name,
                        "terminal_index": terminal_row["Index"],
                        "mask_margin_nm": margin_nm,
                        "row_indices": [next_index],
                    }
                )
                next_index += 1

    boundary_postprocessing = palace_config["Boundaries"].setdefault("Postprocessing", {})
    boundary_postprocessing["Dielectric"] = native_mask_dielectric_rows
    config_path.write_text(json.dumps(palace_config, indent=2) + "\n")
    _update_palace_index_map(
        index_map_path=output_dir / "metadata" / "palace_index_map.json",
        dielectric_rows=native_mask_dielectric_rows,
        manifest_attr_names=_read_manifest_boundary_surface_names(
            json.loads((output_dir / "metadata" / "mesh_manifest.json").read_text())
        ),
    )

    native_mask_metadata = {
        "schema_version": 1,
        "native_mask_schema": NATIVE_MASK_CONFIG_SCHEMA,
        "run_mode": "legacy_run02_compatibility",
        "model_l0": palace_config["Model"]["L0"],
        "mask_margins_l0_units": list(NATIVE_MASK_MARGINS_L0_UNITS),
        "mask_margins_nm": list(NATIVE_MASK_MARGINS_NM),
        "substrate_material_patch": palace_config["Domains"]["Materials"][0],
        "interface_params": LEGACY_RUN02_INTERFACE_PARAMS,
        "dielectric_rows": native_mask_dielectric_rows,
        "groups": native_mask_groups,
        "palace_requirement": "Palace fork with Dielectric.Mask and surface-mask CSV output",
    }
    native_mask_metadata_path = output_dir / "metadata" / "native_mask_postprocessing.json"
    native_mask_metadata_path.write_text(json.dumps(native_mask_metadata, indent=2) + "\n")

    display(
        {
            "config_file": config_path.relative_to(output_dir).as_posix(),
            "native_mask_metadata": native_mask_metadata_path.relative_to(output_dir).as_posix(),
            "dielectric_postprocessing_rows": len(native_mask_dielectric_rows),
            "legacy_substrate_permittivity": LEGACY_RUN02_SUBSTRATE_PERMITTIVITY,
            "mask_margins_nm": NATIVE_MASK_MARGINS_NM,
        }
    )

# %% [markdown]
# ## Run Stage

# %%
if NOTEBOOK_PREPARE_RUN_STAGE:
    handoff_metadata = {
        "component": component.name,
        "problem_type": "Electrostatic",
        "workflow": "martinis2022_ribbon_native_mask_hpc_handoff",
        "native_mask_schema": NATIVE_MASK_CONFIG_SCHEMA,
        "palace_requirement": "Palace fork with Dielectric.Mask and surface-mask CSV output",
        "launcher_source": "notebook config cell",
    }
    sbatch_handoff = sim.write_slurm_sbatch_handoff(
        run_profile,
        job_name=PALACE_SBATCH_JOB_NAME,
        metadata=handoff_metadata,
    )
    sbatch_relpath = sbatch_handoff.script_path.relative_to(output_dir).as_posix()
    run_handle = sim.generate_handoff_package(
        write_config=False,
        profile=run_profile,
        script_path=sbatch_handoff.script_path,
        metadata={
            **handoff_metadata,
            "sbatch_path": sbatch_relpath,
            "patched_config": "config.json",
            "native_mask_metadata": "metadata/native_mask_postprocessing.json",
        },
    )
    display(
        {
            "run_folder": output_dir.as_posix(),
            "archive": run_handle.archive_path.as_posix(),
            "sbatch_file": sbatch_relpath,
            "run_command": f"cd {output_dir.as_posix()} && sbatch {sbatch_relpath}",
            "hpc_profile": PALACE_HPC_PROFILE,
            "hpc_resources": PALACE_HPC_RESOURCE_OVERRIDES,
            "palace_executable": PALACE_NATIVE_MASK_EXECUTABLE,
            "palace_command_style": PALACE_NATIVE_MASK_COMMAND_STYLE,
        }
    )

# %% [markdown]
# ## Resolve Native Mask Results

# %%
analysis_run_root = Path(NOTEBOOK_ANALYSIS_RUN_ROOT or NOTEBOOK_RUN_ROOT)
native_mask_metadata_path = analysis_run_root / "metadata" / "native_mask_postprocessing.json"
surface_mask_q_final_path = analysis_run_root / "results" / "palace" / "surface-mask-Q.csv"

if not native_mask_metadata_path.is_file() or not surface_mask_q_final_path.is_file():
    native_mask_history = pd.DataFrame()
    display(
        {
            "analysis_run_folder": analysis_run_root.as_posix(),
            "native_mask_result_status": "missing surface-mask-Q.csv; run the sbatch package first",
        }
    )
else:
    native_mask_metadata = json.loads(native_mask_metadata_path.read_text())
    native_mask_groups_by_key = defaultdict(list)
    for group in native_mask_metadata["groups"]:
        key = (group["interface_type"], int(group["mask_margin_nm"]))
        native_mask_groups_by_key[key].extend(group["row_indices"])

    log_text = "\n".join(
        path.read_text(errors="replace")[-20_000:]
        for path in sorted((analysis_run_root / "logs").glob("*"))
        if path.is_file()
    )
    native_mask_run_status = (
        "oom_killed"
        if re.search(r"oom|out of memory", log_text, flags=re.IGNORECASE)
        else "no_oom_marker_found"
    )
    result_dirs = []
    palace_results_root = analysis_run_root / "results" / "palace"
    for candidate in sorted(palace_results_root.glob("iteration*")):
        match = re.fullmatch(r"iteration(\d+)", candidate.name)
        if match and (candidate / "surface-mask-Q.csv").is_file():
            pass_index = int(match.group(1))
            result_dirs.append((pass_index, f"Pass {pass_index}", False, candidate))
    if surface_mask_q_final_path.is_file():
        final_index = max((row[0] for row in result_dirs), default=0) + 1
        if native_mask_run_status == "oom_killed":
            result_dirs.append((final_index, "Latest root", False, palace_results_root))
        else:
            result_dirs.append((final_index, "Final", True, palace_results_root))

    history_rows = []
    for pass_index, label, is_final, result_dir in result_dirs:
        with (result_dir / "surface-mask-Q.csv").open(newline="") as handle:
            records = [
                {key.strip(): value.strip() for key, value in row.items()}
                for row in csv.DictReader(handle)
            ]
        source_row = next(
            (row for row in records if int(round(float(row["i"]))) == NATIVE_MASK_SOURCE_INDEX),
            None,
        )
        if source_row is None:
            raise RuntimeError(f"Missing source index {NATIVE_MASK_SOURCE_INDEX} in {result_dir}.")
        for (interface_type, margin_nm), row_indices in native_mask_groups_by_key.items():
            p_surf_mask_sum = sum(
                float(source_row[f"p_surf_mask[{row_index}]"]) for row_index in row_indices
            )
            history_rows.append(
                {
                    "pass_index": pass_index,
                    "label": label,
                    "is_final": is_final,
                    "source_index": NATIVE_MASK_SOURCE_INDEX,
                    "interface_type": interface_type,
                    "mask_margin_nm": margin_nm,
                    "mask_margin_label": f"{margin_nm} nm" if margin_nm < 1000 else "1 um",
                    "series_label": f"{margin_nm} nm, {interface_type}"
                    if margin_nm < 1000
                    else f"1 um, {interface_type}",
                    "p_surf_mask_sum": p_surf_mask_sum,
                }
            )

    native_mask_history = pd.DataFrame(history_rows)
    native_mask_history_path = (
        analysis_run_root / "metadata" / "native_mask_surface_epr_history.csv"
    )
    native_mask_history.to_csv(native_mask_history_path, index=False)
    display(
        {
            "analysis_run_folder": analysis_run_root.as_posix(),
            "native_mask_history": native_mask_history_path.relative_to(
                analysis_run_root
            ).as_posix(),
            "history_rows": len(native_mask_history),
            "available_result_directories": len(result_dirs),
            "run_log_status": native_mask_run_status,
        }
    )

# %% [markdown]
# ## Native Mask Surface EPR Convergence

# %%
if not native_mask_history.empty:
    visible_history = native_mask_history.copy()
    visible_history["label"] = pd.Categorical(
        visible_history["label"],
        categories=[row[1] for row in result_dirs],
        ordered=True,
    )
    fig = px.line(
        visible_history,
        x="label",
        y="p_surf_mask_sum",
        color="series_label",
        markers=True,
        log_y=True,
        title="Native Masked Surface EPR Convergence - All Interfaces",
    )
    fig.update_layout(
        xaxis_title="label",
        yaxis_title="p_surf_mask_sum (log scale)",
        legend_title_text="",
    )
    native_mask_convergence_html_path = (
        analysis_run_root / "native_mask_all_interfaces_convergence.html"
    )
    fig.write_html(native_mask_convergence_html_path)
    fig.show()
    display(
        {"plot_html": native_mask_convergence_html_path.relative_to(analysis_run_root).as_posix()}
    )

# %% [markdown]
# ## Native Mask Surface EPR Summary

# %%
if not native_mask_history.empty:
    latest_pass_index = int(native_mask_history["pass_index"].max())
    native_mask_latest_summary = (
        native_mask_history[native_mask_history["pass_index"] == latest_pass_index]
        .sort_values(["interface_type", "mask_margin_nm"])[
            ["label", "source_index", "interface_type", "mask_margin_nm", "p_surf_mask_sum"]
        ]
        .reset_index(drop=True)
    )
    native_mask_latest_summary_path = (
        analysis_run_root / "metadata" / "native_mask_surface_epr_latest.csv"
    )
    native_mask_latest_summary.to_csv(native_mask_latest_summary_path, index=False)
    display(
        {
            "latest_summary": native_mask_latest_summary_path.relative_to(
                analysis_run_root
            ).as_posix(),
            "latest_label": native_mask_latest_summary["label"].iloc[0],
            "summary_rows": len(native_mask_latest_summary),
        }
    )
    display(native_mask_latest_summary)

# %% [markdown]
# ## Electrostatic Report

# %%
if not NOTEBOOK_PREPARE_RUN_STAGE:
    _ensure_native_mask_dielectric_index_map(analysis_run_root)
    palace_resource_record_path = analysis_run_root / "metadata" / "palace_resource_record.json"
    if not palace_resource_record_path.is_file():
        palace_log_paths = sorted((analysis_run_root / "logs").glob("palace-*.log"))
        if palace_log_paths:
            from gsim.palace.resolve.sources.resources import (
                write_palace_resource_record_from_log,
            )

            write_palace_resource_record_from_log(
                analysis_run_root,
                palace_log_paths[-1],
                status=_palace_log_run_status(analysis_run_root),
                allocation=_handoff_requested_allocation(analysis_run_root),
                metadata={"source": "notebook_analysis"},
            )

resolved_result = resolve_palace_result(analysis_run_root, problem_type="Electrostatic")
electrostatic_report = resolved_result.load_report(require_report=True).require_report()
electrostatic_report.show_all_results()
display(
    {
        "analysis_run_folder": analysis_run_root.as_posix(),
        "problem_type": electrostatic_report.problem_type,
        "paper_scale_reference_capacitance_fF": round(paper_reference_capacitance_ff, 1),
        "notebook_reference_capacitance_fF": round(notebook_reference_capacitance_ff, 1),
    }
)

# %% [markdown]
# ## Simulation Performance / Benchmark

# %%
if not NOTEBOOK_PREPARE_RUN_STAGE:
    electrostatic_report.show_simulation_benchmark()
