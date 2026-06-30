"""Host-side AEDT handoff package writer.

This module owns manifest layout, source-artifact copying, sidecar validation,
run-config writing, generated launcher placement, and archive packaging. It does
not define package models, material compilation, or template text.
"""

from __future__ import annotations

import csv
import json
import shutil
import tarfile
from collections.abc import Mapping, Sequence
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
from orpen_sc_pdk.simulation.aedt.templates import (
    render_aedt_package_readme,
    render_aedt_requirements,
    render_powershell_launcher,
    render_q2d_runner_script,
    render_runtime_runner,
    render_shell_launcher,
)

_ARCHIVE_SKIP_NAMES = {".DS_Store", "__pycache__"}


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
    import_profile = import_run_profile or AedtNativeRunProfileSpec(
        mode="import",
        parallel=point_local_q2d_sweep,
        max_workers=resource.max_workers if point_local_q2d_sweep else None,
        num_cores=resource.num_cores if point_local_q2d_sweep else None,
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
    """Write a generic AEDT-native package with manifest and PyAEDT scripts."""

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
        gds_dir,
        tech_dir,
        layer_mapping_dir,
        metadata_dir,
        hpc_dir,
        run_configs_dir,
        scripts_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    project_path = spec.project_path or (resolved_package_dir / f"{spec.project_name}.aedt")
    case_rows = []
    for case in spec.cases:
        _validate_native_2d_case_sidecars(case)
        gds_path = gds_dir / f"{case.id}.gds"
        tech_path = tech_dir / f"{case.id}.tech"
        control_path = tech_dir / f"{case.id}.xml"
        layer_mapping_csv_path = layer_mapping_dir / f"{case.id}_layer_mapping.csv"
        layer_mapping_json_path = layer_mapping_dir / f"{case.id}_layer_mapping.json"
        aedt_material_context_path = metadata_dir / f"{case.id}_aedt_material_context.json"
        source_metadata_path = metadata_dir / f"{case.id}_cross_section.json"
        q2d_conductors_csv_path = metadata_dir / f"{case.id}_q2d_conductors.csv"
        q2d_conductors_json_path = metadata_dir / f"{case.id}_q2d_conductors.json"
        _copy_required_file(case.gds_path, gds_path)
        _copy_required_file(case.tech_path, tech_path)
        control_relative = None
        csv_relative = None
        json_relative = None
        aedt_material_context_relative = None
        source_metadata_relative = None
        q2d_csv_relative = None
        q2d_json_relative = None
        source_control_path = case.control_path or _candidate_control_path(case.tech_path)
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
        if case.source_metadata_path is not None:
            _copy_required_file(case.source_metadata_path, source_metadata_path)
            source_metadata_relative = _relative_posix(resolved_package_dir, source_metadata_path)
        if case.q2d_conductors_csv_path is not None:
            _copy_required_file(case.q2d_conductors_csv_path, q2d_conductors_csv_path)
            q2d_csv_relative = _relative_posix(resolved_package_dir, q2d_conductors_csv_path)
        if case.q2d_conductors_json_path is not None:
            _validate_q2d_conductor_sidecar(case.q2d_conductors_json_path)
            _copy_required_file(case.q2d_conductors_json_path, q2d_conductors_json_path)
            q2d_json_relative = _relative_posix(resolved_package_dir, q2d_conductors_json_path)

        case_rows.append(
            {
                "id": case.id,
                "gds": _relative_posix(resolved_package_dir, gds_path),
                "tech": _relative_posix(resolved_package_dir, tech_path),
                "control": control_relative,
                "layer_mapping": csv_relative,
                "layer_mapping_json": json_relative,
                "aedt_material_context": aedt_material_context_relative,
                "source_metadata": source_metadata_relative,
                "q2d_conductors": q2d_json_relative,
                "q2d_conductors_csv": q2d_csv_relative,
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
    q2d_script_path = scripts_dir / "run_aedt_q2d_cross_section.py"
    bash_script_path = scripts_dir / "run_aedt_native.sh"
    powershell_script_path = scripts_dir / "run_aedt_native.ps1"
    python_script_path.write_text(render_runtime_runner(), encoding="utf-8")
    q2d_script_path.write_text(render_q2d_runner_script(), encoding="utf-8")
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
        q2d_script_path=q2d_script_path,
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
                source_metadata_path=_optional_single_matching_file(
                    source_dir,
                    "*_cross_section.json",
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
    return prepare_aedt_native_handoff_package(
        spec,
        package_dir=resolved_package_dir,
        overwrite=overwrite,
    )


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
    _validate_required_file(
        package_dir / "scripts" / "run_aedt_q2d_cross_section.py",
        "Q2D PyAEDT runner",
    )
    _validate_required_file(package_dir / "scripts" / "run_aedt_native.sh", "shell runner")
    _validate_required_file(package_dir / "scripts" / "run_aedt_native.ps1", "PowerShell runner")

    resolved_archive_path.parent.mkdir(parents=True, exist_ok=True)
    if resolved_archive_path.exists() and not overwrite:
        raise FileExistsError(resolved_archive_path)

    included: list[str] = []
    archive_root = _standard_aedt_run_archive_root(package_dir)
    with tarfile.open(resolved_archive_path, "w:gz") as archive:
        if archive_root is None:
            _add_aedt_archive_tree(archive, package_dir, package_dir.name, included)
        else:
            root_dir = archive_root
            root_name = root_dir.name
            _add_archive_directory_entry(archive, root_dir, root_name, included)
            for file_name in ("manifest.json", "points.csv", "points.json", "README.md"):
                path = root_dir / file_name
                if path.is_file():
                    _add_aedt_archive_file(archive, path, f"{root_name}/{file_name}", included)
            metadata_dir = root_dir / "metadata"
            if metadata_dir.is_dir():
                _add_aedt_archive_tree(archive, metadata_dir, f"{root_name}/metadata", included)
            else:
                _add_archive_directory_entry(
                    archive,
                    metadata_dir,
                    f"{root_name}/metadata",
                    included,
                )
            _add_aedt_archive_tree(
                archive,
                package_dir,
                f"{root_name}/exports/aedt_native",
                included,
            )
            for directory_name in ("logs", "results"):
                directory = root_dir / directory_name
                _add_archive_directory_entry(
                    archive,
                    directory,
                    f"{root_name}/{directory_name}",
                    included,
                )
                _add_archive_directory_entry(
                    archive,
                    directory / "aedt",
                    f"{root_name}/{directory_name}/aedt",
                    included,
                )
    return AedtNativeHandoffArchiveResult(
        archive_path=resolved_archive_path.resolve(),
        included=tuple(dict.fromkeys(included)),
    )


def _is_point_local_q2d_sweep(spec: AedtNativePackageSpec) -> bool:
    if not spec.point_local_sweep:
        return False
    return any(recipe.type == "q2d_extraction" for case in spec.cases for recipe in case.recipes)


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


def _candidate_control_path(tech_path: Path) -> Path | None:
    control_path = Path(tech_path).with_suffix(".xml")
    return control_path if control_path.is_file() else None


def _validate_required_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Missing {label}: {path}")


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


def _validate_native_2d_case_sidecars(case: AedtNativeCaseSpec) -> None:
    if not any(
        recipe.type == "q2d_extraction" and recipe.q2d_geometry_mode == "native_2d"
        for recipe in case.recipes
    ):
        return
    if case.source_metadata_path is None:
        raise ValueError(f"case {case.id!r} native_2d requires source_metadata_path")
    if case.layer_mapping_json_path is None:
        raise ValueError(f"case {case.id!r} native_2d requires layer_mapping_json_path")
    if case.q2d_conductors_json_path is None:
        raise ValueError(f"case {case.id!r} native_2d requires q2d_conductors_json_path")
    source_metadata = json.loads(Path(case.source_metadata_path).read_text(encoding="utf-8"))
    mapping_payload = json.loads(Path(case.layer_mapping_json_path).read_text(encoding="utf-8"))
    conductor_payload = json.loads(Path(case.q2d_conductors_json_path).read_text(encoding="utf-8"))
    _validate_native_2d_source_metadata(case.id, source_metadata)
    _validate_native_2d_layer_mapping(case.id, mapping_payload)
    _validate_native_2d_conductors(case.id, conductor_payload)


def _validate_native_2d_source_metadata(case_id: str, payload: Mapping[str, Any]) -> None:
    parameters = dict(payload.get("parameters") or {})
    for key in (
        "case_kind",
        "cpw_left_gap_um",
        "cpw_width_um",
        "cpw_right_gap_um",
        "flip_chip_gap_um",
        "horizontal_offset_um",
    ):
        if key not in parameters and key in payload:
            parameters[key] = payload[key]
    case_kind = str(parameters.get("case_kind") or payload.get("case_kind") or "")
    if "flip_chip" not in case_kind:
        raise ValueError(
            f"case {case_id!r} native_2d requires flip-chip source_metadata; "
            f"got case_kind={case_kind!r}"
        )
    positive = ("cpw_left_gap_um", "cpw_width_um", "cpw_right_gap_um", "flip_chip_gap_um")
    required = (*positive, "horizontal_offset_um")
    missing = [key for key in required if key not in parameters]
    if missing:
        raise ValueError(f"case {case_id!r} native_2d source_metadata missing {missing}")
    for key in required:
        value = _required_float(parameters, key, label=f"case {case_id!r} source_metadata")
        if key in positive and value <= 0.0:
            raise ValueError(f"case {case_id!r} native_2d parameter {key!r} must be positive")


def _validate_native_2d_layer_mapping(case_id: str, payload: Mapping[str, Any]) -> None:
    rows = payload.get("layers") or payload.get("gds_import_layers") or []
    rows_by_name = {
        str(row.get("layer_name") or "").strip(): row for row in rows if isinstance(row, Mapping)
    }
    for layer_name in ("D0_SUBSTRATE", "D1_SUBSTRATE", "D0_TOP_M1", "D1_BOTTOM_M1"):
        row = rows_by_name.get(layer_name)
        if row is None:
            raise ValueError(f"case {case_id!r} native_2d missing layer {layer_name!r}")
        _required_float(row, "bbox_ymin_um", label=layer_name)
        _required_float(row, "bbox_ymax_um", label=layer_name)
        _required_float(row, "zmin_um", label=layer_name)
        thickness = _required_float(row, "thickness_um", label=layer_name)
        if thickness <= 0.0:
            raise ValueError(f"case {case_id!r} native_2d layer {layer_name!r} thickness <= 0")


def _validate_native_2d_conductors(case_id: str, payload: Any) -> None:
    rows = payload.get("conductors") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError(f"case {case_id!r} native_2d q2d_conductors must be a row list")
    grouped: dict[tuple[str, str, str], list[Mapping[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError(f"case {case_id!r} native_2d q2d_conductors rows must be objects")
        key = (
            str(row.get("assignment_name") or "").strip(),
            str(row.get("conductor_type") or "").strip(),
            str(row.get("layer_stack_layer_name") or "").strip(),
        )
        grouped.setdefault(key, []).append(row)
    for layer_name, assignment_name in (
        ("D0_TOP_M1", "Trace1"),
        ("D1_BOTTOM_M1", "Trace2"),
    ):
        signal_rows = grouped.get((assignment_name, "Signal Line", layer_name), [])
        if len(signal_rows) != 1:
            raise ValueError(
                f"case {case_id!r} native_2d requires exactly one {assignment_name} "
                f"Signal Line marker on {layer_name}; got {len(signal_rows)}"
            )
        _required_float(signal_rows[0], "center_y_um", label=assignment_name)
        ground_rows = grouped.get(("Ground", "Reference Ground", layer_name), [])
        if len(ground_rows) < 2:
            raise ValueError(
                f"case {case_id!r} native_2d requires at least two Ground markers "
                f"on {layer_name}; got {len(ground_rows)}"
            )


def _required_float(payload: Mapping[str, Any], key: str, *, label: str) -> float:
    value = payload.get(key)
    if value in (None, ""):
        raise ValueError(f"{label} requires numeric field {key!r}")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} field {key!r} must be numeric; got {value!r}") from exc


def _relative_posix(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _standard_aedt_run_archive_root(package_dir: Path) -> Path | None:
    resolved = package_dir.resolve()
    if resolved.name == "aedt_native" and resolved.parent.name == "exports":
        return resolved.parent.parent
    return None


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
    if any(part in {"logs", "results"} for part in path.parts) and not member.isdir():
        return None
    included.append(member.name if not member.isdir() else member.name.rstrip("/") + "/")
    return member


__all__ = [
    "package_aedt_native_handoff",
    "prepare_aedt_native_handoff_package",
    "prepare_aedt_native_sweep_handoff_package",
    "write_aedt_run_config_artifacts",
]
