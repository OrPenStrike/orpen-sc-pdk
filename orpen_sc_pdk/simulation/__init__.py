"""Public simulation helpers owned by the OrPen PDK.

This package collects public PDK simulation-facing defaults that are not
generic `gsim` code: reusable Palace run-profile catalogs and simulation-only
layer catalogs. The PDK owns those public site/layer values; `gsim` owns Palace
config generation, Slurm rendering, archive packaging, result parsing, typed
data, reports, and display helpers.

Notebooks import these helpers explicitly, then compose the visible `gsim`
workflow chain such as `set_simulation_layers()`, `write_config()`,
`run_local()`, `write_slurm_sbatch_handoff()`, and
`generate_handoff_package()`.
"""

from __future__ import annotations

from .palace_hpc import (
    get_public_palace_run_profile_catalog,
    list_public_palace_run_profiles,
    resolve_public_palace_run_profile,
)
from .palace_layers import (
    get_gsim_palace_simulation_layer_catalog,
)

__all__ = [
    "get_gsim_palace_simulation_layer_catalog",
    "get_public_palace_run_profile_catalog",
    "list_public_palace_run_profiles",
    "resolve_public_palace_run_profile",
]
