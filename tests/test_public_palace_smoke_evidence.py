from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

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
        assert record["resource_status"] == "skipped"
        assert record["resource_nodes"] == 1
        assert record["resource_num_processes"] == 1
        assert record["resource_num_threads"] == 1
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
        assert run_summary["resource"]["status"] == "skipped"
        assert run_summary["resource"]["path"] == (
            f"{problem['output_dir']}/metadata/records/palace_resource_record.json"
        )
        assert run_summary["resource"]["allocation"] == {
            "cores": 1,
            "nodes": 1,
            "num_processes": 1,
            "num_threads": 1,
        }
        assert run_summary["resource"]["runtime"] == {}
        assert run_summary["resource"]["missing_source_count"] == 1
        assert run_summary["resource"]["metadata"] == {
            "fixture": problem["fixture"],
            "measured": False,
            "problem_type": problem["problem_type"],
            "workflow": "public-palace-smoke-evidence",
        }

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
