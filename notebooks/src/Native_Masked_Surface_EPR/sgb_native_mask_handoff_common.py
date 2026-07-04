"""Shared SGB Route A/B native-mask handoff notebook logic.

This module lets the two public notebooks differ only by Route A versus Route B.
SGB owns route geometry and semantic physical-group sidecars; this file owns the
run-local Palace fork configuration patch that converts SGB physical groups into
native `Boundaries.Postprocessing.Dielectric` Mask rows.
"""

from __future__ import annotations

import csv
import json
import math
import os
import re
import shutil
import warnings
from collections import defaultdict
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any, Literal

import pandas as pd

try:
    from IPython.display import display
except ImportError:  # pragma: no cover - notebook convenience fallback
    display = print

warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    message="Material model for evaluation at wavelength=.*has unspecified validity range.*",
    module="gsim.palace.materials",
)

DEMO_MODE = "hpc_handoff"
PALACE_ORDER = 2
HPC_MAX_ITS = 20
PALACE_UPDATE_FRACTION = 0.15
PALACE_REFINEMENT_TOL = 1e-12
PALACE_LINEAR_TOL = 1e-6

NATIVE_MASK_MARGINS_NM = (0, 50, 100, 200, 500, 1000)
NATIVE_MASK_MARGINS_L0_UNITS = tuple(value / 1000 for value in NATIVE_MASK_MARGINS_NM)
NATIVE_MASK_SOURCE_INDEX = int(os.environ.get("NATIVE_MASK_SOURCE_INDEX", "1"))

MARTINIS_RIBBON_A_UM = 50.0
MARTINIS_RIBBON_B_UM = 100.0
MARTINIS_PAPER_LENGTH_UM = 1300.0
MARTINIS_NOTEBOOK_LENGTH_UM = 1391.0

LEGACY_RUN02_SUBSTRATE_PERMITTIVITY = 11.7
LEGACY_RUN02_SUBSTRATE_CONDUCTIVITY = 0.0
LEGACY_RUN02_INTERFACE_PARAMS = {
    "SA": {"thickness": 0.002, "permittivity": 3.8, "loss_tangent": 0.0017},
    "MS": {"thickness": 0.002, "permittivity": 9.8, "loss_tangent": 0.00048},
    "MA": {"thickness": 0.002, "permittivity": 9.8, "loss_tangent": 0.0033},
}


def _load_generation_dependencies() -> dict[str, Any]:
    from gsim.palace import ElectrostaticSim
    from gsim.palace.handoff import PalaceSlurmLauncherSpec
    from gsim.palace.mesh import build_postprocessing_config_from_manifest

    from orpen_sc_pdk.cells import martinis2022_differential_ribbon_capacitor
    from orpen_sc_pdk.config import PATH
    from orpen_sc_pdk.materials import get_gsim_material_overlay
    from orpen_sc_pdk.pdk import PDK
    from orpen_sc_pdk.simulation import resolve_public_palace_run_profile

    PDK.activate()
    return {
        "ElectrostaticSim": ElectrostaticSim,
        "PalaceSlurmLauncherSpec": PalaceSlurmLauncherSpec,
        "PATH": PATH,
        "PDK": PDK,
        "build_postprocessing_config_from_manifest": build_postprocessing_config_from_manifest,
        "get_gsim_material_overlay": get_gsim_material_overlay,
        "martinis2022_differential_ribbon_capacitor": martinis2022_differential_ribbon_capacitor,
        "resolve_public_palace_run_profile": resolve_public_palace_run_profile,
    }


def _route_name(route: Literal["A", "B"]) -> str:
    return f"martinis2022_ribbon_sgb_route_{route.lower()}_native_mask_hpc_handoff"


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


def _read_msh_physical_names(mesh_path: Path) -> list[dict[str, Any]]:
    lines = mesh_path.read_text(errors="replace").splitlines()
    rows: list[dict[str, Any]] = []
    try:
        start = lines.index("$PhysicalNames") + 1
    except ValueError:
        return rows
    count = int(lines[start])
    for line in lines[start + 1 : start + 1 + count]:
        dim_text, tag_text, name_text = line.split(maxsplit=2)
        name_text = name_text.strip()
        if name_text.startswith('"') and name_text.endswith('"'):
            physical_name = json.loads(name_text)
        else:
            physical_name = name_text
        rows.append(
            {
                "dimension": int(dim_text),
                "attribute": int(tag_text),
                "physical_name": physical_name,
            }
        )
    return rows


def _surface_interface_records(groups: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for alias, info in sorted((groups.get("boundary_surfaces") or {}).items()):
        if not isinstance(info, dict) or not info.get("surface_epr"):
            continue
        interface_type = str(info.get("interface_type") or "").upper()
        if interface_type not in {"SA", "MS", "MA"}:
            continue
        attributes = _as_int_tuple(info.get("phys_group"))
        if not attributes:
            continue
        physical_name = str(info.get("sgb_physical_name") or alias)
        interface_types = (interface_type,)
        if physical_name.startswith("MS_MA__"):
            interface_types = ("MS", "MA")
        for attribute in attributes:
            for expanded_interface_type in interface_types:
                records.append(
                    {
                        "interface_type": expanded_interface_type,
                        "face_kind": (
                            "top"
                            if expanded_interface_type == "MA"
                            else info.get("face_kind")
                        ),
                        "source_id": info.get("source_id"),
                        "representation": info.get("representation"),
                        "attribute": attribute,
                        "physical_name": physical_name,
                        "alias": alias,
                        "bbox": info.get("bbox"),
                        "centroid": info.get("centroid"),
                    }
                )
    return records


def _append_config_role(
    roles: dict[tuple[int, int], list[str]],
    dimension: int,
    attributes: Any,
    label: str,
) -> None:
    for attribute in _as_int_tuple(attributes):
        roles[(dimension, attribute)].append(label)


def _config_roles_by_attribute(config: dict[str, Any]) -> dict[tuple[int, int], list[str]]:
    roles: dict[tuple[int, int], list[str]] = defaultdict(list)
    for index, row in enumerate(config.get("Domains", {}).get("Materials", []), start=1):
        _append_config_role(roles, 3, row.get("Attributes"), f"Domains.Materials[{index}]")
    boundaries = config.get("Boundaries", {})
    for row in boundaries.get("Terminal", []):
        _append_config_role(
            roles,
            2,
            row.get("Attributes"),
            f"Boundaries.Terminal[{row.get('Index')}]",
        )
    for row in boundaries.get("Ground", []):
        _append_config_role(
            roles,
            2,
            row.get("Attributes"),
            f"Boundaries.Ground[{row.get('Index')}]",
        )
    dielectric_rows = boundaries.get("Postprocessing", {}).get("Dielectric", [])
    for row in dielectric_rows:
        margin_nm = int(round(float(row.get("Mask", {}).get("Margin", 0.0)) * 1000))
        _append_config_role(
            roles,
            2,
            row.get("Attributes"),
            f"Dielectric.Mask[{row.get('Index')}] {row.get('Type')} {margin_nm} nm",
        )
    return roles


def _build_config_tables(
    *,
    route: Literal["A", "B"],
    output_dir: Path,
    palace_config: dict[str, Any],
    interface_records: list[dict[str, Any]],
    dielectric_rows: list[dict[str, Any]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    records_by_attr = {
        (2, int(record["attribute"])): record for record in interface_records
    }
    roles_by_attr = _config_roles_by_attribute(palace_config)
    physical_rows = []
    for row in _read_msh_physical_names(output_dir / "palace.msh"):
        key = (int(row["dimension"]), int(row["attribute"]))
        record = records_by_attr.get(key, {})
        physical_rows.append(
            {
                "route": route,
                "dimension": row["dimension"],
                "attribute": row["attribute"],
                "physical_name": row["physical_name"],
                "interface_type": record.get("interface_type", ""),
                "face_kind": record.get("face_kind", ""),
                "source_id": record.get("source_id", ""),
                "representation": record.get("representation", ""),
                "palace_config_roles": "; ".join(roles_by_attr.get(key, [])),
            }
        )

    names_by_attr = defaultdict(list)
    for record in interface_records:
        names_by_attr[int(record["attribute"])].append(str(record["physical_name"]))
    config_rows = []
    for row in dielectric_rows:
        attrs = _as_int_tuple(row.get("Attributes"))
        margin_nm = int(round(float(row.get("Mask", {}).get("Margin", 0.0)) * 1000))
        physical_names = sorted(
            {
                physical_name
                for attribute in attrs
                for physical_name in names_by_attr.get(attribute, [])
            }
        )
        config_rows.append(
            {
                "route": route,
                "config_row_index": row["Index"],
                "interface_type": row["Type"],
                "mask_margin_nm": margin_nm,
                "mask_margin_l0_units": row["Mask"]["Margin"],
                "attribute_count": len(attrs),
                "attributes": " ".join(str(attribute) for attribute in attrs),
                "physical_names": "; ".join(physical_names),
                "thickness_um": row["Thickness"],
                "permittivity": row["Permittivity"],
                "loss_tangent": row["LossTan"],
            }
        )

    physical_map = pd.DataFrame(physical_rows).sort_values(
        ["dimension", "attribute", "physical_name"]
    )
    config_map = pd.DataFrame(config_rows).sort_values(
        ["interface_type", "mask_margin_nm", "config_row_index"]
    )
    metadata_dir = output_dir / "metadata"
    physical_map.to_csv(
        metadata_dir / f"sgb_route_{route.lower()}_physical_group_config_map.csv",
        index=False,
    )
    config_map.to_csv(
        metadata_dir / f"sgb_route_{route.lower()}_dielectric_mask_config.csv",
        index=False,
    )
    return physical_map, config_map


def _build_native_mask_rows(
    interface_records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, list[int]]]:
    attrs_by_interface: dict[str, list[int]] = {}
    for interface_type in ("SA", "MS", "MA"):
        attrs = sorted(
            {
                int(record["attribute"])
                for record in interface_records
                if record["interface_type"] == interface_type
            }
        )
        if not attrs:
            raise RuntimeError(f"SGB route output has no {interface_type} surface attributes.")
        attrs_by_interface[interface_type] = attrs

    rows: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    next_index = 1
    for margin_l0, margin_nm in zip(
        NATIVE_MASK_MARGINS_L0_UNITS,
        NATIVE_MASK_MARGINS_NM,
        strict=True,
    ):
        for interface_type in ("SA", "MS", "MA"):
            params = LEGACY_RUN02_INTERFACE_PARAMS[interface_type]
            rows.append(
                {
                    "Index": next_index,
                    "Attributes": list(attrs_by_interface[interface_type]),
                    "Type": interface_type,
                    "Thickness": params["thickness"],
                    "Permittivity": params["permittivity"],
                    "LossTan": params["loss_tangent"],
                    "Mask": {"Type": "Inset", "Margin": margin_l0},
                }
            )
            groups.append(
                {
                    "interface_type": interface_type,
                    "mask_margin_nm": margin_nm,
                    "row_indices": [next_index],
                }
            )
            next_index += 1
    return rows, groups, attrs_by_interface


def _patch_native_mask_config(
    *,
    route: Literal["A", "B"],
    output_dir: Path,
    config_path: Path,
    mesh_groups: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    palace_config = json.loads(config_path.read_text())
    palace_config["Problem"]["Verbose"] = 2
    palace_config["Model"]["L0"] = 1e-6
    substrate_attrs = tuple(palace_config["Domains"]["Materials"][0]["Attributes"])
    if not substrate_attrs:
        raise RuntimeError("Substrate material attributes are empty; cannot patch material.")
    palace_config["Domains"]["Materials"][0] = {
        "Attributes": list(substrate_attrs),
        "Permittivity": LEGACY_RUN02_SUBSTRATE_PERMITTIVITY,
        "Permeability": 1.0,
        "Conductivity": LEGACY_RUN02_SUBSTRATE_CONDUCTIVITY,
        "LossTan": 0.0,
    }

    interface_records = _surface_interface_records(mesh_groups)
    dielectric_rows, native_mask_groups, attrs_by_interface = _build_native_mask_rows(
        interface_records
    )
    palace_config["Boundaries"].setdefault("Postprocessing", {})["Dielectric"] = dielectric_rows
    config_path.write_text(json.dumps(palace_config, indent=2) + "\n")

    native_mask_metadata = {
        "schema_version": 1,
        "native_mask_schema": f"palace_fork_sgb_route_{route.lower()}_dielectric_mask",
        "surface_epr_route": route,
        "run_mode": "sgb_geometry_sidecar_native_mask_patch",
        "model_l0": palace_config["Model"]["L0"],
        "mask_margins_l0_units": list(NATIVE_MASK_MARGINS_L0_UNITS),
        "mask_margins_nm": list(NATIVE_MASK_MARGINS_NM),
        "substrate_material_patch": palace_config["Domains"]["Materials"][0],
        "interface_params": LEGACY_RUN02_INTERFACE_PARAMS,
        "interface_attributes": attrs_by_interface,
        "surface_epr_interface_records": interface_records,
        "dielectric_rows": dielectric_rows,
        "groups": native_mask_groups,
        "palace_requirement": "Palace fork with Dielectric.Mask and surface-mask CSV output",
    }
    metadata_dir = output_dir / "metadata"
    native_mask_metadata_path = metadata_dir / "native_mask_postprocessing.json"
    native_mask_metadata_path.write_text(json.dumps(native_mask_metadata, indent=2) + "\n")

    physical_map, config_map = _build_config_tables(
        route=route,
        output_dir=output_dir,
        palace_config=palace_config,
        interface_records=interface_records,
        dielectric_rows=dielectric_rows,
    )
    physical_group_map_path = (
        f"metadata/sgb_route_{route.lower()}_physical_group_config_map.csv"
    )
    dielectric_mask_config_path = (
        f"metadata/sgb_route_{route.lower()}_dielectric_mask_config.csv"
    )
    display(
        {
            "config_file": config_path.relative_to(output_dir).as_posix(),
            "native_mask_metadata": native_mask_metadata_path.relative_to(output_dir).as_posix(),
            "physical_group_map": physical_group_map_path,
            "dielectric_mask_config": dielectric_mask_config_path,
            "dielectric_postprocessing_rows": len(dielectric_rows),
            "interface_attributes": attrs_by_interface,
            "mask_margins_nm": NATIVE_MASK_MARGINS_NM,
        }
    )
    display(config_map)
    return physical_map, config_map


def _analyze_native_mask_results(analysis_run_root: Path) -> pd.DataFrame:
    native_mask_metadata_path = analysis_run_root / "metadata" / "native_mask_postprocessing.json"
    surface_mask_q_final_path = analysis_run_root / "results" / "palace" / "surface-mask-Q.csv"
    if not native_mask_metadata_path.is_file() or not surface_mask_q_final_path.is_file():
        display(
            {
                "analysis_run_folder": analysis_run_root.as_posix(),
                "native_mask_result_status": (
                    "missing surface-mask-Q.csv; run the sbatch package first"
                ),
            }
        )
        return pd.DataFrame()

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
        final_label = "Latest root" if native_mask_run_status == "oom_killed" else "Final"
        result_dirs.append(
            (
                final_index,
                final_label,
                native_mask_run_status != "oom_killed",
                palace_results_root,
            )
        )

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
                    "series_label": (
                        f"{margin_nm} nm, {interface_type}"
                        if margin_nm < 1000
                        else f"1 um, {interface_type}"
                    ),
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
    return native_mask_history


def _plot_native_mask_history(
    route: Literal["A", "B"],
    analysis_run_root: Path,
    history: pd.DataFrame,
) -> None:
    if history.empty:
        return
    try:
        import plotly.express as px
    except ImportError:
        display({"plot_status": "Plotly is required to render the convergence plot."})
        return
    visible_history = history.copy()
    visible_history["label"] = pd.Categorical(
        visible_history["label"],
        categories=list(dict.fromkeys(visible_history["label"])),
        ordered=True,
    )
    fig = px.line(
        visible_history,
        x="label",
        y="p_surf_mask_sum",
        color="series_label",
        markers=True,
        log_y=True,
        title=f"SGB Route {route} Native Masked Surface EPR Convergence - All Interfaces",
    )
    fig.update_layout(
        xaxis_title="label",
        yaxis_title="p_surf_mask_sum (log scale)",
        legend_title_text="",
    )
    html_path = (
        analysis_run_root
        / f"sgb_route_{route.lower()}_native_mask_all_interfaces_convergence.html"
    )
    fig.write_html(html_path)
    fig.show()
    display({"plot_html": html_path.relative_to(analysis_run_root).as_posix()})


def _display_electrostatic_report(analysis_run_root: Path) -> None:
    try:
        from gsim.palace import resolve_palace_result
    except ImportError as exc:
        display({"electrostatic_result_status": f"skipped: {exc}"})
        return

    try:
        resolved_result = resolve_palace_result(analysis_run_root, problem_type="Electrostatic")
    except Exception as exc:  # noqa: BLE001
        display({"electrostatic_result_status": f"unavailable: {exc}"})
        return
    if not hasattr(resolved_result, "report"):
        display({"electrostatic_result_status": "resolved result has no report view yet"})
        return
    display(resolved_result.report)


def run_sgb_native_mask_handoff(
    route: Literal["A", "B"],
    *,
    analysis_run_root: Path | None = None,
) -> dict[str, Any]:
    """Create or analyze one SGB route handoff package.

    Args:
        route: Surface EPR geometry route. Route A and Route B each get their
            own notebook/run folder, while sharing the same Palace fork native
            Mask patching contract.
        analysis_run_root: Existing handoff run folder to analyze. When set,
            geometry, config, sbatch, and package generation are skipped.

    Returns:
        A compact dictionary containing run-folder, archive, and table paths.

    Raises:
        RuntimeError: If SGB does not produce physical groups for SA, MS, and MA.
    """

    if route not in {"A", "B"}:
        raise ValueError(f"Unsupported SGB route: {route!r}")

    notebook_name = _route_name(route)
    run_date = date.today().isoformat()
    run_index = int(os.environ.get("NOTEBOOK_RUN_INDEX", "1"))
    run_id = f"{run_date}-Run{run_index:02d}"
    resolved_analysis_run_root = (
        analysis_run_root.expanduser().resolve() if analysis_run_root is not None else None
    )
    prepare_run_stage = resolved_analysis_run_root is None
    generation_deps = _load_generation_dependencies() if prepare_run_stage else None
    run_root = (
        generation_deps["PATH"].simulation
        / "notebooks"
        / "Native_Masked_Surface_EPR"
        / notebook_name
        / run_id
        if generation_deps is not None
        else resolved_analysis_run_root
    )
    if run_root is None:
        raise RuntimeError("Unable to resolve run root.")
    if prepare_run_stage:
        run_root.mkdir(parents=True, exist_ok=True)

    ribbon_k_ratio = MARTINIS_RIBBON_A_UM / MARTINIS_RIBBON_B_UM
    ribbon_ck_approx = (
        math.log(2.0 * (1.0 + math.sqrt(ribbon_k_ratio)) / (1.0 - math.sqrt(ribbon_k_ratio)))
        / math.pi
    )
    vacuum_permittivity_f_per_um = 8.8541878128e-18
    ribbon_effective_permittivity = (1.0 + LEGACY_RUN02_SUBSTRATE_PERMITTIVITY) / 2.0
    paper_reference_capacitance_ff = (
        ribbon_effective_permittivity
        * vacuum_permittivity_f_per_um
        * MARTINIS_PAPER_LENGTH_UM
        / ribbon_ck_approx
        * 1e15
    )
    notebook_reference_capacitance_ff = (
        ribbon_effective_permittivity
        * vacuum_permittivity_f_per_um
        * MARTINIS_NOTEBOOK_LENGTH_UM
        / ribbon_ck_approx
        * 1e15
    )
    display(
        {
            "demo_mode": DEMO_MODE,
            "surface_epr_route": route,
            "native_mask_schema": f"palace_fork_sgb_route_{route.lower()}_dielectric_mask",
            "mask_margins_nm": NATIVE_MASK_MARGINS_NM,
            "source_index_for_plot": NATIVE_MASK_SOURCE_INDEX,
            "paper_scale_reference_capacitance_fF": round(paper_reference_capacitance_ff, 1),
            "notebook_reference_capacitance_fF": round(notebook_reference_capacitance_ff, 1),
        }
    )

    physical_map = pd.DataFrame()
    config_map = pd.DataFrame()
    archive_path: Path | None = None
    sbatch_relpath = ""
    if prepare_run_stage:
        assert generation_deps is not None
        ElectrostaticSim = generation_deps["ElectrostaticSim"]
        PalaceSlurmLauncherSpec = generation_deps["PalaceSlurmLauncherSpec"]
        build_postprocessing_config_from_manifest = generation_deps[
            "build_postprocessing_config_from_manifest"
        ]
        get_gsim_material_overlay = generation_deps["get_gsim_material_overlay"]
        martinis2022_differential_ribbon_capacitor = generation_deps[
            "martinis2022_differential_ribbon_capacitor"
        ]
        resolve_public_palace_run_profile = generation_deps["resolve_public_palace_run_profile"]
        PDK = generation_deps["PDK"]

        output_dir = run_root
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
        sim.add_terminal(
            "positive",
            layer="D0_TOP_M1",
            center=positive_center,
            physical_label="positive",
        )
        sim.add_terminal(
            "negative",
            layer="D0_TOP_M1",
            center=negative_center,
            physical_label="negative",
        )
        sim.set_surface_epr(representation=route, interfaces=None)
        mesh_result = sim.mesh(
            preset="coarse",
            refined_mesh_size=20,
            max_mesh_size=200,
            planar_conductors=False,
            auto_size=False,
        )
        display(
            {
                "mesh_file": (output_dir / "palace.msh").as_posix(),
                "xao_route": f"geometry/semantic_geometry_route_{route.lower()}.xao",
                "semantic_sidecar": "metadata/semantic_geometry/04_export_physical_groups.json",
                "mesh_manifest_entries": len(mesh_result.manifest.entries),
                "surface_epr_route": route,
                "inset_geometry": False,
            }
        )

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
        sim.set_linear_solver(tol=PALACE_LINEAR_TOL, max_its=2000, estimator_mg=True)
        sim.set_output_formats(paraview=False, grid_function=False)
        postprocessing = build_postprocessing_config_from_manifest(mesh_result.manifest)

        hpc_profile = os.environ.get("PALACE_HPC_PROFILE", "f1:ct112")
        hpc_resource_overrides = {
            "account": os.environ.get("PALACE_HPC_ACCOUNT", "public_alloc"),
            "partition": os.environ.get("PALACE_HPC_PARTITION", "ct112"),
            "nodes": int(os.environ.get("PALACE_HPC_NODES", "1")),
            "ntasks_per_node": int(os.environ.get("PALACE_HPC_NTASKS_PER_NODE", "2")),
            "cpus_per_task": int(os.environ.get("PALACE_HPC_CPUS_PER_TASK", "16")),
            "memory_mb": int(os.environ.get("PALACE_HPC_MEMORY_MB", "480000")),
            "wall_time": os.environ.get("PALACE_HPC_WALL_TIME", "12:00:00"),
        }
        default_native_mask_source_executable = (
            generation_deps["PATH"].simulation.parents[2]
            / "palace"
            / "build"
            / "bin"
            / "palace-x86_64.bin"
        )
        native_mask_executable = os.environ.get("PALACE_NATIVE_MASK_EXECUTABLE", "palace")
        native_mask_command_style = os.environ.get("PALACE_NATIVE_MASK_COMMAND_STYLE", "binary")
        native_mask_setup_commands = tuple(
            command.strip()
            for command in os.environ.get("PALACE_NATIVE_MASK_SETUP_COMMANDS", "").splitlines()
            if command.strip()
        )
        if os.environ.get("PALACE_NATIVE_MASK_BUNDLE_EXECUTABLE", "1") == "1":
            source_executable = Path(
                os.environ.get(
                    "PALACE_NATIVE_MASK_SOURCE_EXECUTABLE",
                    default_native_mask_source_executable,
                )
            )
            if not source_executable.is_file():
                raise FileNotFoundError(source_executable)
            bundled_executable = output_dir / source_executable.name
            shutil.copy2(source_executable, bundled_executable)
            bundled_executable.chmod(bundled_executable.stat().st_mode | 0o755)
            native_mask_executable = f"./{bundled_executable.name}"
        sbatch_job_name = os.environ.get(
            "PALACE_SBATCH_JOB_NAME",
            f"orpen_sgb_route_{route.lower()}_native_mask",
        )

        run_profile = resolve_public_palace_run_profile(
            hpc_profile,
            resource_overrides=hpc_resource_overrides,
        )
        native_mask_launcher = PalaceSlurmLauncherSpec(
            palace_executable=native_mask_executable,
            command_style=native_mask_command_style,
            setup_commands=native_mask_setup_commands,
        )
        native_mask_profile_metadata = {
            **dict(run_profile.profile),
            "launcher": native_mask_launcher.to_dict(),
            "metadata": {
                **dict(run_profile.profile.get("metadata", {})),
                "palace_requirement": "native Dielectric.Mask fork",
                "surface_epr_route": route,
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
        physical_map, config_map = _patch_native_mask_config(
            route=route,
            output_dir=output_dir,
            config_path=config_path,
            mesh_groups=mesh_result.groups,
        )

        handoff_metadata = {
            "component": component.name,
            "problem_type": "Electrostatic",
            "workflow": notebook_name,
            "surface_epr_route": route,
            "native_mask_schema": f"palace_fork_sgb_route_{route.lower()}_dielectric_mask",
            "palace_requirement": "Palace fork with Dielectric.Mask and surface-mask CSV output",
            "launcher_source": "environment override or job environment",
        }
        sbatch_handoff = sim.write_slurm_sbatch_handoff(
            run_profile,
            job_name=sbatch_job_name,
            metadata=handoff_metadata,
        )
        sbatch_relpath = sbatch_handoff.script_path.relative_to(output_dir).as_posix()
        physical_group_map_path = (
            f"metadata/sgb_route_{route.lower()}_physical_group_config_map.csv"
        )
        dielectric_mask_config_path = (
            f"metadata/sgb_route_{route.lower()}_dielectric_mask_config.csv"
        )
        run_handle = sim.generate_handoff_package(
            write_config=False,
            profile=run_profile,
            script_path=sbatch_handoff.script_path,
            metadata={
                **handoff_metadata,
                "sbatch_path": sbatch_relpath,
                "patched_config": "config.json",
                "native_mask_metadata": "metadata/native_mask_postprocessing.json",
                "physical_group_map": physical_group_map_path,
                "dielectric_mask_config": dielectric_mask_config_path,
            },
        )
        archive_path = run_handle.archive_path
        display(
            {
                "run_folder": output_dir.as_posix(),
                "archive": archive_path.as_posix(),
                "sbatch_file": sbatch_relpath,
                "run_command": f"cd {output_dir.as_posix()} && sbatch {sbatch_relpath}",
                "hpc_profile": hpc_profile,
                "hpc_resources": hpc_resource_overrides,
                "palace_executable": native_mask_executable,
                "palace_command_style": native_mask_command_style,
            }
        )

    active_analysis_root = resolved_analysis_run_root or run_root
    history = _analyze_native_mask_results(active_analysis_root)
    _plot_native_mask_history(route, active_analysis_root, history)
    _display_electrostatic_report(active_analysis_root)

    return {
        "route": route,
        "run_folder": str(run_root),
        "archive": None if archive_path is None else str(archive_path),
        "sbatch_file": sbatch_relpath,
        "physical_group_map_rows": int(len(physical_map)),
        "dielectric_mask_config_rows": int(len(config_map)),
    }
