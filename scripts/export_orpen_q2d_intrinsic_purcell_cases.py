"""Export verified same-face Q2D Maxwell L/C cases for Purcell studies.

The exporter accepts one homogeneous selection of either two-trace coupled
cases or one-trace isolated-reference cases. Every selected semantic
cross-section keeps its signal conductor(s) on D0 and removes D1 ground metal
only inside a tagged local clearance. The exporter rejects the earlier
opposing-face sweep and never substitutes historical or proxy values for a
missing same-face solve.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from orpen_sc_pdk.simulation.aedt.q2d import (
    Q2dMatrixElement,
    load_q2d_raw_point_result,
    validate_q2d_same_face_upper_ground_clearance_payload,
    validate_q2d_single_reference_upper_ground_clearance_payload,
)

RECIPE_ID = "q2d"
CASE_ROLE_CONDUCTORS = {
    "coupled_pair": ("T1", "T2"),
    "single_reference": ("T1",),
}
CASE_ROLE_SCHEMAS = {
    "coupled_pair": "orpen-q2d-coupled-pair-maxwell-lc.v1",
    "single_reference": "orpen-q2d-single-reference-maxwell-lc.v1",
}
MAXWELL_MATRIX_FILE_NAMES = (
    "cg_maxwell_matrix.csv",
    "rl_maxwell_matrix.csv",
)
MATRIX_FILE_NAMES = (
    *MAXWELL_MATRIX_FILE_NAMES,
    "cg_couple_matrix.csv",
    "rl_couple_matrix.csv",
)


class PendingQ2dArtifactError(RuntimeError):
    """The requested artifact is pending a compatible completed solver run."""


def _pending(message: str) -> PendingQ2dArtifactError:
    return PendingQ2dArtifactError(f"Pending Q2D artifact: {message}")


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size <= 0:
        raise _pending(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid {label} JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return payload


def _read_manifest(run_root: Path) -> dict[str, Any]:
    path = run_root / "manifest.yaml"
    if not path.is_file() or path.stat().st_size <= 0:
        raise _pending(f"missing AEDT manifest: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"AEDT manifest must be a mapping: {path}")
    if not isinstance(payload.get("project"), dict):
        raise ValueError(f"AEDT manifest requires project metadata: {path}")
    if not isinstance(payload.get("cases"), list):
        raise ValueError(f"AEDT manifest requires case rows: {path}")
    return payload


def _manifest_case(manifest: Mapping[str, Any], case_id: str) -> dict[str, Any]:
    matches = [case for case in manifest["cases"] if case.get("id") == case_id]
    if len(matches) != 1:
        raise ValueError(f"AEDT manifest requires exactly one case {case_id!r}")
    return dict(matches[0])


def _manifest_recipe(case: Mapping[str, Any]) -> dict[str, Any]:
    recipes = case.get("recipes")
    if not isinstance(recipes, list):
        raise ValueError(f"AEDT case {case.get('id')!r} requires recipe rows")
    matches = [recipe for recipe in recipes if recipe.get("id") == RECIPE_ID]
    if len(matches) != 1:
        raise ValueError(f"AEDT case {case.get('id')!r} requires exactly one {RECIPE_ID!r} recipe")
    recipe = dict(matches[0])
    expected = {
        "type": "q2d_extraction",
        "q2d_geometry_mode": "semantic_cross_section",
        "section_plane": "XY",
    }
    for field, expected_value in expected.items():
        if recipe.get(field) != expected_value:
            raise ValueError(
                f"AEDT case {case.get('id')!r} has incompatible {field}: {recipe.get(field)!r}"
            )
    if tuple(recipe.get("matrix_problem_types", ("CG", "RL"))) != ("CG", "RL"):
        raise ValueError(f"AEDT case {case.get('id')!r} must export Q2D CG and RL matrices")
    if "Maxwell" not in tuple(recipe.get("matrix_types", ("Maxwell", "Couple"))):
        raise ValueError(f"AEDT case {case.get('id')!r} must export Maxwell matrices")
    return recipe


def _run_source_path(run_root: Path, relative: Any, label: str) -> Path:
    text = str(relative or "").strip()
    if not text:
        raise _pending(f"manifest does not declare {label}")
    path = (run_root / text).resolve()
    try:
        path.relative_to(run_root.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} escapes the AEDT run root: {text}") from exc
    return path


def _point_parameters(run_root: Path, case_id: str) -> tuple[dict[str, Any], Path]:
    path = run_root / "points.json"
    payload = _read_json_object(path, "Q2D point ledger")
    rows = payload.get("points")
    if not isinstance(rows, list):
        raise ValueError(f"Q2D point ledger requires points: {path}")
    matches = [row for row in rows if row.get("point_slug") == case_id]
    if len(matches) != 1:
        raise ValueError(f"Q2D point ledger requires exactly one point {case_id!r}")
    return (
        {
            key.removeprefix("parameter_"): value
            for key, value in matches[0].items()
            if key.startswith("parameter_") and key != "parameter_id"
        },
        path,
    )


def _matrix(
    point: Any,
    source: str,
    quantity: str,
    conductor_order: Sequence[str],
) -> list[list[float]]:
    return [
        [
            point.value_si(Q2dMatrixElement(source, quantity, row, column))
            for column in conductor_order
        ]
        for row in conductor_order
    ]


def _require_symmetric(name: str, matrix: list[list[float]]) -> None:
    for row_index, row in enumerate(matrix):
        for column_index in range(row_index + 1, len(matrix)):
            if not math.isclose(
                row[column_index],
                matrix[column_index][row_index],
                rel_tol=1e-9,
                abs_tol=1e-18,
            ):
                raise ValueError(f"{name} must be symmetric: {matrix}")


def _require_positive_definite(name: str, matrix: list[list[float]]) -> None:
    if not all(math.isfinite(value) for row in matrix for value in row):
        raise ValueError(f"{name} must contain only finite values: {matrix}")
    _require_symmetric(name, matrix)
    if matrix[0][0] <= 0.0 or (
        len(matrix) == 2 and matrix[0][0] * matrix[1][1] - matrix[0][1] ** 2 <= 0.0
    ):
        raise ValueError(f"{name} must be positive definite: {matrix}")


def _terminal_order(
    point: Any,
    expected_order: tuple[str, ...],
) -> tuple[str, ...]:
    observed_orders = []
    for source, quantity in (("cg_maxwell", "C"), ("rl_maxwell", "L")):
        rows = [
            row
            for row in point.matrix_table()
            if row.get("matrix_source") == source and row.get("quantity") == quantity
        ]
        expected_pairs = {
            (row_terminal, column_terminal)
            for row_terminal in expected_order
            for column_terminal in expected_order
        }
        observed_pairs = [(str(row["row_terminal"]), str(row["column_terminal"])) for row in rows]
        if len(observed_pairs) != len(expected_pairs) or set(observed_pairs) != expected_pairs:
            raise ValueError(
                f"Q2D {source} matrix must be exactly {len(expected_order)}x"
                f"{len(expected_order)} in conductor order {expected_order!r}"
            )
        row_order = tuple(dict.fromkeys(str(row["row_terminal"]) for row in rows))
        column_order = tuple(dict.fromkeys(str(row["column_terminal"]) for row in rows))
        if row_order != column_order:
            raise ValueError(
                f"Q2D {source} matrix row/column order mismatch: {row_order} vs {column_order}"
            )
        if row_order != expected_order:
            raise ValueError(f"Q2D conductor order must be {expected_order!r}, got {row_order!r}")
        observed_orders.append(row_order)
    if len(set(observed_orders)) != 1:
        raise ValueError("Q2D Maxwell L/C matrices disagree on conductor order")
    return observed_orders[0]


def _frequency_hz(point: Any) -> float:
    values = {
        (float(row["frequency"]), str(row["frequency_unit"]))
        for row in point.matrix_table()
        if row.get("frequency") is not None and row.get("frequency_unit")
    }
    if len(values) != 1:
        raise ValueError(f"Q2D matrix exports require one extraction frequency, got {values}")
    value, unit = values.pop()
    scale = {"Hz": 1.0, "kHz": 1e3, "MHz": 1e6, "GHz": 1e9}.get(unit)
    if scale is None:
        raise ValueError(f"Unsupported Q2D extraction frequency unit: {unit!r}")
    return value * scale


def _frequency_expression_hz(expression: str) -> float:
    match = re.fullmatch(
        r"\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?)\s*"
        r"(Hz|kHz|MHz|GHz)\s*",
        expression,
    )
    if not match:
        raise ValueError(f"Unsupported Q2D adaptive frequency expression: {expression!r}")
    scale = {"Hz": 1.0, "kHz": 1e3, "MHz": 1e6, "GHz": 1e9}[match.group(2)]
    return float(match.group(1)) * scale


def _assignment_contract(
    path: Path,
    conductor_order: tuple[str, ...],
) -> dict[str, Any]:
    payload = _read_json_object(path, "Q2D assignment summary")
    assignments = payload.get("assignments")
    if not isinstance(assignments, list):
        raise ValueError(f"Q2D assignment summary requires assignments: {path}")
    assignment_names = [str(row.get("assignment_name")) for row in assignments]
    if len(assignment_names) != len(set(assignment_names)):
        raise ValueError("Q2D assignment summary contains duplicate assignment names")
    signal_names = tuple(
        str(row.get("assignment_name"))
        for row in assignments
        if row.get("conductor_type") == "Signal Line"
    )
    if signal_names != conductor_order:
        raise ValueError(
            "Q2D Signal Line assignments must exactly match conductor order "
            f"{conductor_order!r}, got {signal_names!r}"
        )
    reference_names = sorted(
        str(row.get("assignment_name"))
        for row in assignments
        if row.get("conductor_type") == "Reference Ground"
    )
    if reference_names != ["Ground"]:
        raise ValueError(
            "Q2D same-face artifact requires one Reference Ground assignment named "
            f"'Ground', got {reference_names}"
        )
    return {
        "conductor_order": list(conductor_order),
        "reference_group": "Ground",
    }


def _require_complete_solver_metadata(
    payload: Mapping[str, Any],
    *,
    result_dir: Path,
) -> dict[str, int]:
    if payload.get("recipe_type") != "q2d_extraction":
        raise ValueError("simulation_metadata recipe_type must be q2d_extraction")
    if payload.get("q2d_geometry_mode") != "semantic_cross_section":
        raise ValueError("simulation_metadata must identify semantic_cross_section geometry")
    solve_status = payload.get("solve_status")
    if not isinstance(solve_status, dict):
        raise _pending(f"missing solve_status in {result_dir / 'simulation_metadata.json'}")
    analyze_setup = solve_status.get("analyze_setup")
    if not isinstance(analyze_setup, dict) or analyze_setup.get("return_value") is not True:
        raise _pending(f"AEDT solve did not complete successfully for {result_dir.parent.name}")
    exports = solve_status.get("matrix_exports")
    if not isinstance(exports, list):
        raise _pending(f"missing matrix export ledger for {result_dir.parent.name}")
    sizes: dict[str, int] = {}
    for record in exports:
        name = Path(str(record.get("file_name") or "")).name
        if name not in MATRIX_FILE_NAMES:
            continue
        if record.get("return_value") is not True:
            raise _pending(f"AEDT did not export {name} for {result_dir.parent.name}")
        sizes[name] = int(record.get("file_size") or 0)
    if not set(MAXWELL_MATRIX_FILE_NAMES) <= set(sizes):
        missing = sorted(set(MAXWELL_MATRIX_FILE_NAMES) - set(sizes))
        raise _pending(f"solver metadata is missing matrix exports: {missing}")
    for name, solver_size in sizes.items():
        actual_size = (result_dir / name).stat().st_size if (result_dir / name).is_file() else 0
        if actual_size <= 0 or actual_size != solver_size:
            raise ValueError(
                f"Q2D matrix size does not match solver metadata for {name}: "
                f"{actual_size} vs {solver_size}"
            )
    return sizes


def _topology_contract(payload: Mapping[str, Any]) -> tuple[str, tuple[str, ...], dict[str, Any]]:
    trace_names = tuple(
        str(segment.get("name"))
        for pattern in payload.get("face_patterns", [])
        if isinstance(pattern, Mapping)
        for segment in pattern.get("segments", [])
        if isinstance(segment, Mapping) and segment.get("kind") == "trace"
    )
    if trace_names == CASE_ROLE_CONDUCTORS["coupled_pair"]:
        role = "coupled_pair"
        topology = validate_q2d_same_face_upper_ground_clearance_payload(
            payload,
            trace_names=CASE_ROLE_CONDUCTORS[role],
        )
    elif trace_names == CASE_ROLE_CONDUCTORS["single_reference"]:
        role = "single_reference"
        topology = validate_q2d_single_reference_upper_ground_clearance_payload(
            payload,
            trace_name=CASE_ROLE_CONDUCTORS[role][0],
        )
    else:
        raise ValueError(
            "Q2D artifact geometry must contain exactly ordered T1/T2 coupled traces "
            f"or one T1 reference trace; got {trace_names!r}"
        )
    return role, CASE_ROLE_CONDUCTORS[role], topology


def _preflight_path(run_root: Path, case_id: str) -> Path:
    return run_root / "logs" / "workers" / f"{case_id}__{RECIPE_ID}" / "aedt_preflight.json"


def _solver_provenance(path: Path) -> dict[str, Any]:
    payload = _read_json_object(path, "AEDT worker preflight")
    aedt_version = str(payload.get("aedt_version") or "").strip()
    pyaedt_version = str(payload.get("pyaedt_version") or "").strip()
    if not aedt_version or not pyaedt_version:
        raise _pending(f"solver versions are unavailable in {path}")
    return {
        "solver": "Ansys Electronics Desktop 2D Extractor",
        "aedt_version": aedt_version,
        "pyaedt_version": pyaedt_version,
    }


def _source_record(run_root: Path, path: Path) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size <= 0:
        raise _pending(f"integrity source is missing or empty: {path}")
    try:
        relative = path.resolve().relative_to(run_root.resolve())
    except ValueError as exc:
        raise ValueError(f"integrity source is outside the run root: {path}") from exc
    return {
        "path": relative.as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _case_payload(
    run_root: Path,
    manifest: Mapping[str, Any],
    case_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    case = _manifest_case(manifest, case_id)
    recipe = _manifest_recipe(case)
    cross_section_path = _run_source_path(
        run_root,
        case.get("q2d_cross_section"),
        "Q2D semantic cross-section",
    )
    cross_section = _read_json_object(cross_section_path, "Q2D semantic cross-section")
    case_role, expected_conductor_order, topology = _topology_contract(cross_section)

    parameters, points_path = _point_parameters(run_root, case_id)
    ledger_role = str(parameters.get("case_role") or "").strip()
    if ledger_role not in CASE_ROLE_CONDUCTORS:
        raise ValueError(
            "Q2D point ledger must include case_role as coupled_pair or single_reference"
        )
    if ledger_role != case_role:
        raise ValueError(
            f"point-ledger case_role {ledger_role!r} does not match semantic geometry "
            f"role {case_role!r}"
        )
    if "upper_ground_clearance_width_um" not in parameters:
        raise ValueError("Q2D point ledger must include explicit upper_ground_clearance_width_um")
    if not math.isclose(
        float(parameters["upper_ground_clearance_width_um"]),
        topology["upper_ground_clearance_width_um"],
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ValueError(
            "point-ledger upper_ground_clearance_width_um does not match semantic geometry"
        )

    result_dir = run_root / "points" / case_id / RECIPE_ID
    simulation_metadata_path = result_dir / "simulation_metadata.json"
    simulation_metadata = _read_json_object(
        simulation_metadata_path,
        "Q2D simulation metadata",
    )
    solver_export_sizes = _require_complete_solver_metadata(
        simulation_metadata,
        result_dir=result_dir,
    )
    assignment_path = result_dir / "assignment_summary.json"
    assignment = _assignment_contract(assignment_path, expected_conductor_order)
    if assignment["reference_group"] != topology["reference_group"]:
        raise ValueError("semantic and solver reference-ground groups do not match")

    try:
        raw = load_q2d_raw_point_result(
            result_dir,
            point_id=case_id,
            point_slug=case_id,
            coords=parameters,
            required_sources=("cg_maxwell", "rl_maxwell"),
        )
    except (FileNotFoundError, ValueError) as exc:
        raise _pending(f"incomplete matrix exports for {case_id}: {exc}") from exc
    conductor_order = _terminal_order(raw, expected_conductor_order)
    if tuple(assignment["conductor_order"]) != conductor_order:
        raise ValueError("matrix and assignment conductor order do not match")

    l_matrix = _matrix(raw, "rl_maxwell", "L", conductor_order)
    c_matrix = _matrix(raw, "cg_maxwell", "C", conductor_order)
    _require_positive_definite("Maxwell L matrix", l_matrix)
    _require_positive_definite("Maxwell C matrix", c_matrix)
    c_row_sums = [math.fsum(row) for row in c_matrix]
    if any(row_sum <= 0.0 for row_sum in c_row_sums):
        raise ValueError(f"Maxwell C row sums must be positive: {c_row_sums}")
    if case_role == "coupled_pair":
        if c_matrix[0][1] >= 0.0:
            raise ValueError(f"Maxwell C off-diagonal must be negative: {c_matrix}")
        if l_matrix[0][1] <= 0.0:
            raise ValueError(f"Maxwell mutual L must be positive: {l_matrix}")

    frequency_hz = _frequency_hz(raw)
    adaptive_frequency = str(
        (recipe.get("q2d_setup") or {}).get("adaptive_frequency") or ""
    ).strip()
    if not adaptive_frequency:
        raise ValueError(f"AEDT recipe for {case_id} has no adaptive frequency")
    if not math.isclose(
        _frequency_expression_hz(adaptive_frequency),
        frequency_hz,
        rel_tol=0.0,
        abs_tol=1e-6,
    ):
        raise ValueError(f"Q2D matrix frequency does not match adaptive frequency for {case_id}")

    preflight_path = _preflight_path(run_root, case_id)
    solver_provenance = _solver_provenance(preflight_path)
    matrix_paths = [result_dir / name for name in MATRIX_FILE_NAMES if name in solver_export_sizes]
    integrity_paths = [
        run_root / "manifest.yaml",
        points_path,
        cross_section_path,
        assignment_path,
        simulation_metadata_path,
        preflight_path,
        *matrix_paths,
    ]
    source_hashes = [_source_record(run_root, path) for path in integrity_paths]

    derived: dict[str, Any] = {
        "self_impedance_ohm": {
            trace: math.sqrt(l_matrix[index][index] / c_matrix[index][index])
            for index, trace in enumerate(conductor_order)
        },
    }
    if case_role == "coupled_pair":
        derived["mutual_impedance_ohm"] = math.sqrt(l_matrix[0][1] / -c_matrix[0][1])

    case_payload = {
        "schema_version": CASE_ROLE_SCHEMAS[case_role],
        "id": case_id,
        "case_role": case_role,
        "parameters": parameters,
        "topology": topology,
        "l_matrix_h_per_m": l_matrix,
        "c_matrix_f_per_m": c_matrix,
        "derived": derived,
    }
    if case_role == "coupled_pair":
        matrix_semantics = {
            "C": "F/m; Maxwell off-diagonal retained as negative",
            "L": "H/m; Maxwell mutual entries retained as positive",
        }
    else:
        matrix_semantics = {
            "C": "F/m; one signal-to-Ground Maxwell self entry",
            "L": "H/m; one signal-to-Ground Maxwell self entry",
        }

    contract = {
        "case_role": case_role,
        "case_schema_version": CASE_ROLE_SCHEMAS[case_role],
        "topology_contract": topology["schema_version"],
        "conductor_order": list(conductor_order),
        "reference_group": assignment["reference_group"],
        "directions": {
            "voltage": "V[i] = potential(Ti) - potential(Ground)",
            "current": "positive I[i] flows in +z",
            "positive_z": "normal to the XY cross-section and along line propagation",
        },
        "matrix_representation": {
            "kind": "distributed_maxwell_per_unit_length",
            "row_column_order": "conductor_order",
            "shape": [len(conductor_order), len(conductor_order)],
            **matrix_semantics,
        },
        "extraction_frequency_hz": frequency_hz,
        "adaptive_frequency_expression": adaptive_frequency,
        "loss_terms": {
            "R": {
                "status": "unavailable",
                "assumed_zero_for_v1": True,
                "unit": "ohm/m",
            },
            "G": {
                "status": "unavailable",
                "assumed_zero_for_v1": True,
                "unit": "S/m",
            },
        },
        "solver_provenance": solver_provenance,
        "source_hashes": source_hashes,
    }
    return case_payload, contract


def _require_shared_metadata(contracts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    shared_fields = (
        "case_role",
        "case_schema_version",
        "topology_contract",
        "conductor_order",
        "reference_group",
        "directions",
        "matrix_representation",
        "extraction_frequency_hz",
        "adaptive_frequency_expression",
        "loss_terms",
        "solver_provenance",
    )
    first = contracts[0]
    for index, contract in enumerate(contracts[1:], start=1):
        for field in shared_fields:
            if contract[field] != first[field]:
                raise ValueError(
                    f"selected Q2D cases disagree on shared metadata {field!r}: case index {index}"
                )
    return {field: first[field] for field in shared_fields}


def export_cases(
    run_root: Path,
    output_path: Path,
    *,
    case_ids: Sequence[str] = (),
) -> Path:
    """Export selected compatible solver results after full semantic validation.

    Raises:
        PendingQ2dArtifactError: No case was selected or solver evidence is
            incomplete. The output file is not written.
        ValueError: A selected case uses an incompatible topology or violates
            the artifact contract.
    """

    run_root = Path(run_root)
    output_path = Path(output_path)
    selected = tuple(dict.fromkeys(str(case_id).strip() for case_id in case_ids if case_id))
    if not selected:
        raise _pending(
            "select at least one completed same-D0 case with --case-id; "
            "historical opposing-face candidates are intentionally not defaults"
        )
    if not run_root.is_dir():
        raise _pending(f"AEDT run root does not exist: {run_root}")

    manifest = _read_manifest(run_root)
    case_rows = []
    contracts = []
    for case_id in selected:
        case_payload, contract = _case_payload(run_root, manifest, case_id)
        case_rows.append(case_payload)
        contracts.append(contract)
    shared = _require_shared_metadata(contracts)

    payload = {
        "schema_version": "orpen-q2d-intrinsic-purcell-maxwell-lc-cases.v3",
        "artifact_status": "complete",
        "metadata": {
            **shared,
            "run_provenance": {
                "run_id": run_root.name,
                "project_name": str(manifest["project"].get("name") or ""),
                "manifest_schema_version": manifest.get("schema_version"),
                "recipe_id": RECIPE_ID,
                "case_ids": list(selected),
                "selected_case_status": "solve_complete",
            },
            "source_integrity": {
                "algorithm": "sha256",
                "all_sources_hashed": True,
                "solver_export_sizes_verified": True,
                "cases": {
                    case_id: contracts[index]["source_hashes"]
                    for index, case_id in enumerate(selected)
                },
            },
        },
        "cases": case_rows,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--case-id",
        action="append",
        required=True,
        help="Solved same-face Q2D case id; repeat to export multiple cases.",
    )
    args = parser.parse_args()

    output_path = export_cases(args.run_root, args.output, case_ids=args.case_id)
    print(output_path)


if __name__ == "__main__":
    main()
