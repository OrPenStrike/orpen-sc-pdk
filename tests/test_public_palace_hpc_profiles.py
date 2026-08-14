"""Tests for Public PDK Palace HPC profile handoff.

Responsibility:
Validate that public F1/Nano4 profile values live in the PDK while `gsim`
remains the renderer and archive owner.
"""

from __future__ import annotations

import tarfile
from pathlib import Path

from gsim.palace import DrivenSim, resolve_palace_result
from gsim.palace.run_stage import PalaceRunHandle

from orpen_sc_pdk.simulation import (
    list_public_palace_run_profiles,
    resolve_public_palace_run_profile,
)


def test_public_profile_catalog_exposes_f1_and_nano4_profiles() -> None:
    profiles = list_public_palace_run_profiles()

    assert profiles == (
        "f1:ct112",
        "f1:ct448",
        "f1:ct448-2x56",
        "f1:development",
        "nano4:8gpus",
    )
    assert "ltlab-workstation1:ltlab-workstation1" not in profiles


def test_public_f1_ct112_profile_defaults_to_four_28_core_tasks() -> None:
    profile = resolve_public_palace_run_profile("f1:ct112")

    assert profile.resources.account == "public_alloc"
    assert profile.resources.partition == "ct112"
    assert profile.resources.nodes == 1
    assert profile.resources.ntasks_per_node == 4
    assert profile.resources.cpus_per_task == 28
    assert profile.resources.num_processes == 4
    assert profile.resources.num_threads == 28
    assert profile.resources.memory_mb == 482496
    assert profile.launcher.palace_executable == "palace-x86_64.bin"
    assert "spack load palace@0.16.0" in profile.launcher.setup_commands
    assert profile.to_palace_config_hints() == {"Solver": {"Device": "CPU"}}


def test_public_f1_ct448_profiles_expose_both_task_layouts() -> None:
    four_by_28 = resolve_public_palace_run_profile("f1:ct448")
    two_by_56 = resolve_public_palace_run_profile("f1:ct448-2x56")

    assert four_by_28.resources.partition == "ct448"
    assert four_by_28.resources.nodes == 4
    assert four_by_28.resources.ntasks_per_node == 4
    assert four_by_28.resources.cpus_per_task == 28
    assert four_by_28.resources.num_processes == 16
    assert four_by_28.resources.num_threads == 28

    assert two_by_56.resources.partition == "ct448"
    assert two_by_56.resources.nodes == 4
    assert two_by_56.resources.ntasks_per_node == 2
    assert two_by_56.resources.cpus_per_task == 56
    assert two_by_56.resources.num_processes == 8
    assert two_by_56.resources.num_threads == 56


def test_public_f1_development_profile_uses_full_two_hour_shape() -> None:
    profile = resolve_public_palace_run_profile("f1:development")

    assert profile.resources.partition == "development"
    assert profile.resources.wall_time == "02:00:00"
    assert profile.resources.nodes == 10
    assert profile.resources.ntasks_per_node == 2
    assert profile.resources.cpus_per_task == 56
    assert profile.resources.num_processes == 20
    assert profile.resources.num_threads == 56


def test_public_nano4_profile_resolves_gpu_sbatch_resources() -> None:
    profile = resolve_public_palace_run_profile(
        "nano4:8gpus",
        resource_overrides={
            "account": "p00lcy01",
            "wall_time": "2-00:00:00",
        },
    )

    assert profile.resources.account == "p00lcy01"
    assert profile.resources.partition == "8gpus"
    assert profile.resources.ntasks_per_node == 8
    assert profile.resources.gres == "gpu:8"
    assert profile.resources.memory_mb == 1600000
    assert profile.launcher.srun_args == ("--mpi=pmix",)
    assert profile.to_palace_config_hints() == {"Solver": {"Device": "GPU"}}


def test_public_profile_sbatch_is_packaged_by_sim_handoff_archive(tmp_path: Path) -> None:
    run_dir = tmp_path / "2026-06-17-Run01"
    run_dir.mkdir()
    (run_dir / "config.json").write_text('{"Problem": {"Type": "Driven"}}\n')
    (run_dir / "palace.msh").write_text("$MeshFormat\n4.1 0 8\n$EndMeshFormat\n")

    profile = resolve_public_palace_run_profile(
        "nano4:8gpus",
        resource_overrides={"account": "p00lcy01", "wall_time": "00:30:00"},
    )
    sim = DrivenSim()
    sim.set_output_dir(run_dir)
    sim.write_slurm_sbatch_handoff(profile, job_name="orpen_public_hpc")
    handle = sim.generate_handoff_package(
        write_config=False,
        script_path=run_dir / "run_palace.sbatch",
        profile=profile,
    )

    assert isinstance(handle, PalaceRunHandle)
    assert handle.kind == "slurm"
    script = (run_dir / "run_palace.sbatch").read_text()
    assert "#SBATCH --gres=gpu:8" in script
    assert "srun --mpi=pmix" in script
    assert '"$PALACE_EXECUTABLE" "$PALACE_CONFIG"' in script
    resolved = resolve_palace_result(handle.run_folder, problem_type="Driven")
    assert resolved.run_summary.handoff["script"] == {"path": "run_palace.sbatch"}

    archive_path = run_dir.parent / f"{run_dir.name}-palace.tar.gz"
    with tarfile.open(archive_path, "r:gz") as tar:
        names = set(tar.getnames())
    assert "2026-06-17-Run01/run_palace.sbatch" in names
    assert "2026-06-17-Run01/results/palace" in names
