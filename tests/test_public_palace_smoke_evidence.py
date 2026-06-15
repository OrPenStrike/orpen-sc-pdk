from __future__ import annotations

import json
from pathlib import Path

from scripts.public_palace_smoke_evidence import (
    EVIDENCE_FILENAME,
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

    for problem in evidence["problems"].values():
        output_dir = tmp_path / problem["output_dir"]
        run_summary = problem["run_summary"]

        assert problem["solver_report"]["status"] == "skipped"
        assert output_dir.is_dir()
        assert run_summary["problem_type"] == problem["problem_type"]
        assert run_summary["config"]["problem_type"] == problem["problem_type"]
        assert run_summary["mesh_manifest"]["present"] is True
        assert run_summary["mesh_manifest"]["entry_count"] > 0
        assert run_summary["index_map"]["present"] is True
        assert run_summary["index_map"]["entry_count"] > 0
        assert run_summary["missing_artifacts"] == []

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
