"""Build the public D3 same-face ground-clearance Q2D AEDT package.

This script owns the fixed, publication-safe 12-case sweep requested by the
Workbench handoff. It writes semantic cross-sections and package metadata only;
AEDT owns all matrices, solver logs, and completion evidence. Existing run
roots require explicit ``--overwrite``, and overwrite refreshes generated
package files without altering existing ``results/``, ``logs/``, or ``points/``
runtime trees.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import yaml

from orpen_sc_pdk.simulation.aedt.models import (
    AedtNativeCaseSpec,
    AedtNativePackageResult,
    AedtNativePackageSpec,
    AedtQ2dSetupSpec,
    AedtRecipeSpec,
)
from orpen_sc_pdk.simulation.aedt.package import prepare_aedt_native_handoff_package
from orpen_sc_pdk.simulation.aedt.q2d import (
    make_q2d_same_face_single_trace_cross_section,
    make_q2d_same_face_two_trace_cross_section,
    validate_q2d_same_face_upper_ground_clearance_payload,
    validate_q2d_single_reference_upper_ground_clearance_payload,
    write_q2d_cross_section_payload,
)

PROJECT_NAME = "d3_same_face_ground_clearance_q2d"
RECIPE_ID = "q2d"
TRACE_WIDTH_UM = 5.0
TRACE_GAP_UM = 7.5
INTER_TRACE_GROUND_WIDTHS_UM = (3.8, 4.65, 5.5)
UPPER_GROUND_CLEARANCE_WIDTHS_UM = (60.0, 120.0, 240.0)
FLIP_CHIP_GAP_HEIGHT_UM = 7.0
D0_DIE_THICKNESS_UM = 500.0
D1_DIE_THICKNESS_UM = 500.0
AIR_HEIGHT_UM = 200.0
GROUND_WIDTH_UM = 150.0
METAL_THICKNESS_UM = 0.2
ADAPTIVE_FREQUENCY = "6GHz"
PROTECTED_RUNTIME_DIRS = ("results", "logs", "points")


def _number_slug(value: float, *, places: int) -> str:
    return f"{float(value):.{places}f}".replace(".", "p")


def _pair_case_id(inter_trace_ground_width_um: float, clearance_um: float) -> str:
    return (
        "coupled_pair__d_"
        f"{_number_slug(inter_trace_ground_width_um, places=2)}um__"
        f"clearance_{int(clearance_um):03d}um"
    )


def _single_case_id(clearance_um: float) -> str:
    return f"single_reference__clearance_{int(clearance_um):03d}um"


def _point_row(
    *,
    run_id: str,
    case_id: str,
    case_role: str,
    clearance_um: float,
    inter_trace_ground_width_um: float | None,
) -> dict[str, Any]:
    return {
        "point_slug": case_id,
        "run_id": run_id,
        "parameter_id": case_id,
        "parameter_case_role": case_role,
        "parameter_trace_width_um": TRACE_WIDTH_UM,
        "parameter_trace_gap_um": TRACE_GAP_UM,
        "parameter_inter_trace_ground_width_um": inter_trace_ground_width_um,
        "parameter_upper_ground_clearance_width_um": clearance_um,
        "parameter_flip_chip_gap_height_um": FLIP_CHIP_GAP_HEIGHT_UM,
        "parameter_d0_die_thickness_um": D0_DIE_THICKNESS_UM,
        "parameter_d1_die_thickness_um": D1_DIE_THICKNESS_UM,
        "parameter_air_height_um": AIR_HEIGHT_UM,
        "parameter_ground_width_um": GROUND_WIDTH_UM,
        "parameter_metal_thickness_um": METAL_THICKNESS_UM,
        "parameter_adaptive_frequency": ADAPTIVE_FREQUENCY,
    }


def public_sweep_rows(run_id: str) -> tuple[dict[str, Any], ...]:
    """Return the exact public nine-pair plus three-reference sweep ledger."""

    rows = [
        _point_row(
            run_id=run_id,
            case_id=_pair_case_id(inter_ground_um, clearance_um),
            case_role="coupled_pair",
            clearance_um=clearance_um,
            inter_trace_ground_width_um=inter_ground_um,
        )
        for inter_ground_um in INTER_TRACE_GROUND_WIDTHS_UM
        for clearance_um in UPPER_GROUND_CLEARANCE_WIDTHS_UM
    ]
    rows.extend(
        _point_row(
            run_id=run_id,
            case_id=_single_case_id(clearance_um),
            case_role="single_reference",
            clearance_um=clearance_um,
            inter_trace_ground_width_um=None,
        )
        for clearance_um in UPPER_GROUND_CLEARANCE_WIDTHS_UM
    )
    return tuple(rows)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _write_point_ledgers(run_root: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    payload = {
        "schema_version": "aedt-q2d-sweep-points.v1",
        "sweep_contract": "d3-same-face-ground-clearance-q2d.v1",
        "points": [dict(row) for row in rows],
    }
    _atomic_write_text(run_root / "points.json", json.dumps(payload, indent=2) + "\n")

    fieldnames = list(rows[0])
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    _atomic_write_text(run_root / "points.csv", stream.getvalue())


def _runtime_tree_inventory(run_root: Path) -> dict[str, list[dict[str, Any]]]:
    inventory: dict[str, list[dict[str, Any]]] = {}
    for directory_name in PROTECTED_RUNTIME_DIRS:
        directory = run_root / directory_name
        inventory[directory_name] = (
            [
                {
                    "path": path.relative_to(directory).as_posix(),
                    "size_bytes": path.stat().st_size,
                }
                for path in sorted(directory.rglob("*"))
                if path.is_file()
            ]
            if directory.is_dir()
            else []
        )
    return inventory


def _validate_overwrite_compatibility(
    run_root: Path,
    rows: Sequence[Mapping[str, Any]],
) -> None:
    expected_by_id = {str(row["point_slug"]): dict(row) for row in rows}
    manifest_path = run_root / "manifest.yaml"
    if manifest_path.is_file():
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        project_name = (
            manifest.get("project", {}).get("name") if isinstance(manifest, dict) else None
        )
        if project_name != PROJECT_NAME:
            raise ValueError(
                "--overwrite may update only an existing "
                f"{PROJECT_NAME!r} package, got {project_name!r}"
            )

    points_path = run_root / "points.json"
    if points_path.is_file():
        existing = json.loads(points_path.read_text(encoding="utf-8"))
        existing_rows = existing.get("points") if isinstance(existing, dict) else None
        if not isinstance(existing_rows, list):
            raise ValueError(f"Existing Q2D point ledger is invalid: {points_path}")
        for row in existing_rows:
            case_id = str(row.get("point_slug") or "")
            if case_id not in expected_by_id:
                raise ValueError(f"Existing point {case_id!r} is outside the fixed public sweep")
            expected = expected_by_id[case_id]
            comparable = {key: value for key, value in row.items() if key != "run_id"}
            expected_comparable = {key: value for key, value in expected.items() if key != "run_id"}
            if comparable != expected_comparable:
                raise ValueError(
                    f"Existing point parameters do not match the fixed sweep: {case_id}"
                )

    points_dir = run_root / "points"
    if points_dir.is_dir():
        unknown = sorted(
            path.name
            for path in points_dir.iterdir()
            if path.is_dir() and path.name not in expected_by_id
        )
        if unknown:
            raise ValueError(
                f"Existing point-local results are outside the fixed public sweep: {unknown}"
            )


def _sha256_record(root: Path, path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(root).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _validate_written_package(
    result: AedtNativePackageResult,
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    manifest = yaml.safe_load(result.manifest_path.read_text(encoding="utf-8"))
    expected_ids = [str(row["point_slug"]) for row in rows]
    case_rows = manifest.get("cases") if isinstance(manifest, dict) else None
    if not isinstance(case_rows, list) or [case.get("id") for case in case_rows] != expected_ids:
        raise RuntimeError("Written AEDT manifest case order does not match points.json")
    if manifest.get("execution", {}).get("point_local_sweep") is not True:
        raise RuntimeError("Written AEDT manifest must enable point_local_sweep")

    topology_counts = {"coupled_pair": 0, "single_reference": 0}
    for case, point in zip(case_rows, rows, strict=True):
        recipes = case.get("recipes")
        if not isinstance(recipes, list) or len(recipes) != 1:
            raise RuntimeError(f"AEDT case {case.get('id')!r} must contain one recipe")
        recipe = recipes[0]
        expected_recipe = {
            "id": RECIPE_ID,
            "type": "q2d_extraction",
            "q2d_geometry_mode": "semantic_cross_section",
            "section_plane": "XY",
            "matrix_problem_types": ["CG", "RL"],
            "matrix_types": ["Maxwell"],
        }
        for field, value in expected_recipe.items():
            if recipe.get(field) != value:
                raise RuntimeError(
                    f"AEDT case {case.get('id')!r} has unexpected recipe {field}: "
                    f"{recipe.get(field)!r}"
                )
        if (recipe.get("q2d_setup") or {}).get("adaptive_frequency") != ADAPTIVE_FREQUENCY:
            raise RuntimeError(f"AEDT case {case.get('id')!r} does not use {ADAPTIVE_FREQUENCY}")

        sidecar = result.package_dir / str(case.get("q2d_cross_section") or "")
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        role = str(point["parameter_case_role"])
        if role == "coupled_pair":
            topology = validate_q2d_same_face_upper_ground_clearance_payload(payload)
        elif role == "single_reference":
            topology = validate_q2d_single_reference_upper_ground_clearance_payload(payload)
        else:
            raise RuntimeError(f"Unsupported public sweep case role: {role!r}")
        if (
            topology["upper_ground_clearance_width_um"]
            != point["parameter_upper_ground_clearance_width_um"]
        ):
            raise RuntimeError(f"Clearance provenance mismatch for AEDT case {case.get('id')!r}")
        topology_counts[role] += 1
    return {
        "manifest_schema_version": manifest.get("schema_version"),
        "case_ids": expected_ids,
        "topology_counts": topology_counts,
    }


def _write_package_audit(
    result: AedtNativePackageResult,
    rows: Sequence[Mapping[str, Any]],
    manifest_summary: Mapping[str, Any],
    *,
    overwrite: bool,
    protected_before: Mapping[str, Any],
    protected_after: Mapping[str, Any],
) -> Path:
    audit_path = result.metadata_dir / "d3_same_face_ground_clearance_package_audit.json"
    payload = {
        "schema_version": "d3-same-face-ground-clearance-q2d-package-audit.v1",
        "status": "package_ready_solver_pending",
        "project_name": PROJECT_NAME,
        "case_count": len(rows),
        "recipe_count": result.recipe_count,
        "case_roles": manifest_summary["topology_counts"],
        "manifest": {
            **_sha256_record(result.package_dir, result.manifest_path),
            "schema_version": manifest_summary["manifest_schema_version"],
            "point_local_sweep": True,
            "case_ids": manifest_summary["case_ids"],
        },
        "point_ledgers": [
            _sha256_record(result.package_dir, result.package_dir / "points.json"),
            _sha256_record(result.package_dir, result.package_dir / "points.csv"),
        ],
        "fixed_public_stack_um": {
            "flip_chip_gap": FLIP_CHIP_GAP_HEIGHT_UM,
            "d0_silicon": D0_DIE_THICKNESS_UM,
            "d1_silicon": D1_DIE_THICKNESS_UM,
            "air_each_side": AIR_HEIGHT_UM,
            "side_ground": GROUND_WIDTH_UM,
            "metal": METAL_THICKNESS_UM,
        },
        "fixed_public_cpw_um": {
            "trace_width": TRACE_WIDTH_UM,
            "trace_gap": TRACE_GAP_UM,
            "coupled_pair_inter_trace_ground_widths": list(INTER_TRACE_GROUND_WIDTHS_UM),
            "upper_ground_clearance_widths": list(UPPER_GROUND_CLEARANCE_WIDTHS_UM),
        },
        "adaptive_frequency": ADAPTIVE_FREQUENCY,
        "matrix_contract": {
            "problem_types": ["CG", "RL"],
            "matrix_types": ["Maxwell"],
            "coupled_pair_shape": [2, 2],
            "single_reference_shape": [1, 1],
            "solver_results_generated": False,
        },
        "runtime_capability": {
            "minimum_signal_line_assignments": 1,
            "single_terminal_semantic_plan_supported": True,
        },
        "overwrite": {
            "requested": overwrite,
            "protected_directories": list(PROTECTED_RUNTIME_DIRS),
            "protected_inventory_unchanged": protected_before == protected_after,
            "protected_file_counts": {
                name: len(protected_after[name]) for name in PROTECTED_RUNTIME_DIRS
            },
        },
    }
    _atomic_write_text(audit_path, json.dumps(payload, indent=2) + "\n")
    return audit_path


def build_package(
    run_root: str | Path,
    *,
    overwrite: bool = False,
) -> AedtNativePackageResult:
    """Write the exact public D3 same-face Q2D package at ``run_root``."""

    resolved_run_root = Path(run_root)
    if resolved_run_root.exists() and not overwrite:
        raise FileExistsError(resolved_run_root)

    rows = public_sweep_rows(resolved_run_root.name)
    if resolved_run_root.exists():
        _validate_overwrite_compatibility(resolved_run_root, rows)
    protected_before = _runtime_tree_inventory(resolved_run_root)

    recipe = AedtRecipeSpec(
        id=RECIPE_ID,
        type="q2d_extraction",
        q2d_geometry_mode="semantic_cross_section",
        section_plane="XY",
        matrix_problem_types=("CG", "RL"),
        matrix_types=("Maxwell",),
        q2d_setup=AedtQ2dSetupSpec(adaptive_frequency=ADAPTIVE_FREQUENCY),
    )

    with TemporaryDirectory(prefix="orpen-d3-q2d-") as temporary_directory:
        source_dir = Path(temporary_directory)
        cases = []
        for row in rows:
            case_id = str(row["point_slug"])
            role = str(row["parameter_case_role"])
            common_dimensions = {
                "trace_width_um": TRACE_WIDTH_UM,
                "trace_gap_um": TRACE_GAP_UM,
                "upper_ground_clearance_width_um": float(
                    row["parameter_upper_ground_clearance_width_um"]
                ),
                "flip_chip_gap_height_um": FLIP_CHIP_GAP_HEIGHT_UM,
                "die_thickness_um": D0_DIE_THICKNESS_UM,
                "air_height_um": AIR_HEIGHT_UM,
                "ground_width_um": GROUND_WIDTH_UM,
                "metal_thickness_um": METAL_THICKNESS_UM,
            }
            if role == "coupled_pair":
                cross_section = make_q2d_same_face_two_trace_cross_section(
                    **common_dimensions,
                    inter_trace_ground_width_um=float(row["parameter_inter_trace_ground_width_um"]),
                )
            elif role == "single_reference":
                cross_section = make_q2d_same_face_single_trace_cross_section(
                    **common_dimensions,
                )
            else:
                raise RuntimeError(f"Unsupported public sweep case role: {role!r}")
            cross_section_path = write_q2d_cross_section_payload(
                source_dir / f"{case_id}_q2d_cross_section.json",
                cross_section,
            )
            cases.append(
                AedtNativeCaseSpec(
                    id=case_id,
                    q2d_cross_section_json_path=cross_section_path,
                    recipes=(recipe,),
                )
            )

        spec = AedtNativePackageSpec(
            project_name=PROJECT_NAME,
            point_local_sweep=True,
            cases=tuple(cases),
        )
        result = prepare_aedt_native_handoff_package(
            spec,
            package_dir=resolved_run_root,
            overwrite=overwrite,
        )

    _write_point_ledgers(result.package_dir, rows)
    protected_after = _runtime_tree_inventory(result.package_dir)
    if protected_after != protected_before:
        raise RuntimeError(
            "AEDT package refresh changed protected results/logs/points runtime files"
        )
    manifest_summary = _validate_written_package(result, rows)
    _write_package_audit(
        result,
        rows,
        manifest_summary,
        overwrite=overwrite,
        protected_before=protected_before,
        protected_after=protected_after,
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Refresh a compatible package while preserving runtime result trees.",
    )
    args = parser.parse_args()

    result = build_package(args.run_root, overwrite=args.overwrite)
    print(
        json.dumps(
            {
                "run_root": str(result.package_dir),
                "manifest": str(result.manifest_path),
                "case_count": result.case_count,
                "recipe_count": result.recipe_count,
                "status": "package_ready_solver_pending",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
