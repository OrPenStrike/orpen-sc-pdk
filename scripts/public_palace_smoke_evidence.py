from __future__ import annotations

import argparse
import json
import os
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
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


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _relative_run_summary(summary: dict[str, Any], output_root: Path) -> dict[str, Any]:
    for group_name in ("artifacts", "results"):
        group = summary.get(group_name, {})
        if not isinstance(group, dict):
            continue
        for row in group.values():
            if not isinstance(row, dict) or row.get("path") is None:
                continue
            row["path"] = _relative_path(Path(row["path"]), output_root)
    for group_name in ("handoff", "runtime"):
        group = summary.get(group_name, {})
        if not isinstance(group, dict):
            continue
        if group.get("path") is not None:
            group["path"] = _relative_path(Path(group["path"]), output_root)
        for ref_name in ("script", "archive"):
            ref = group.get(ref_name)
            if isinstance(ref, dict) and ref.get("path") is not None:
                ref["path"] = _relative_path(Path(ref["path"]), output_root)
    return summary


def _relative_sweep_summary(
    summary: dict[str, Any],
    output_root: Path,
) -> dict[str, Any]:
    source_path = summary.get("source_path")
    if source_path is not None:
        summary["source_path"] = _relative_path(Path(source_path), output_root)
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
    from gsim.palace import load_palace_run_summary, write_palace_handoff_metadata

    output_dir = output_root / problem_key
    sim, mesh_result = build_sim(output_dir)
    sim.write_config(
        postprocessing=build_postprocessing(mesh_result),
        validate_mesh=False,
        material_overlay=get_gsim_material_overlay(),
    )
    write_palace_handoff_metadata(
        output_dir,
        status="planned",
        launcher={
            "kind": "dry_run",
            "target": "palace",
            "solver_enabled": solver_skip_reason is None,
        },
        profile={"name": "public-local-dry-run"},
        resources={
            "num_processes": int(run_kwargs.get("num_processes", 1) or 1),
            "num_threads": int(run_kwargs.get("num_threads", 1) or 1),
        },
        script_path="run_palace.sbatch",
        archive_path="palace-handoff.tar.gz",
        command={"argv": ["palace", "config.json"], "redacted": True},
        metadata={
            "fixture": fixture_name,
            "problem_type": problem_type,
            "workflow": "public-palace-smoke-evidence",
        },
    )
    run_summary = _relative_run_summary(
        load_palace_run_summary(output_dir, include_hashes=True).to_dict(),
        output_root,
    )

    if solver_skip_reason is None:
        sim.run_local(**dict(run_kwargs))
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
        "solver_report": solver_report,
    }


def _build_sweep_evidence(
    output_root: Path,
    problems: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    from gsim.palace import (
        PalaceSweepPointSpec,
        load_palace_sweep_summary,
        write_palace_sweep_points,
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
        )
        for problem_key, problem in sorted(problems.items())
    ]
    write_palace_sweep_points(
        output_root,
        points,
        sweep_id="public_palace_problem_type_smoke",
    )
    return _relative_sweep_summary(
        load_palace_sweep_summary(
            output_root,
            include_hashes=True,
            include_report_metrics=True,
        ).to_dict(),
        output_root,
    )


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
    sweep_summary = _build_sweep_evidence(output_root, problems)

    evidence = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "workflow": "public-palace-smoke-evidence",
        "repo": "orpen-sc-pdk",
        "solver": solver,
        "problems": problems,
        "sweep_summary": sweep_summary,
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
