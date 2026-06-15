from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.public_palace_smoke_evidence import (
    EVIDENCE_FILENAME,
    _driven_report_summary,
    build_public_palace_smoke_evidence,
)


def test_public_palace_smoke_evidence_dry_run_writes_artifacts(tmp_path: Path) -> None:
    evidence = build_public_palace_smoke_evidence(tmp_path, environ={})

    evidence_path = tmp_path / EVIDENCE_FILENAME
    saved = json.loads(evidence_path.read_text())

    assert saved == evidence
    assert evidence["schema_version"] == 1
    assert evidence["workflow"] == "public-palace-smoke-evidence"
    assert evidence["solver"]["enabled"] is False
    assert "ORPEN_RUN_LOCAL_PALACE_SMOKE=1" in evidence["solver"]["skip_reason"]
    assert set(evidence["problems"]) == {
        "driven_cpw",
        "eigenmode_resonator",
        "electrostatic_same_layer_capacitor",
    }
    sweep_summary = evidence["sweep_summary"]
    assert sweep_summary["sweep_id"] == "public_palace_problem_type_smoke"
    assert sweep_summary["source_path"] == "points.json"
    assert (tmp_path / "points.csv").is_file()
    assert (tmp_path / "run_sweep_array.sbatch").is_file()
    assert (tmp_path / "palace_sweep_handoff_metadata.json").is_file()
    assert (tmp_path / "palace_sweep_handoff_archive_manifest.json").is_file()
    assert sweep_summary["handoff"]["present"] is True
    assert sweep_summary["handoff"]["status"] == "scripted"
    assert sweep_summary["handoff"]["launcher"] == {
        "array": True,
        "dry_run": True,
        "kind": "slurm",
        "submission": "manual",
    }
    assert sweep_summary["handoff"]["profile"] == {
        "name": "public-slurm-sweep-dry-run",
        "source": "caller-supplied public fixture",
    }
    assert sweep_summary["handoff"]["resources"]["array"] == {
        "point_count": 3,
        "max_parallel": 3,
    }
    assert sweep_summary["handoff"]["resources"]["requested"] == {
        "account": "public_alloc",
        "cpus_per_task": 1,
        "gres": None,
        "memory_mb": None,
        "nodes": 1,
        "ntasks_per_node": 1,
        "num_processes": 1,
        "num_threads": 1,
        "partition": "public_cpu",
        "wall_time": "00:10:00",
    }
    assert (
        sweep_summary["handoff"]["resources"]["resolved"]
        == sweep_summary["handoff"]["resources"]["requested"]
    )
    assert sweep_summary["handoff"]["path"] == "palace_sweep_handoff_metadata.json"
    assert sweep_summary["handoff"]["script"]["path"] == "run_sweep_array.sbatch"
    assert sweep_summary["handoff"]["script_present"] is True
    assert sweep_summary["handoff"]["archive"] == {
        "manifest_path": "palace_sweep_handoff_archive_manifest.json"
    }
    assert sweep_summary["handoff"]["archive_present"] is False
    assert sweep_summary["handoff"]["archive_manifest_present"] is True
    assert sweep_summary["handoff"]["metadata"] == {
        "command_style": "binary",
        "point_count": 3,
        "points_csv_path": "points.csv",
        "points_path": "points.json",
        "script_schema_version": 1,
        "workflow": "public-palace-smoke-evidence",
    }
    assert sweep_summary["handoff"]["command"] == {
        "argv": ["sbatch", "run_sweep_array.sbatch"],
        "redacted": True,
    }
    assert sweep_summary["point_count"] == 3
    assert sweep_summary["point_slugs"] == [
        "driven_cpw",
        "eigenmode_resonator",
        "electrostatic_same_layer_capacitor",
    ]
    assert sweep_summary["duplicate_point_slugs"] == []
    assert sweep_summary["parse_warnings"] == []
    assert sweep_summary["complete_point_count"] == 3
    assert sweep_summary["runtime_present_count"] == 0
    assert sweep_summary["resource_present_count"] == 3
    assert set(sweep_summary["problem_types"]) == {"Driven", "Eigenmode", "Electrostatic"}

    sweep_resource_index = evidence["sweep_resource_index"]
    assert sweep_resource_index == {
        "benchmark_jsonl_path": "metadata/records/sweep_benchmark_index.jsonl",
        "point_count": 3,
        "point_records_csv_path": "metadata/records/sweep_point_records.csv",
        "resource_present_count": 3,
        "resource_records_csv_path": "metadata/records/sweep_resource_records.csv",
        "summary_path": "metadata/records/sweep_resource_index.json",
    }
    for path in (
        sweep_resource_index["summary_path"],
        sweep_resource_index["point_records_csv_path"],
        sweep_resource_index["resource_records_csv_path"],
        sweep_resource_index["benchmark_jsonl_path"],
    ):
        assert (tmp_path / path).is_file()
    index_payload = json.loads((tmp_path / sweep_resource_index["summary_path"]).read_text())
    assert index_payload["sweep_id"] == "public_palace_problem_type_smoke"
    assert index_payload["point_count"] == 3
    assert index_payload["resource_present_count"] == 3
    assert index_payload["records"] == {
        "benchmark_jsonl": "metadata/records/sweep_benchmark_index.jsonl",
        "point_records_csv": "metadata/records/sweep_point_records.csv",
        "resource_records_csv": "metadata/records/sweep_resource_records.csv",
    }
    point_records_csv = (tmp_path / sweep_resource_index["point_records_csv_path"]).read_text()
    resource_records_csv = (
        tmp_path / sweep_resource_index["resource_records_csv_path"]
    ).read_text()
    assert "resource_scheduler_job_id" in point_records_csv
    assert "eigenmode_resonator" in resource_records_csv
    benchmark_jsonl_rows = (
        (tmp_path / sweep_resource_index["benchmark_jsonl_path"]).read_text().splitlines()
    )
    assert len(benchmark_jsonl_rows) == 3
    assert {json.loads(row)["point_slug"] for row in benchmark_jsonl_rows} == {
        "driven_cpw",
        "eigenmode_resonator",
        "electrostatic_same_layer_capacitor",
    }

    assert [point["point_slug"] for point in sweep_summary["points"]] == [
        "driven_cpw",
        "eigenmode_resonator",
        "electrostatic_same_layer_capacitor",
    ]
    point_records = sweep_summary["point_records"]
    assert [record["point_slug"] for record in point_records] == [
        "driven_cpw",
        "eigenmode_resonator",
        "electrostatic_same_layer_capacitor",
    ]
    for record in point_records:
        assert record["sweep_id"] == "public_palace_problem_type_smoke"
        assert record["complete"] is True
        assert record["missing_artifact_count"] == 0
        assert record["core_artifact_count"] == 5
        assert record["core_artifact_bytes"] > 0
        assert record["handoff_present"] is True
        assert record["handoff_status"] == "scripted"
        assert record["handoff_profile_name"] == "public-slurm-dry-run"
        assert record["handoff_script_present"] is True
        assert record["handoff_archive_present"] is False
        assert record["handoff_archive_manifest_present"] is True
        assert record["runtime_present"] is False
        assert record["resource_present"] is True
        assert record["resource_status"] == "synthetic"
        assert record["resource_wall_time_seconds"] == pytest.approx(121.0)
        assert record["resource_core_hours"] == pytest.approx(121.0 / 3600)
        assert record["resource_nodes"] == 1
        assert record["resource_num_processes"] == 1
        assert record["resource_num_threads"] == 1
        assert record["resource_global_unknowns"] == 10718029
        assert record["resource_peak_total_hwm_gib"] == pytest.approx(20.8)
        assert record["resource_scheduler_kind"] == "slurm"
        assert record["resource_scheduler_job_id"] == 12345
        assert record["resource_scheduler_job_state"] == "COMPLETED"
        assert record["resource_scheduler_partition"] == "public_cpu"
        assert record["report_status"] == "missing"
        assert record["report_problem_type"] in {"Driven", "Eigenmode", "Electrostatic"}
        assert record["report_message"]
        assert record["parameter_fixture"]
        assert record["parameter_problem_type"] in {"Driven", "Eigenmode", "Electrostatic"}

    for problem in evidence["problems"].values():
        output_dir = tmp_path / problem["output_dir"]
        run_summary = problem["run_summary"]

        assert problem["solver_report"]["status"] == "skipped"
        assert output_dir.is_dir()
        assert (output_dir / "palace_handoff_metadata.json").is_file()
        assert (output_dir / "palace_handoff_archive_manifest.json").is_file()
        assert (output_dir / "metadata" / "records" / "palace_resource_record.json").is_file()
        assert (output_dir / "metadata" / "records" / "palace_amr_passes.csv").is_file()
        assert (output_dir / "metadata" / "records" / "palace_stage_timing.csv").is_file()
        assert (output_dir / "metadata" / "records" / "palace_stage_memory.csv").is_file()
        assert (output_dir / "metadata" / "scontrol-job-public.txt").is_file()
        assert (output_dir / "logs" / "palace-public-resource.log").is_file()
        assert (output_dir / "run_palace.sbatch").is_file()
        assert run_summary["problem_type"] == problem["problem_type"]
        assert run_summary["config"]["problem_type"] == problem["problem_type"]
        assert run_summary["mesh_manifest"]["present"] is True
        assert run_summary["mesh_manifest"]["entry_count"] > 0
        assert run_summary["index_map"]["present"] is True
        assert run_summary["index_map"]["entry_count"] > 0
        assert run_summary["handoff"]["present"] is True
        assert run_summary["handoff"]["status"] == "scripted"
        assert run_summary["handoff"]["launcher"] == {
            "dry_run": True,
            "kind": "slurm",
            "submission": "manual",
        }
        assert run_summary["handoff"]["profile"] == {
            "name": "public-slurm-dry-run",
            "source": "caller-supplied public fixture",
        }
        assert run_summary["handoff"]["resources"]["requested"] == {
            "account": "public_alloc",
            "cpus_per_task": 1,
            "gres": None,
            "memory_mb": None,
            "nodes": 1,
            "ntasks_per_node": 1,
            "num_processes": 1,
            "num_threads": 1,
            "partition": "public_cpu",
            "wall_time": "00:10:00",
        }
        assert (
            run_summary["handoff"]["resources"]["resolved"]
            == (run_summary["handoff"]["resources"]["requested"])
        )
        assert (
            run_summary["handoff"]["path"]
            == f"{problem['output_dir']}/palace_handoff_metadata.json"
        )
        assert run_summary["handoff"]["script"]["path"] == "run_palace.sbatch"
        assert run_summary["handoff"]["script_present"] is True
        assert run_summary["handoff"]["archive"] == {
            "manifest_path": "palace_handoff_archive_manifest.json"
        }
        assert run_summary["handoff"]["archive_present"] is False
        assert run_summary["handoff"]["archive_manifest_present"] is True
        assert run_summary["handoff"]["metadata"] == {
            "command_style": "binary",
            "fixture": problem["fixture"],
            "problem_type": problem["problem_type"],
            "script_schema_version": 1,
            "solver_enabled": False,
            "workflow": "public-palace-smoke-evidence",
        }
        assert run_summary["handoff"]["command"] == {
            "argv": ["sbatch", "run_palace.sbatch"],
            "redacted": True,
        }
        assert run_summary["missing_artifacts"] == []
        assert run_summary["runtime"]["present"] is False
        assert run_summary["resource"]["present"] is True
        assert run_summary["resource"]["status"] == "synthetic"
        assert run_summary["resource"]["path"] == (
            f"{problem['output_dir']}/metadata/records/palace_resource_record.json"
        )
        assert run_summary["resource"]["allocation"] == {
            "cores": 1,
            "nodes": 1,
            "num_cpus": 1,
            "num_processes": 1,
            "num_tasks": 1,
            "num_threads": 1,
            "cpus_per_task": 1,
            "requested_memory": "1024M",
            "requested_memory_bytes": 1024 * 1024**2,
        }
        assert run_summary["resource"]["runtime"]["wall_time_seconds"] == pytest.approx(121.0)
        assert run_summary["resource"]["runtime"]["core_hours"] == pytest.approx(121.0 / 3600)
        assert run_summary["resource"]["model_size"]["global_unknowns"] == 10718029
        assert run_summary["resource"]["memory"]["peak_total_hwm_gib"] == pytest.approx(20.8)
        assert run_summary["resource"]["solver"] == {
            "device_configuration": "omp,cpu",
            "libceed_backend": "/cpu/self/xsmm/blocked",
            "memory_configuration": "host-std",
            "palace_git_changeset": "v0.16.1",
            "petsc_version": "3.24.3",
        }
        assert run_summary["resource"]["scheduler"] == {
            "end_time": "2026-05-21T18:26:48",
            "job_id": 12345,
            "job_state": "COMPLETED",
            "kind": "slurm",
            "partition": "public_cpu",
            "run_time": "00:02:01",
            "run_time_seconds": 121,
            "start_time": "2026-05-21T18:24:47",
            "submit_time": "2026-05-21T18:16:44",
            "time_limit": "00:10:00",
            "time_limit_seconds": 600,
        }
        assert run_summary["resource"]["source_count"] == 2
        assert (
            run_summary["resource"]["sources"]["palace_log"]["path"]
            == "logs/palace-public-resource.log"
        )
        assert (
            run_summary["resource"]["sources"]["slurm_scontrol"]["path"]
            == "metadata/scontrol-job-public.txt"
        )
        assert run_summary["resource"]["table_count"] == 3
        assert run_summary["resource"]["tables"]["amr_passes"]["row_count"] == 1
        assert run_summary["resource"]["tables"]["stage_timing"]["row_count"] == 8
        assert run_summary["resource"]["tables"]["stage_memory"]["row_count"] == 8
        assert run_summary["resource"]["tables"]["stage_timing"]["path"] == (
            "metadata/records/palace_stage_timing.csv"
        )
        assert run_summary["resource"]["missing_source_count"] == 1
        assert run_summary["resource"]["metadata"] == {
            "fixture": problem["fixture"],
            "measured": False,
            "problem_type": problem["problem_type"],
            "resource_log_source": "synthetic-public-fixture",
            "workflow": "public-palace-smoke-evidence",
        }
        resource_payload = json.dumps(run_summary["resource"])
        assert "public_palace_fixture" not in resource_payload
        assert "public-node" not in resource_payload

        for artifact_name in (
            "palace.msh",
            "config.json",
            "mesh_manifest.json",
            "palace_index_map.json",
            "palace_material_resolution.json",
        ):
            artifact = run_summary["artifacts"][artifact_name]
            assert artifact["present"] is True
            assert artifact["bytes"] > 0
            assert artifact["sha256"]
            assert (tmp_path / artifact["path"]).is_file()

    driven = evidence["problems"]["driven_cpw"]
    driven_summary = driven["run_summary"]
    assert driven_summary["config"]["lumped_port_count"] == 2
    assert "Boundaries.Postprocessing.SurfaceFlux" in driven_summary["index_map"]["sections"]
    assert driven_summary["index_map"]["port_names"] == ["P1", "P2"]

    eigenmode = evidence["problems"]["eigenmode_resonator"]
    eigenmode_summary = eigenmode["run_summary"]
    assert eigenmode_summary["config"]["problem_type"] == "Eigenmode"
    assert "Boundaries.Postprocessing.SurfaceFlux" in eigenmode_summary["index_map"]["sections"]

    electrostatic = evidence["problems"]["electrostatic_same_layer_capacitor"]
    electrostatic_summary = electrostatic["run_summary"]
    assert electrostatic_summary["config"]["terminal_count"] == 2
    assert electrostatic_summary["index_map"]["terminal_names"] == [
        "negative",
        "positive",
    ]


def test_driven_report_summary_uses_sparams_public_keys(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import gsim.palace

    class FakeSParams:
        port_names = ("o1", "o2")
        freq = (4e9, 6e9, 8e9)

        def keys(self) -> list[tuple[str, str]]:
            return [("o1", "o1"), ("o2", "o1")]

        @property
        def data(self):
            raise AssertionError("Use SParams.keys(), not private data storage")

    report = SimpleNamespace(
        sparams=FakeSParams(),
        port_epr=(),
        index_map=(),
        sources=None,
    )
    monkeypatch.setattr(gsim.palace, "load_driven_report", lambda _path: report)

    summary = _driven_report_summary(tmp_path)

    assert summary["status"] == "loaded"
    assert summary["port_names"] == ["o1", "o2"]
    assert summary["frequency_points"] == 3
    assert summary["s_parameter_count"] == 2
