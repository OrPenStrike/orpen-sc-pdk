"""Public simulation helpers owned by the OrPen PDK.

Responsibility:
Owns Public PDK simulation-facing defaults that are not generic `gsim` code,
such as public HPC profile catalogs for notebook handoff.

Does not own Palace config generation, Slurm rendering, archive packaging,
result parsing, typed data, reports, or display helpers. Those remain in
`gsim`.

Pipeline position:
Notebook controls select public PDK run-profile values here, then compose the
explicit `sim.write_config() -> sim.write_slurm_sbatch_handoff() ->
sim.generate_handoff_package()` Run Stage with `gsim`.
"""

from __future__ import annotations

from .palace_hpc import (
    get_public_palace_run_profile_catalog,
    list_public_palace_run_profiles,
    resolve_public_palace_run_profile,
)

__all__ = [
    "get_public_palace_run_profile_catalog",
    "list_public_palace_run_profiles",
    "resolve_public_palace_run_profile",
]
