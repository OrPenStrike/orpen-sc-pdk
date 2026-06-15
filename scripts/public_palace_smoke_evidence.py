from __future__ import annotations

import argparse
import json
import math
import os
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from textwrap import dedent
from typing import Any

import orpen_sc_pdk
from orpen_sc_pdk.cells import (
    cpw_straight,
    martinis2022_differential_ribbon_capacitor,
    resonator,
)
from orpen_sc_pdk.materials import get_gsim_material_overlay

DEFAULT_OUTPUT_DIR = Path("build/public-palace-smoke-evidence")
EVIDENCE_FILENAME = "public_palace_smoke_evidence.json"
PUBLIC_SLURM_PROFILE_CATALOG = (
    Path(__file__).resolve().parent / "fixtures" / "public_slurm_profiles.json"
)
PUBLIC_HELPER_NODE_INVENTORY = (
    Path(__file__).resolve().parent / "fixtures" / "public_simulation_helper_nodes.json"
)
PUBLIC_PROBLEM_NOTEBOOK_CROSSCHECK = (
    Path(__file__).resolve().parent / "fixtures" / "public_problem_notebook_crosscheck.json"
)
PUBLIC_SIMULATION_GOAL_AUDIT = (
    Path(__file__).resolve().parent / "fixtures" / "public_simulation_goal_audit.json"
)
PUBLIC_GSIM_BOUNDARY_REVIEW_CROSSCHECK = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "public_gsim_boundary_review_crosscheck.json"
)
PUBLIC_INTERFACE_PRESET_REVIEW_QUEUE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "public_interface_preset_review_queue.json"
)


def load_public_simulation_helper_node_inventory() -> list[dict[str, Any]]:
    """Load the public helper-node coverage matrix used by docs and evidence."""

    return json.loads(PUBLIC_HELPER_NODE_INVENTORY.read_text())


def load_public_problem_notebook_crosscheck() -> list[dict[str, Any]]:
    """Load the public/private notebook cross-check matrix."""

    return json.loads(PUBLIC_PROBLEM_NOTEBOOK_CROSSCHECK.read_text())


def load_public_simulation_goal_audit() -> list[dict[str, Any]]:
    """Load the public simulation migration goal audit matrix."""

    return json.loads(PUBLIC_SIMULATION_GOAL_AUDIT.read_text())


def load_public_gsim_boundary_review_crosscheck() -> list[dict[str, Any]]:
    """Load the local gsim branch boundary-review cross-check matrix."""

    return json.loads(PUBLIC_GSIM_BOUNDARY_REVIEW_CROSSCHECK.read_text())


def load_public_interface_preset_review_queue() -> dict[str, Any]:
    """Load the source-backed dielectric-interface preset review queue."""

    return json.loads(PUBLIC_INTERFACE_PRESET_REVIEW_QUEUE.read_text())


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _relative_result_paths(payload: dict[str, Any], output_root: Path) -> dict[str, Any]:
    for key, value in list(payload.items()):
        if key.endswith("_path") and isinstance(value, str):
            payload[key] = _relative_path(Path(value), output_root)
    return payload


def _relative_run_summary(summary: dict[str, Any], output_root: Path) -> dict[str, Any]:
    for group_name in ("artifacts", "results"):
        group = summary.get(group_name, {})
        if not isinstance(group, dict):
            continue
        for row in group.values():
            if not isinstance(row, dict) or row.get("path") is None:
                continue
            row["path"] = _relative_path(Path(row["path"]), output_root)
    for group_name in ("handoff", "runtime", "resource"):
        group = summary.get(group_name, {})
        if not isinstance(group, dict):
            continue
        if group.get("path") is not None:
            group["path"] = _relative_path(Path(group["path"]), output_root)
        for ref_name in ("script", "archive"):
            ref = group.get(ref_name)
            if isinstance(ref, dict) and ref.get("path") is not None:
                ref["path"] = _relative_path(Path(ref["path"]), output_root)
        if group_name == "resource":
            _relative_resource_refs(group, output_root)
    return summary


def _relative_resource_refs(group: dict[str, Any], output_root: Path) -> None:
    for collection_name in ("sources", "tables"):
        collection = group.get(collection_name)
        if not isinstance(collection, dict):
            continue
        for key, value in list(collection.items()):
            if isinstance(value, dict) and value.get("path") is not None:
                value["path"] = _relative_path(Path(value["path"]), output_root)
            elif isinstance(value, str):
                collection[key] = _relative_path(Path(value), output_root)


def _relative_sweep_summary(
    summary: dict[str, Any],
    output_root: Path,
) -> dict[str, Any]:
    source_path = summary.get("source_path")
    if source_path is not None:
        summary["source_path"] = _relative_path(Path(source_path), output_root)
    handoff = summary.get("handoff")
    if isinstance(handoff, dict):
        if handoff.get("path") is not None:
            handoff["path"] = _relative_path(Path(handoff["path"]), output_root)
        for ref_name in ("script", "archive"):
            ref = handoff.get(ref_name)
            if isinstance(ref, dict) and ref.get("path") is not None:
                ref["path"] = _relative_path(Path(ref["path"]), output_root)
    for point in summary.get("points", []):
        if not isinstance(point, dict):
            continue
        source = point.get("source")
        if isinstance(source, dict):
            point["source"] = {
                name: _relative_path(Path(path), output_root) for name, path in source.items()
            }
        elif source is not None:
            point["source"] = _relative_path(Path(source), output_root)
        run_summary = point.get("run_summary")
        if isinstance(run_summary, dict):
            point["run_summary"] = _relative_run_summary(run_summary, output_root)
    return summary


def _source_summary(rows: Any) -> list[dict[str, Any]]:
    if rows is None or getattr(rows, "empty", True):
        return []
    fields = ("name", "required", "present", "loaded", "message")
    summary = []
    for row in rows.loc[:, [field for field in fields if field in rows.columns]].to_dict("records"):
        summary.append(
            {
                key: bool(value) if key in {"required", "present", "loaded"} else value
                for key, value in row.items()
            }
        )
    return summary


def _json_safe(value: Any) -> Any:
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if hasattr(value, "item"):
        return _json_safe(value.item())
    return value


def _frame_records(rows: Any, columns: Sequence[str]) -> list[dict[str, Any]]:
    if rows is None or getattr(rows, "empty", True):
        return []
    selected_columns = [column for column in columns if column in rows.columns]
    frame = rows.loc[:, selected_columns]
    return [
        {key: _json_safe(value) for key, value in row.items()} for row in frame.to_dict("records")
    ]


def _config_generation_evidence(source: Path) -> dict[str, Any]:
    from gsim.palace import load_domain_material_summary

    config = json.loads((source / "config.json").read_text())
    material_resolution_path = source / "palace_material_resolution.json"
    material_resolution = (
        json.loads(material_resolution_path.read_text())
        if material_resolution_path.exists()
        else {}
    )
    boundaries = config.get("Boundaries", {})
    postprocessing = boundaries.get("Postprocessing", {})
    surface_currents = boundaries.get("SurfaceCurrent", ())
    domains = config.get("Domains", {})
    solver = config.get("Solver", {})
    domain_materials = load_domain_material_summary(source)
    problem_block = next(
        (
            name
            for name in (
                "Driven",
                "Eigenmode",
                "Electrostatic",
                "Magnetostatic",
                "Transient",
            )
            if name in solver
        ),
        None,
    )
    return {
        "problem_type": config.get("Problem", {}).get("Type"),
        "solver_device": solver.get("Device"),
        "solver_has_linear": bool(solver.get("Linear")),
        "solver_problem_block": problem_block,
        "domain_material_count": len(domains.get("Materials", ())),
        "domain_postprocessing_energy_count": len(
            domains.get("Postprocessing", {}).get("Energy", ())
        ),
        "lumped_port_count": len(boundaries.get("LumpedPort", ())),
        "terminal_count": len(boundaries.get("Terminal", ())),
        "wave_port_count": len(boundaries.get("WavePort", ())),
        "surface_current_count": len(surface_currents),
        "surface_current_element_count": sum(
            len(entry.get("Elements", ())) for entry in surface_currents if isinstance(entry, dict)
        ),
        "surface_current_directions": [
            _json_safe(entry.get("Direction"))
            for entry in surface_currents
            if isinstance(entry, dict) and "Direction" in entry
        ],
        "surface_current_coordinate_systems": sorted(
            {
                str(entry["CoordinateSystem"])
                for entry in surface_currents
                if isinstance(entry, dict) and "CoordinateSystem" in entry
            }
            | {
                str(element["CoordinateSystem"])
                for entry in surface_currents
                if isinstance(entry, dict)
                for element in entry.get("Elements", ())
                if isinstance(element, dict) and "CoordinateSystem" in element
            }
        ),
        "pmc_count": int(bool(boundaries.get("PMC"))),
        "surface_flux_count": len(postprocessing.get("SurfaceFlux", ())),
        "dielectric_postprocessing_count": len(postprocessing.get("Dielectric", ())),
        "boundary_sections": sorted(boundaries.keys()),
        "material_resolution": {
            "schema_version": material_resolution.get("schema_version"),
            "material_count": len(material_resolution.get("materials", ())),
            "interface_count": len(material_resolution.get("interfaces", ())),
        },
        "domain_materials": _frame_records(
            domain_materials,
            (
                "domain_index",
                "physical_name",
                "stack_material_name",
                "matched_material_name",
                "material_model_source",
                "material_within_validity",
                "material_frequency_ghz",
                "permittivity",
                "loss_tangent",
                "conductivity",
                "permeability",
            ),
        ),
    }


def _index_map_lookup_evidence(source: Path) -> dict[str, Any]:
    from gsim.palace import load_postprocessing_index_map

    index_map = load_postprocessing_index_map(source)
    lookup_rows: list[dict[str, Any]] = []
    for entry in sorted(
        index_map.entries,
        key=lambda row: (row.section, row.index, row.entry_name),
    ):
        physical_name = index_map.physical_name_for_index(entry.section, entry.index)
        reverse_indices = (
            index_map.indices_for_physical_name(
                physical_name,
                section=entry.section,
            )
            if physical_name is not None
            else ()
        )
        attribute = entry.attributes[0] if entry.attributes else None
        attribute_entry_names = (
            sorted(
                matched.entry_name
                for matched in index_map.entries_for_attribute(
                    attribute,
                    section=entry.section,
                )
            )
            if attribute is not None
            else []
        )
        row = {
            "section": entry.section,
            "index": entry.index,
            "entry_name": entry.entry_name,
            "role": entry.role,
            "physical_name": physical_name,
            "reverse_indices_for_physical_name": list(reverse_indices),
            "attribute": attribute,
            "entry_names_for_attribute": attribute_entry_names,
        }
        if entry.metadata:
            row["metadata"] = dict(entry.metadata)
        if entry.extra:
            row["extra"] = dict(entry.extra)
            if entry.extra.get("terminal_name") is not None:
                row["terminal_name"] = entry.extra["terminal_name"]
            if entry.extra.get("current_source_name") is not None:
                row["current_source_name"] = entry.extra["current_source_name"]
        lookup_rows.append(row)
    return {
        "schema_version": index_map.schema_version,
        "row_count": len(lookup_rows),
        "lookups": lookup_rows,
    }


def _solver_env(environ: Mapping[str, str]) -> tuple[dict[str, Any], dict[str, Any]]:
    if environ.get("ORPEN_RUN_LOCAL_PALACE_SMOKE") != "1":
        return {}, {
            "enabled": False,
            "skip_reason": "set ORPEN_RUN_LOCAL_PALACE_SMOKE=1 to run local Palace smokes",
        }

    palace_sif = environ.get("PALACE_SIF")
    palace_executable = environ.get("PALACE_EXECUTABLE")
    if not palace_sif and not palace_executable:
        return {}, {
            "enabled": False,
            "skip_reason": "set PALACE_SIF or PALACE_EXECUTABLE for local Palace smokes",
        }

    executable_mode = environ.get("PALACE_EXECUTABLE_MODE", "wrapper")
    if executable_mode not in {"wrapper", "binary"}:
        msg = "PALACE_EXECUTABLE_MODE must be 'wrapper' or 'binary'"
        raise ValueError(msg)

    run_kwargs: dict[str, Any] = {
        "use_apptainer": palace_sif is not None,
        "num_processes": int(environ.get("PALACE_NP", "1")),
        "num_threads": int(environ.get("PALACE_NT", "1")),
        "verbose": False,
    }
    if palace_sif is not None:
        run_kwargs["palace_sif_path"] = palace_sif
        launcher = {"kind": "apptainer", "palace_sif_configured": True}
    else:
        run_kwargs["palace_executable"] = palace_executable
        run_kwargs["executable_mode"] = executable_mode
        run_kwargs["serial"] = environ.get("PALACE_SERIAL") == "1"
        launcher = {
            "kind": "executable",
            "palace_executable_configured": True,
            "executable_mode": executable_mode,
            "serial": run_kwargs["serial"],
        }

    return run_kwargs, {
        "enabled": True,
        "skip_reason": None,
        "num_processes": run_kwargs["num_processes"],
        "num_threads": run_kwargs["num_threads"],
        "launcher": launcher,
    }


def _public_slurm_resource_overrides(
    *,
    num_processes: int,
    num_threads: int,
) -> dict[str, int]:
    overrides: dict[str, int] = {}
    if num_processes != 1:
        overrides["ntasks_per_node"] = num_processes
    if num_threads != 1:
        overrides["cpus_per_task"] = num_threads
    return overrides


def _public_driven_cpw_sim(output_dir: Path):
    from gsim.palace import DrivenSim

    orpen_sc_pdk.activate()
    component = cpw_straight(length=300, signal_width=10, gap=6, ground_width=40)

    sim = DrivenSim()
    sim.set_output_dir(output_dir)
    sim.set_geometry(component)
    sim.set_stack(
        include_substrate=True,
        substrate_thickness=20,
        add_oxide_dielectric=False,
        add_passivation_dielectric=False,
    )
    sim.set_airbox(margin_x=40, margin_y=40, z_above=50, z_below=10)
    sim.add_cpw_port("o1", layer="D0_TOP_M1", s_width=10, gap_width=6, length=10)
    sim.add_cpw_port(
        "o2",
        layer="D0_TOP_M1",
        s_width=10,
        gap_width=6,
        length=10,
        excited=False,
    )
    sim.set_driven(fmin=4e9, fmax=8e9, num_points=3, excitation_port="o1")
    sim.mesh(
        preset="coarse",
        refined_mesh_size=20,
        max_mesh_size=200,
        margin_x=40,
        margin_y=40,
        planar_conductors=True,
        auto_size=False,
    )
    return sim, sim._last_mesh_result


def _driven_postprocessing(mesh_result: Any) -> dict[str, Any]:
    from gsim.palace.mesh import SurfaceFluxSpec, build_postprocessing_config_from_manifest

    return build_postprocessing_config_from_manifest(
        mesh_result.manifest,
        surface_flux=(
            SurfaceFluxSpec(
                role="port_surface",
                flux_type="Power",
                two_sided=None,
            ),
        ),
    )


def _driven_report_summary(output_dir: Path) -> dict[str, Any]:
    from gsim.palace import load_driven_report

    report = load_driven_report(output_dir)
    return {
        "status": "loaded",
        "port_names": list(report.sparams.port_names),
        "frequency_points": int(len(report.sparams.freq)),
        "s_parameter_count": int(len(report.sparams.keys())),
        "port_epr_rows": int(len(report.port_epr)),
        "index_map_rows": int(len(report.index_map)),
        "sources": _source_summary(report.sources),
    }


def _public_eigenmode_resonator_sim(output_dir: Path):
    from gsim.palace import EigenmodeSim

    orpen_sc_pdk.activate()
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
    sim.set_stack(
        include_substrate=True,
        substrate_thickness=20,
        add_oxide_dielectric=False,
        add_passivation_dielectric=False,
    )
    sim.set_airbox(margin_x=50, margin_y=50, z_above=50, z_below=10)
    sim.set_eigenmode(num_modes=2, target=6e9)
    sim.mesh(
        preset="coarse",
        refined_mesh_size=20,
        max_mesh_size=200,
        margin_x=50,
        margin_y=50,
        planar_conductors=True,
        auto_size=False,
    )
    return sim, sim._last_mesh_result


def _eigenmode_postprocessing(mesh_result: Any) -> dict[str, Any]:
    from gsim.palace.mesh import SurfaceFluxSpec, build_postprocessing_config_from_manifest

    return build_postprocessing_config_from_manifest(
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


def _eigenmode_report_summary(output_dir: Path) -> dict[str, Any]:
    from gsim.palace import load_eigenmode_report

    report = load_eigenmode_report(output_dir)
    return {
        "status": "loaded",
        "mode_count": int(report.eigenmodes.n_modes),
        "min_frequency_ghz": float(report.eigenmodes.freq_real_ghz.min()),
        "min_q": float(report.eigenmodes.q.min()),
        "domain_energy_rows": int(len(report.domain_energy)),
        "surface_q_rows": int(len(report.surface_q)),
        "index_map_rows": int(len(report.index_map)),
        "sources": _source_summary(report.sources),
    }


def _public_same_layer_capacitor_electrostatic_sim(output_dir: Path):
    from gsim.palace import ElectrostaticSim

    orpen_sc_pdk.activate()
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
    sim.set_stack(
        include_substrate=True,
        substrate_thickness=20,
        add_oxide_dielectric=False,
        add_passivation_dielectric=False,
    )
    sim.set_airbox(margin_x=40, margin_y=40, z_above=50, z_below=10)
    sim.add_terminal("positive", layer="D0_TOP_M1", center=positive_center)
    sim.add_terminal("negative", layer="D0_TOP_M1", center=negative_center)
    sim.set_electrostatic(save_fields=0)
    sim.mesh(
        preset="coarse",
        refined_mesh_size=20,
        max_mesh_size=200,
        margin_x=40,
        margin_y=40,
        planar_conductors=True,
        auto_size=False,
    )
    return sim, sim._last_mesh_result


def _electrostatic_postprocessing(mesh_result: Any) -> dict[str, Any]:
    from gsim.palace.mesh import build_postprocessing_config_from_manifest

    return build_postprocessing_config_from_manifest(mesh_result.manifest)


def _electrostatic_report_summary(output_dir: Path) -> dict[str, Any]:
    from gsim.palace import load_electrostatic_report

    report = load_electrostatic_report(output_dir)
    return {
        "status": "loaded",
        "terminal_names": list(report.capacitance.terminal_names),
        "capacitance_shape": list(report.capacitance.dataframe.shape),
        "has_mutual_capacitance": report.mutual_capacitance is not None,
        "has_inverse_capacitance": report.inverse_capacitance is not None,
        "domain_energy_rows": int(len(report.domain_energy)),
        "surface_q_rows": int(len(report.surface_q)),
        "index_map_rows": int(len(report.index_map)),
        "sources": _source_summary(report.sources),
    }


def _write_public_report_json(path: Path, data: Mapping[str, Any]) -> Path:
    path.write_text(json.dumps(dict(data), indent=2, sort_keys=True) + "\n")
    return path


def _public_report_material_resolution() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "materials": [
            {
                "material_row_index": 1,
                "material_attribute": 10,
                "material_attributes": [10],
                "volume_name": "substrate",
                "stack_material_name": "Si",
                "matched_material_name": "Si",
                "evaluation_frequency_hz": 5.0e9,
                "evaluation_frequency_ghz": 5.0,
                "model_type": "constant",
                "model_source": "orpen-sc-pdk tech.material_properties",
                "within_validity": True,
                "validity_note": None,
                "effective_material": {
                    "permittivity": 11.45,
                    "loss_tangent": 2.0e-6,
                },
                "palace_material": {
                    "Attributes": [10],
                    "Name": "Si",
                    "Permittivity": 11.45,
                    "LossTan": 2.0e-6,
                },
            }
        ],
        "interfaces": [
            {
                "interface_row_index": 1,
                "surface_index": 2,
                "surface_attributes": [20],
                "interface_type": "SA",
                "interface_material_name": "AlOx_native_generic",
                "matched_material_name": "AlOx_native_generic",
                "evaluation_frequency_hz": 5.0e9,
                "evaluation_frequency_ghz": 5.0,
                "model_type": "constant",
                "model_source": "orpen-sc-pdk tech.material_properties",
                "within_validity": True,
                "validity_note": None,
                "effective_material": {
                    "permittivity": 10.0,
                    "loss_tangent": 0.0017,
                },
                "palace_interface": {
                    "Index": 2,
                    "Attributes": [20],
                    "Type": "SA",
                    "Thickness": 0.003,
                    "Permittivity": 10.0,
                    "LossTan": 0.0017,
                },
            }
        ],
    }


def _write_public_driven_report_fixture(output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    port_info_path = _write_public_report_json(
        output_dir / "port_information.json",
        {
            "ports": [
                {"portnumber": 1, "name": "o1", "Z0": 50.0, "type": "cpw"},
                {"portnumber": 2, "name": "o2", "Z0": 50.0, "type": "cpw"},
            ],
            "unit": 1e-6,
            "name": "palace",
        },
    )
    port_s_path = output_dir / "port-S.csv"
    port_s_path.write_text(
        "f (GHz), |S[1][1]| (dB), arg(S[1][1]) (deg.), "
        "|S[2][1]| (dB), arg(S[2][1]) (deg.)\n"
        "4.0, -18.0, -45.0, -3.0, -90.0\n"
        "6.0, -12.0, -50.0, -2.0, -95.0\n"
        "8.0, -16.0, -55.0, -4.0, -100.0\n"
    )
    port_epr_path = output_dir / "port-EPR.csv"
    port_epr_path.write_text("m, p[3], p[4]\n1, 0.60, 0.40\n")
    config_path = _write_public_report_json(
        output_dir / "config.json",
        {
            "Domains": {
                "Materials": [
                    {
                        "Attributes": [10],
                        "Name": "Si",
                        "Permittivity": 11.45,
                        "LossTan": 2.0e-6,
                    }
                ]
            }
        },
    )
    index_map_path = _write_public_report_json(
        output_dir / "palace_index_map.json",
        {
            "schema_version": 1,
            "entries": [
                {
                    "section": "Domains.Postprocessing.Energy",
                    "index": 1,
                    "entry_name": "substrate",
                    "role": "dielectric_volume",
                    "attributes": [10],
                    "physical_names": ["D1_SUBSTRATE"],
                    "dimension": 3,
                },
                {
                    "section": "Boundaries.Postprocessing.SurfaceFlux",
                    "index": 3,
                    "entry_name": "o1_port_surface",
                    "role": "port_surface",
                    "attributes": [31],
                    "physical_names": ["P1_E0"],
                    "dimension": 2,
                    "Type": "Power",
                    "metadata": {"port": "P1", "port_type": "cpw"},
                },
                {
                    "section": "Boundaries.Postprocessing.SurfaceFlux",
                    "index": 4,
                    "entry_name": "o2_port_surface",
                    "role": "port_surface",
                    "attributes": [41],
                    "physical_names": ["P2_E0"],
                    "dimension": 2,
                    "Type": "Power",
                    "metadata": {"port": "P2", "port_type": "cpw"},
                },
            ],
        },
    )
    material_resolution_path = _write_public_report_json(
        output_dir / "palace_material_resolution.json",
        _public_report_material_resolution(),
    )
    return {
        "port-S.csv": port_s_path,
        "port-EPR.csv": port_epr_path,
        "port_information.json": port_info_path,
        "config.json": config_path,
        "palace_index_map.json": index_map_path,
        "palace_material_resolution.json": material_resolution_path,
    }


def _write_public_eigenmode_report_fixture(output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    eig_path = output_dir / "eig.csv"
    eig_path.write_text(
        "m, Re{f} (GHz), Im{f} (GHz), Q, Error (Bkwd.), Error (Abs.)\n"
        "1, 5.0, 0.0, 2.0e6, 0.0, 0.0\n"
    )
    domain_e_path = output_dir / "domain-E.csv"
    domain_e_path.write_text("m, E_elec[1] (J), p_elec[1]\n1, 1.0, 0.25\n")
    surface_q_path = output_dir / "surface-Q.csv"
    surface_q_path.write_text("m, p_surf[2], Q_surf[2]\n1, 0.125, 1.0e6\n")
    config_path = _write_public_report_json(
        output_dir / "config.json",
        {
            "Domains": {
                "Materials": [
                    {
                        "Attributes": [10],
                        "Name": "Si",
                        "Permittivity": 11.45,
                        "LossTan": 2.0e-6,
                    }
                ]
            },
            "Boundaries": {
                "Postprocessing": {
                    "Dielectric": [
                        {
                            "Index": 2,
                            "Attributes": [20],
                            "Type": "SA",
                            "Thickness": 0.003,
                            "Permittivity": 10.0,
                            "LossTan": 0.0017,
                        }
                    ]
                }
            },
        },
    )
    index_map_path = _write_public_report_json(
        output_dir / "palace_index_map.json",
        {
            "schema_version": 1,
            "entries": [
                {
                    "section": "Domains.Postprocessing.Energy",
                    "index": 1,
                    "entry_name": "substrate",
                    "role": "dielectric_volume",
                    "attributes": [10],
                    "physical_names": ["D1_SUBSTRATE"],
                    "dimension": 3,
                },
                {
                    "section": "Boundaries.Postprocessing.Dielectric",
                    "index": 2,
                    "entry_name": "sa_interface",
                    "role": "boundary_surface",
                    "attributes": [20],
                    "physical_names": ["SA:D1_SUBSTRATE___OUTER_VACUUM"],
                    "dimension": 2,
                    "Type": "SA",
                },
            ],
        },
    )
    material_resolution_path = _write_public_report_json(
        output_dir / "palace_material_resolution.json",
        _public_report_material_resolution(),
    )
    return {
        "eig.csv": eig_path,
        "domain-E.csv": domain_e_path,
        "surface-Q.csv": surface_q_path,
        "config.json": config_path,
        "palace_index_map.json": index_map_path,
        "palace_material_resolution.json": material_resolution_path,
    }


def _write_public_electrostatic_report_fixture(output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    terminal_c_path = output_dir / "terminal-C.csv"
    terminal_c_path.write_text(
        "i, C[i][1] (F), C[i][2] (F)\n"
        "1.00e+00, 1.0e-15, -2.0e-15\n"
        "2.00e+00, -2.0e-15, 4.0e-15\n"
    )
    domain_e_path = output_dir / "domain-E.csv"
    domain_e_path.write_text("i, E_elec[1] (J), p_elec[1]\n1, 1.0, 0.25\n2, 1.0, 0.125\n")
    surface_q_path = output_dir / "surface-Q.csv"
    surface_q_path.write_text("i, p_surf[2], Q_surf[2]\n1, 0.125, 1.0e6\n2, 0.25, 2.0e6\n")
    config_path = _write_public_report_json(
        output_dir / "config.json",
        {
            "Domains": {
                "Materials": [
                    {
                        "Attributes": [10],
                        "Name": "Si",
                        "Permittivity": 11.45,
                        "LossTan": 2.0e-6,
                    }
                ]
            },
            "Boundaries": {
                "Postprocessing": {
                    "Dielectric": [
                        {
                            "Index": 2,
                            "Attributes": [20],
                            "Type": "SA",
                            "Thickness": 0.003,
                            "Permittivity": 10.0,
                            "LossTan": 0.0017,
                        }
                    ]
                }
            },
        },
    )
    index_map_path = _write_public_report_json(
        output_dir / "palace_index_map.json",
        {
            "schema_version": 1,
            "entries": [
                {
                    "section": "Boundaries.Terminal",
                    "index": 1,
                    "entry_name": "positive_electrode",
                    "role": "pec_surface",
                    "attributes": [11],
                    "physical_names": ["D0_TOP_M1@positive"],
                    "dimension": 2,
                    "terminal_name": "positive",
                },
                {
                    "section": "Boundaries.Terminal",
                    "index": 2,
                    "entry_name": "negative_electrode",
                    "role": "pec_surface",
                    "attributes": [12],
                    "physical_names": ["D0_TOP_M1@negative"],
                    "dimension": 2,
                    "terminal_name": "negative",
                },
                {
                    "section": "Domains.Postprocessing.Energy",
                    "index": 1,
                    "entry_name": "substrate",
                    "role": "dielectric_volume",
                    "attributes": [10],
                    "physical_names": ["D1_SUBSTRATE"],
                    "dimension": 3,
                },
                {
                    "section": "Boundaries.Postprocessing.Dielectric",
                    "index": 2,
                    "entry_name": "sa_interface",
                    "role": "boundary_surface",
                    "attributes": [20],
                    "physical_names": ["SA:D1_SUBSTRATE___OUTER_VACUUM"],
                    "dimension": 2,
                    "Type": "SA",
                },
            ],
        },
    )
    material_resolution_path = _write_public_report_json(
        output_dir / "palace_material_resolution.json",
        _public_report_material_resolution(),
    )
    return {
        "terminal-C.csv": terminal_c_path,
        "domain-E.csv": domain_e_path,
        "surface-Q.csv": surface_q_path,
        "config.json": config_path,
        "palace_index_map.json": index_map_path,
        "palace_material_resolution.json": material_resolution_path,
    }


def build_public_driven_cpw_sim(output_dir: str | Path) -> tuple[Any, Any]:
    """Build the public Driven CPW fixture and return the sim plus mesh result."""

    return _public_driven_cpw_sim(Path(output_dir))


def build_public_driven_postprocessing(mesh_result: Any) -> dict[str, Any]:
    """Build Driven postprocessing from the generated mesh manifest."""

    return _driven_postprocessing(mesh_result)


def build_public_eigenmode_resonator_sim(output_dir: str | Path) -> tuple[Any, Any]:
    """Build the public Eigenmode resonator fixture and return the sim plus mesh result."""

    return _public_eigenmode_resonator_sim(Path(output_dir))


def build_public_eigenmode_postprocessing(mesh_result: Any) -> dict[str, Any]:
    """Build Eigenmode postprocessing from the generated mesh manifest."""

    return _eigenmode_postprocessing(mesh_result)


def build_public_eigenmode_interface_postprocessing(mesh_result: Any) -> dict[str, Any]:
    """Build caller-supplied Eigenmode dielectric-interface postprocessing."""

    from gsim.palace.mesh import (
        build_dielectric_interface_specs_from_material_kinds,
        build_postprocessing_config_from_manifest,
    )

    from orpen_sc_pdk.materials import (
        get_gsim_material_kind_alias_map,
        get_gsim_material_kind_map,
        validate_interface_preset_records,
    )

    interface_records = {
        "public_sa_example": {
            "interface_type": "SA",
            "thickness": 0.003,
            "material_name": "AlOx_native_generic",
            "source": "public notebook fixture only",
        }
    }
    dielectric_interfaces = build_dielectric_interface_specs_from_material_kinds(
        mesh_result.manifest,
        material_kind_by_name=get_gsim_material_kind_map(),
        material_name_aliases=get_gsim_material_kind_alias_map(),
        presets=validate_interface_preset_records(interface_records),
        preset_by_interface_type={"SA": "public_sa_example"},
    )
    return build_postprocessing_config_from_manifest(
        mesh_result.manifest,
        dielectric_interfaces=dielectric_interfaces,
    )


def build_public_electrostatic_capacitor_sim(output_dir: str | Path) -> tuple[Any, Any]:
    """Build the public Electrostatic capacitor fixture and return the sim plus mesh result."""

    return _public_same_layer_capacitor_electrostatic_sim(Path(output_dir))


def build_public_electrostatic_postprocessing(mesh_result: Any) -> dict[str, Any]:
    """Build Electrostatic postprocessing from the generated mesh manifest."""

    return _electrostatic_postprocessing(mesh_result)


def load_public_json(path: str | Path) -> dict[str, Any]:
    """Load a JSON artifact produced by a public simulation workflow."""

    return json.loads(Path(path).read_text())


def write_public_json(path: str | Path, data: Mapping[str, Any]) -> Path:
    """Write a small public JSON fixture used by notebook examples."""

    path = Path(path)
    path.write_text(json.dumps(dict(data), indent=2, sort_keys=True) + "\n")
    return path


def public_artifact_status(output_dir: str | Path) -> dict[str, bool]:
    """Report whether the standard public mesh/config artifacts exist."""

    output_dir = Path(output_dir)
    return {
        name: (output_dir / name).exists()
        for name in (
            "palace.msh",
            "config.json",
            "mesh_manifest.json",
            "palace_index_map.json",
        )
    }


def resolve_public_slurm_profile(
    profile_name: str,
    *,
    num_processes: int = 1,
    num_threads: int = 1,
) -> Any:
    """Resolve a docs-safe public Slurm profile through the `gsim` handoff API."""

    from gsim.palace.handoff import (
        load_palace_slurm_profile_catalog,
        resolve_palace_slurm_profile,
    )

    resource_overrides = _public_slurm_resource_overrides(
        num_processes=num_processes,
        num_threads=num_threads,
    )
    profiles = load_palace_slurm_profile_catalog(PUBLIC_SLURM_PROFILE_CATALOG)
    return resolve_palace_slurm_profile(
        profiles,
        profile_name,
        resource_overrides=resource_overrides,
    )


def public_solver_config_hints() -> dict[str, Any]:
    """Return public dry-run solver hints for Palace config generation."""

    return resolve_public_slurm_profile("public-slurm-dry-run").to_palace_config_hints()


def preview_public_slurm_script(script_path: str | Path) -> list[str]:
    """Return the scheduler-relevant lines from a generated public Slurm script."""

    return [
        line
        for line in Path(script_path).read_text().splitlines()
        if line.startswith("#SBATCH") or line.startswith("srun")
    ]


def public_simulation_helper_node_inventory_table() -> Any:
    """Return the public helper-node inventory as a notebook table."""

    import pandas as pd

    columns = [
        "node",
        "private_capability",
        "private_anchor",
        "why_helper_exists",
        "gdsfactory_home",
        "public_api_or_artifact",
        "public_status",
        "promotion_gate",
        "missing_evidence",
        "next_issue",
    ]
    return pd.DataFrame(load_public_simulation_helper_node_inventory()).loc[:, columns]


def public_problem_notebook_crosscheck_table() -> Any:
    """Return the representative notebook cross-check as a notebook table."""

    import pandas as pd

    columns = [
        "problem_type",
        "private_representative_notebook",
        "private_capability_anchor",
        "public_notebook",
        "public_helper_node",
        "gdsfactory_home",
        "owner_decision",
        "gsim_api_or_artifact",
        "notebook_support_wrapper",
        "coverage_status",
        "missing_evidence",
        "next_issue",
    ]
    return pd.DataFrame(load_public_problem_notebook_crosscheck()).loc[:, columns]


def public_simulation_goal_audit_table() -> Any:
    """Return the goal-level simulation migration audit as a notebook table."""

    import pandas as pd

    columns = [
        "objective_requirement",
        "current_status",
        "current_evidence",
        "remaining_gap",
        "next_issue",
    ]
    return pd.DataFrame(load_public_simulation_goal_audit()).loc[:, columns]


def public_gsim_boundary_review_crosscheck_table() -> Any:
    """Return the local gsim commit boundary-review matrix as a notebook table."""

    import pandas as pd

    columns = [
        "commit",
        "summary",
        "boundary_group",
        "review_status",
        "ecosystem_home",
        "owner_surface",
        "evidence_anchor",
    ]
    return pd.DataFrame(load_public_gsim_boundary_review_crosscheck()).loc[:, columns]


def public_interface_preset_source_review_table() -> Any:
    """Return source-review rows for public dielectric-interface preset candidates."""

    import pandas as pd

    columns = [
        "source_id",
        "source",
        "doi",
        "candidate_use",
        "review_status",
    ]
    queue = load_public_interface_preset_review_queue()
    return pd.DataFrame(queue["sources"]).loc[:, columns]


def public_interface_preset_candidate_review_table() -> Any:
    """Return candidate rows for public dielectric-interface preset review."""

    import pandas as pd

    columns = [
        "candidate_record",
        "source_id",
        "role",
        "geometry_family",
        "thickness_um",
        "material_or_permittivity",
        "loss_tangent",
        "extracted_fields_status",
        "promotion_status",
        "public_default_status",
        "owner_repo",
        "promotion_gate",
    ]
    queue = load_public_interface_preset_review_queue()
    return pd.DataFrame(queue["candidate_records"]).loc[:, columns]


def public_domain_material_table(output_dir: str | Path) -> Any:
    """Load the public domain-material provenance table for a generated config."""

    from gsim.palace import load_domain_material_summary

    frame = load_domain_material_summary(Path(output_dir))
    columns = [
        "domain_index",
        "physical_name",
        "stack_material_name",
        "matched_material_name",
        "material_model_source",
        "material_within_validity",
        "material_frequency_ghz",
        "permittivity",
        "loss_tangent",
        "conductivity",
        "permeability",
    ]
    selected_columns = [column for column in columns if column in frame.columns]
    return frame.loc[:, selected_columns].copy()


def public_index_map_lookup_table(
    output_dir: str | Path,
    *,
    sections: tuple[str, ...] | None = None,
) -> Any:
    """Load section/index lookup rows from the public Palace index map."""

    import pandas as pd
    from gsim.palace import load_postprocessing_index_map

    index_map = load_postprocessing_index_map(Path(output_dir))
    rows: list[dict[str, Any]] = []
    for entry in sorted(
        index_map.entries,
        key=lambda row: (row.section, row.index, row.entry_name),
    ):
        if sections is not None and entry.section not in sections:
            continue
        physical_name = index_map.physical_name_for_index(entry.section, entry.index)
        reverse_indices = (
            index_map.indices_for_physical_name(physical_name, section=entry.section)
            if physical_name is not None
            else ()
        )
        attribute = entry.attributes[0] if entry.attributes else None
        attribute_entry_names = (
            [
                matched.entry_name
                for matched in index_map.entries_for_attribute(
                    attribute,
                    section=entry.section,
                )
            ]
            if attribute is not None
            else []
        )
        rows.append(
            {
                "section": entry.section,
                "index": entry.index,
                "physical_name": physical_name,
                "reverse_indices_for_physical_name": list(reverse_indices),
                "attribute": attribute,
                "entry_names_for_attribute": attribute_entry_names,
                "entry_name": entry.entry_name,
                "role": entry.role,
                "port": entry.metadata.get("port"),
                "terminal_name": entry.extra.get("terminal_name"),
                "current_source_name": entry.extra.get("current_source_name"),
                "current_source_element_index": entry.extra.get(
                    "current_source_element_index"
                ),
                "current_source_element_count": entry.extra.get(
                    "current_source_element_count"
                ),
                "direction": entry.extra.get("Direction"),
                "coordinate_system": entry.extra.get("CoordinateSystem"),
                "type": entry.extra.get("Type"),
            }
        )
    return pd.DataFrame(rows)


def public_config_generation_summary(output_dir: str | Path) -> dict[str, Any]:
    """Return notebook-sized config/material/index summary fields."""

    output_dir = Path(output_dir)
    config = load_public_json(output_dir / "config.json")
    evidence = _config_generation_evidence(output_dir)
    return {
        "problem_type": evidence["problem_type"],
        "solver_device": evidence["solver_device"],
        "solver_problem_block": evidence["solver_problem_block"],
        "solver_has_linear": evidence["solver_has_linear"],
        "domain_material_count": evidence["domain_material_count"],
        "domain_material_rows": len(evidence["domain_materials"]),
        "domain_postprocessing_energy_count": evidence[
            "domain_postprocessing_energy_count"
        ],
        "surface_flux_count": evidence["surface_flux_count"],
        "dielectric_postprocessing_count": evidence["dielectric_postprocessing_count"],
        "lumped_port_count": evidence["lumped_port_count"],
        "terminal_count": evidence["terminal_count"],
        "boundary_sections": evidence["boundary_sections"],
        "config_problem_type": config["Problem"]["Type"],
    }


def select_public_report_table(
    frame: Any,
    columns: Sequence[str],
    *,
    max_rows: int = 8,
) -> dict[str, Any]:
    """Select a compact report table preview for notebook display."""

    selected_columns = [column for column in columns if column in frame.columns]
    table = frame.loc[:, selected_columns].head(max_rows).copy()
    return {
        "summary": {
            "rows": int(len(frame)),
            "shown_columns": selected_columns,
        },
        "table": table,
    }


def write_public_driven_report_fixture(output_dir: str | Path) -> dict[str, Path]:
    """Write docs-safe synthetic Driven report artifacts."""

    return _write_public_driven_report_fixture(Path(output_dir))


def write_public_eigenmode_report_fixture(output_dir: str | Path) -> dict[str, Path]:
    """Write docs-safe synthetic Eigenmode report artifacts."""

    return _write_public_eigenmode_report_fixture(Path(output_dir))


def write_public_electrostatic_report_fixture(output_dir: str | Path) -> dict[str, Path]:
    """Write docs-safe synthetic Electrostatic report artifacts."""

    return _write_public_electrostatic_report_fixture(Path(output_dir))


def local_palace_run_settings(
    environ: Mapping[str, str] | None = None,
) -> tuple[dict[str, Any], str | None]:
    """Return optional local Palace run kwargs or a docs-safe skip reason."""

    run_kwargs, solver = _solver_env(os.environ if environ is None else environ)
    return run_kwargs, solver["skip_reason"]


def run_public_driven_local_smoke(
    output_dir: str | Path,
    run_kwargs: Mapping[str, Any],
) -> dict[str, Any]:
    """Run the public Driven fixture through a configured local Palace executable."""

    from gsim.palace import load_driven_report

    output_dir = Path(output_dir)
    sim, mesh_result = build_public_driven_cpw_sim(output_dir)
    sim.write_config(
        postprocessing=build_public_driven_postprocessing(mesh_result),
        validate_mesh=False,
        material_overlay=get_gsim_material_overlay(),
        hints=public_solver_config_hints(),
    )
    results = sim.run_local(**dict(run_kwargs))
    report = load_driven_report(output_dir)
    return {
        "problem_type": "Driven",
        "port_names": list(report.sparams.port_names),
        "frequency_points": int(len(report.sparams.freq)),
        "port_epr_rows": int(len(report.port_epr)),
        "source_rows": int(len(report.sources)),
        "has_port_s": "port-S.csv" in results.files,
        "port_s_bytes": int(results.files["port-S.csv"].stat().st_size),
    }


def _apply_public_eigenmode_local_smoke_profile(sim: Any) -> None:
    sim.set_numerical(order=1, tolerance=1e-4, max_iterations=200)
    sim.set_eigenmode(num_modes=1, target=6e9, tolerance=1e-3)


def run_public_eigenmode_local_smoke(
    output_dir: str | Path,
    run_kwargs: Mapping[str, Any],
) -> dict[str, Any]:
    """Run the public Eigenmode fixture through a configured local Palace executable."""

    from gsim.palace import load_eigenmode_report

    output_dir = Path(output_dir)
    sim, mesh_result = build_public_eigenmode_resonator_sim(output_dir)
    _apply_public_eigenmode_local_smoke_profile(sim)
    sim.write_config(
        postprocessing=build_public_eigenmode_postprocessing(mesh_result),
        validate_mesh=False,
        material_overlay=get_gsim_material_overlay(),
        hints=public_solver_config_hints(),
    )
    results = sim.run_local(**dict(run_kwargs))
    report = load_eigenmode_report(results)
    return {
        "problem_type": "Eigenmode",
        "mode_count": int(report.eigenmodes.n_modes),
        "min_frequency_ghz": float(report.eigenmodes.freq_real_ghz.min()),
        "domain_energy_rows": int(len(report.domain_energy)),
        "eig_bytes": int(results["eig.csv"].stat().st_size),
    }


def run_public_electrostatic_local_smoke(
    output_dir: str | Path,
    run_kwargs: Mapping[str, Any],
) -> dict[str, Any]:
    """Run the public Electrostatic fixture through a configured local Palace executable."""

    from gsim.palace import load_electrostatic_report

    output_dir = Path(output_dir)
    sim, mesh_result = build_public_electrostatic_capacitor_sim(output_dir)
    sim.write_config(
        postprocessing=build_public_electrostatic_postprocessing(mesh_result),
        validate_mesh=False,
        material_overlay=get_gsim_material_overlay(),
        hints=public_solver_config_hints(),
    )
    results = sim.run_local(**dict(run_kwargs))
    report = load_electrostatic_report(results)
    return {
        "problem_type": "Electrostatic",
        "terminal_names": list(report.capacitance.terminal_names),
        "matrix_shape": list(report.capacitance.dataframe.shape),
        "has_mutual_matrix": report.mutual_capacitance is not None,
        "has_inverse_matrix": report.inverse_capacitance is not None,
        "terminal_c_bytes": int(results["terminal-C.csv"].stat().st_size),
    }


def _public_magnetostatic_cpw_sim(output_dir: Path):
    from gsim.palace import MagnetostaticSim

    component = cpw_straight(length=300, signal_width=10, gap=6, ground_width=40)

    sim = MagnetostaticSim()
    sim.set_output_dir(output_dir)
    sim.set_geometry(component)
    sim.set_stack(
        include_substrate=True,
        substrate_thickness=20,
        add_oxide_dielectric=False,
        add_passivation_dielectric=False,
    )
    sim.set_airbox(margin_x=40, margin_y=40, z_above=50, z_below=10)
    sim.add_current_source(
        "signal",
        layer="D0_TOP_M1",
        center=(0, 0),
        direction=[1.0, 0.0, 0.0],
        coordinate_system="Cartesian",
    )
    sim.add_current_source(
        "return",
        elements=(
            {
                "layer": "D0_TOP_M1",
                "center": (0, 31),
                "direction": "-X",
            },
            {
                "layer": "D0_TOP_M1",
                "center": (0, -31),
                "direction": [-1.0, 0.0, 0.0],
                "coordinate_system": "Cartesian",
            },
        ),
    )
    sim.set_magnetostatic(save_fields=0)
    sim.mesh(
        preset="coarse",
        refined_mesh_size=20,
        max_mesh_size=200,
        margin_x=40,
        margin_y=40,
        planar_conductors=True,
        auto_size=False,
    )
    return sim, sim._last_mesh_result


def _magnetostatic_postprocessing(mesh_result: Any) -> Any:
    from gsim.palace.mesh import build_postprocessing_config_from_manifest

    return build_postprocessing_config_from_manifest(
        mesh_result.manifest,
        include_empty_sections=False,
    )


def _magnetostatic_report_summary(_output_dir: Path) -> dict[str, Any]:
    return {
        "status": "not_implemented",
        "reason": "Magnetostatic report loader is pending a confirmed Palace output contract.",
    }


def _build_problem_evidence(
    *,
    output_root: Path,
    problem_key: str,
    fixture_name: str,
    problem_type: str,
    build_sim: Callable[[Path], tuple[Any, Any]],
    build_postprocessing: Callable[[Any], dict[str, Any]],
    report_summary: Callable[[Path], dict[str, Any]],
    run_kwargs: Mapping[str, Any],
    solver_skip_reason: str | None,
    solver_enabled: bool = True,
    prepare_local_solver: Callable[[Any], None] | None = None,
) -> dict[str, Any]:
    from gsim.palace.handoff import (
        PalaceSlurmSbatchSpec,
        load_palace_slurm_profile_catalog,
        resolve_palace_slurm_profile,
        write_palace_run_handoff_archive_manifest,
        write_palace_slurm_sbatch_handoff,
    )
    from gsim.palace.results import (
        load_palace_run_summary,
        write_palace_resource_record,
        write_palace_resource_record_from_log,
    )

    output_dir = output_root / problem_key
    effective_solver_skip_reason = solver_skip_reason
    if not solver_enabled and effective_solver_skip_reason is None:
        effective_solver_skip_reason = (
            f"{problem_type} local Palace solve deferred by current scope"
        )
    num_processes = int(run_kwargs.get("num_processes", 1) or 1)
    num_threads = int(run_kwargs.get("num_threads", 1) or 1)
    slurm_profiles = load_palace_slurm_profile_catalog(PUBLIC_SLURM_PROFILE_CATALOG)
    slurm_profile = resolve_palace_slurm_profile(
        slurm_profiles,
        "public-slurm-dry-run",
        resource_overrides=_public_slurm_resource_overrides(
            num_processes=num_processes,
            num_threads=num_threads,
        ),
    )
    sim, mesh_result = build_sim(output_dir)
    if effective_solver_skip_reason is None and prepare_local_solver is not None:
        prepare_local_solver(sim)
    sim.write_config(
        postprocessing=build_postprocessing(mesh_result),
        validate_mesh=False,
        material_overlay=get_gsim_material_overlay(),
        hints=slurm_profile.to_palace_config_hints(),
    )
    write_palace_slurm_sbatch_handoff(
        output_dir,
        PalaceSlurmSbatchSpec(
            job_name=f"palace_{problem_key}",
            resources=slurm_profile.resources,
            **slurm_profile.launcher.to_sbatch_kwargs(),
        ),
        profile=slurm_profile.profile,
        metadata={
            "fixture": fixture_name,
            "problem_type": problem_type,
            "solver_enabled": effective_solver_skip_reason is None,
            "workflow": "public-palace-smoke-evidence",
        },
    )
    write_palace_run_handoff_archive_manifest(
        output_dir,
        metadata={
            "fixture": fixture_name,
            "problem_type": problem_type,
            "workflow": "public-palace-smoke-evidence",
        },
    )
    if effective_solver_skip_reason is not None:
        _write_public_log_resource_record(
            write_palace_resource_record_from_log,
            output_dir=output_dir,
            fixture_name=fixture_name,
            problem_type=problem_type,
            run_kwargs=run_kwargs,
            status="synthetic",
            missing_sources=(effective_solver_skip_reason,),
        )
    run_summary = _relative_run_summary(
        load_palace_run_summary(output_dir, include_hashes=True).to_dict(),
        output_root,
    )

    if effective_solver_skip_reason is None:
        sim.run_local(**dict(run_kwargs))
        completed_summary = load_palace_run_summary(output_dir, include_hashes=True)
        _write_public_resource_record(
            write_palace_resource_record,
            output_dir=output_dir,
            fixture_name=fixture_name,
            problem_type=problem_type,
            run_kwargs=run_kwargs,
            status="completed",
            runtime_summary=completed_summary.runtime,
            missing_sources=(),
        )
        run_summary = _relative_run_summary(
            load_palace_run_summary(output_dir, include_hashes=True).to_dict(),
            output_root,
        )
        solver_report = report_summary(output_dir)
    else:
        solver_report = {"status": "skipped", "reason": effective_solver_skip_reason}

    return {
        "problem_type": problem_type,
        "fixture": fixture_name,
        "output_dir": _relative_path(output_dir, output_root),
        "run_summary": run_summary,
        "config_generation": _config_generation_evidence(output_dir),
        "index_map_lookup": _index_map_lookup_evidence(output_dir),
        "solver_report": solver_report,
    }


def _build_sweep_evidence(
    output_root: Path,
    problems: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    from gsim.palace.handoff import (
        PalaceSlurmSweepArraySpec,
        load_palace_slurm_profile_catalog,
        resolve_palace_slurm_profile,
        write_palace_slurm_sweep_array_handoff,
        write_palace_sweep_handoff_archive_manifest,
    )
    from gsim.palace.results import (
        PalaceSweepPointSpec,
        load_palace_sweep_summary,
        write_palace_sweep_points,
        write_palace_sweep_resource_index,
    )

    points = [
        PalaceSweepPointSpec(
            point_slug=problem_key,
            parameters={
                "problem_type": problem["problem_type"],
                "fixture": problem["fixture"],
            },
            run_dir=problem["output_dir"],
            handoff_metadata_path=(f"{problem['output_dir']}/palace_handoff_metadata.json"),
            resource_record_path=(
                f"{problem['output_dir']}/metadata/records/palace_resource_record.json"
            ),
        )
        for problem_key, problem in sorted(problems.items())
    ]
    write_palace_sweep_points(
        output_root,
        points,
        sweep_id="public_palace_problem_type_smoke",
    )
    slurm_profiles = load_palace_slurm_profile_catalog(PUBLIC_SLURM_PROFILE_CATALOG)
    slurm_profile = resolve_palace_slurm_profile(
        slurm_profiles,
        "public-slurm-sweep-dry-run",
    )
    write_palace_slurm_sweep_array_handoff(
        output_root,
        PalaceSlurmSweepArraySpec(
            job_name="palace_public_problem_smoke",
            resources=slurm_profile.resources,
            max_parallel=len(points),
            **slurm_profile.launcher.to_sbatch_kwargs(),
        ),
        profile=slurm_profile.profile,
        metadata={
            "workflow": "public-palace-smoke-evidence",
            "point_count": len(points),
        },
    )
    write_palace_sweep_handoff_archive_manifest(
        output_root,
        metadata={
            "workflow": "public-palace-smoke-evidence",
            "point_count": len(points),
        },
    )
    sweep_summary = _relative_sweep_summary(
        load_palace_sweep_summary(
            output_root,
            include_hashes=True,
            include_report_metrics=True,
        ).to_dict(),
        output_root,
    )
    resource_index = write_palace_sweep_resource_index(
        output_root,
        include_hashes=True,
        include_report_metrics=True,
    )
    return {
        "summary": sweep_summary,
        "resource_index": _relative_result_paths(resource_index.to_dict(), output_root),
    }


def _write_public_resource_record(
    writer: Callable[..., Path],
    *,
    output_dir: Path,
    fixture_name: str,
    problem_type: str,
    run_kwargs: Mapping[str, Any],
    status: str,
    runtime_summary: Mapping[str, Any] | None,
    missing_sources: Sequence[str],
) -> None:
    num_processes = int(run_kwargs.get("num_processes", 1) or 1)
    num_threads = int(run_kwargs.get("num_threads", 1) or 1)
    runtime: dict[str, Any] = {}
    launcher: dict[str, Any] = {}
    if runtime_summary:
        runtime["return_code"] = runtime_summary.get("return_code")
        if runtime_summary.get("elapsed_seconds") is not None:
            runtime["wall_time_seconds"] = runtime_summary["elapsed_seconds"]
        launcher = dict(runtime_summary.get("launcher", {}) or {})

    writer(
        output_dir,
        status=status,
        launcher=launcher,
        allocation={
            "nodes": 1,
            "num_processes": num_processes,
            "num_threads": num_threads,
            "cores": num_processes * num_threads,
        },
        runtime=runtime,
        missing_sources=missing_sources,
        metadata={
            "fixture": fixture_name,
            "problem_type": problem_type,
            "workflow": "public-palace-smoke-evidence",
            "measured": status == "completed",
        },
    )


def _write_public_log_resource_record(
    writer: Callable[..., Path],
    *,
    output_dir: Path,
    fixture_name: str,
    problem_type: str,
    run_kwargs: Mapping[str, Any],
    status: str,
    missing_sources: Sequence[str],
) -> None:
    num_processes = int(run_kwargs.get("num_processes", 1) or 1)
    num_threads = int(run_kwargs.get("num_threads", 1) or 1)
    log_path = _write_public_palace_resource_log(
        output_dir,
        num_processes=num_processes,
        num_threads=num_threads,
    )
    scontrol_path = _write_public_slurm_scontrol(
        output_dir,
        num_processes=num_processes,
        num_threads=num_threads,
    )
    writer(
        output_dir,
        log_path,
        scontrol_path=scontrol_path,
        status=status,
        allocation={
            "nodes": 1,
            "num_processes": num_processes,
            "num_threads": num_threads,
            "cores": num_processes * num_threads,
        },
        missing_sources=missing_sources,
        metadata={
            "fixture": fixture_name,
            "measured": False,
            "problem_type": problem_type,
            "resource_log_source": "synthetic-public-fixture",
            "workflow": "public-palace-smoke-evidence",
        },
    )


def _write_public_palace_resource_log(
    output_dir: Path,
    *,
    num_processes: int,
    num_threads: int,
) -> Path:
    log_path = output_dir / "logs" / "palace-public-resource.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        dedent(
            f"""
            Git changeset ID: v0.16.1
            Running with {num_processes} MPI processes, {num_threads} OpenMP threads
            Device configuration: omp,cpu
            Memory configuration: host-std
            libCEED backend: /cpu/self/xsmm/blocked

            Cumulative timing statistics:

            Elapsed Time Report (s)           Min.        Max.        Avg.
            ==============================================================
            Initialization                   1.000       1.100       1.050
            Operator Construction            2.000       2.200       2.100
            Disk IO                          0.400       0.500       0.450
            --------------------------------------------------------------
            Total                           58.573      58.580      58.578

            Peak Memory                   Per-Node       Total   Total HWM
            ==============================================================
            Initialization                   79.1M       79.1M       79.1M
            Operator Construction             1.6G        1.6G        2.0G
            Disk IO                         216.9M      216.9M        2.1G
            --------------------------------------------------------------
            Total                            10.8G       10.8G       10.8G
            Estimated peak per-rank memory usage is: Min. 2.7G, Max. 2.7G, Avg. 2.7G, Total 10.9G
            Estimated peak per-node memory usage is: Min. 10.9G, Max. 10.9G, Avg. 10.9G, Total 10.9G

            Adaptive mesh refinement (AMR) iteration 1:
             Indicator norm = 3.158e-01, global unknowns = 887970
             Max. iterations = 15, tol. = 1.000e-02, max. size = 5000000
             Marked 12568/664696 elements for refinement (70.00% of the error, theta = 0.70)
             Conforming mesh refinement added 659265 elements (initial = 664696, final = 1323961)

            Proceeding with solve/estimate iteration 2...

            Elapsed Time Report (s)           Min.        Max.        Avg.
            ==============================================================
            Initialization                   1.000       1.100       1.050
            Operator Construction            3.000       3.200       3.100
            Disk IO                          0.400       0.500       0.450
            --------------------------------------------------------------
            Total                          120.000     121.000     120.500

            Peak Memory                   Per-Node       Total   Total HWM
            ==============================================================
            Initialization                   79.1M       79.1M       79.1M
            Operator Construction             2.6G        2.6G        3.0G
            Disk IO                         216.9M      216.9M        3.1G
            --------------------------------------------------------------
            Total                            20.8G       20.8G       20.8G
            Estimated peak per-rank memory usage is: Min. 5.2G, Max. 5.2G, Avg. 5.2G, Total 20.9G
            Estimated peak per-node memory usage is: Min. 20.9G, Max. 20.9G, Avg. 20.9G, Total 20.9G

            Completed 1 iterations of adaptive mesh refinement (AMR):
             Indicator norm = 1.522e-01, global unknowns = 10718029
             Max. iterations = 15, tol. = 1.000e-02, max. size = 5000000

            ---------- PETSc Performance Summary: ----------

            palace on a  named public-node with {num_processes} processes, by user on 2026-05-21
            Using {num_threads} OpenMP threads
            Using PETSc Release Version 3.24.3, unknown

                                     Max       Max/Min     Avg       Total
            Time (sec):           1.029e+03     1.000   1.029e+03
            """
        )
    )
    return log_path


def _write_public_slurm_scontrol(
    output_dir: Path,
    *,
    num_processes: int,
    num_threads: int,
) -> Path:
    scontrol_path = output_dir / "metadata" / "scontrol-job-public.txt"
    scontrol_path.parent.mkdir(parents=True, exist_ok=True)
    num_cpus = num_processes * num_threads
    scontrol_path.write_text(
        dedent(
            f"""
            JobId=12345 JobName=public_palace_fixture
               Account=public_alloc JobState=COMPLETED
               SubmitTime=2026-05-21T18:16:44 StartTime=2026-05-21T18:24:47
               EndTime=2026-05-21T18:26:48
               Partition=public_cpu NodeList=public-node BatchHost=public-node
               NumNodes=1 NumCPUs={num_cpus} NumTasks={num_processes}
               CPUs/Task={num_threads} TimeLimit=00:10:00 RunTime=00:02:01
               TRES=cpu={num_cpus},mem=1024M,node=1,billing={num_cpus}
            """
        )
    )
    return scontrol_path


def build_public_palace_smoke_evidence(
    output_root: str | Path = DEFAULT_OUTPUT_DIR,
    *,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build publication-safe public Palace smoke evidence for local review."""

    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    environ = os.environ if environ is None else environ
    run_kwargs, solver = _solver_env(environ)

    orpen_sc_pdk.activate()
    problem_specs = (
        {
            "problem_key": "driven_cpw",
            "fixture_name": "cpw_straight",
            "problem_type": "Driven",
            "build_sim": _public_driven_cpw_sim,
            "build_postprocessing": _driven_postprocessing,
            "report_summary": _driven_report_summary,
            "solver_enabled": True,
            "prepare_local_solver": None,
        },
        {
            "problem_key": "eigenmode_resonator",
            "fixture_name": "resonator",
            "problem_type": "Eigenmode",
            "build_sim": _public_eigenmode_resonator_sim,
            "build_postprocessing": _eigenmode_postprocessing,
            "report_summary": _eigenmode_report_summary,
            "solver_enabled": True,
            "prepare_local_solver": _apply_public_eigenmode_local_smoke_profile,
        },
        {
            "problem_key": "electrostatic_same_layer_capacitor",
            "fixture_name": "martinis2022_differential_ribbon_capacitor",
            "problem_type": "Electrostatic",
            "build_sim": _public_same_layer_capacitor_electrostatic_sim,
            "build_postprocessing": _electrostatic_postprocessing,
            "report_summary": _electrostatic_report_summary,
            "solver_enabled": True,
            "prepare_local_solver": None,
        },
        {
            "problem_key": "magnetostatic_cpw",
            "fixture_name": "cpw_straight",
            "problem_type": "Magnetostatic",
            "build_sim": _public_magnetostatic_cpw_sim,
            "build_postprocessing": _magnetostatic_postprocessing,
            "report_summary": _magnetostatic_report_summary,
            "solver_enabled": False,
            "prepare_local_solver": None,
        },
    )

    problems = {
        spec["problem_key"]: _build_problem_evidence(
            output_root=output_root,
            problem_key=spec["problem_key"],
            fixture_name=spec["fixture_name"],
            problem_type=spec["problem_type"],
            build_sim=spec["build_sim"],
            build_postprocessing=spec["build_postprocessing"],
            report_summary=spec["report_summary"],
            run_kwargs=run_kwargs,
            solver_skip_reason=solver["skip_reason"],
            solver_enabled=spec["solver_enabled"],
            prepare_local_solver=spec["prepare_local_solver"],
        )
        for spec in problem_specs
    }
    sweep_evidence = _build_sweep_evidence(output_root, problems)

    evidence = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "workflow": "public-palace-smoke-evidence",
        "repo": "orpen-sc-pdk",
        "solver": solver,
        "helper_node_inventory": load_public_simulation_helper_node_inventory(),
        "problem_notebook_crosscheck": load_public_problem_notebook_crosscheck(),
        "goal_audit": load_public_simulation_goal_audit(),
        "gsim_boundary_review_crosscheck": load_public_gsim_boundary_review_crosscheck(),
        "interface_preset_review_queue": load_public_interface_preset_review_queue(),
        "problems": problems,
        "sweep_summary": sweep_evidence["summary"],
        "sweep_resource_index": sweep_evidence["resource_index"],
    }

    evidence_path = output_root / EVIDENCE_FILENAME
    evidence["evidence_path"] = _relative_path(evidence_path, output_root)
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    return evidence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build public OrPen/gsim Palace smoke evidence artifacts.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Evidence output directory. Defaults to {DEFAULT_OUTPUT_DIR}.",
    )
    args = parser.parse_args(argv)

    evidence = build_public_palace_smoke_evidence(args.output_dir)
    print(args.output_dir / evidence["evidence_path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
