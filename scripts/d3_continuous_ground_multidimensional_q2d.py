"""Prepare, cache, analyze, and plot a continuous-ground D3 Q2D sweep.

This is a notebook-facing research workflow.  The SQLite file is a local,
cross-run cache of validated completed point results.  Each cache key owns one
immutable row, so identical geometry solved by different runtime identities
coexists as distinct evidence.  Run folders continue to own AEDT projects,
logs, and raw matrix exports.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from itertools import product
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.lines import Line2D

from orpen_sc_pdk.simulation.aedt.models import (
    AedtCompiledMaterialSpec,
    AedtMaterialContext,
    AedtNativeCaseSpec,
    AedtNativePackageSpec,
    AedtQ2dSetupSpec,
    AedtRecipeSpec,
    AedtRuntimeSpec,
    AedtSupportedMaterialProperties,
)
from orpen_sc_pdk.simulation.aedt.package import prepare_aedt_native_handoff_package
from orpen_sc_pdk.simulation.aedt.q2d import (
    Q2dImpedanceFormula,
    load_q2d_raw_point_result,
    make_q2d_same_face_single_trace_cross_section,
    make_q2d_same_face_two_trace_cross_section,
    write_q2d_cross_section_payload,
)

PROJECT_NAME = "d3_continuous_ground_multidimensional_q2d"
# This value participates in every scientific cache key.  SQLite ownership and
# index migrations are versioned separately through PRAGMA user_version.
CACHE_SCHEMA = "orpen-q2d-point-result-cache.v3"
DATABASE_SCHEMA_VERSION = 3
SWEEP_SCHEMA = "d3-continuous-ground-multidimensional-q2d.v2"
AEDT_VERSION = "2024.2"
PYAEDT_VERSION = "0.26.2"
ADAPTIVE_FREQUENCY = "6GHz"
DIE_THICKNESS_UM = 500.0
AIR_HEIGHT_UM = 200.0
GROUND_WIDTH_UM = 150.0
METAL_THICKNESS_UM = 0.2
UPPER_GROUND_CLEARANCE_WIDTH_UM = 0.0
SUBSTRATE_PHYSICAL_MATERIAL = "silicon"
SUBSTRATE_AEDT_MATERIAL = "D3Silicon_er11p9"
SUBSTRATE_RELATIVE_PERMITTIVITY = 11.9
CONDUCTOR_AEDT_MATERIAL = "pec"
REGION_AEDT_MATERIAL = "Vacuum"
LEGACY_GEOMETRY_INDEX = "q2d_point_result_geometry"
GEOMETRY_LOOKUP_INDEX = "q2d_point_result_geometry_lookup"
LEGACY_GEOMETRY_INDEX_SQL = f"""
    CREATE UNIQUE INDEX {LEGACY_GEOMETRY_INDEX}
    ON q2d_point_result(role, w_nm, s_nm, COALESCE(d_nm, -1), h_nm)
"""
GEOMETRY_LOOKUP_INDEX_SQL = f"""
    CREATE INDEX {GEOMETRY_LOOKUP_INDEX}
    ON q2d_point_result(role, w_nm, s_nm, COALESCE(d_nm, -1), h_nm)
"""
DATABASE_COLUMNS = (
    "cache_key",
    "role",
    "input_json",
    "solver_json",
    "w_nm",
    "s_nm",
    "d_nm",
    "h_nm",
    "c_matrix_json",
    "l_matrix_json",
    "convergence_json",
    "z0_ohm",
    "zc1_ohm",
    "zc2_ohm",
    "zm_ohm",
    "source_run_root",
    "source_case_id",
    "source_sha256_json",
    "solver_completed_at",
    "ingested_at",
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _nm(value_um: float) -> int:
    value_nm = round(float(value_um) * 1000)
    if not math.isclose(value_nm / 1000, float(value_um), abs_tol=1e-9):
        raise ValueError(f"Dimension must resolve to integer nm: {value_um!r} um")
    return value_nm


def _um(value_nm: int) -> float:
    return value_nm / 1000


def _validate_axes(
    widths_um: Iterable[float],
    gaps_um: Iterable[float],
    center_grounds_um: Iterable[float],
    heights_um: Iterable[float],
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    axes_nm = tuple(
        tuple(dict.fromkeys(_nm(value) for value in values))
        for values in (widths_um, gaps_um, center_grounds_um, heights_um)
    )
    if any(not values for values in axes_nm):
        raise ValueError("w, s, d, and height axes must all be non-empty")
    for label, values in zip(("w", "s", "d"), axes_nm[:3], strict=True):
        if min(values) < 3000:
            raise ValueError(f"{label} must be at least 3 um")
    if min(axes_nm[3]) < 4000 or max(axes_nm[3]) > 9000:
        raise ValueError("Flip-chip height must stay within the requested 4-9 um sweep")
    return axes_nm


def _recipe() -> AedtRecipeSpec:
    return AedtRecipeSpec(
        id="q2d",
        type="q2d_extraction",
        q2d_geometry_mode="semantic_cross_section",
        section_plane="XY",
        matrix_problem_types=("CG", "RL"),
        matrix_types=("Maxwell",),
        q2d_setup=AedtQ2dSetupSpec(adaptive_frequency=ADAPTIVE_FREQUENCY),
    )


def _material_identity() -> dict[str, Any]:
    return {
        "substrate": {
            "physical_material_key": SUBSTRATE_PHYSICAL_MATERIAL,
            "aedt_material_name": SUBSTRATE_AEDT_MATERIAL,
            "relative_permittivity": SUBSTRATE_RELATIVE_PERMITTIVITY,
            "relative_permeability": 1.0,
        },
        "conductor": {"aedt_material_name": CONDUCTOR_AEDT_MATERIAL},
        "region": {
            "aedt_material_name": REGION_AEDT_MATERIAL,
            "relative_permittivity": 1.0,
            "relative_permeability": 1.0,
        },
    }


def _material_context() -> AedtMaterialContext:
    return AedtMaterialContext(
        material_condition="cryogenic",
        compiled_materials=(
            AedtCompiledMaterialSpec(
                aedt_material_name=SUBSTRATE_AEDT_MATERIAL,
                source_physical_material_key=SUBSTRATE_PHYSICAL_MATERIAL,
                material_kind="dielectric",
                supported_properties=AedtSupportedMaterialProperties(
                    permittivity=SUBSTRATE_RELATIVE_PERMITTIVITY,
                    permeability=1.0,
                ),
            ),
        ),
    )


def _runtime_bundle_hash(runtime_root: Path | None = None) -> str:
    if runtime_root is None:
        runtime_root = (
            Path(__file__).resolve().parents[1]
            / "orpen_sc_pdk"
            / "simulation"
            / "aedt"
            / "runtime_bundle"
        )
    digest = hashlib.sha256()
    files = sorted(
        path
        for path in runtime_root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    )
    if not files:
        raise FileNotFoundError(f"AEDT runtime bundle is empty: {runtime_root}")
    for path in files:
        relative = path.relative_to(runtime_root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _cross_section(role: str, *, w_nm: int, s_nm: int, d_nm: int | None, h_nm: int):
    common = {
        "trace_width_um": _um(w_nm),
        "trace_gap_um": _um(s_nm),
        "upper_ground_clearance_width_um": UPPER_GROUND_CLEARANCE_WIDTH_UM,
        "flip_chip_gap_height_um": _um(h_nm),
        "die_thickness_um": DIE_THICKNESS_UM,
        "air_height_um": AIR_HEIGHT_UM,
        "ground_width_um": GROUND_WIDTH_UM,
        "metal_thickness_um": METAL_THICKNESS_UM,
        "substrate_material": SUBSTRATE_AEDT_MATERIAL,
        "conductor_material": CONDUCTOR_AEDT_MATERIAL,
    }
    if role == "coupled_pair":
        if d_nm is None:
            raise ValueError("coupled_pair requires d")
        return make_q2d_same_face_two_trace_cross_section(
            **common,
            inter_trace_ground_width_um=_um(d_nm),
        )
    if role == "single_reference":
        return make_q2d_same_face_single_trace_cross_section(**common)
    raise ValueError(f"Unsupported role: {role!r}")


def _cache_input(
    role: str,
    cross_section_payload: dict[str, Any],
    *,
    runtime_bundle_sha256: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": CACHE_SCHEMA,
        "role": role,
        "semantic_cross_section": cross_section_payload,
        "materials": _material_identity(),
        "recipe": _recipe().model_dump(mode="json"),
        "solver": {
            "aedt_version": AEDT_VERSION,
            "pyaedt_version": PYAEDT_VERSION,
            "runtime_bundle_sha256": runtime_bundle_sha256 or _runtime_bundle_hash(),
        },
    }


def _cache_key(cache_input: dict[str, Any]) -> str:
    return _sha256_bytes(_canonical_json(cache_input).encode("utf-8"))


def _case_id(
    role: str,
    *,
    w_nm: int,
    s_nm: int,
    d_nm: int | None,
    h_nm: int,
    cache_key: str,
) -> str:
    geometry = f"w{w_nm}_s{s_nm}_h{h_nm}"
    if d_nm is not None:
        geometry = f"w{w_nm}_s{s_nm}_d{d_nm}_h{h_nm}"
    prefix = "pair" if role == "coupled_pair" else "single"
    return f"{prefix}__{geometry}__{cache_key[:10]}"


def _normalized_sql(value: str) -> str:
    return " ".join(value.lower().split())


def _migrate_database_indexes(connection: sqlite3.Connection) -> None:
    legacy = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = ?",
        (LEGACY_GEOMETRY_INDEX,),
    ).fetchone()
    if legacy is not None:
        actual_sql = legacy["sql"]
        if actual_sql is None or _normalized_sql(actual_sql) != _normalized_sql(
            LEGACY_GEOMETRY_INDEX_SQL
        ):
            raise ValueError(f"Refusing to migrate unexpected index {LEGACY_GEOMETRY_INDEX!r}.")
        connection.execute(f"DROP INDEX {LEGACY_GEOMETRY_INDEX}")
    lookup = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = ?",
        (GEOMETRY_LOOKUP_INDEX,),
    ).fetchone()
    if lookup is None:
        connection.execute(GEOMETRY_LOOKUP_INDEX_SQL)
        return
    actual_sql = lookup["sql"]
    if actual_sql is None or _normalized_sql(actual_sql) != _normalized_sql(
        GEOMETRY_LOOKUP_INDEX_SQL
    ):
        raise ValueError(f"Refusing to use unexpected index {GEOMETRY_LOOKUP_INDEX!r}.")


def _migrate_database_schema(connection: sqlite3.Connection) -> None:
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version not in (0, DATABASE_SCHEMA_VERSION):
        raise ValueError(
            f"Unsupported Q2D SQLite schema version {version}; "
            f"expected 0 or {DATABASE_SCHEMA_VERSION}."
        )
    _migrate_database_indexes(connection)
    connection.execute(f"PRAGMA user_version = {DATABASE_SCHEMA_VERSION}")


def _connect(database_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS q2d_point_result (
                cache_key TEXT PRIMARY KEY,
                role TEXT NOT NULL CHECK(role IN ('single_reference', 'coupled_pair')),
                input_json TEXT NOT NULL,
                solver_json TEXT NOT NULL,
                w_nm INTEGER NOT NULL,
                s_nm INTEGER NOT NULL,
                d_nm INTEGER,
                h_nm INTEGER NOT NULL,
                c_matrix_json TEXT NOT NULL,
                l_matrix_json TEXT NOT NULL,
                convergence_json TEXT NOT NULL,
                z0_ohm REAL,
                zc1_ohm REAL,
                zc2_ohm REAL,
                zm_ohm REAL,
                source_run_root TEXT NOT NULL,
                source_case_id TEXT NOT NULL,
                source_sha256_json TEXT NOT NULL,
                solver_completed_at TEXT NOT NULL,
                ingested_at TEXT NOT NULL
            )
            """
        )
        actual_columns = {
            str(row["name"]) for row in connection.execute("PRAGMA table_info(q2d_point_result)")
        }
        if actual_columns != set(DATABASE_COLUMNS):
            raise ValueError(
                f"Q2D cache schema mismatch at {database_path}; use a new v2 database path"
            )
        _migrate_database_schema(connection)
        connection.commit()
    except Exception:
        connection.rollback()
        connection.close()
        raise
    return connection


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _point_definition(
    role: str,
    *,
    w_nm: int,
    s_nm: int,
    d_nm: int | None,
    h_nm: int,
) -> dict[str, Any]:
    cross_section = _cross_section(role, w_nm=w_nm, s_nm=s_nm, d_nm=d_nm, h_nm=h_nm)
    payload = cross_section.to_payload()
    cache_input = _cache_input(role, payload)
    cache_key = _cache_key(cache_input)
    return {
        "role": role,
        "w_nm": w_nm,
        "s_nm": s_nm,
        "d_nm": d_nm,
        "h_nm": h_nm,
        "w_um": _um(w_nm),
        "s_um": _um(s_nm),
        "d_um": "" if d_nm is None else _um(d_nm),
        "h_um": _um(h_nm),
        "cache_key": cache_key,
        "case_id": _case_id(
            role,
            w_nm=w_nm,
            s_nm=s_nm,
            d_nm=d_nm,
            h_nm=h_nm,
            cache_key=cache_key,
        ),
        "cache_input": cache_input,
        "cross_section": cross_section,
    }


def prepare_sweep(
    run_root: Path,
    database_path: Path,
    *,
    phase_id: str,
    widths_um: Iterable[float],
    gaps_um: Iterable[float],
    center_grounds_um: Iterable[float],
    heights_um: Iterable[float],
) -> dict[str, Any]:
    """Create/update one Run folder, scheduling only cross-run cache misses."""

    w_values, s_values, d_values, h_values = _validate_axes(
        widths_um,
        gaps_um,
        center_grounds_um,
        heights_um,
    )
    pair_points = [
        _point_definition(
            "coupled_pair",
            w_nm=w_nm,
            s_nm=s_nm,
            d_nm=d_nm,
            h_nm=h_nm,
        )
        for w_nm, s_nm, d_nm, h_nm in product(w_values, s_values, d_values, h_values)
    ]
    single_points = [
        _point_definition(
            "single_reference",
            w_nm=w_nm,
            s_nm=s_nm,
            d_nm=None,
            h_nm=h_nm,
        )
        for w_nm, s_nm, h_nm in product(w_values, s_values, h_values)
    ]
    all_points = pair_points + single_points
    single_key_by_geometry = {
        (point["w_nm"], point["s_nm"], point["h_nm"]): point["cache_key"] for point in single_points
    }

    with _connect(database_path) as connection:
        cached_keys = {
            str(row["cache_key"])
            for row in connection.execute("SELECT cache_key FROM q2d_point_result")
        }
    # Solve single references first so partial runs can already join Z0 to later
    # pair results; the database still deduplicates each (w, s, h) single point.
    misses = [
        point for point in single_points + pair_points if point["cache_key"] not in cached_keys
    ]
    run_root.mkdir(parents=True, exist_ok=True)

    if misses:
        recipe = _recipe()
        with TemporaryDirectory(prefix="orpen-d3-multidimensional-q2d-") as temporary_directory:
            source_dir = Path(temporary_directory)
            material_context_path = source_dir / "aedt_material_context.json"
            material_context_path.write_text(
                json.dumps(_material_context().model_dump(mode="json"), indent=2) + "\n",
                encoding="utf-8",
            )
            cases = []
            for point in misses:
                sidecar = write_q2d_cross_section_payload(
                    source_dir / f"{point['case_id']}_q2d_cross_section.json",
                    point["cross_section"],
                )
                cases.append(
                    AedtNativeCaseSpec(
                        id=str(point["case_id"]),
                        aedt_material_context_path=material_context_path,
                        q2d_cross_section_json_path=sidecar,
                        recipes=(recipe,),
                    )
                )
            prepare_aedt_native_handoff_package(
                AedtNativePackageSpec(
                    project_name=PROJECT_NAME,
                    runtime=AedtRuntimeSpec(
                        aedt_version=AEDT_VERSION,
                        allowed_aedt_versions=(AEDT_VERSION,),
                        version_policy="require",
                    ),
                    point_local_sweep=True,
                    cases=tuple(cases),
                ),
                package_dir=run_root,
                overwrite=True,
            )

    ledger_rows = []
    for point in all_points:
        pair_key = point["cache_key"] if point["role"] == "coupled_pair" else ""
        single_key = (
            point["cache_key"]
            if point["role"] == "single_reference"
            else single_key_by_geometry[(point["w_nm"], point["s_nm"], point["h_nm"])]
        )
        ledger_rows.append(
            {
                "schema_version": SWEEP_SCHEMA,
                "phase_id": phase_id,
                "role": point["role"],
                "case_id": point["case_id"],
                "cache_key": point["cache_key"],
                "pair_cache_key": pair_key,
                "single_cache_key": single_key,
                "cache_status_at_prepare": (
                    "hit_complete" if point["cache_key"] in cached_keys else "scheduled"
                ),
                "w_nm": point["w_nm"],
                "s_nm": point["s_nm"],
                "d_nm": "" if point["d_nm"] is None else point["d_nm"],
                "h_nm": point["h_nm"],
                "w_um": point["w_um"],
                "s_um": point["s_um"],
                "d_um": point["d_um"],
                "h_um": point["h_um"],
                "substrate_material": SUBSTRATE_AEDT_MATERIAL,
                "substrate_relative_permittivity": SUBSTRATE_RELATIVE_PERMITTIVITY,
                "conductor_material": CONDUCTOR_AEDT_MATERIAL,
                "region_material": REGION_AEDT_MATERIAL,
            }
        )
    _write_csv(run_root / "sweep_points.csv", ledger_rows)
    runtime_rows = [
        {
            "point_slug": point["case_id"],
            "run_id": run_root.name,
            "parameter_id": point["cache_key"],
            "parameter_case_role": point["role"],
            "parameter_trace_width_um": point["w_um"],
            "parameter_trace_gap_um": point["s_um"],
            "parameter_inter_trace_ground_width_um": point["d_um"],
            "parameter_flip_chip_gap_height_um": point["h_um"],
            "parameter_upper_ground_clearance_width_um": (UPPER_GROUND_CLEARANCE_WIDTH_UM),
            "parameter_substrate_material": SUBSTRATE_AEDT_MATERIAL,
            "parameter_substrate_relative_permittivity": SUBSTRATE_RELATIVE_PERMITTIVITY,
            "parameter_conductor_material": CONDUCTOR_AEDT_MATERIAL,
            "parameter_region_material": REGION_AEDT_MATERIAL,
        }
        for point in misses
    ]
    _write_csv(run_root / "points.csv", runtime_rows)
    (run_root / "points.json").write_text(
        json.dumps(
            {
                "schema_version": "aedt-q2d-sweep-points.v1",
                "sweep_contract": SWEEP_SCHEMA,
                "points": runtime_rows,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    contract = {
        "schema_version": SWEEP_SCHEMA,
        "phase_id": phase_id,
        "run_root": str(run_root.resolve()),
        "database_path": str(database_path.resolve()),
        "axes_um": {
            "w": [_um(value) for value in w_values],
            "s": [_um(value) for value in s_values],
            "d": [_um(value) for value in d_values],
            "flip_chip_height": [_um(value) for value in h_values],
        },
        "minimum_feature_um": 3.0,
        "nominal_height_window_um": [7.0, 8.0],
        "upper_ground_policy": "continuous",
        "materials": _material_identity(),
        "requested_pair_points": len(pair_points),
        "requested_single_points": len(single_points),
        "cache_hits": len(all_points) - len(misses),
        "scheduled_cases": len(misses),
    }
    (run_root / "sweep_contract.json").write_text(
        json.dumps(contract, indent=2) + "\n",
        encoding="utf-8",
    )
    return contract


def _parse_convergence(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="strict")

    def require(pattern: str, label: str) -> str:
        match = re.search(pattern, text, flags=re.MULTILINE)
        if match is None:
            raise ValueError(f"Missing {label} in convergence export: {path}")
        return match.group(1)

    problem_type = require(r"^Problem Type\s*:\s*(\S+)\s*$", "problem type")
    completed = int(require(r"^Completed\s*:\s*(\d+)\s*$", "completed passes"))
    maximum = int(require(r"^Maximum\s*:\s*(\d+)\s*$", "maximum passes"))
    target = float(require(r"^Target\s*:\s*([0-9.eE+-]+)\s*$", "target"))
    current_text = require(r"^Current\s*:\s*\(([^)]+)\)\s*$", "current values")
    current = tuple(float(value.strip()) for value in current_text.split(","))
    if not current or any(not math.isfinite(value) for value in current):
        raise ValueError(f"Invalid convergence current values: {path}")
    if target <= 0 or max(current) > target:
        raise ValueError(
            f"Q2D {problem_type} did not meet convergence target: "
            f"current={current}, target={target}"
        )
    if completed >= maximum:
        raise ValueError(f"Q2D {problem_type} stopped at maximum passes: {completed}/{maximum}")
    return {
        "problem_type": problem_type,
        "completed_passes": completed,
        "maximum_passes": maximum,
        "target_percent": target,
        "current_percent": list(current),
    }


def _validated_point(run_root: Path, row: dict[str, str]) -> dict[str, Any] | None:
    case_id = row["case_id"]
    result_dir = run_root / "points" / case_id / "q2d"
    metadata_path = result_dir / "simulation_metadata.json"
    matrix_paths = {
        "C": result_dir / "cg_maxwell_matrix.csv",
        "L": result_dir / "rl_maxwell_matrix.csv",
    }
    convergence_paths = {
        "CG": result_dir / "aedt_convergenceCG.prop",
        "RL": result_dir / "aedt_convergenceCGRL.prop",
    }
    if not metadata_path.is_file() or any(
        not path.is_file() or path.stat().st_size <= 0 for path in matrix_paths.values()
    ):
        return None
    if any(not path.is_file() or path.stat().st_size <= 0 for path in convergence_paths.values()):
        return None
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    analyze = metadata.get("solve_status", {}).get("analyze_setup", {})
    if not analyze.get("return_value"):
        return None

    sidecar_path = run_root / "metadata" / f"{case_id}_q2d_cross_section.json"
    material_context_path = run_root / "metadata" / f"{case_id}_aedt_material_context.json"
    sidecar_payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
    material_context_payload = json.loads(material_context_path.read_text(encoding="utf-8"))
    if _canonical_json(material_context_payload) != _canonical_json(
        _material_context().model_dump(mode="json")
    ):
        raise ValueError(f"Solved material context does not match declared materials: {case_id}")
    expected_payload = _cross_section(
        row["role"],
        w_nm=int(row["w_nm"]),
        s_nm=int(row["s_nm"]),
        d_nm=None if not row["d_nm"] else int(row["d_nm"]),
        h_nm=int(row["h_nm"]),
    ).to_payload()
    if _canonical_json(sidecar_payload) != _canonical_json(expected_payload):
        raise ValueError(f"Solved sidecar does not match ledger geometry: {case_id}")
    run_runtime_root = run_root / "scripts" / "runtime_bundle"
    cache_input = _cache_input(
        row["role"],
        sidecar_payload,
        runtime_bundle_sha256=_runtime_bundle_hash(run_runtime_root),
    )
    cache_key = _cache_key(cache_input)
    if cache_key != row["cache_key"]:
        raise ValueError(
            f"Run evidence no longer reconstructs its prepared cache identity: {case_id}"
        )

    preflight_path = run_root / "logs" / "workers" / f"{case_id}__q2d" / "aedt_preflight.json"
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    if (
        str(preflight.get("aedt_version")) != AEDT_VERSION
        or str(preflight.get("pyaedt_version")) != PYAEDT_VERSION
    ):
        raise ValueError(f"Solver version mismatch for {case_id}")

    workflow_state_path = run_root / "logs" / case_id / "q2d" / "q2d_workflow_state.json"
    workflow_state = json.loads(workflow_state_path.read_text(encoding="utf-8"))
    if (
        workflow_state.get("completion_status") != "complete"
        or workflow_state.get("case_id") != case_id
        or workflow_state.get("recipe_id") != "q2d"
        or workflow_state.get("recipe_settings_stale")
    ):
        raise ValueError(f"Q2D workflow state is not reusable: {case_id}")
    sidecar_sha = _sha256_file(sidecar_path)
    if workflow_state.get("source_hashes", {}).get("q2d_cross_section") != sidecar_sha:
        raise ValueError(f"Q2D workflow source hash is stale: {case_id}")
    solver_completed_at = workflow_state.get("completed_at")
    if not isinstance(solver_completed_at, str) or not solver_completed_at:
        raise ValueError(f"Q2D workflow completion time is missing: {case_id}")
    convergence = {name: _parse_convergence(path) for name, path in convergence_paths.items()}
    applied_materials_path = result_dir / "aedt_material_context_applied.json"
    applied_materials = json.loads(applied_materials_path.read_text(encoding="utf-8"))
    substrate_records = [
        item
        for item in applied_materials.get("materials", [])
        if item.get("aedt_material_name") == SUBSTRATE_AEDT_MATERIAL
    ]
    if len(substrate_records) != 1 or substrate_records[0].get("applied") != {
        "permittivity": SUBSTRATE_RELATIVE_PERMITTIVITY,
        "permeability": 1.0,
    }:
        raise ValueError(f"AEDT did not apply the declared silicon properties: {case_id}")

    point = load_q2d_raw_point_result(
        result_dir,
        point_id=case_id,
        point_slug=case_id,
        coords={},
        required_sources=("cg_maxwell", "rl_maxwell"),
    )
    role = row["role"]
    derived: dict[str, float | None] = {
        "z0_ohm": None,
        "zc1_ohm": None,
        "zc2_ohm": None,
        "zm_ohm": None,
    }
    if role == "single_reference":
        derived["z0_ohm"] = Q2dImpedanceFormula.self(
            name="z0",
            trace_names=("T1",),
        ).evaluate(point)["z0_T1_ohm"]
    else:
        self_values = Q2dImpedanceFormula.self(
            name="zc",
            trace_names=("T1", "T2"),
        ).evaluate(point)
        derived["zc1_ohm"] = self_values["zc_T1_ohm"]
        derived["zc2_ohm"] = self_values["zc_T2_ohm"]
        derived["zm_ohm"] = Q2dImpedanceFormula.mutual(name="zm").evaluate(point)["zm_T1_T2_ohm"]
    if any(value is not None and not math.isfinite(value) for value in derived.values()):
        raise ValueError(f"Non-finite impedance for {case_id}")

    matrix_rows = point.matrix_table()
    matrix_json = {
        quantity: _canonical_json(
            [
                {
                    "row_terminal": item["row_terminal"],
                    "column_terminal": item["column_terminal"],
                    "value": item["value"],
                    "unit": item.get("unit"),
                    "value_si": item.get("value_si"),
                }
                for item in matrix_rows
                if item["quantity"] == quantity
            ]
        )
        for quantity in ("C", "L")
    }
    source_sha = {
        path.name: _sha256_file(path)
        for path in (
            *matrix_paths.values(),
            *convergence_paths.values(),
            metadata_path,
            sidecar_path,
            material_context_path,
            applied_materials_path,
            preflight_path,
            workflow_state_path,
        )
    }
    return {
        "cache_key": cache_key,
        "role": role,
        "input_json": _canonical_json(cache_input),
        "solver_json": _canonical_json(cache_input["solver"]),
        "w_nm": int(row["w_nm"]),
        "s_nm": int(row["s_nm"]),
        "d_nm": None if not row["d_nm"] else int(row["d_nm"]),
        "h_nm": int(row["h_nm"]),
        "c_matrix_json": matrix_json["C"],
        "l_matrix_json": matrix_json["L"],
        "convergence_json": _canonical_json(convergence),
        **derived,
        "source_run_root": str(run_root.resolve()),
        "source_case_id": case_id,
        "source_sha256_json": _canonical_json(source_sha),
        "solver_completed_at": solver_completed_at,
        "ingested_at": datetime.now(UTC).isoformat(),
    }


def _database_rows(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = [
        dict(row)
        for row in connection.execute(
            """
            SELECT cache_key, role, input_json, w_nm / 1000.0 AS w_um,
                   s_nm / 1000.0 AS s_um, d_nm / 1000.0 AS d_um,
                   h_nm / 1000.0 AS h_um, z0_ohm, zc1_ohm, zc2_ohm, zm_ohm,
                   source_run_root, source_case_id, solver_completed_at, ingested_at
            FROM q2d_point_result
            ORDER BY role, h_nm, w_nm, s_nm, d_nm
            """
        )
    ]
    for row in rows:
        materials = json.loads(row.pop("input_json")).get("materials", {})
        substrate = materials.get("substrate", {})
        row["substrate_material"] = substrate.get("aedt_material_name")
        row["substrate_relative_permittivity"] = substrate.get("relative_permittivity")
        row["conductor_material"] = materials.get("conductor", {}).get("aedt_material_name")
        row["region_material"] = materials.get("region", {}).get("aedt_material_name")
    return rows


def _requested_rows(
    connection: sqlite3.Connection,
    ledger_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    by_cache_key = {
        str(row["cache_key"]): dict(row)
        for row in connection.execute("SELECT * FROM q2d_point_result")
    }
    requested = []
    for ledger in ledger_rows:
        if ledger["role"] != "coupled_pair":
            continue
        pair = by_cache_key.get(ledger["pair_cache_key"])
        single = by_cache_key.get(ledger["single_cache_key"])
        if pair is None or single is None:
            continue
        _require_common_authority(single, pair)
        z0 = float(single["z0_ohm"])
        zc1 = float(pair["zc1_ohm"])
        zc2 = float(pair["zc2_ohm"])
        zc = (zc1 + zc2) / 2
        zm = float(pair["zm_ohm"])
        mean = (z0 + zc + zm) / 3
        rc = (zc - z0) / z0
        rm = (zm - z0) / z0
        requested.append(
            {
                "phase_id": ledger["phase_id"],
                "pair_cache_key": pair["cache_key"],
                "single_cache_key": single["cache_key"],
                "w_um": float(ledger["w_um"]),
                "s_um": float(ledger["s_um"]),
                "d_um": float(ledger["d_um"]),
                "h_um": float(ledger["h_um"]),
                "nominal_height_window": 7.0 <= float(ledger["h_um"]) <= 8.0,
                "z0_ohm": z0,
                "zc1_ohm": zc1,
                "zc2_ohm": zc2,
                "zc_ohm": zc,
                "zm_ohm": zm,
                "zc_asymmetry_relative": abs(zc1 - zc2) / zc,
                "rc": rc,
                "rm": rm,
                "root_score": math.hypot(rc, rm),
                "max_pairwise_relative_mismatch": max(
                    abs(z0 - zc),
                    abs(z0 - zm),
                    abs(zc - zm),
                )
                / mean,
            }
        )
    return sorted(
        requested,
        key=lambda row: (
            row["root_score"],
            row["h_um"],
            row["w_um"],
            row["s_um"],
            row["d_um"],
        ),
    )


def _require_common_authority(
    single: dict[str, Any] | sqlite3.Row,
    pair: dict[str, Any] | sqlite3.Row,
) -> None:
    single_input = json.loads(single["input_json"])
    pair_input = json.loads(pair["input_json"])
    for field in ("recipe", "solver"):
        if single_input[field] != pair_input[field]:
            raise ValueError(
                "Q2D single-reference and coupled-pair rows do not share one "
                f"{field} authority. Select exact cache keys from the same Run."
            )


def load_current_q2d_point_pair(
    database_path: Path,
    *,
    width_um: float,
    gap_um: float,
    center_ground_um: float,
    height_um: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load the exact single/pair rows for the current recipe and runtime."""

    if not database_path.is_file():
        raise FileNotFoundError(database_path)
    w_nm, s_nm, d_nm, h_nm = (
        _nm(width_um),
        _nm(gap_um),
        _nm(center_ground_um),
        _nm(height_um),
    )
    single_key = _point_definition(
        "single_reference",
        w_nm=w_nm,
        s_nm=s_nm,
        d_nm=None,
        h_nm=h_nm,
    )["cache_key"]
    pair_key = _point_definition(
        "coupled_pair",
        w_nm=w_nm,
        s_nm=s_nm,
        d_nm=d_nm,
        h_nm=h_nm,
    )["cache_key"]
    with _connect(database_path) as connection:
        by_key = {
            str(row["cache_key"]): dict(row)
            for row in connection.execute(
                "SELECT * FROM q2d_point_result WHERE cache_key IN (?, ?)",
                (single_key, pair_key),
            )
        }
    single = by_key.get(single_key)
    pair = by_key.get(pair_key)
    if single is None or pair is None:
        raise RuntimeError(
            "The selected single-reference and coupled-pair Q2D points for the "
            "current recipe/runtime identity must both be complete in the cache."
        )
    _require_common_authority(single, pair)
    return single, pair


def _root_cell_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank complete 4-D cells by simultaneous signed-residual zero coverage."""

    axis_names = ("w_um", "s_um", "d_um", "h_um")
    axes = {name: sorted({float(row[name]) for row in rows}) for name in axis_names}
    if any(len(values) < 2 for values in axes.values()):
        return []
    by_coordinate = {tuple(float(row[name]) for name in axis_names): row for row in rows}
    cells = []
    intervals = {name: list(zip(values, values[1:], strict=False)) for name, values in axes.items()}
    for bounds in product(*(intervals[name] for name in axis_names)):
        vertices = [
            by_coordinate.get(coordinate)
            for coordinate in product(*[(lower, upper) for lower, upper in bounds])
        ]
        if any(vertex is None for vertex in vertices):
            continue
        complete_vertices = [vertex for vertex in vertices if vertex is not None]
        rc_values = [float(vertex["rc"]) for vertex in complete_vertices]
        rm_values = [float(vertex["rm"]) for vertex in complete_vertices]
        rc_min, rc_max = min(rc_values), max(rc_values)
        rm_min, rm_max = min(rm_values), max(rm_values)

        def zero_distance(minimum: float, maximum: float) -> float:
            return 0.0 if minimum <= 0 <= maximum else min(abs(minimum), abs(maximum))

        row = {
            **{
                f"{name.removesuffix('_um')}_{edge}_um": value
                for name, (lower, upper) in zip(axis_names, bounds, strict=True)
                for edge, value in (("min", lower), ("max", upper))
            },
            "rc_min": rc_min,
            "rc_max": rc_max,
            "rm_min": rm_min,
            "rm_max": rm_max,
            "rc_brackets_zero": rc_min <= 0 <= rc_max,
            "rm_brackets_zero": rm_min <= 0 <= rm_max,
            "simultaneous_zero_bracket": (rc_min <= 0 <= rc_max and rm_min <= 0 <= rm_max),
            "cell_root_score": math.hypot(
                zero_distance(rc_min, rc_max),
                zero_distance(rm_min, rm_max),
            ),
            "best_vertex_root_score": min(
                float(vertex["root_score"]) for vertex in complete_vertices
            ),
        }
        row["nominal_height_overlap"] = (
            float(row["h_min_um"]) <= 8.0 and float(row["h_max_um"]) >= 7.0
        )
        cells.append(row)
    return sorted(
        cells,
        key=lambda row: (
            not row["simultaneous_zero_bracket"],
            not row["nominal_height_overlap"],
            row["cell_root_score"],
            row["best_vertex_root_score"],
        ),
    )


def _insert_immutable_points(
    connection: sqlite3.Connection,
    points: list[dict[str, Any]],
) -> tuple[int, int]:
    inserted = 0
    already_present = 0
    compare_columns = tuple(column for column in DATABASE_COLUMNS if column != "ingested_at")
    for point in points:
        existing = connection.execute(
            "SELECT * FROM q2d_point_result WHERE cache_key = ?",
            (point["cache_key"],),
        ).fetchone()
        if existing is not None:
            mismatches = [column for column in compare_columns if existing[column] != point[column]]
            if mismatches:
                raise ValueError(
                    "Immutable Q2D cache row conflicts with existing evidence for "
                    f"{point['cache_key']}: {', '.join(mismatches)}"
                )
            already_present += 1
            continue
        placeholders = ", ".join("?" for _ in DATABASE_COLUMNS)
        connection.execute(
            f"""
            INSERT INTO q2d_point_result ({", ".join(DATABASE_COLUMNS)})
            VALUES ({placeholders})
            """,
            tuple(point[column] for column in DATABASE_COLUMNS),
        )
        inserted += 1
    return inserted, already_present


def ingest_sweep(run_root: Path, database_path: Path) -> dict[str, Any]:
    """Ingest only validated completed results, then export agent-readable CSVs."""

    ledger_rows = _read_csv(run_root / "sweep_points.csv")
    completed = []
    for row in ledger_rows:
        if row["cache_status_at_prepare"] != "scheduled":
            continue
        point = _validated_point(run_root, row)
        if point is not None:
            completed.append(point)

    with _connect(database_path) as connection:
        inserted, already_present = _insert_immutable_points(connection, completed)
        database_rows = _database_rows(connection)
        requested_rows = _requested_rows(connection, ledger_rows)
    root_cells = _root_cell_rows(requested_rows)

    results_dir = run_root / "results"
    _write_csv(results_dir / "q2d_point_result_database.csv", database_rows)
    _write_csv(results_dir / "q2d_impedance_sweep.csv", requested_rows)
    _write_csv(results_dir / "q2d_root_cells.csv", root_cells)
    summary = {
        "schema_version": SWEEP_SCHEMA,
        "validated_from_run": len(completed),
        "ingested_from_run": inserted,
        "already_present_from_run": already_present,
        "database_complete_points": len(database_rows),
        "requested_complete_pair_rows": len(requested_rows),
        "requested_pair_rows": sum(row["role"] == "coupled_pair" for row in ledger_rows),
        "complete_root_cells": len(root_cells),
        "simultaneous_zero_bracket_cells": sum(
            bool(row["simultaneous_zero_bracket"]) for row in root_cells
        ),
    }
    (results_dir / "ingest_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def _matrix_value_si(payload: str, row: str, column: str) -> float:
    matches = [
        float(item["value_si"])
        for item in json.loads(payload)
        if item["row_terminal"] == row and item["column_terminal"] == column
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one {row},{column} matrix entry, found {len(matches)}")
    return matches[0]


def export_consonant_length_seeds(
    database_path: Path,
    output_dir: Path,
    *,
    width_um: float = 3.0,
    gap_um: float = 3.0,
    center_ground_um: float = 3.0,
    height_um: float = 8.0,
    slot_hz: tuple[float, ...] = (5.52e9, 5.76e9, 6.00e9, 6.24e9, 6.48e9),
    readout_offset_hz: float = -2.0e6,
    filter_offset_hz: float = 2.0e6,
    notch_hz: float = 4.5e9,
    j_hz: float = 5.0e6,
    kappa_p_lb_hz: float = 20.0e6,
    consonant_max_relative: float = 0.01,
) -> dict[str, Any]:
    """Export Spring2025 B7/C16 seeds from one solved consonant Q2D point."""

    single, pair = load_current_q2d_point_pair(
        database_path,
        width_um=width_um,
        gap_um=gap_um,
        center_ground_um=center_ground_um,
        height_um=height_um,
    )

    single_l = _matrix_value_si(single["l_matrix_json"], "T1", "T1")
    single_c = _matrix_value_si(single["c_matrix_json"], "T1", "T1")
    pair_l11 = _matrix_value_si(pair["l_matrix_json"], "T1", "T1")
    pair_l22 = _matrix_value_si(pair["l_matrix_json"], "T2", "T2")
    pair_lm = _matrix_value_si(pair["l_matrix_json"], "T1", "T2")
    pair_c11 = _matrix_value_si(pair["c_matrix_json"], "T1", "T1")
    pair_c22 = _matrix_value_si(pair["c_matrix_json"], "T2", "T2")
    pair_cm = -_matrix_value_si(pair["c_matrix_json"], "T1", "T2")

    z0_ohm = float(single["z0_ohm"])
    zc1_ohm = float(pair["zc1_ohm"])
    zc2_ohm = float(pair["zc2_ohm"])
    zc_ohm = (zc1_ohm + zc2_ohm) / 2.0
    zm_ohm = float(pair["zm_ohm"])
    velocity_m_per_s = 1.0 / math.sqrt(single_l * single_c)
    vc1_m_per_s = 1.0 / math.sqrt(pair_l11 * pair_c11)
    vc2_m_per_s = 1.0 / math.sqrt(pair_l22 * pair_c22)
    rho = zm_ohm / z0_ohm
    consonant_relative = max(
        abs(zc1_ohm / z0_ohm - 1.0),
        abs(zc2_ohm / z0_ohm - 1.0),
        abs(vc1_m_per_s / velocity_m_per_s - 1.0),
        abs(vc2_m_per_s / velocity_m_per_s - 1.0),
    )
    if consonant_relative > consonant_max_relative:
        raise ValueError(
            "Selected Q2D point is not consonant within "
            f"{consonant_max_relative:.3%}: {consonant_relative:.3%}"
        )

    def sinc(value: float) -> float:
        return 1.0 - value**2 / 6.0 if abs(value) < 1.0e-8 else math.sin(value) / value

    def sinc_prime(value: float) -> float:
        if abs(value) < 1.0e-6:
            return -value / 3.0 + value**3 / 30.0
        return (value * math.cos(value) - math.sin(value)) / value**2

    def bridge_seed(
        *,
        fr_hz: float,
        fp_hz: float,
        coupled_length_m: float,
        impedance_ratio: float,
    ) -> dict[str, float]:
        wn = 2.0 * math.pi * notch_hz
        wr = 2.0 * math.pi * fr_hz
        wp = 2.0 * math.pi * fp_hz
        x = wn * coupled_length_m / velocity_m_per_s
        sinc_x = sinc(x)
        cosine = (1.0 - impedance_ratio**2) / ((1.0 + impedance_ratio**2) * sinc_x)
        if not -1.0 < cosine < 1.0:
            raise ValueError(
                "B7 has no first real symmetric-short-tail zero for this coupled length."
            )

        theta = math.acos(cosine)
        notch_path_m = theta * velocity_m_per_s / wn
        short_m = (notch_path_m - coupled_length_m) / 2.0
        readout_total_m = velocity_m_per_s / (4.0 * fr_hz)
        filter_total_m = velocity_m_per_s / (4.0 * fp_hz)
        readout_open_m = readout_total_m - coupled_length_m - short_m
        filter_open_m = filter_total_m - coupled_length_m - short_m
        if min(short_m, readout_open_m, filter_open_m) <= 0.0:
            raise ValueError("B7 target frequencies produce a nonpositive section.")

        f_prime = (1.0 + impedance_ratio**2) * (
            sinc_prime(x) * coupled_length_m / velocity_m_per_s * math.cos(theta)
            - sinc_x * math.sin(theta) * notch_path_m / velocity_m_per_s
        )
        denominator = (
            2.0 * math.cos(math.pi * wn / (2.0 * wr)) * math.cos(math.pi * wn / (2.0 * wp))
        )
        d_im_z21_d_omega = z0_ohm**2 * wn * coupled_length_m * pair_cm * f_prime / denominator

        cr = readout_total_m / (2.0 * z0_ohm * velocity_m_per_s)
        lr = 8.0 * z0_ohm * readout_total_m / (math.pi**2 * velocity_m_per_s)
        cp = filter_total_m / (2.0 * z0_ohm * velocity_m_per_s)
        lp = 8.0 * z0_ohm * filter_total_m / (math.pi**2 * velocity_m_per_s)
        br = wn * cr - 1.0 / (wn * lr)
        bp = wn * cp - 1.0 / (wn * lp)
        cn = -0.5 * d_im_z21_d_omega * br * bp
        if cn <= 0.0:
            raise ValueError("B7 zero slope did not produce a positive response-matched Cn.")
        zn = 1.0 / (wn * cn)
        geometric_omega = math.sqrt(wr * wp)
        j_rad_per_s = (
            math.sqrt(math.sqrt(lr / cr) * math.sqrt(lp / cp))
            / (2.0 * zn)
            * geometric_omega
            * (geometric_omega / wn - wn / geometric_omega)
        )
        return {
            "fr_hz": fr_hz,
            "fp_hz": fp_hz,
            "lr_open_um": readout_open_m * 1.0e6,
            "lr_short_um": short_m * 1.0e6,
            "lc_um": coupled_length_m * 1.0e6,
            "lp_short_um": short_m * 1.0e6,
            "lp_open_um": filter_open_m * 1.0e6,
            "lr_total_um": readout_total_m * 1.0e6,
            "lp_total_um": filter_total_m * 1.0e6,
            "notch_path_um": notch_path_m * 1.0e6,
            "notch_hz": notch_hz,
            "j_hz": j_rad_per_s / (2.0 * math.pi),
            "cn_fF": cn * 1.0e15,
            "zn_ohm": zn,
            "b7_zero_residual": (
                (1.0 + impedance_ratio**2) * sinc_x * math.cos(theta) - (1.0 - impedance_ratio**2)
            ),
        }

    def solve_coupled_length(target_slot_hz: float) -> dict[str, float]:
        fr_hz = target_slot_hz + readout_offset_hz
        fp_hz = target_slot_hz + filter_offset_hz
        lower_m, upper_m = 1.0e-6, 1.0e-3
        lower = bridge_seed(
            fr_hz=fr_hz,
            fp_hz=fp_hz,
            coupled_length_m=lower_m,
            impedance_ratio=rho,
        )
        upper = bridge_seed(
            fr_hz=fr_hz,
            fp_hz=fp_hz,
            coupled_length_m=upper_m,
            impedance_ratio=rho,
        )
        if not lower["j_hz"] < j_hz < upper["j_hz"]:
            raise ValueError("The 1–1000 um coupled-length bracket does not contain J target.")
        for _ in range(80):
            midpoint_m = (lower_m + upper_m) / 2.0
            midpoint = bridge_seed(
                fr_hz=fr_hz,
                fp_hz=fp_hz,
                coupled_length_m=midpoint_m,
                impedance_ratio=rho,
            )
            if midpoint["j_hz"] < j_hz:
                lower_m = midpoint_m
            else:
                upper_m = midpoint_m
        result = bridge_seed(
            fr_hz=fr_hz,
            fp_hz=fp_hz,
            coupled_length_m=(lower_m + upper_m) / 2.0,
            impedance_ratio=rho,
        )
        result["slot_hz"] = target_slot_hz
        return result

    homogeneous = bridge_seed(
        fr_hz=6.0e9,
        fp_hz=6.0e9,
        coupled_length_m=160.0e-6,
        impedance_ratio=1.0,
    )
    omega_bar = 2.0 * math.pi * 6.0e9
    omega_n = 2.0 * math.pi * notch_hz
    capacitance_per_m = 1.0 / (z0_ohm * velocity_m_per_s)
    spring_c17_j_hz = (
        omega_bar
        * math.pi**2
        / 32.0
        * (omega_bar / omega_n - omega_n / omega_bar) ** 3
        / math.cos(math.pi * omega_n / (2.0 * omega_bar)) ** 2
        * (pair_cm / capacitance_per_m)
        * math.sin(omega_n * 160.0e-6 / velocity_m_per_s)
        / (2.0 * math.pi)
    )
    if not math.isclose(homogeneous["j_hz"], spring_c17_j_hz, rel_tol=1.0e-12):
        raise AssertionError("Generalized B7 slope does not reduce to Eq. C17.")

    rows = [solve_coupled_length(target) for target in slot_hz]
    if max(abs(row["b7_zero_residual"]) for row in rows) >= 1.0e-12:
        raise AssertionError("B7 zero residual exceeds tolerance.")

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "spring2025_b7_consonant_length_seeds.csv"
    json_path = output_dir / "spring2025_b7_consonant_length_seeds.json"
    _write_csv(csv_path, rows)
    payload = {
        "schema_version": "d3-spring2025-b7-consonant-length-seeds.v1",
        "status": "estimator_only_not_distributed_validated",
        "q2d_cache_keys": {
            "single_reference": single["cache_key"],
            "coupled_pair": pair["cache_key"],
        },
        "q2d_sources": {
            role: {
                "source_run_root": row["source_run_root"],
                "source_case_id": row["source_case_id"],
                "source_sha256": json.loads(row["source_sha256_json"]),
                "solver_completed_at": row["solver_completed_at"],
            }
            for role, row in (
                ("single_reference", single),
                ("coupled_pair", pair),
            )
        },
        "cross_section_um": {
            "w": width_um,
            "s": gap_um,
            "d": center_ground_um,
            "flip_chip_height": height_um,
        },
        "q2d_readback": {
            "z0_ohm": z0_ohm,
            "zc1_ohm": zc1_ohm,
            "zc2_ohm": zc2_ohm,
            "zc_ohm": zc_ohm,
            "zm_ohm": zm_ohm,
            "single_velocity_m_per_s": velocity_m_per_s,
            "coupled_diagonal_line_velocities_m_per_s": [
                vc1_m_per_s,
                vc2_m_per_s,
            ],
            "consonant_max_relative": consonant_relative,
            "consonant_limit_relative": consonant_max_relative,
            "zm_equality_is_gate": False,
            "lm_over_lc": pair_lm / ((pair_l11 + pair_l22) / 2.0),
            "cm_over_cc": pair_cm / ((pair_c11 + pair_c22) / 2.0 - pair_cm),
        },
        "targets": {
            "notch_hz": notch_hz,
            "j_hz": j_hz,
            "kappa_p_lb_hz": kappa_p_lb_hz,
            "readout_offset_hz": readout_offset_hz,
            "filter_offset_hz": filter_offset_hz,
        },
        "formula_scope": (
            "Spring2025 Appendix B Eq. B7 zero and slope, response-matched "
            "bridge LC, Appendix C Eq. C16; symmetric short-tail initializer"
        ),
        "rows": rows,
    }
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "csv": str(csv_path.resolve()),
        "json": str(json_path.resolve()),
        "row_count": len(rows),
        "consonant_max_relative": consonant_relative,
    }


def _dash_styles(values: list[float]) -> dict[float, tuple[int, tuple[int, ...]] | str]:
    styles: list[tuple[int, tuple[int, ...]] | str] = [
        "solid",
        (0, (6, 3)),
        (0, (2, 2)),
        (0, (8, 2, 2, 2)),
        (0, (1, 2)),
    ]
    return {value: styles[index % len(styles)] for index, value in enumerate(values)}


def plot_sweep(run_root: Path) -> list[Path]:
    """Render the requested three-row Z0/Zc/Zm facet figures."""

    rows = [
        {
            key: (
                float(value)
                if key
                in {
                    "w_um",
                    "s_um",
                    "d_um",
                    "h_um",
                    "z0_ohm",
                    "zc_ohm",
                    "zm_ohm",
                }
                else value
            )
            for key, value in row.items()
        }
        for row in _read_csv(run_root / "results" / "q2d_impedance_sweep.csv")
    ]
    if not rows:
        raise ValueError("No complete requested sweep rows are available to plot")
    heights = sorted({row["h_um"] for row in rows})
    outputs = []
    if len(heights) <= 4:
        for height in heights:
            outputs.append(
                _plot_three_rows(
                    [row for row in rows if row["h_um"] == height],
                    x_key="w_um",
                    facet_key="s_um",
                    color_key="d_um",
                    dash_key=None,
                    title=f"Continuous upper ground: h = {height:g} µm",
                    output_path=run_root
                    / "results"
                    / f"q2d_impedance_three_row__h_{_nm(height)}nm.png",
                )
            )
    else:
        outputs.append(
            _plot_three_rows(
                rows,
                x_key="h_um",
                facet_key="w_um",
                color_key="s_um",
                dash_key="d_um",
                title="Continuous upper ground: flip-chip-height tolerance",
                output_path=run_root / "results" / "q2d_impedance_three_row__height_sweep.png",
            )
        )
    return outputs


def _plot_three_rows(
    rows: list[dict[str, Any]],
    *,
    x_key: str,
    facet_key: str,
    color_key: str,
    dash_key: str | None,
    title: str,
    output_path: Path,
) -> Path:
    symbols = {"w_um": "w", "s_um": "s", "d_um": "d", "h_um": "h"}
    metrics = (
        ("z0_ohm", r"$Z_0$ (Ω)"),
        ("zc_ohm", r"$Z_c$ (Ω)"),
        ("zm_ohm", r"$Z_m$ (Ω)"),
    )
    facets = sorted({float(row[facet_key]) for row in rows})
    colors = sorted({float(row[color_key]) for row in rows})
    dashes = sorted({float(row[dash_key]) for row in rows}) if dash_key else [0.0]
    single_series = len(colors) == 1 and len(dashes) == 1
    dash_map = _dash_styles(dashes)
    norm = Normalize(vmin=min(colors), vmax=max(colors))
    cmap = plt.get_cmap("viridis")
    fig, axes = plt.subplots(
        3,
        len(facets),
        figsize=(6.6 if len(facets) == 1 else 4.4 * len(facets) + 1.2, 10.2),
        squeeze=False,
        sharey="row",
        constrained_layout=True,
    )
    for column, facet in enumerate(facets):
        for row_index, (metric, label) in enumerate(metrics):
            ax = axes[row_index, column]
            if metric == "z0_ohm" and color_key == "d_um":
                subset = [item for item in rows if float(item[facet_key]) == facet]
                unique_by_x = {float(item[x_key]): item for item in subset}
                ordered = [unique_by_x[value] for value in sorted(unique_by_x)]
                ax.plot(
                    [float(item[x_key]) for item in ordered],
                    [float(item[metric]) for item in ordered],
                    color="0.2",
                    marker="o",
                    markersize=3.5,
                )
                if column == 0:
                    ax.text(
                        0.02,
                        0.05,
                        "single reference; independent of d",
                        transform=ax.transAxes,
                        fontsize=8,
                        color="0.3",
                    )
                color_dash_pairs = ()
            else:
                color_dash_pairs = product(colors, dashes)
            for color, dash in color_dash_pairs:
                subset = [
                    item
                    for item in rows
                    if float(item[facet_key]) == facet
                    and float(item[color_key]) == color
                    and (dash_key is None or float(item[dash_key]) == dash)
                ]
                subset.sort(key=lambda item: float(item[x_key]))
                if not subset:
                    continue
                ax.plot(
                    [float(item[x_key]) for item in subset],
                    [float(item[metric]) for item in subset],
                    color="tab:blue" if single_series else cmap(norm(color)),
                    linestyle=dash_map[dash],
                    marker="o",
                    markersize=3.5,
                )
            if metric == "zc_ohm" and color_key == "d_um" and column == 0:
                spreads = []
                for x_value in sorted({float(item[x_key]) for item in rows}):
                    values = [
                        float(item[metric])
                        for item in rows
                        if float(item[facet_key]) == facet and float(item[x_key]) == x_value
                    ]
                    if values:
                        spreads.append((max(values) - min(values)) / (sum(values) / len(values)))
                if spreads:
                    ax.text(
                        0.02,
                        0.05,
                        f"max d spread = {100 * max(spreads):.2f}%",
                        transform=ax.transAxes,
                        fontsize=8,
                        color="0.3",
                    )
            ax.axhline(50, color="0.45", linewidth=0.9, linestyle=":")
            if x_key == "h_um":
                ax.axvspan(7, 8, color="tab:orange", alpha=0.1)
            ax.grid(alpha=0.22)
            if row_index == 0:
                ax.set_title(f"{symbols.get(facet_key, facet_key)} = {facet:g} µm")
            if column == 0:
                ax.set_ylabel(label)
            if row_index == 2:
                ax.set_xlabel(f"{symbols.get(x_key, x_key)} (µm)")
    if len(colors) > 1:
        scalar = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
        scalar.set_array([])
        colorbar = fig.colorbar(scalar, ax=axes, shrink=0.72, pad=0.025)
        colorbar.set_ticks(colors)
        colorbar.set_label(f"{symbols.get(color_key, color_key)} (µm)")
    if dash_key and len(dashes) > 1:
        handles = [
            Line2D([0], [0], color="black", linestyle=dash_map[value], label=f"{value:g}")
            for value in dashes
        ]
        fig.legend(
            handles=handles,
            title=f"{symbols.get(dash_key, dash_key)} (µm)",
            loc="outside upper center",
            ncols=min(6, len(handles)),
        )
    fig.suptitle(title, fontweight="bold")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=220)
    plt.close(fig)
    return output_path


def _float_args(values: list[float] | None, label: str) -> tuple[float, ...]:
    if not values:
        raise ValueError(f"At least one {label} value is required")
    return tuple(values)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--run-root", required=True, type=Path)
    prepare.add_argument("--database", required=True, type=Path)
    prepare.add_argument("--phase-id", required=True)
    prepare.add_argument("--w-um", action="append", type=float)
    prepare.add_argument("--s-um", action="append", type=float)
    prepare.add_argument("--d-um", action="append", type=float)
    prepare.add_argument("--height-um", action="append", type=float)

    ingest = subparsers.add_parser("ingest")
    ingest.add_argument("--run-root", required=True, type=Path)
    ingest.add_argument("--database", required=True, type=Path)

    plot = subparsers.add_parser("plot")
    plot.add_argument("--run-root", required=True, type=Path)

    seeds = subparsers.add_parser("export-length-seeds")
    seeds.add_argument("--database", required=True, type=Path)
    seeds.add_argument("--output-dir", required=True, type=Path)
    seeds.add_argument("--w-um", type=float, default=3.0)
    seeds.add_argument("--s-um", type=float, default=3.0)
    seeds.add_argument("--d-um", type=float, default=3.0)
    seeds.add_argument("--height-um", type=float, default=8.0)

    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare_sweep(
            args.run_root,
            args.database,
            phase_id=args.phase_id,
            widths_um=_float_args(args.w_um, "w"),
            gaps_um=_float_args(args.s_um, "s"),
            center_grounds_um=_float_args(args.d_um, "d"),
            heights_um=_float_args(args.height_um, "height"),
        )
    elif args.command == "ingest":
        result = ingest_sweep(args.run_root, args.database)
    elif args.command == "export-length-seeds":
        result = export_consonant_length_seeds(
            args.database,
            args.output_dir,
            width_um=args.w_um,
            gap_um=args.s_um,
            center_ground_um=args.d_um,
            height_um=args.height_um,
        )
    else:
        result = {"plots": [str(path) for path in plot_sweep(args.run_root)]}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
