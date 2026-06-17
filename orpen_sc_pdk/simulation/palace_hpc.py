"""Public Palace HPC profile catalog for OrPen notebooks.

Responsibility:
Owns public, site-specific Slurm profile values for Palace handoff from the
Public PDK. F1 and Nano4 are public HPC sites, so their reusable profile shapes
belong here instead of in `gsim`.

Does not own:
`gsim` owns Slurm schema validation, sbatch rendering, Palace config generation,
archive packaging, result parsing, typed data, reports, and display helpers.
Private lab machines such as LTLab belong in private/site configuration.

Inputs:
Notebook-facing profile name plus optional resource overrides such as account,
wall time, task shape, or GPU count.

Outputs:
Resolved `gsim.palace.handoff.PalaceSlurmProfileResolution` objects that can be
passed through the explicit notebook Run Stage:
`sim.write_config(hints=...)`, `sim.write_slurm_sbatch_handoff(...)`, and
`sim.generate_handoff_package(...)`.

Pipeline position:
Notebook controls -> Public PDK profile catalog -> `gsim` profile resolver ->
`gsim` config/sbatch/archive handoff.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gsim.palace.handoff import PalaceSlurmProfileResolution

F1_PALACE_SETUP_COMMANDS = (
    "module use /home/qusim/module_gcc11/",
    "ml purge",
    "ml gcc/11.2.0 openmpi/5.0.10",
    "set +u",
    ". /pkg/compiler/intel/2021_4/mkl/latest/env/vars.sh intel64",
    "set -u",
    "source /home/qusim/spack/share/spack/setup-env.sh",
    "spack load palace@0.16.0",
)
F1_PALACE_LAUNCHER = {
    "palace_executable": "palace-x86_64.bin",
    "command_style": "binary",
    "setup_commands": F1_PALACE_SETUP_COMMANDS,
}
NANO4_PALACE_SETUP_COMMANDS = (
    "module use /work/p00lcy01/pubmodules",
    "ml purge",
    "ml oneapi/tbb oneapi/compiler-rt oneapi/mkl",
    "ml g13/openmpi/5.0.10",
)
NANO4_PALACE_LAUNCHER = {
    "palace_executable": "/work/p00lcy01/palace-0.16.1/bin/palace-x86_64.bin",
    "command_style": "binary",
    "setup_commands": NANO4_PALACE_SETUP_COMMANDS,
    "srun_args": ("--mpi=pmix",),
}

PUBLIC_PALACE_SLURM_PROFILE_CATALOG: dict[str, dict[str, Any]] = {
    "f1:development": {
        "source": "OrPen public PDK profile catalog for public NCHC F1 resources",
        "description": (
            "NCHC F1 development partition using the full public 1120-core "
            "shape with the partition's two-hour wall-time limit."
        ),
        "launcher": F1_PALACE_LAUNCHER,
        "solver": {"device": "CPU"},
        "resources": {
            "account": "public_alloc",
            "partition": "development",
            "wall_time": "02:00:00",
            "nodes": 10,
            "ntasks_per_node": 2,
            "cpus_per_task": 56,
            "memory_mb": 482496,
        },
        "metadata": {"site": "F1", "accelerator": "cpu", "palace_version": "0.16.0"},
    },
    "f1:ct112": {
        "source": "OrPen public PDK profile catalog for public NCHC F1 resources",
        "description": "NCHC F1 ct112 CPU partition for public Palace handoff.",
        "launcher": F1_PALACE_LAUNCHER,
        "solver": {"device": "CPU"},
        "resources": {
            "account": "public_alloc",
            "partition": "ct112",
            "wall_time": "96:00:00",
            "nodes": 1,
            "ntasks_per_node": 4,
            "cpus_per_task": 28,
            "memory_mb": 482496,
        },
        "metadata": {"site": "F1", "accelerator": "cpu", "palace_version": "0.16.0"},
    },
    "f1:ct448": {
        "source": "OrPen public PDK profile catalog for public NCHC F1 resources",
        "description": "NCHC F1 ct448 CPU partition for public Palace handoff.",
        "launcher": F1_PALACE_LAUNCHER,
        "solver": {"device": "CPU"},
        "resources": {
            "account": "public_alloc",
            "partition": "ct448",
            "wall_time": "96:00:00",
            "nodes": 4,
            "ntasks_per_node": 4,
            "cpus_per_task": 28,
            "memory_mb": 482496,
        },
        "metadata": {"site": "F1", "accelerator": "cpu", "palace_version": "0.16.0"},
    },
    "f1:ct448-2x56": {
        "source": "OrPen public PDK profile catalog for public NCHC F1 resources",
        "description": (
            "NCHC F1 ct448 CPU partition for public Palace handoff "
            "using two 56-core tasks per node across four nodes."
        ),
        "launcher": F1_PALACE_LAUNCHER,
        "solver": {"device": "CPU"},
        "resources": {
            "account": "public_alloc",
            "partition": "ct448",
            "wall_time": "96:00:00",
            "nodes": 4,
            "ntasks_per_node": 2,
            "cpus_per_task": 56,
            "memory_mb": 482496,
        },
        "metadata": {"site": "F1", "accelerator": "cpu", "palace_version": "0.16.0"},
    },
    "nano4:8gpus": {
        "source": "OrPen public PDK profile catalog for public NCHC Nano4 resources",
        "description": "NCHC Nano4 single-node H200 GPU partition for public Palace handoff.",
        "launcher": NANO4_PALACE_LAUNCHER,
        "solver": {"device": "GPU"},
        "resources": {
            "account": "public_alloc",
            "partition": "8gpus",
            "wall_time": "48:00:00",
            "nodes": 1,
            "ntasks_per_node": 8,
            "cpus_per_task": 1,
            "memory_mb": 1600000,
            "gres": "gpu:8",
        },
        "metadata": {
            "site": "Nano4",
            "accelerator": "gpu",
            "gpu_type": "H200",
            "palace_version": "0.16.1",
        },
    },
}


def get_public_palace_run_profile_catalog() -> dict[str, dict[str, Any]]:
    """Return a mutable copy of the Public PDK Palace run-profile catalog."""

    return copy.deepcopy(PUBLIC_PALACE_SLURM_PROFILE_CATALOG)


def list_public_palace_run_profiles() -> tuple[str, ...]:
    """Return public Palace run-profile names exposed by the PDK."""

    return tuple(sorted(PUBLIC_PALACE_SLURM_PROFILE_CATALOG))


def resolve_public_palace_run_profile(
    profile_name: str,
    *,
    resource_overrides: Mapping[str, Any] | None = None,
) -> PalaceSlurmProfileResolution:
    """Resolve a Public PDK run profile through the generic `gsim` resolver."""

    from gsim.palace.handoff import resolve_palace_slurm_profile

    return resolve_palace_slurm_profile(
        get_public_palace_run_profile_catalog(),
        profile_name,
        resource_overrides=resource_overrides,
    )


__all__ = [
    "F1_PALACE_LAUNCHER",
    "F1_PALACE_SETUP_COMMANDS",
    "NANO4_PALACE_LAUNCHER",
    "NANO4_PALACE_SETUP_COMMANDS",
    "PUBLIC_PALACE_SLURM_PROFILE_CATALOG",
    "get_public_palace_run_profile_catalog",
    "list_public_palace_run_profiles",
    "resolve_public_palace_run_profile",
]
