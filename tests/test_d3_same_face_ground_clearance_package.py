from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

import pytest
import yaml

from scripts.build_d3_same_face_ground_clearance_q2d_package import (
    ADAPTIVE_FREQUENCY,
    AIR_HEIGHT_UM,
    D0_DIE_THICKNESS_UM,
    D1_DIE_THICKNESS_UM,
    FLIP_CHIP_GAP_HEIGHT_UM,
    GROUND_WIDTH_UM,
    INTER_TRACE_GROUND_WIDTHS_UM,
    METAL_THICKNESS_UM,
    TRACE_GAP_UM,
    TRACE_WIDTH_UM,
    UPPER_GROUND_CLEARANCE_WIDTHS_UM,
    build_package,
)
from scripts.export_orpen_q2d_intrinsic_purcell_cases import (
    PendingQ2dArtifactError,
    export_cases,
)


def _load_package(run_root: Path) -> tuple[dict, dict]:
    manifest = yaml.safe_load((run_root / "manifest.yaml").read_text(encoding="utf-8"))
    points = json.loads((run_root / "points.json").read_text(encoding="utf-8"))
    return manifest, points


def test_d3_package_has_exact_public_cases_topologies_and_ledgers(tmp_path: Path) -> None:
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.run_aedt_native import (
        q2d_semantic_geometry_plan,
        validate_runtime_q2d_cross_section_payload,
    )

    run_root = tmp_path / "2026-07-20-Run01"
    result = build_package(run_root)
    manifest, point_ledger = _load_package(run_root)
    point_rows = point_ledger["points"]

    expected_pair_ids = [
        f"coupled_pair__d_{d:.2f}um__clearance_{int(clearance):03d}um".replace(".", "p")
        for d in INTER_TRACE_GROUND_WIDTHS_UM
        for clearance in UPPER_GROUND_CLEARANCE_WIDTHS_UM
    ]
    expected_single_ids = [
        f"single_reference__clearance_{int(clearance):03d}um"
        for clearance in UPPER_GROUND_CLEARANCE_WIDTHS_UM
    ]
    expected_ids = expected_pair_ids + expected_single_ids

    assert result.case_count == 12
    assert result.recipe_count == 12
    assert manifest["project"]["name"] == "d3_same_face_ground_clearance_q2d"
    assert manifest["execution"]["point_local_sweep"] is True
    assert [case["id"] for case in manifest["cases"]] == expected_ids
    assert [row["point_slug"] for row in point_rows] == expected_ids
    assert Counter(row["parameter_case_role"] for row in point_rows) == {
        "coupled_pair": 9,
        "single_reference": 3,
    }

    expected_common = {
        "parameter_trace_width_um": TRACE_WIDTH_UM,
        "parameter_trace_gap_um": TRACE_GAP_UM,
        "parameter_flip_chip_gap_height_um": FLIP_CHIP_GAP_HEIGHT_UM,
        "parameter_d0_die_thickness_um": D0_DIE_THICKNESS_UM,
        "parameter_d1_die_thickness_um": D1_DIE_THICKNESS_UM,
        "parameter_air_height_um": AIR_HEIGHT_UM,
        "parameter_ground_width_um": GROUND_WIDTH_UM,
        "parameter_metal_thickness_um": METAL_THICKNESS_UM,
        "parameter_adaptive_frequency": ADAPTIVE_FREQUENCY,
    }
    for row in point_rows:
        assert {key: row[key] for key in expected_common} == expected_common
        assert row["parameter_upper_ground_clearance_width_um"] in (
            UPPER_GROUND_CLEARANCE_WIDTHS_UM
        )
        if row["parameter_case_role"] == "coupled_pair":
            assert row["parameter_inter_trace_ground_width_um"] in (INTER_TRACE_GROUND_WIDTHS_UM)
        else:
            assert row["parameter_inter_trace_ground_width_um"] is None

    csv_rows = list(csv.DictReader((run_root / "points.csv").open(encoding="utf-8")))
    assert [row["point_slug"] for row in csv_rows] == expected_ids
    assert {row["parameter_case_role"] for row in csv_rows} == {
        "coupled_pair",
        "single_reference",
    }
    assert {float(row["parameter_upper_ground_clearance_width_um"]) for row in csv_rows} == set(
        UPPER_GROUND_CLEARANCE_WIDTHS_UM
    )

    points_by_id = {row["point_slug"]: row for row in point_rows}
    for case in manifest["cases"]:
        recipes = case["recipes"]
        assert len(recipes) == 1
        recipe = recipes[0]
        assert recipe["id"] == "q2d"
        assert recipe["type"] == "q2d_extraction"
        assert recipe["q2d_geometry_mode"] == "semantic_cross_section"
        assert recipe["section_plane"] == "XY"
        assert recipe["matrix_problem_types"] == ["CG", "RL"]
        assert recipe["matrix_types"] == ["Maxwell"]
        assert recipe["q2d_setup"]["adaptive_frequency"] == "6GHz"

        sidecar_path = run_root / case["q2d_cross_section"]
        payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
        stack = payload["stack"]
        assert [element["kind"] for element in stack] == [
            "air",
            "die",
            "die_gap",
            "die",
            "air",
        ]
        die_rows = [
            (stack[1]["id"], stack[1]["thickness_um"]),
            (stack[3]["id"], stack[3]["thickness_um"]),
        ]
        assert die_rows == [
            ("D0", 500.0),
            ("D1", 500.0),
        ]
        assert stack[2]["height_um"] == 7.0
        assert stack[0]["height_um"] == stack[4]["height_um"] == 200.0

        trace_locations = [
            (segment["name"], pattern["die"], pattern["face"])
            for pattern in payload["face_patterns"]
            for segment in pattern["segments"]
            if segment["kind"] == "trace"
        ]
        point = points_by_id[case["id"]]
        expected_traces = (
            [("T1", "D0", "top"), ("T2", "D0", "top")]
            if point["parameter_case_role"] == "coupled_pair"
            else [("T1", "D0", "top")]
        )
        assert trace_locations == expected_traces

        d1_pattern = next(
            pattern
            for pattern in payload["face_patterns"]
            if (pattern["die"], pattern["face"]) == ("D1", "bottom")
        )
        assert [segment["kind"] for segment in d1_pattern["segments"]] == [
            "ground",
            "gap",
            "ground",
        ]
        clearance = d1_pattern["segments"][1]
        assert clearance["role"] == "upper_ground_clearance"
        assert clearance["width_um"] == point["parameter_upper_ground_clearance_width_um"]

        plan = q2d_semantic_geometry_plan(
            validate_runtime_q2d_cross_section_payload(payload, case["id"])
        )
        assert [
            name
            for name, assignment in plan["assignments"].items()
            if assignment["conductor_type"] == "Reference Ground"
        ] == ["Ground"]
        assert [
            name
            for name, assignment in plan["assignments"].items()
            if assignment["conductor_type"] == "Signal Line"
        ] == [trace[0] for trace in expected_traces]

    audit = json.loads(
        (run_root / "metadata" / "d3_same_face_ground_clearance_package_audit.json").read_text(
            encoding="utf-8"
        )
    )
    assert audit["status"] == "package_ready_solver_pending"
    assert audit["case_roles"] == {"coupled_pair": 9, "single_reference": 3}
    assert audit["matrix_contract"]["coupled_pair_shape"] == [2, 2]
    assert audit["matrix_contract"]["single_reference_shape"] == [1, 1]
    assert audit["matrix_contract"]["solver_results_generated"] is False
    assert len(audit["manifest"]["sha256"]) == 64
    assert not (run_root / "results").exists()
    assert not any(run_root.rglob("*_matrix.csv"))


def test_d3_package_requires_explicit_safe_overwrite(tmp_path: Path) -> None:
    run_root = tmp_path / "2026-07-20-Run02"
    build_package(run_root)
    manifest_before = (run_root / "manifest.yaml").read_bytes()

    with pytest.raises(FileExistsError):
        build_package(run_root)
    assert (run_root / "manifest.yaml").read_bytes() == manifest_before

    first_case_id = json.loads((run_root / "points.json").read_text())["points"][0]["point_slug"]
    protected_files = {
        run_root / "results" / "sentinel.txt": "result",
        run_root / "logs" / "sentinel.txt": "log",
        run_root / "points" / first_case_id / "q2d" / "sentinel.txt": "point",
    }
    for path, content in protected_files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    build_package(run_root, overwrite=True)

    assert {path: path.read_text(encoding="utf-8") for path in protected_files} == (protected_files)
    audit = json.loads(
        (run_root / "metadata" / "d3_same_face_ground_clearance_package_audit.json").read_text(
            encoding="utf-8"
        )
    )
    assert audit["overwrite"]["requested"] is True
    assert audit["overwrite"]["protected_inventory_unchanged"] is True
    assert audit["overwrite"]["protected_file_counts"] == {
        "results": 1,
        "logs": 1,
        "points": 1,
    }


def _write_matrix(
    path: Path,
    terminals: tuple[str, ...],
    values: tuple[tuple[float, ...], ...],
    *,
    quantity: str,
) -> None:
    unit_line = (
        "C Units:pF/meter, G Units:mho/meter"
        if quantity == "C"
        else "L Units:nH/meter, R Units:ohm/meter"
    )
    title = "Capacitance Matrix" if quantity == "C" else "Inductance Matrix"
    path.write_text(
        "\n".join(
            [
                "Setup1:LastAdaptive",
                unit_line,
                "Reduce Matrix: Original",
                "Frequency: 6GHz",
                "",
                title,
                "," + ",".join(terminals),
                *[
                    f"{terminal}," + ",".join(str(value) for value in row)
                    for terminal, row in zip(terminals, values, strict=True)
                ],
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _complete_case(
    run_root: Path,
    case_id: str,
    *,
    terminals: tuple[str, ...],
    c_values: tuple[tuple[float, ...], ...] | None = None,
    l_values: tuple[tuple[float, ...], ...] | None = None,
) -> None:
    result_dir = run_root / "points" / case_id / "q2d"
    result_dir.mkdir(parents=True, exist_ok=True)
    if c_values is None:
        c_values = ((100.0, -20.0), (-20.0, 110.0)) if terminals == ("T1", "T2") else ((95.0,),)
    if l_values is None:
        l_values = ((400.0, 80.0), (80.0, 420.0)) if terminals == ("T1", "T2") else ((390.0,),)
    matrix_paths = (
        result_dir / "cg_maxwell_matrix.csv",
        result_dir / "rl_maxwell_matrix.csv",
    )
    _write_matrix(matrix_paths[0], terminals, c_values, quantity="C")
    _write_matrix(matrix_paths[1], terminals, l_values, quantity="L")

    (result_dir / "assignment_summary.json").write_text(
        json.dumps(
            {
                "recipe_type": "q2d_extraction",
                "assignment_source": "semantic_cross_section",
                "assignments": [
                    {"assignment_name": "Ground", "conductor_type": "Reference Ground"},
                    *[
                        {"assignment_name": name, "conductor_type": "Signal Line"}
                        for name in terminals
                    ],
                ],
            }
        ),
        encoding="utf-8",
    )
    (result_dir / "simulation_metadata.json").write_text(
        json.dumps(
            {
                "recipe_type": "q2d_extraction",
                "q2d_geometry_mode": "semantic_cross_section",
                "solve_status": {
                    "analyze_setup": {"return_value": True},
                    "matrix_exports": [
                        {
                            "file_name": str(path),
                            "return_value": True,
                            "file_size": path.stat().st_size,
                        }
                        for path in matrix_paths
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    preflight = run_root / "logs" / "workers" / f"{case_id}__q2d" / "aedt_preflight.json"
    preflight.parent.mkdir(parents=True, exist_ok=True)
    preflight.write_text(
        json.dumps({"aedt_version": "2024.2", "pyaedt_version": "0.26.2"}),
        encoding="utf-8",
    )


def test_d3_exporter_requires_material_schema_before_matrix_validation(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "2026-07-20-Run03"
    build_package(run_root)
    _, point_ledger = _load_package(run_root)
    case_id = next(
        row["point_slug"]
        for row in point_ledger["points"]
        if row["parameter_case_role"] == "coupled_pair"
    )
    _complete_case(
        run_root,
        case_id,
        terminals=("T1", "T2"),
        l_values=((400.0, 500.0), (500.0, 400.0)),
    )
    output = tmp_path / f"{case_id}.json"

    with pytest.raises(PendingQ2dArtifactError, match="schema omits material authority"):
        export_cases(run_root, output, case_ids=(case_id,))

    assert not output.exists()


def test_d3_exporter_is_pending_for_explicit_material_single_and_pair(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "2026-07-20-Run03"
    build_package(run_root)
    _, point_ledger = _load_package(run_root)
    pair_id = next(
        row["point_slug"]
        for row in point_ledger["points"]
        if row["parameter_case_role"] == "coupled_pair"
    )
    single_id = next(
        row["point_slug"]
        for row in point_ledger["points"]
        if row["parameter_case_role"] == "single_reference"
    )

    for case_id in (pair_id, single_id):
        output = tmp_path / f"{case_id}.json"
        with pytest.raises(PendingQ2dArtifactError, match="schema omits material authority"):
            export_cases(run_root, output, case_ids=(case_id,))
        assert not output.exists()
