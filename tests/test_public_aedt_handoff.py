from __future__ import annotations

import json
import signal
import socket
import subprocess
import sys
import tarfile
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import orpen_sc_pdk.simulation.aedt as public_aedt
from orpen_sc_pdk.simulation import (
    AedtHpcProfileSpec,
    AedtHpcResourceSpec,
    AedtHpcValidationSpec,
    AedtNativeCaseSpec,
    AedtNativePackageSpec,
    AedtQ2dMatrixProblemType,
    AedtQ3dMatrixProblemType,
    AedtRecipeSpec,
    package_aedt_native_handoff,
    prepare_aedt_native_handoff_package,
)


def test_aedt_hpc_default_memory_total_is_240gb() -> None:
    assert AedtHpcResourceSpec().memory_mb_total == 240000


def test_private_repo_can_generate_aedt_handoff_with_custom_profile(tmp_path: Path) -> None:
    source_dir = tmp_path / "private_artifacts"
    source_dir.mkdir()
    _write_public_aedt_case_artifacts(source_dir, "cpw")

    profile = AedtHpcProfileSpec(
        profile_name="private-lab-node",
        resource_defaults={
            "machine_name": "workstation-a",
            "num_cores": 16,
            "max_workers": 2,
            "memory_mb_per_worker": 96000,
        },
        validation=AedtHpcValidationSpec(core_budget=32, memory_mb_total=256000),
    )
    spec = AedtNativePackageSpec(
        project_name="private_cpw",
        hpc_profile=profile,
        cases=(
            AedtNativeCaseSpec(
                id="cpw",
                gds_path=source_dir / "cpw.gds",
                tech_path=source_dir / "cpw.tech",
                control_path=source_dir / "cpw.xml",
                layer_mapping_json_path=source_dir / "cpw_layer_mapping.json",
                q2d_conductors_json_path=source_dir / "cpw_q2d_conductors.json",
                recipes=(
                    AedtRecipeSpec(
                        id="q2d",
                        type="q2d_extraction",
                        assignment_source="q2d_conductors",
                    ),
                ),
            ),
        ),
    )

    run_dir = tmp_path / "exports" / "2026-07-04-Run01"
    result = prepare_aedt_native_handoff_package(spec, package_dir=run_dir)
    existing_matrix = result.package_dir / "results" / "cpw" / "q2d" / "cg_maxwell_matrix.csv"
    existing_matrix.parent.mkdir(parents=True)
    existing_matrix.write_text("solved", encoding="utf-8")
    result = prepare_aedt_native_handoff_package(spec, package_dir=run_dir)
    assert existing_matrix.read_text(encoding="utf-8") == "solved"
    manifest = yaml.safe_load(result.manifest_path.read_text(encoding="utf-8"))
    material_context = json.loads(
        (result.metadata_dir / "cpw_aedt_material_context.json").read_text(encoding="utf-8")
    )

    assert manifest["hpc"]["profile"] == "private-lab-node"
    assert manifest["hpc"]["resource"]["machine_name"] == "workstation-a"
    assert manifest["hpc"]["resource"]["worker_core_total"] == 32
    assert manifest["hpc"]["resource"]["ram_percent_resolved"] == 37
    assert manifest["cases"][0]["q2d_conductors"] == "metadata/cpw_q2d_conductors.json"
    assert {binding["aedt_material_name"] for binding in material_context["bindings"]} == {
        "pec",
        "Silicon",
    }
    readme = result.readme_path.read_text(encoding="utf-8")
    assert "from ansys.aedt.core" in readme
    assert "manifest.yaml points.csv" in readme
    assert "metadata logs results points" in readme
    assert "--exclude='points/*'" not in readme
    assert "--exclude='points/*/exports/*'" in readme
    assert "--exclude='points/*/mesh.msh'" in readme
    assert "--exclude='*/aedt_project/*'" in readme
    assert (result.scripts_dir / "runtime_bundle" / "run_aedt_native.py").is_file()
    assert "runtime_bundle.run_aedt_native" in result.python_script_path.read_text(encoding="utf-8")
    shell_launcher = result.bash_script_path.read_text(encoding="utf-8")
    assert 'PYTHON_BIN="${PYTHON:-python3}"' in shell_launcher
    assert 'exec "$PYTHON_BIN" "$SCRIPT_DIR/run_aedt_native.py" "$@"' in shell_launcher
    runtime_text = (result.scripts_dir / "runtime_bundle" / "run_aedt_native.py").read_text(
        encoding="utf-8"
    )
    assert "PyAEDT" in runtime_text
    assert 'parents[2] / "manifest.yaml"' in runtime_text
    help_run = subprocess.run(
        [sys.executable, str(result.python_script_path), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert help_run.returncode == 0, help_run.stderr

    archive = package_aedt_native_handoff(
        result,
        archive_path=run_dir.parent / f"{run_dir.name}-aedt.tar.gz",
    )

    with tarfile.open(archive.archive_path, "r:gz") as tar:
        names = set(tar.getnames())
    assert archive.archive_path.name == "2026-07-04-Run01-aedt.tar.gz"
    assert "2026-07-04-Run01/manifest.yaml" in names
    assert "aedt_native/manifest.yaml" not in names
    assert not any(name.startswith("exports/") for name in names)
    assert any(name.endswith("scripts/run_aedt_native.py") for name in names)
    assert any(name.endswith("scripts/runtime_bundle/run_aedt_native.py") for name in names)

    (result.scripts_dir / "runtime_bundle" / "session.py").unlink()
    with pytest.raises(FileNotFoundError, match="runtime bundle file session.py"):
        package_aedt_native_handoff(result, archive_path=tmp_path / "bad.tar.gz")


def test_legacy_native_2d_recipe_is_rejected() -> None:
    with pytest.raises(ValueError, match="q2d_geometry_mode"):
        AedtRecipeSpec(
            id="q2d",
            type="q2d_extraction",
            assignment_source="q2d_conductors",
            q2d_geometry_mode="native_2d",
        )


def test_semantic_cross_section_sidecar_is_packaged(tmp_path: Path) -> None:
    from orpen_sc_pdk.simulation.aedt import (
        Air,
        Die,
        DieGap,
        FacePattern,
        Gap,
        Ground,
        Q2dSemanticCrossSection,
        Stack,
        Trace,
        write_q2d_cross_section_payload,
    )

    source_dir = tmp_path / "private_artifacts"
    source_dir.mkdir()
    cross_section_path = write_q2d_cross_section_payload(
        source_dir / "semantic_q2d_cross_section.json",
        Q2dSemanticCrossSection(
            stack=Stack(
                (
                    Air(height_um=100),
                    Die(id="D0", thickness_um=500, material="Silicon"),
                    DieGap(height_um=8),
                    Die(id="D1", thickness_um=500, material="Silicon"),
                    Air(height_um=100),
                )
            ),
            face_patterns=(
                FacePattern(
                    die="D0",
                    face="top",
                    metal_thickness_um=0.2,
                    segments=(
                        Ground(width_um=50),
                        Gap(width_um=6),
                        Trace("T1", width_um=7),
                        Gap(width_um=6),
                        Ground(width_um=50),
                    ),
                ),
            ),
        ),
    )
    spec = AedtNativePackageSpec(
        project_name="semantic_q2d",
        cases=(
            AedtNativeCaseSpec(
                id="semantic",
                q2d_cross_section_json_path=cross_section_path,
                recipes=(
                    AedtRecipeSpec(
                        id="q2d",
                        type="q2d_extraction",
                        q2d_geometry_mode="semantic_cross_section",
                    ),
                ),
            ),
        ),
    )

    result = prepare_aedt_native_handoff_package(
        spec,
        package_dir=tmp_path / "exports" / "aedt_native",
    )
    manifest = yaml.safe_load(result.manifest_path.read_text(encoding="utf-8"))
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.io import load_manifest
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.run_aedt_native import (
        q2d_semantic_geometry_plan,
        validate_runtime_q2d_cross_section_payload,
    )

    assert manifest["cases"][0]["gds"] is None
    assert manifest["cases"][0]["tech"] is None
    assert manifest["cases"][0]["q2d_cross_section"] == ("metadata/semantic_q2d_cross_section.json")
    assert (result.metadata_dir / "semantic_q2d_cross_section.json").is_file()
    assert load_manifest(result.manifest_path)["cases"][0]["q2d_cross_section"]
    payload = json.loads(
        (result.metadata_dir / "semantic_q2d_cross_section.json").read_text(encoding="utf-8")
    )
    plan = q2d_semantic_geometry_plan(validate_runtime_q2d_cross_section_payload(payload, "test"))
    assert {item["name"] for item in plan["rectangles"]} >= {
        "q2d_die_D0",
        "q2d_die_D1",
        "q2d_fp00_D0_top_00_ground",
        "q2d_fp00_D0_top_02_trace_T1",
    }
    assert plan["assignments"]["Ground"]["conductor_type"] == "Reference Ground"
    assert plan["assignments"]["T1"]["conductor_type"] == "Signal Line"
    assert plan["region_padding_um"]["+Y"] == 100.0
    assert plan["region_padding_um"]["-Y"] == 100.0


def test_layout_backed_recipe_requires_gds_and_tech() -> None:
    with pytest.raises(ValueError, match="requires gds_path and tech_path"):
        AedtNativeCaseSpec(
            id="layout_backed",
            recipes=(
                AedtRecipeSpec(
                    id="q2d",
                    type="q2d_extraction",
                    signal_patterns=("Signal*",),
                    ground_patterns=("Ground*",),
                ),
            ),
        )


def test_point_local_parallel_handoff_fails_before_mixed_recipe_package(tmp_path: Path) -> None:
    source_dir = tmp_path / "private_artifacts"
    source_dir.mkdir()
    _write_public_aedt_case_artifacts(source_dir, "cpw")

    spec = AedtNativePackageSpec(
        project_name="mixed_parallel",
        point_local_sweep=True,
        cases=(
            AedtNativeCaseSpec(
                id="cpw",
                gds_path=source_dir / "cpw.gds",
                tech_path=source_dir / "cpw.tech",
                control_path=source_dir / "cpw.xml",
                layer_mapping_json_path=source_dir / "cpw_layer_mapping.json",
                q2d_conductors_json_path=source_dir / "cpw_q2d_conductors.json",
                recipes=(
                    AedtRecipeSpec(
                        id="q2d",
                        type="q2d_extraction",
                        assignment_source="q2d_conductors",
                    ),
                    AedtRecipeSpec(id="hfss", type="hfss_eigenmode", mode_count=1),
                ),
            ),
        ),
    )

    with pytest.raises(ValueError, match="q2d_extraction recipes only"):
        prepare_aedt_native_handoff_package(spec, package_dir=tmp_path / "exports/aedt_native")


def test_point_local_import_uses_one_core_workers_while_solve_keeps_resource(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "private_artifacts"
    source_dir.mkdir()
    _write_public_aedt_case_artifacts(source_dir, "cpw")
    spec = AedtNativePackageSpec(
        project_name="parallel_q2d",
        point_local_sweep=True,
        hpc_resource=AedtHpcResourceSpec(
            num_cores=4,
            max_workers=7,
            core_budget=28,
            memory_mb_total=240000,
        ),
        cases=(
            AedtNativeCaseSpec(
                id="cpw",
                gds_path=source_dir / "cpw.gds",
                tech_path=source_dir / "cpw.tech",
                control_path=source_dir / "cpw.xml",
                layer_mapping_json_path=source_dir / "cpw_layer_mapping.json",
                q2d_conductors_json_path=source_dir / "cpw_q2d_conductors.json",
                recipes=(
                    AedtRecipeSpec(
                        id="q2d",
                        type="q2d_extraction",
                        assignment_source="q2d_conductors",
                    ),
                ),
            ),
        ),
    )

    result = prepare_aedt_native_handoff_package(spec, package_dir=tmp_path / "exports/aedt")
    import_config = yaml.safe_load(
        (result.package_dir / "run_configs" / "import.yaml").read_text(encoding="utf-8")
    )
    solve_config = yaml.safe_load(
        (result.package_dir / "run_configs" / "solve.yaml").read_text(encoding="utf-8")
    )

    assert import_config["num_cores"] == 1
    assert import_config["max_workers"] == 28
    assert import_config["core_budget"] == 28
    assert import_config["resume_policy"] == "skip_completed_retry_failed"
    assert import_config["skip_completed"] is True
    assert import_config["continue_on_failure"] is True
    assert solve_config["num_cores"] == 4
    assert solve_config["max_workers"] == 7
    assert solve_config["core_budget"] == 28


def test_point_local_import_resume_skips_existing_worker_project(tmp_path: Path) -> None:
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.sweep import should_skip_recipe_for_resume

    worker_project = tmp_path / "points" / "point_a" / "aedt_project" / "point_a.aedt"
    worker_project.parent.mkdir(parents=True)
    worker_project.write_text("", encoding="utf-8")

    status = should_skip_recipe_for_resume(
        tmp_path / "points" / "point_a" / "q2d",
        tmp_path / "logs" / "point_a" / "q2d",
        {"type": "q2d_extraction"},
        SimpleNamespace(
            mode="import",
            resume_policy="skip_completed_retry_failed",
            skip_completed=True,
        ),
        lambda _result_dir, _log_dir, _recipe: {"completion_status": "failed"},
        worker_project=worker_project,
    )

    assert status["completion_status"] == "import_complete"
    assert status["skip_reason"] == "import_project_exists"


def test_parallel_worker_port_allocator_skips_occupied_port() -> None:
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.sweep import allocate_worker_ports

    occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        for port in range(41000, 41100):
            try:
                occupied.bind(("127.0.0.1", port))
                break
            except OSError:
                continue
        else:
            pytest.skip("no free local port in AEDT test range")

        ports = allocate_worker_ports(port, 2)

        assert len(ports) == 2
        assert port not in ports
    finally:
        occupied.close()


def test_parallel_aedt_worker_command_uses_leased_grpc_port(tmp_path: Path) -> None:
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.sweep import parallel_worker_command

    args = SimpleNamespace(
        mode="import",
        resume_policy="run_all",
        worker_project_root=None,
        skip_completed=False,
        continue_on_failure=False,
        force_rebuild=False,
        non_graphical=True,
        aedt_version=None,
        grpc_port=None,
        grpc_mode=None,
        grpc_local=None,
        acf_file=None,
        num_cores=4,
        max_workers=7,
        memory_mb_total=240000,
        memory_mb_per_worker=None,
        ram_percent=None,
        core_budget=28,
    )

    commands = [
        parallel_worker_command(
            tmp_path / "manifest.yaml",
            args,
            case={"id": f"point_{index}"},
            recipe={"id": "q2d"},
            results_root=tmp_path / "points",
            logs_root=tmp_path / "logs",
            worker_log_root=tmp_path / "logs" / "workers" / f"point_{index}",
            worker_project_root=tmp_path / "points",
            grpc_port=41042 + index,
        )
        for index in range(2)
    ]
    ports = [command[command.index("--grpc-port") + 1] for command in commands]
    memory_totals = [command[command.index("--memory-mb-total") + 1] for command in commands]

    assert ports == ["41042", "41043"]
    assert memory_totals == ["240000", "240000"]
    assert all("--close-desktop" in command for command in commands)


def test_parallel_progress_line_reports_active_worker_context() -> None:
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.sweep import (
        format_parallel_progress_line,
    )

    line = format_parallel_progress_line(
        {
            "total": 6864,
            "done": 7,
            "queued": 14,
            "active": 7,
            "max_workers": 7,
            "pending": 6850,
            "skipped": 0,
            "failed": 0,
            "aborted": 7,
            "elapsed_seconds": 65,
            "eta_seconds": None,
            "oldest_active_seconds": 42,
            "active_sample": ("horizontal_offset_um_0.0__trace_gap_um_3.0__central_width_um_3.0"),
            "stage_counts": {"session_start": 7},
        }
    )

    assert "done=7/6864" in line
    assert "workers=7/7" in line
    assert "launched=14" in line
    assert "pending=6850" in line
    assert "queued=" not in line
    assert "running<=" not in line
    assert "aborted=" not in line
    assert "oldest=42s" in line
    assert "sample=horizontal_offset_um_0.0" in line
    assert "stages=session_start:7" in line

    skipped_line = format_parallel_progress_line(
        {
            "total": 1,
            "done": 1,
            "queued": 0,
            "active": 0,
            "max_workers": 28,
            "pending": 0,
            "failed": 0,
            "elapsed_seconds": 0,
        }
    )
    assert "pending=0" in skipped_line


def test_parallel_progress_done_does_not_count_aborted(tmp_path: Path) -> None:
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.sweep import ParallelProgressReporter

    progress = ParallelProgressReporter(
        total=100,
        max_workers=7,
        mode="off",
        interval_seconds=1,
        log_path=tmp_path / "progress.jsonl",
    )
    progress.complete = 7
    progress.aborted = 3

    assert progress.snapshot()["done"] == 7


def test_parallel_progress_modes_choose_tty_overwrite_or_stream(tmp_path: Path) -> None:
    import contextlib
    import io

    from orpen_sc_pdk.simulation.aedt.runtime_bundle.sweep import ParallelProgressReporter

    class TtyBuffer(io.StringIO):
        def isatty(self) -> bool:
            return True

    tty_output = TtyBuffer()
    with contextlib.redirect_stdout(tty_output):
        ParallelProgressReporter(
            total=1,
            max_workers=1,
            mode="auto",
            interval_seconds=1,
            log_path=tmp_path / "auto.jsonl",
        ).render(force=True)
    assert tty_output.getvalue().startswith("\r")

    stream_output = TtyBuffer()
    with contextlib.redirect_stdout(stream_output):
        ParallelProgressReporter(
            total=1,
            max_workers=1,
            mode="stream",
            interval_seconds=1,
            log_path=tmp_path / "stream.jsonl",
        ).render(force=True)
    assert stream_output.getvalue().startswith("AEDT parallel")

    off_output = TtyBuffer()
    with contextlib.redirect_stdout(off_output):
        ParallelProgressReporter(
            total=1,
            max_workers=1,
            mode="off",
            interval_seconds=1,
            log_path=tmp_path / "off.jsonl",
        ).render(force=True)
    assert off_output.getvalue() == ""


def test_parallel_axis_coverage_ignores_parameter_id(tmp_path: Path) -> None:
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.sweep import parallel_axis_coverage

    tmp_path.joinpath("points.json").write_text(
        json.dumps(
            {
                "points": [
                    {
                        "point_slug": "point_a",
                        "parameter_id": "width=3",
                        "parameter_width_um": 3,
                    },
                    {
                        "point_slug": "point_b",
                        "parameter_id": "width=5",
                        "parameter_width_um": 5,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    manifest = {"cases": [{"id": "point_a"}, {"id": "point_b"}]}
    coverage = parallel_axis_coverage(
        manifest,
        tmp_path,
        [({"id": "point_a"}, {"id": "q2d"}), ({"id": "point_b"}, {"id": "q2d"})],
    )

    assert [record["axis"] for record in coverage] == ["parameter_width_um"]
    assert coverage[0]["unique_count"] == 2


def test_parallel_worker_subprocess_can_be_terminated(tmp_path: Path) -> None:
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.sweep import (
        cleanup_worker_process_group,
        signal_worker_process,
        start_worker_subprocess,
        wait_for_processes,
        worker_abort_command,
    )

    process, stdout = start_worker_subprocess(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        tmp_path / "worker_stdout.log",
    )
    try:
        time.sleep(0.2)
        signal_worker_process(process, signal.SIGINT)
        wait_for_processes([process], 5)
        assert process.poll() is not None
        assert process.returncode != 0
    finally:
        if process.poll() is None:
            signal_worker_process(process, signal.SIGKILL)
        stdout.close()

    args = SimpleNamespace(aedt_version="2024.2", grpc_mode="secure", grpc_local="true")
    command = worker_abort_command(args, 41000)
    assert "--abort-worker" in command
    assert command[command.index("--grpc-port") + 1] == "41000"
    assert "--grpc-secure" in command

    child_pid_path = tmp_path / "child.pid"
    process, stdout = start_worker_subprocess(
        [
            sys.executable,
            "-c",
            (
                "import pathlib, subprocess, sys; "
                "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
                f"pathlib.Path({str(child_pid_path)!r}).write_text(str(child.pid))"
            ),
        ],
        tmp_path / "worker_with_child_stdout.log",
    )
    try:
        wait_for_processes([process], 5)
        child_pid = int(child_pid_path.read_text(encoding="utf-8"))
        cleanup_worker_process_group(process)
        time.sleep(0.2)
        assert subprocess.run(["ps", "-p", str(child_pid)], check=False).returncode != 0
    finally:
        stdout.close()


def test_aedt_runtime_bundle_keeps_general_v1_and_solver_boundaries(
    tmp_path: Path,
) -> None:
    from orpen_sc_pdk.simulation.aedt.models import AedtRecipeType
    from orpen_sc_pdk.simulation.aedt.package import prepare_aedt_native_handoff_package
    from orpen_sc_pdk.simulation.aedt.runtime_bundle import (
        create_aedt_session,
        load_manifest,
        register_aedt_materials,
        run_point_local_sweep,
    )
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.session import finalize_aedt_session
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.solver.hfss.driven_terminal import (
        run_hfss_driven_terminal,
    )
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.solver.hfss.eigenmode import (
        run_hfss_eigenmode,
    )
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.solver.q2d.assignment import (
        assign_q2d_conductors,
    )
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.solver.q2d.audit import write_q2d_audit
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.solver.q2d.export import (
        export_q2d_results,
    )
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.solver.q2d.geometry import (
        build_q2d_geometry,
    )
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.solver.q2d.region import (
        create_q2d_region,
    )
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.solver.q2d.setup import create_q2d_setup
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.solver.q2d.solve import solve_q2d
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.solver.q2d.state import (
        validate_q2d_state,
    )
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.solver.q2d.workflow import (
        run_q2d_workflow,
    )
    from orpen_sc_pdk.simulation.aedt.runtime_bundle.solver.q3d import run_q3d_extraction

    scaffold_root = Path(public_aedt.__file__).parent / "runtime_bundle"
    aedt_root = Path(public_aedt.__file__).parent
    expected_scaffold = {
        "io.py",
        "materials.py",
        "session.py",
        "sweep.py",
        "solver/hfss/driven_terminal.py",
        "solver/hfss/eigenmode.py",
        "solver/q3d.py",
        "solver/q2d/workflow.py",
        "solver/q2d/state.py",
        "solver/q2d/geometry.py",
        "solver/q2d/assignment.py",
        "solver/q2d/region.py",
        "solver/q2d/setup.py",
        "solver/q2d/solve.py",
        "solver/q2d/export.py",
        "solver/q2d/audit.py",
    }

    assert repr(public_aedt.AedtRecipeType) == repr(AedtRecipeType)
    assert public_aedt.prepare_aedt_native_handoff_package is prepare_aedt_native_handoff_package
    assert repr(AedtQ2dMatrixProblemType) == repr(public_aedt.AedtQ2dMatrixProblemType)
    assert repr(AedtQ3dMatrixProblemType) == repr(public_aedt.AedtQ3dMatrixProblemType)
    assert not (aedt_root / "native.py").exists()
    assert all((scaffold_root / relative).is_file() for relative in expected_scaffold)

    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "project": {
                    "name": "runtime_contract",
                    "path": "runtime_contract.aedt",
                    "platform": "ubuntu",
                },
                "execution": {},
                "runtime": {},
                "hpc": {},
                "cases": [
                    {
                        "id": "cpw",
                        "gds": "gds/cpw.gds",
                        "tech": "tech/cpw.tech",
                        "recipes": [
                            {
                                "id": "q2d",
                                "type": "q2d_extraction",
                                "design_name": "cpw_q2d",
                            }
                        ],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    assert load_manifest(manifest_path)["schema_version"] == 1
    bad_manifest_path = tmp_path / "bad_manifest.yaml"
    bad_manifest_path.write_text("schema_version: 1\ncases: []\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="project"):
        load_manifest(bad_manifest_path)
    assert register_aedt_materials(object(), {"compiled_materials": []}) == {
        "material_count": 0,
        "materials": [],
    }
    material_result_dir = tmp_path / "material_audit"
    skipped_materials = register_aedt_materials(
        object(),
        {"compiled_materials": [{"aedt_material_name": "Al"}]},
        material_result_dir,
        allow_missing=True,
    )
    assert skipped_materials["material_count"] == 0
    assert skipped_materials["expected_material_count"] == 1
    assert skipped_materials["skipped"] is True
    assert (material_result_dir / "aedt_material_context_applied.json").is_file()

    fail_fast_calls = (
        lambda: create_aedt_session(),
        lambda: run_point_local_sweep(),
        lambda: run_hfss_driven_terminal({}),
        lambda: run_hfss_eigenmode({}),
        lambda: run_q3d_extraction({}),
        lambda: run_q2d_workflow({}),
        lambda: validate_q2d_state(),
        lambda: build_q2d_geometry(),
        lambda: assign_q2d_conductors(),
        lambda: create_q2d_region(),
        lambda: create_q2d_setup(),
        lambda: solve_q2d(),
        lambda: export_q2d_results(),
        lambda: write_q2d_audit(),
    )
    for call in fail_fast_calls:
        with pytest.raises(NotImplementedError):
            call()

    class FailingSaveApp:
        project_name = "runtime_contract"
        design_name = "q2d"

        def save_project(self):
            return False

        def release_desktop(self, *, close_projects, close_desktop):
            return True

    lifecycle_dir = tmp_path / "lifecycle"
    lifecycle_args = SimpleNamespace(
        _aedt_apps=[FailingSaveApp()],
        _aedt_log_dirs=[],
        close_desktop=False,
        new_desktop=True,
    )
    with pytest.raises(RuntimeError, match="AEDT lifecycle finalization failed"):
        finalize_aedt_session(
            lifecycle_args,
            lifecycle_dir,
            {"project": {"path": str(lifecycle_dir / "runtime_contract.aedt")}},
        )
    lifecycle_payload = json.loads((lifecycle_dir / "aedt_lifecycle.json").read_text())
    assert lifecycle_payload["lifecycle_status"] == "failed"


def test_intrinsic_purcell_q2d_export_requires_explicit_solved_cases(
    tmp_path: Path,
) -> None:
    from scripts.export_orpen_q2d_intrinsic_purcell_cases import (
        PendingQ2dArtifactError,
        export_cases,
    )

    output_path = tmp_path / "rlgc.json"
    with pytest.raises(PendingQ2dArtifactError, match="select at least one completed"):
        export_cases(tmp_path / "missing_run", output_path)
    assert not output_path.exists()


def test_intrinsic_purcell_q2d_export_rejects_opposing_face_geometry(
    tmp_path: Path,
) -> None:
    from orpen_sc_pdk.simulation.aedt import (
        Air,
        Die,
        DieGap,
        FacePattern,
        Gap,
        Ground,
        Q2dSemanticCrossSection,
        Stack,
        Trace,
        write_q2d_cross_section_payload,
    )
    from scripts.export_orpen_q2d_intrinsic_purcell_cases import export_cases

    run_root = tmp_path / "opposing_face_run"
    cross_section_path = write_q2d_cross_section_payload(
        run_root / "metadata" / "old_q2d_cross_section.json",
        Q2dSemanticCrossSection(
            stack=Stack(
                (
                    Air(height_um=50),
                    Die(id="D0", thickness_um=100),
                    DieGap(height_um=10),
                    Die(id="D1", thickness_um=100),
                    Air(height_um=50),
                )
            ),
            face_patterns=(
                FacePattern(
                    die="D0",
                    face="top",
                    metal_thickness_um=0.2,
                    segments=(
                        Ground(width_um=30),
                        Gap(width_um=6),
                        Trace("T1", width_um=8),
                        Gap(width_um=6),
                        Ground(width_um=30),
                    ),
                ),
                FacePattern(
                    die="D1",
                    face="bottom",
                    metal_thickness_um=0.2,
                    segments=(
                        Ground(width_um=30),
                        Gap(width_um=6),
                        Trace("T2", width_um=8),
                        Gap(width_um=6),
                        Ground(width_um=30),
                    ),
                ),
            ),
        ),
    )
    run_root.joinpath("manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "project": {"name": "old_opposing_face"},
                "cases": [
                    {
                        "id": "old",
                        "q2d_cross_section": str(cross_section_path.relative_to(run_root)),
                        "recipes": [
                            {
                                "id": "q2d",
                                "type": "q2d_extraction",
                                "q2d_geometry_mode": "semantic_cross_section",
                                "section_plane": "XY",
                                "q2d_setup": {"adaptive_frequency": "6GHz"},
                            }
                        ],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "must_not_exist.json"

    with pytest.raises(ValueError, match="every trace on D0/top"):
        export_cases(run_root, output_path, case_ids=("old",))
    assert not output_path.exists()


def test_intrinsic_purcell_q2d_export_records_complete_semantic_provenance(
    tmp_path: Path,
) -> None:
    from orpen_sc_pdk.simulation.aedt.q2d import (
        make_q2d_same_face_two_trace_cross_section,
        write_q2d_cross_section_payload,
    )
    from scripts.export_orpen_q2d_intrinsic_purcell_cases import export_cases

    run_root = tmp_path / "2026-07-20-Run01"
    case_id = "public_same_face_case"
    cross_section_path = write_q2d_cross_section_payload(
        run_root / "metadata" / f"{case_id}_q2d_cross_section.json",
        make_q2d_same_face_two_trace_cross_section(
            trace_width_um=8.0,
            trace_gap_um=6.0,
            inter_trace_ground_width_um=4.0,
            upper_ground_clearance_width_um=40.0,
            flip_chip_gap_height_um=10.0,
            die_thickness_um=100.0,
            air_height_um=50.0,
            ground_width_um=30.0,
            metal_thickness_um=0.2,
        ),
    )
    run_root.joinpath("manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "project": {"name": "same_face_public_fixture"},
                "cases": [
                    {
                        "id": case_id,
                        "q2d_cross_section": str(cross_section_path.relative_to(run_root)),
                        "recipes": [
                            {
                                "id": "q2d",
                                "type": "q2d_extraction",
                                "q2d_geometry_mode": "semantic_cross_section",
                                "section_plane": "XY",
                                "q2d_setup": {"adaptive_frequency": "6GHz"},
                            }
                        ],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    run_root.joinpath("points.json").write_text(
        json.dumps(
            {
                "schema_version": "aedt-q2d-sweep-points.v1",
                "points": [
                    {
                        "point_slug": case_id,
                        "parameter_id": "upper_ground_clearance_width_um=40.0",
                        "parameter_case_role": "coupled_pair",
                        "parameter_upper_ground_clearance_width_um": 40.0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    result_dir = run_root / "points" / case_id / "q2d"
    result_dir.mkdir(parents=True)

    def write_matrix(
        name: str,
        *,
        unit_line: str,
        title: str,
        values: tuple[tuple[float, float], tuple[float, float]],
    ) -> Path:
        path = result_dir / name
        path.write_text(
            "\n".join(
                (
                    "Setup1:LastAdaptive",
                    unit_line,
                    "Reduce Matrix: Original",
                    "Frequency: 6GHz",
                    "",
                    title,
                    ",T1,T2",
                    f"T1,{values[0][0]},{values[0][1]}",
                    f"T2,{values[1][0]},{values[1][1]}",
                )
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    matrix_paths = (
        write_matrix(
            "cg_maxwell_matrix.csv",
            unit_line="C Units:pF/meter, G Units:mho/meter",
            title="Capacitance Matrix",
            values=((100.0, -20.0), (-20.0, 110.0)),
        ),
        write_matrix(
            "rl_maxwell_matrix.csv",
            unit_line="L Units:nH/meter, R Units:ohm/meter",
            title="Inductance Matrix",
            values=((400.0, 80.0), (80.0, 420.0)),
        ),
        write_matrix(
            "cg_couple_matrix.csv",
            unit_line="C Units:1",
            title="Capacitance Matrix Coupling Coefficient",
            values=((1.0, -0.2), (-0.2, 1.0)),
        ),
        write_matrix(
            "rl_couple_matrix.csv",
            unit_line="L Units:1",
            title="Inductance Matrix Coupling Coefficient",
            values=((1.0, 0.2), (0.2, 1.0)),
        ),
    )
    assignment_path = result_dir / "assignment_summary.json"
    assignment_path.write_text(
        json.dumps(
            {
                "recipe_type": "q2d_extraction",
                "assignment_source": "semantic_cross_section",
                "assignments": [
                    {"assignment_name": "Ground", "conductor_type": "Reference Ground"},
                    {"assignment_name": "T1", "conductor_type": "Signal Line"},
                    {"assignment_name": "T2", "conductor_type": "Signal Line"},
                ],
            }
        ),
        encoding="utf-8",
    )
    simulation_metadata_path = result_dir / "simulation_metadata.json"
    simulation_metadata_path.write_text(
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
    preflight_path = run_root / "logs" / "workers" / f"{case_id}__q2d" / "aedt_preflight.json"
    preflight_path.parent.mkdir(parents=True)
    preflight_path.write_text(
        json.dumps({"aedt_version": "2024.2", "pyaedt_version": "0.26.2"}),
        encoding="utf-8",
    )

    output_path = export_cases(
        run_root,
        tmp_path / "same_face_rlgc.json",
        case_ids=(case_id,),
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    metadata = payload["metadata"]

    assert payload["artifact_status"] == "complete"
    assert metadata["conductor_order"] == ["T1", "T2"]
    assert metadata["reference_group"] == "Ground"
    assert metadata["directions"]["current"] == "positive I[i] flows in +z"
    assert metadata["directions"]["positive_z"].startswith("normal to the XY")
    assert metadata["matrix_representation"]["kind"] == ("distributed_maxwell_per_unit_length")
    assert metadata["extraction_frequency_hz"] == 6e9
    assert metadata["loss_terms"]["R"] == {
        "status": "unavailable",
        "assumed_zero_for_v1": True,
        "unit": "ohm/m",
    }
    assert metadata["loss_terms"]["G"]["assumed_zero_for_v1"] is True
    assert metadata["solver_provenance"]["aedt_version"] == "2024.2"
    assert metadata["run_provenance"] == {
        "run_id": "2026-07-20-Run01",
        "project_name": "same_face_public_fixture",
        "manifest_schema_version": 1,
        "recipe_id": "q2d",
        "case_ids": [case_id],
        "selected_case_status": "solve_complete",
    }
    integrity = metadata["source_integrity"]
    assert integrity["algorithm"] == "sha256"
    assert integrity["all_sources_hashed"] is True
    assert integrity["solver_export_sizes_verified"] is True
    assert len(integrity["cases"][case_id]) == 10
    assert all(len(record["sha256"]) == 64 for record in integrity["cases"][case_id])
    assert all(not Path(record["path"]).is_absolute() for record in integrity["cases"][case_id])
    assert payload["cases"][0]["topology"]["upper_die_substrate_present"] is True
    assert payload["cases"][0]["topology"]["upper_ground_clearance_width_um"] == 40.0


def _write_public_aedt_case_artifacts(directory: Path, stem: str) -> None:
    directory.joinpath(f"{stem}.gds").write_bytes(b"\x00\x06HEADER")
    directory.joinpath(f"{stem}.tech").write_text("layer D0_TOP_M1\n", encoding="utf-8")
    directory.joinpath(f"{stem}.xml").write_text("<Control />\n", encoding="utf-8")
    directory.joinpath(f"{stem}_layer_mapping.json").write_text(
        json.dumps(
            {
                "artifact_stem": stem,
                "units": "um",
                "layers": [
                    {
                        "layer_name": "D0_TOP_M1",
                        "aedt_import_policy": "gds_import",
                        "aedt_layer_number": 1,
                        "aedt_datatype": 0,
                        "aedt_layer_tuple": "1/0",
                        "aedt_object_name_base": "D0_TOP_M1",
                        "material": "Al",
                        "recommended_aedt_role": "conductor",
                        "zmin_um": 0.0,
                        "thickness_um": 0.2,
                        "bbox_ymin_um": -100.0,
                        "bbox_ymax_um": 100.0,
                    },
                    {
                        "layer_name": "D1_BOTTOM_M1",
                        "aedt_import_policy": "gds_import",
                        "aedt_layer_number": 3,
                        "aedt_datatype": 0,
                        "aedt_layer_tuple": "3/0",
                        "aedt_object_name_base": "D1_BOTTOM_M1",
                        "material": "Al",
                        "recommended_aedt_role": "conductor",
                        "zmin_um": 7.7,
                        "thickness_um": 0.2,
                        "bbox_ymin_um": -100.0,
                        "bbox_ymax_um": 100.0,
                    },
                    {
                        "layer_name": "D0_SUBSTRATE",
                        "aedt_import_policy": "region",
                        "aedt_layer_number": 2,
                        "aedt_datatype": 0,
                        "aedt_layer_tuple": "2/0",
                        "aedt_object_name_base": "D0_SUBSTRATE",
                        "material": "Si",
                        "recommended_aedt_role": "dielectric_volume",
                        "zmin_um": -500.0,
                        "thickness_um": 500.0,
                        "bbox_ymin_um": -100.0,
                        "bbox_ymax_um": 100.0,
                    },
                    {
                        "layer_name": "D1_SUBSTRATE",
                        "aedt_import_policy": "region",
                        "aedt_layer_number": 4,
                        "aedt_datatype": 0,
                        "aedt_layer_tuple": "4/0",
                        "aedt_object_name_base": "D1_SUBSTRATE",
                        "material": "Si",
                        "recommended_aedt_role": "dielectric_volume",
                        "zmin_um": 7.9,
                        "thickness_um": 500.0,
                        "bbox_ymin_um": -100.0,
                        "bbox_ymax_um": 100.0,
                    },
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    directory.joinpath(f"{stem}_q2d_conductors.json").write_text(
        json.dumps(
            {
                "conductors": [
                    {
                        "name": "q2d_d0_signal",
                        "center_y_um": 0.0,
                        "layer_stack_layer_name": "D0_TOP_M1",
                        "conductor_type": "Signal Line",
                        "assignment_name": "Trace1",
                    },
                    {
                        "name": "q2d_d0_left_ground",
                        "center_y_um": -16.0,
                        "layer_stack_layer_name": "D0_TOP_M1",
                        "conductor_type": "Reference Ground",
                        "assignment_name": "Ground",
                    },
                    {
                        "name": "q2d_d0_right_ground",
                        "center_y_um": 16.0,
                        "layer_stack_layer_name": "D0_TOP_M1",
                        "conductor_type": "Reference Ground",
                        "assignment_name": "Ground",
                    },
                    {
                        "name": "q2d_d1_signal",
                        "center_y_um": 10.0,
                        "layer_stack_layer_name": "D1_BOTTOM_M1",
                        "conductor_type": "Signal Line",
                        "assignment_name": "Trace2",
                    },
                    {
                        "name": "q2d_d1_left_ground",
                        "center_y_um": -6.0,
                        "layer_stack_layer_name": "D1_BOTTOM_M1",
                        "conductor_type": "Reference Ground",
                        "assignment_name": "Ground",
                    },
                    {
                        "name": "q2d_d1_right_ground",
                        "center_y_um": 26.0,
                        "layer_stack_layer_name": "D1_BOTTOM_M1",
                        "conductor_type": "Reference Ground",
                        "assignment_name": "Ground",
                    },
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )
