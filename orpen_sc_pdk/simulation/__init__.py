"""Public simulation helpers owned by the OrPen PDK.

This package collects public PDK simulation-facing defaults that are not
generic `gsim` code: reusable Palace run-profile catalogs, simulation-only
layer catalogs, and portable AEDT handoff package scaffolding. The PDK owns
those public site/layer/package contracts; `gsim` owns Palace config
generation, Slurm rendering, archive packaging, result parsing, typed data,
reports, and display helpers.

Private design repositories may import the AEDT package models and writers to
generate target-machine PyAEDT packages with their own artifacts and HPC
profiles. The PDK scaffold does not own private geometry, private machine
catalogs, or AEDT run evidence.
"""

from __future__ import annotations

from .aedt import (
    AedtHpcProfileSpec,
    AedtHpcResourceSpec,
    AedtHpcValidationSpec,
    AedtMatrixProblemType,
    AedtNativeCaseSpec,
    AedtNativePackageSpec,
    AedtNativeRunProfileSpec,
    AedtQ2dMatrixProblemType,
    AedtQ3dMatrixProblemType,
    AedtRecipeSpec,
    AedtRecipeType,
    AedtRuntimeSpec,
    compile_aedt_material_context,
    package_aedt_native_handoff,
    prepare_aedt_native_handoff_package,
)
from .palace_hpc import (
    get_public_palace_run_profile_catalog,
    list_public_palace_run_profiles,
    resolve_public_palace_run_profile,
)
from .palace_layers import (
    get_gsim_palace_simulation_layer_catalog,
)

__all__ = [
    "AedtHpcProfileSpec",
    "AedtHpcResourceSpec",
    "AedtHpcValidationSpec",
    "AedtMatrixProblemType",
    "AedtNativeCaseSpec",
    "AedtNativePackageSpec",
    "AedtNativeRunProfileSpec",
    "AedtQ2dMatrixProblemType",
    "AedtQ3dMatrixProblemType",
    "AedtRecipeSpec",
    "AedtRecipeType",
    "AedtRuntimeSpec",
    "compile_aedt_material_context",
    "get_gsim_palace_simulation_layer_catalog",
    "get_public_palace_run_profile_catalog",
    "list_public_palace_run_profiles",
    "package_aedt_native_handoff",
    "prepare_aedt_native_handoff_package",
    "resolve_public_palace_run_profile",
]
