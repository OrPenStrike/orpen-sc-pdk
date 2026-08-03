"""Notebook-side AEDT handoff package writer.

This module owns manifest layout, source-artifact copying, sidecar validation,
run-config writing, generated launcher placement, and archive packaging. It does
not define package models, material compilation, template text, or run-side
PyAEDT execution logic.
"""

from __future__ import annotations

import csv
import json
import shutil
import tarfile
from collections.abc import Mapping, Sequence
from importlib.resources import as_file, files
from pathlib import Path
from typing import Any

import yaml

from orpen_sc_pdk.port_metadata import Q2dConductorPortInfo, Q2dConductorType
from orpen_sc_pdk.simulation.aedt.hpc import (
    AedtHpcProfileSpec,
    AedtHpcResourceSpec,
    write_aedt_hpc_artifacts,
)
from orpen_sc_pdk.simulation.aedt.materials import compile_aedt_material_context_from_mapping_path
from orpen_sc_pdk.simulation.aedt.models import (
    AedtNativeCaseSpec,
    AedtNativeHandoffArchiveResult,
    AedtNativePackageResult,
    AedtNativePackageSpec,
    AedtNativeRunProfileSpec,
    AedtPlatform,
    AedtRecipeSpec,
    safe_aedt_name,
)
from orpen_sc_pdk.simulation.aedt.q2d import validate_q2d_cross_section_payload
from orpen_sc_pdk.simulation.aedt.templates import (
    render_aedt_package_readme,
    render_aedt_requirements,
    render_powershell_launcher,
    render_runtime_runner,
    render_shell_launcher,
)

_ARCHIVE_SKIP_NAMES = {".DS_Store", "__pycache__"}
_REQUIRED_RUNTIME_BUNDLE_FILES = (
    "run_aedt_native.py",
    "__init__.py",
    "io.py",
    "materials.py",
    "session.py",
    "sweep.py",
    "solver/__init__.py",
    "solver/q3d.py",
    "solver/hfss/__init__.py",
    "solver/hfss/driven_terminal.py",
    "solver/hfss/eigenmode.py",
    "solver/q2d/__init__.py",
    "solver/q2d/workflow.py",
    "solver/q2d/state.py",
    "solver/q2d/geometry.py",
    "solver/q2d/assignment.py",
    "solver/q2d/region.py",
    "solver/q2d/setup.py",
    "solver/q2d/solve.py",
    "solver/q2d/export.py",
    "solver/q2d/audit.py",
)


def write_aedt_run_config_artifacts(
    run_configs_dir: Path,
    resource: AedtHpcResourceSpec,
    *,
    point_local_q2d_sweep: bool,
    import_run_profile: AedtNativeRunProfileSpec | None = None,
    solve_run_profile: AedtNativeRunProfileSpec | None = None,
) -> tuple[Path, Path]:
    """Write import/solve runner profiles for the generated AEDT package."""

    run_configs_dir.mkdir(parents=True, exist_ok=True)
    import_max_workers = None
    if point_local_q2d_sweep:
        import_max_workers = resource.core_budget or resource.num_cores * resource.max_workers
    import_profile = import_run_profile or AedtNativeRunProfileSpec(
        mode="import",
        resume_policy=("skip_completed_retry_failed" if point_local_q2d_sweep else "run_all"),
        skip_completed=point_local_q2d_sweep,
        continue_on_failure=point_local_q2d_sweep,
        parallel=point_local_q2d_sweep,
        max_workers=import_max_workers,
        num_cores=1 if point_local_q2d_sweep else None,
        memory_mb_total=resource.memory_mb_total if point_local_q2d_sweep else None,
        memory_mb_per_worker=resource.memory_mb_per_worker if point_local_q2d_sweep else None,
        ram_percent=resource.ram_percent if point_local_q2d_sweep else None,
        core_budget=resource.core_budget if point_local_q2d_sweep else None,
        progress="auto",
    )
    solve_profile = solve_run_profile or AedtNativeRunProfileSpec(
        mode="solve",
        resume_policy=("skip_completed_retry_failed" if point_local_q2d_sweep else "run_all"),
        skip_completed=point_local_q2d_sweep,
        continue_on_failure=point_local_q2d_sweep,
        parallel=point_local_q2d_sweep,
        max_workers=resource.max_workers if point_local_q2d_sweep else None,
        num_cores=resource.num_cores if point_local_q2d_sweep else None,
        memory_mb_total=resource.memory_mb_total if point_local_q2d_sweep else None,
        memory_mb_per_worker=resource.memory_mb_per_worker if point_local_q2d_sweep else None,
        ram_percent=resource.ram_percent if point_local_q2d_sweep else None,
        core_budget=resource.core_budget if point_local_q2d_sweep else None,
        progress="auto",
    )
    import_path = run_configs_dir / "import.yaml"
    solve_path = run_configs_dir / "solve.yaml"
    import_path.write_text(
        yaml.safe_dump(import_profile.model_dump(mode="json", exclude_none=True), sort_keys=False),
        encoding="utf-8",
    )
    solve_path.write_text(
        yaml.safe_dump(solve_profile.model_dump(mode="json", exclude_none=True), sort_keys=False),
        encoding="utf-8",
    )
    return import_path, solve_path


def prepare_aedt_native_handoff_package(
    spec: AedtNativePackageSpec,
    *,
    package_dir: str | Path,
    overwrite: bool = True,
) -> AedtNativePackageResult:
    """Write a generic AEDT-native package with manifest and PyAEDT scripts.

    Existing run folders are updated in place when ``overwrite`` is true. The
    writer refreshes generated package metadata, run configs, and scripts, but
    deliberately leaves existing ``results/``, ``logs/``, and ``points/`` data
    in place so expanded point sweeps can resume with skip-completed behavior.
    """

    resolved_package_dir = Path(package_dir)
    if resolved_package_dir.exists() and not overwrite:
        raise FileExistsError(resolved_package_dir)
    gds_dir = resolved_package_dir / "gds"
    tech_dir = resolved_package_dir / "tech"
    layer_mapping_dir = resolved_package_dir / "layer_mapping"
    metadata_dir = resolved_package_dir / "metadata"
    hpc_dir = resolved_package_dir / "hpc"
    run_configs_dir = resolved_package_dir / "run_configs"
    scripts_dir = resolved_package_dir / "scripts"
    for directory in (
        metadata_dir,
        hpc_dir,
        run_configs_dir,
        scripts_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    project_path = spec.project_path or (resolved_package_dir / f"{spec.project_name}.aedt")
    case_rows = []
    for case in spec.cases:
        _validate_q2d_semantic_case_sidecars(case)
        gds_path = gds_dir / f"{case.id}.gds"
        tech_path = tech_dir / f"{case.id}.tech"
        control_path = tech_dir / f"{case.id}.xml"
        layer_mapping_csv_path = layer_mapping_dir / f"{case.id}_layer_mapping.csv"
        layer_mapping_json_path = layer_mapping_dir / f"{case.id}_layer_mapping.json"
        aedt_material_context_path = metadata_dir / f"{case.id}_aedt_material_context.json"
        q2d_conductors_csv_path = metadata_dir / f"{case.id}_q2d_conductors.csv"
        q2d_conductors_json_path = metadata_dir / f"{case.id}_q2d_conductors.json"
        q2d_cross_section_path = metadata_dir / f"{case.id}_q2d_cross_section.json"
        gds_relative = None
        tech_relative = None
        control_relative = None
        csv_relative = None
        json_relative = None
        aedt_material_context_relative = None
        q2d_csv_relative = None
        q2d_json_relative = None
        q2d_cross_section_relative = None
        if case.gds_path is not None:
            _copy_required_file(case.gds_path, gds_path)
            gds_relative = _relative_posix(resolved_package_dir, gds_path)
        if case.tech_path is not None:
            _copy_required_file(case.tech_path, tech_path)
            tech_relative = _relative_posix(resolved_package_dir, tech_path)
        source_control_path = case.control_path
        if source_control_path is None and case.tech_path is not None:
            source_control_path = _candidate_control_path(case.tech_path)
        if source_control_path is not None:
            _copy_required_file(source_control_path, control_path)
            control_relative = _relative_posix(resolved_package_dir, control_path)
        if case.layer_mapping_csv_path is not None:
            _copy_required_file(case.layer_mapping_csv_path, layer_mapping_csv_path)
            csv_relative = _relative_posix(resolved_package_dir, layer_mapping_csv_path)
        if case.layer_mapping_json_path is not None:
            _copy_required_file(case.layer_mapping_json_path, layer_mapping_json_path)
            json_relative = _relative_posix(resolved_package_dir, layer_mapping_json_path)
        if case.aedt_material_context_path is not None:
            _copy_required_file(case.aedt_material_context_path, aedt_material_context_path)
            aedt_material_context_relative = _relative_posix(
                resolved_package_dir,
                aedt_material_context_path,
            )
        elif case.layer_mapping_json_path is not None:
            material_context = compile_aedt_material_context_from_mapping_path(
                case.layer_mapping_json_path,
                material_condition=_case_material_condition(case),
            )
            aedt_material_context_path.write_text(
                json.dumps(material_context.model_dump(mode="json"), indent=2),
                encoding="utf-8",
            )
            aedt_material_context_relative = _relative_posix(
                resolved_package_dir,
                aedt_material_context_path,
            )
        if case.q2d_conductors_csv_path is not None:
            _copy_required_file(case.q2d_conductors_csv_path, q2d_conductors_csv_path)
            q2d_csv_relative = _relative_posix(resolved_package_dir, q2d_conductors_csv_path)
        if case.q2d_conductors_json_path is not None:
            _validate_q2d_conductor_sidecar(case.q2d_conductors_json_path)
            _copy_required_file(case.q2d_conductors_json_path, q2d_conductors_json_path)
            q2d_json_relative = _relative_posix(resolved_package_dir, q2d_conductors_json_path)
        if case.q2d_cross_section_json_path is not None:
            payload = json.loads(Path(case.q2d_cross_section_json_path).read_text(encoding="utf-8"))
            validate_q2d_cross_section_payload(payload)
            _copy_required_file(case.q2d_cross_section_json_path, q2d_cross_section_path)
            q2d_cross_section_relative = _relative_posix(
                resolved_package_dir,
                q2d_cross_section_path,
            )

        case_rows.append(
            {
                "id": case.id,
                "gds": gds_relative,
                "tech": tech_relative,
                "control": control_relative,
                "layer_mapping": csv_relative,
                "layer_mapping_json": json_relative,
                "aedt_material_context": aedt_material_context_relative,
                "q2d_conductors": q2d_json_relative,
                "q2d_conductors_csv": q2d_csv_relative,
                "q2d_cross_section": q2d_cross_section_relative,
                "recipes": [
                    _recipe_manifest_row(case_id=case.id, recipe=recipe) for recipe in case.recipes
                ],
            }
        )

    hpc_resource = spec.resolved_hpc_resource()
    hpc_payload, acf_path, hpc_profile_path = write_aedt_hpc_artifacts(
        resolved_package_dir,
        hpc_dir,
        hpc_resource,
    )
    import_run_config_path, solve_run_config_path = write_aedt_run_config_artifacts(
        run_configs_dir,
        hpc_resource,
        point_local_q2d_sweep=_is_point_local_q2d_sweep(spec),
        import_run_profile=spec.import_run_profile,
        solve_run_profile=spec.solve_run_profile,
    )

    manifest = {
        "schema_version": 1,
        "project": {
            "name": spec.project_name,
            "path": str(project_path),
            "platform": spec.platform,
        },
        "execution": {
            "point_local_sweep": spec.point_local_sweep,
            "import_config": _relative_posix(resolved_package_dir, import_run_config_path),
            "solve_config": _relative_posix(resolved_package_dir, solve_run_config_path),
        },
        "runtime": spec.runtime.model_dump(mode="json"),
        "hpc": hpc_payload,
        "cases": case_rows,
    }
    manifest_path = resolved_package_dir / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    readme_path = resolved_package_dir / "README.md"
    readme_path.write_text(render_aedt_package_readme(spec, case_rows), encoding="utf-8")
    requirements_path = resolved_package_dir / "requirements-aedt.txt"
    requirements_path.write_text(render_aedt_requirements(), encoding="utf-8")

    python_script_path = scripts_dir / "run_aedt_native.py"
    bash_script_path = scripts_dir / "run_aedt_native.sh"
    powershell_script_path = scripts_dir / "run_aedt_native.ps1"
    _copy_runtime_bundle(scripts_dir / "runtime_bundle")
    python_script_path.write_text(render_runtime_runner(), encoding="utf-8")
    bash_script_path.write_text(render_shell_launcher(), encoding="utf-8")
    powershell_script_path.write_text(render_powershell_launcher(), encoding="utf-8")
    bash_script_path.chmod(0o755)

    return AedtNativePackageResult(
        package_dir=resolved_package_dir,
        manifest_path=manifest_path,
        readme_path=readme_path,
        requirements_path=requirements_path,
        gds_dir=gds_dir,
        tech_dir=tech_dir,
        layer_mapping_dir=layer_mapping_dir,
        metadata_dir=metadata_dir,
        hpc_dir=hpc_dir,
        run_configs_dir=run_configs_dir,
        acf_path=acf_path,
        hpc_profile_path=hpc_profile_path,
        import_run_config_path=import_run_config_path,
        solve_run_config_path=solve_run_config_path,
        scripts_dir=scripts_dir,
        python_script_path=python_script_path,
        bash_script_path=bash_script_path,
        powershell_script_path=powershell_script_path,
        project_path=project_path,
        platform=spec.platform,
        case_count=len(spec.cases),
        recipe_count=sum(len(case.recipes) for case in spec.cases),
    )


def prepare_aedt_native_sweep_handoff_package(
    sweep_paths: Any,
    *,
    points: Sequence[Any] | None = None,
    recipes: Sequence[AedtRecipeSpec],
    hpc_profile: AedtHpcProfileSpec | Mapping[str, Any] | None = None,
    hpc_resource: AedtHpcResourceSpec | None = None,
    package_dir: str | Path | None = None,
    project_name: str | None = None,
    project_path: str | Path | None = None,
    import_run_profile: AedtNativeRunProfileSpec | Mapping[str, Any] | None = None,
    solve_run_profile: AedtNativeRunProfileSpec | Mapping[str, Any] | None = None,
    platform: AedtPlatform = "ubuntu",
    overwrite: bool = True,
) -> AedtNativePackageResult:
    """Aggregate point-local GDS/TECH artifacts into one AEDT-native sweep package."""

    point_tuple = (
        tuple(points) if points is not None else tuple(getattr(sweep_paths.spec, "points", ()))
    )
    if not point_tuple:
        raise ValueError("AEDT native sweep packages require at least one sweep point")
    recipe_tuple = tuple(recipes)
    if not recipe_tuple:
        raise ValueError("AEDT native sweep packages require at least one recipe")

    cases = []
    for point in point_tuple:
        runtime_paths = point.runtime_paths
        source_dir = runtime_paths.hfss_gds_tech_dir
        cases.append(
            AedtNativeCaseSpec(
                id=point.point_slug,
                gds_path=_single_matching_file(source_dir, "*.gds", label=point.point_slug),
                tech_path=_single_matching_file(source_dir, "*.tech", label=point.point_slug),
                control_path=_optional_single_matching_file(
                    source_dir,
                    "*.xml",
                    label=point.point_slug,
                ),
                layer_mapping_csv_path=_optional_single_matching_file(
                    source_dir,
                    "*_layer_mapping.csv",
                    label=point.point_slug,
                ),
                layer_mapping_json_path=_optional_single_matching_file(
                    source_dir,
                    "*_layer_mapping.json",
                    label=point.point_slug,
                ),
                q2d_conductors_csv_path=_optional_single_matching_file(
                    source_dir,
                    "*_q2d_conductors.csv",
                    label=point.point_slug,
                ),
                q2d_conductors_json_path=_optional_single_matching_file(
                    source_dir,
                    "*_q2d_conductors.json",
                    label=point.point_slug,
                ),
                recipes=recipe_tuple,
            )
        )
    _write_aedt_sweep_point_tables(sweep_paths, point_tuple)

    spec = AedtNativePackageSpec(
        project_name=project_name or sweep_paths.sweep_id,
        project_path=Path(project_path) if project_path is not None else None,
        platform=platform,
        hpc_profile=(
            hpc_profile
            if isinstance(hpc_profile, AedtHpcProfileSpec)
            else AedtHpcProfileSpec.model_validate(hpc_profile)
            if hpc_profile is not None
            else AedtHpcProfileSpec()
        ),
        hpc_resource=hpc_resource,
        import_run_profile=(
            import_run_profile
            if isinstance(import_run_profile, AedtNativeRunProfileSpec)
            else AedtNativeRunProfileSpec.model_validate(import_run_profile)
            if import_run_profile is not None
            else None
        ),
        solve_run_profile=(
            solve_run_profile
            if isinstance(solve_run_profile, AedtNativeRunProfileSpec)
            else AedtNativeRunProfileSpec.model_validate(solve_run_profile)
            if solve_run_profile is not None
            else None
        ),
        point_local_sweep=True,
        cases=tuple(cases),
    )
    resolved_package_dir = (
        Path(package_dir) if package_dir is not None else sweep_paths.aedt_native_dir
    )
    result = prepare_aedt_native_handoff_package(
        spec,
        package_dir=resolved_package_dir,
        overwrite=overwrite,
    )
    _copy_required_file(sweep_paths.points_csv_path, result.package_dir / "points.csv")
    _copy_required_file(sweep_paths.points_json_path, result.package_dir / "points.json")
    return result


def package_aedt_native_handoff(
    package: AedtNativePackageResult | str | Path,
    *,
    archive_path: str | Path | None = None,
    overwrite: bool = True,
) -> AedtNativeHandoffArchiveResult:
    """Create a tar.gz archive for an AEDT-native package."""

    package_dir = (
        package.package_dir if isinstance(package, AedtNativePackageResult) else Path(package)
    )
    if archive_path is None:
        if isinstance(package, AedtNativePackageResult):
            resolved_archive_path = (
                package.package_dir.parent / f"{package.package_dir.name}.tar.gz"
            )
        else:
            raise ValueError("archive_path is required when packaging from a directory path")
    else:
        resolved_archive_path = Path(archive_path)

    _validate_required_file(package_dir / "manifest.yaml", "AEDT native manifest")
    _validate_required_file(package_dir / "requirements-aedt.txt", "AEDT Python requirements")
    _validate_required_file(package_dir / "scripts" / "run_aedt_native.py", "PyAEDT runner")
    _validate_runtime_bundle_files(package_dir / "scripts" / "runtime_bundle")
    _validate_required_file(package_dir / "scripts" / "run_aedt_native.sh", "shell runner")
    _validate_required_file(package_dir / "scripts" / "run_aedt_native.ps1", "PowerShell runner")

    resolved_archive_path.parent.mkdir(parents=True, exist_ok=True)
    if resolved_archive_path.exists() and not overwrite:
        raise FileExistsError(resolved_archive_path)

    for directory_name in ("logs", "points", "results"):
        (package_dir / directory_name).mkdir(parents=True, exist_ok=True)

    included: list[str] = []
    with tarfile.open(resolved_archive_path, "w:gz") as archive:
        _add_aedt_archive_tree(archive, package_dir, package_dir.name, included)
    return AedtNativeHandoffArchiveResult(
        archive_path=resolved_archive_path.resolve(),
        included=tuple(dict.fromkeys(included)),
    )


def _is_point_local_q2d_sweep(spec: AedtNativePackageSpec) -> bool:
    if not spec.point_local_sweep:
        return False
    recipe_types = {recipe.type for case in spec.cases for recipe in case.recipes}
    if recipe_types and recipe_types <= {"q2d_extraction"}:
        return True
    if "q2d_extraction" in recipe_types:
        raise ValueError(
            "AEDT point-local parallel sweep currently supports q2d_extraction recipes only; "
            f"got mixed recipe types: {sorted(recipe_types)}"
        )
    return False


def _write_aedt_sweep_point_tables(sweep_paths: Any, points: Sequence[Any]) -> None:
    metadata_dir = Path(sweep_paths.metadata_dir)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    parameter_keys: set[str] = set()
    for point in points:
        parameters = {
            f"parameter_{safe_aedt_name(str(key))}": value
            for key, value in dict(getattr(point, "parameters", {}) or {}).items()
        }
        parameter_keys.update(parameters)
        rows.append(
            {
                "point_slug": point.point_slug,
                "run_id": getattr(point.runtime_paths, "run_id", point.point_slug),
                **parameters,
            }
        )
    fieldnames = ["point_slug", "run_id", *sorted(parameter_keys)]
    csv_path = Path(getattr(sweep_paths, "points_csv_path", metadata_dir / "points.csv"))
    json_path = Path(getattr(sweep_paths, "points_json_path", metadata_dir / "points.json"))
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    json_path.write_text(
        json.dumps({"schema_version": "aedt-q2d-sweep-points.v1", "points": rows}, indent=2),
        encoding="utf-8",
    )


def _recipe_manifest_row(*, case_id: str, recipe: AedtRecipeSpec) -> dict[str, Any]:
    row = recipe.model_dump(mode="json")
    row["design_name"] = recipe.resolved_design_name(case_id)
    return row


def _case_material_condition(case: AedtNativeCaseSpec) -> str:
    conditions = {recipe.material_policy.material_condition for recipe in case.recipes}
    if len(conditions) != 1:
        raise ValueError(
            f"Case {case.id!r} recipes use multiple material conditions: {sorted(conditions)}"
        )
    return next(iter(conditions))


def _copy_required_file(source: str | Path, destination: Path) -> None:
    source_path = Path(source)
    _validate_required_file(source_path, "AEDT package source file")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source_path.resolve() == destination.resolve():
        return
    shutil.copy2(source_path, destination)


def _copy_runtime_bundle(destination: Path) -> None:
    source = files("orpen_sc_pdk.simulation.aedt.runtime_bundle")
    if destination.exists():
        shutil.rmtree(destination)
    with as_file(source) as source_path:
        shutil.copytree(
            source_path,
            destination,
            ignore=shutil.ignore_patterns(*_ARCHIVE_SKIP_NAMES, "*.pyc", "*.pyo"),
        )


def _candidate_control_path(tech_path: Path) -> Path | None:
    control_path = Path(tech_path).with_suffix(".xml")
    return control_path if control_path.is_file() else None


def _validate_required_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Missing {label}: {path}")


def _validate_runtime_bundle_files(runtime_bundle_dir: Path) -> None:
    for relative in _REQUIRED_RUNTIME_BUNDLE_FILES:
        _validate_required_file(
            runtime_bundle_dir / relative,
            f"PyAEDT runtime bundle file {relative}",
        )


def _validate_q2d_conductor_sidecar(path: Path) -> None:
    _validate_required_file(path, "Q2D conductor sidecar")
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("conductors") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError(f"Q2D conductor sidecar must contain a conductor row list: {path}")

    marker_names: set[str] = set()
    assignment_types: dict[str, str] = {}
    conductor_types: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"Q2D conductor sidecar rows must be objects: {path}")
        marker_name = str(row.get("name") or "").strip()
        if not marker_name:
            raise ValueError("Q2D conductor sidecar rows require marker name")
        if marker_name in marker_names:
            raise ValueError(f"Duplicate Q2D conductor marker name: {marker_name!r}")
        marker_names.add(marker_name)

        info = Q2dConductorPortInfo(
            conductor_type=row.get("conductor_type"),
            assignment_name=row.get("assignment_name"),
        )
        conductor_type = info.conductor_type.value
        assignment_name = str(info.assignment_name)
        previous_type = assignment_types.get(assignment_name)
        if previous_type is not None and previous_type != conductor_type:
            raise ValueError(
                f"Q2D assignment_name {assignment_name!r} is used with both "
                f"{previous_type!r} and {conductor_type!r}."
            )
        assignment_types[assignment_name] = conductor_type
        conductor_types.add(conductor_type)

    if Q2dConductorType.SIGNAL_LINE.value not in conductor_types:
        raise ValueError("Q2D conductor sidecar requires at least one Signal Line assignment.")
    if Q2dConductorType.REFERENCE_GROUND.value not in conductor_types:
        raise ValueError("Q2D conductor sidecar requires at least one Reference Ground assignment.")


def _validate_q2d_semantic_case_sidecars(case: AedtNativeCaseSpec) -> None:
    if not any(
        recipe.type == "q2d_extraction" and recipe.q2d_geometry_mode == "semantic_cross_section"
        for recipe in case.recipes
    ):
        return
    if case.q2d_cross_section_json_path is None:
        raise ValueError(
            f"case {case.id!r} semantic_cross_section requires q2d_cross_section_json_path"
        )
    payload = json.loads(Path(case.q2d_cross_section_json_path).read_text(encoding="utf-8"))
    validate_q2d_cross_section_payload(payload)


def _relative_posix(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _single_matching_file(directory: Path, pattern: str, *, label: str) -> Path:
    matches = sorted(directory.glob(pattern))
    if len(matches) != 1:
        raise FileNotFoundError(
            f"Expected exactly one {pattern!r} file for AEDT sweep point {label!r}; "
            f"found {len(matches)} in {directory}"
        )
    return matches[0]


def _optional_single_matching_file(directory: Path, pattern: str, *, label: str) -> Path | None:
    matches = sorted(directory.glob(pattern))
    if len(matches) > 1:
        raise FileNotFoundError(
            f"Expected at most one {pattern!r} file for AEDT sweep point {label!r}; "
            f"found {len(matches)} in {directory}"
        )
    return matches[0] if matches else None


def _add_aedt_archive_file(
    archive: tarfile.TarFile,
    path: Path,
    arcname: str,
    included: list[str],
) -> None:
    archive.add(path, arcname=arcname, recursive=False)
    included.append(arcname)


def _add_aedt_archive_tree(
    archive: tarfile.TarFile,
    directory: Path,
    arcname: str,
    included: list[str],
) -> None:
    archive.add(
        directory,
        arcname=arcname,
        recursive=True,
        filter=lambda member: _filter_archive_member(member, included),
    )


def _add_archive_directory_entry(
    archive: tarfile.TarFile,
    directory: Path,
    arcname: str,
    included: list[str],
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    archive.add(directory, arcname=arcname, recursive=False)
    included.append(arcname.rstrip("/") + "/")


def _filter_archive_member(member: tarfile.TarInfo, included: list[str]) -> tarfile.TarInfo | None:
    path = Path(member.name)
    if any(part in _ARCHIVE_SKIP_NAMES for part in path.parts):
        return None
    if member.name.endswith((".pyc", ".tar.gz", ".tar.zst", ".tgz")):
        return None
    if member.name.endswith((".aedt", ".aedt.lock")):
        return None
    if any(part.endswith(".aedtresults") for part in path.parts):
        return None
    if any(part in {"logs", "points", "results"} for part in path.parts) and not member.isdir():
        return None
    included.append(member.name if not member.isdir() else member.name.rstrip("/") + "/")
    return member


__all__ = [
    "package_aedt_native_handoff",
    "prepare_aedt_native_handoff_package",
    "prepare_aedt_native_sweep_handoff_package",
    "write_aedt_run_config_artifacts",
]
