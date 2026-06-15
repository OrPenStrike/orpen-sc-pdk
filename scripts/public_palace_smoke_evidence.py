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


def load_public_simulation_helper_node_inventory() -> list[dict[str, Any]]:
    """Load the public helper-node coverage matrix used by docs and evidence."""

    return json.loads(PUBLIC_HELPER_NODE_INVENTORY.read_text())


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


def _magnetostatic_postprocessing(mesh_result: Any) -> dict[str, Any]:
    from gsim.palace.mesh import (
        PostprocessingConfig,
        build_postprocessing_config_from_manifest,
    )

    base = build_postprocessing_config_from_manifest(mesh_result.manifest)
    return PostprocessingConfig(domains=base.domains, index_map=base.index_map)


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
) -> dict[str, Any]:
    from gsim.palace import (
        PalaceSlurmSbatchSpec,
        load_palace_run_summary,
        load_palace_slurm_profile_catalog,
        resolve_palace_slurm_profile,
        write_palace_resource_record,
        write_palace_resource_record_from_log,
        write_palace_run_handoff_archive_manifest,
        write_palace_slurm_sbatch_handoff,
    )

    output_dir = output_root / problem_key
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
            "solver_enabled": solver_skip_reason is None,
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
    if solver_skip_reason is not None:
        _write_public_log_resource_record(
            write_palace_resource_record_from_log,
            output_dir=output_dir,
            fixture_name=fixture_name,
            problem_type=problem_type,
            run_kwargs=run_kwargs,
            status="synthetic",
            missing_sources=(solver_skip_reason,),
        )
    run_summary = _relative_run_summary(
        load_palace_run_summary(output_dir, include_hashes=True).to_dict(),
        output_root,
    )

    if solver_skip_reason is None:
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
        solver_report = {"status": "skipped", "reason": solver_skip_reason}

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
    from gsim.palace import (
        PalaceSlurmSweepArraySpec,
        PalaceSweepPointSpec,
        load_palace_slurm_profile_catalog,
        load_palace_sweep_summary,
        resolve_palace_slurm_profile,
        write_palace_slurm_sweep_array_handoff,
        write_palace_sweep_handoff_archive_manifest,
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
        },
        {
            "problem_key": "eigenmode_resonator",
            "fixture_name": "resonator",
            "problem_type": "Eigenmode",
            "build_sim": _public_eigenmode_resonator_sim,
            "build_postprocessing": _eigenmode_postprocessing,
            "report_summary": _eigenmode_report_summary,
        },
        {
            "problem_key": "electrostatic_same_layer_capacitor",
            "fixture_name": "martinis2022_differential_ribbon_capacitor",
            "problem_type": "Electrostatic",
            "build_sim": _public_same_layer_capacitor_electrostatic_sim,
            "build_postprocessing": _electrostatic_postprocessing,
            "report_summary": _electrostatic_report_summary,
        },
        {
            "problem_key": "magnetostatic_cpw",
            "fixture_name": "cpw_straight",
            "problem_type": "Magnetostatic",
            "build_sim": _public_magnetostatic_cpw_sim,
            "build_postprocessing": _magnetostatic_postprocessing,
            "report_summary": _magnetostatic_report_summary,
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
