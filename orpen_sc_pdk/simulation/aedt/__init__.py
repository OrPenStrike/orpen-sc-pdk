"""AEDT-native handoff package review contract for public OrPen PDK workflows.

This package owns the portable AEDT/PyAEDT handoff contract that private design
repositories can call with their own GDS, TECH/XML, layer mapping, material
sidecars, solver sidecars, and HPC profile catalogs. It does not own private
chip geometry, private notebook run evidence, local AEDT licenses, or
site-private machine policy. The generated package must be runnable on the
target AEDT machine without importing the private repository or this PDK.

Host-side pipeline:
1. Author a package spec.
   ``AedtNativePackageSpec`` is the source of truth for project, runtime, HPC
   policy, cases, recipes, and sweep behavior.
2. Collect source artifacts.
   A case carries GDS, TECH/XML, layer mapping, material context, source
   metadata, and solver sidecars.
3. Build the handoff package.
   The builder writes ``manifest.yaml``, ``hpc/*.acf``, ``run_configs/*.yaml``,
   launchers, README, scripts, and optional archive.
4. Preserve sweep shape.
   Parameter sweeps are represented as one manifest case per sweep point. Point
   identity, sidecars, result directories, worker project isolation, progress,
   skip-completed, retry-failed, and stale-state fail-fast behavior are part of
   the package contract.

Target-side runtime pipeline:
1. Bootstrap runtime.
   Parse CLI/run config, resolve package root, output roots, AEDT version, gRPC
   mode, Desktop lifecycle, worker mode, and HPC/ACF inputs.
2. Dispatch recipe.
   Each manifest recipe dispatches to one solver-specific path.
3. Validate state for recovery.
   Runtime state records source hashes, geometry settings, recipe settings,
   stage decisions, exported files, completion status, and failures.
4. Register materials.
   Material context creates AEDT project materials and records unsupported
   properties for audit.
5. Build or import geometry.
   Geometry is solver-owned. Common code may provide file copying, material
   binding, object naming, units, and inventory helpers, but each solver path
   declares its own AEDT app class, import/build method, expected sidecars, and
   geometry audit artifacts.
6. Assign boundaries.
   Boundary assignment is solver-owned. Each solver path declares how objects
   become terminals, ports, signal lines, reference grounds, sources, nets, or
   modes.
7. Create region, setup, and sweeps.
   Setup creation is solver-owned. Shared helpers may validate names, run
   configs, HPC policy, and timing records.
8. Solve with HPC policy.
   Solve uses the resolved ACF file. Explicit ACF files and resource override
   flags must not silently disagree.
9. Export results.
   Export solver results, matrices, convergence, benchmark artifacts, timing,
   and metadata.
10. Audit completion.
   Write simulation metadata, stage detection, assignment summary, geometry
   inventory, solve timing, completion status, and AEDT messages when present.

Solver-specific path contracts:
- HFSS Driven Terminal:
  Use ``Hfss3dLayout``. Import GDS with TECH/XML control into an AEDB, create
  the layout setup and frequency sweep, resolve terminal/port patterns, solve,
  export layout results and benchmark artifacts, then save the project.
- HFSS Eigenmode:
  Use ``Hfss3dLayout``. Import GDS with TECH/XML control into an AEDB, create
  the layout setup, apply ``mode_count`` when present, solve, export benchmark
  artifacts, then save the project.
- Q3D extraction:
  Use ``Hfss3dLayout`` as the GDS/AEDB import stage, create a layout setup,
  attempt ``export_to_q3d`` when PyAEDT supports it, open ``Q3d`` in the same
  project, apply materials, resolve source/reference/net patterns, solve, export
  C/AC-RL/DC-RL matrices and benchmark artifacts, then save the project.
- Q2D extraction:
  Use a stateful incremental workflow. Validate previous source and recipe
  hashes, then choose one geometry mode. ``hfss_section`` imports GDS into an
  ``Hfss`` 3D staging design, applies rotations, sections eligible objects,
  copies section objects into ``Q2d``, and audits the section plan/inventory.
  ``native_2d`` loads source metadata, layer mapping, material context, and Q2D
  conductor markers, builds a rectangle geometry plan, creates rectangles
  directly in ``Q2d``, and audits the plan/inventory. After geometry, create the
  Q2D Region, assign signal/reference conductors from markers or object
  patterns, create or repair CG/RL setup blocks, solve with ACF/HPC policy,
  export CG/RL matrices, physical convergence, benchmark artifacts, state, and
  completion metadata.

Scaffold target:
- ``models.py``: public Pydantic package/case/recipe/result models.
- ``package.py``: host-side package, manifest, archive, README, and launcher
  writers.
- ``hpc.py``: host-side HPC profile, resource defaults, validation, and ACF
  rendering.
- ``materials.py``: host-side material context compiler.
- ``templates.py``: generated README, runner, requirements, and launcher text.
- ``runtime_bundle/``: runtime source copied or rendered into handoff packages
  so target machines do not import private repositories.
- ``runtime_bundle/sweep.py``: sweep orchestration, skip/retry/recovery,
  worker project isolation, progress reporting, per-point result/log routing,
  and completion aggregation.
- ``runtime_bundle/session.py``: AEDT version, gRPC, Desktop lifecycle, app
  construction, save/close policy, and message collection.
- ``runtime_bundle/io.py``: manifest loading, package paths, JSON/JSONL writes,
  hashing, result/log roots, and audit file conventions.
- ``runtime_bundle/materials.py``: AEDT material creation and object/material
  binding.
- ``runtime_bundle/solver/hfss/driven_terminal.py``: HFSS Driven Terminal path.
- ``runtime_bundle/solver/hfss/eigenmode.py``: HFSS Eigenmode path.
- ``runtime_bundle/solver/q3d.py``: Q3D extraction path.
- ``runtime_bundle/solver/q2d/``: Q2D workflow, state, geometry, assignment,
  region, setup, solve, export, and audit code.
"""

from __future__ import annotations

from .hpc import (
    AedtAcfConfigSpec,
    AedtHpcProfileSpec,
    AedtHpcResourceSpec,
    AedtHpcValidationSpec,
    render_aedt_acf_config,
    write_aedt_hpc_artifacts,
)
from .materials import (
    aedt_material_fallback_reason,
    aedt_material_name_for_physical_material,
    aedt_material_name_from_physical_key,
    compile_aedt_material_context,
    compile_aedt_material_context_from_mapping_path,
)
from .models import (
    AedtCompiledMaterialSpec,
    AedtGrpcMode,
    AedtLayerMaterialBinding,
    AedtMaterialContext,
    AedtMaterialPolicySpec,
    AedtMatrixProblemType,
    AedtMatrixType,
    AedtNativeCaseSpec,
    AedtNativeHandoffArchiveResult,
    AedtNativePackageResult,
    AedtNativePackageSpec,
    AedtNativeRunMode,
    AedtNativeRunProfileSpec,
    AedtParallelProgressMode,
    AedtPlatform,
    AedtQ2dAssignmentSource,
    AedtQ2dConvergenceBlockSpec,
    AedtQ2dGeometryMode,
    AedtQ2dMatrixProblemType,
    AedtQ2dRegionMode,
    AedtQ2dRegionPaddingType,
    AedtQ2dRegionSpec,
    AedtQ2dSetupSpec,
    AedtQ3dMatrixProblemType,
    AedtRecipeSpec,
    AedtRecipeType,
    AedtResumePolicy,
    AedtRotationAxis,
    AedtRotationSpec,
    AedtRuntimeSpec,
    AedtRuntimeVersionPolicy,
    AedtSectionPlane,
    AedtSupportedMaterialProperties,
    AedtUnsupportedMaterialProperties,
)
from .package import (
    package_aedt_native_handoff,
    prepare_aedt_native_handoff_package,
    prepare_aedt_native_sweep_handoff_package,
)

__all__ = [
    "AedtAcfConfigSpec",
    "AedtCompiledMaterialSpec",
    "AedtGrpcMode",
    "AedtHpcProfileSpec",
    "AedtHpcResourceSpec",
    "AedtHpcValidationSpec",
    "AedtLayerMaterialBinding",
    "AedtMaterialContext",
    "AedtMaterialPolicySpec",
    "AedtMatrixProblemType",
    "AedtMatrixType",
    "AedtNativeCaseSpec",
    "AedtNativeHandoffArchiveResult",
    "AedtNativePackageResult",
    "AedtNativePackageSpec",
    "AedtNativeRunMode",
    "AedtNativeRunProfileSpec",
    "AedtParallelProgressMode",
    "AedtPlatform",
    "AedtQ2dAssignmentSource",
    "AedtQ2dConvergenceBlockSpec",
    "AedtQ2dGeometryMode",
    "AedtQ2dMatrixProblemType",
    "AedtQ2dRegionMode",
    "AedtQ2dRegionPaddingType",
    "AedtQ2dRegionSpec",
    "AedtQ2dSetupSpec",
    "AedtQ3dMatrixProblemType",
    "AedtRecipeSpec",
    "AedtRecipeType",
    "AedtResumePolicy",
    "AedtRotationAxis",
    "AedtRotationSpec",
    "AedtRuntimeSpec",
    "AedtRuntimeVersionPolicy",
    "AedtSectionPlane",
    "AedtSupportedMaterialProperties",
    "AedtUnsupportedMaterialProperties",
    "aedt_material_fallback_reason",
    "aedt_material_name_for_physical_material",
    "aedt_material_name_from_physical_key",
    "compile_aedt_material_context",
    "compile_aedt_material_context_from_mapping_path",
    "package_aedt_native_handoff",
    "prepare_aedt_native_handoff_package",
    "prepare_aedt_native_sweep_handoff_package",
    "render_aedt_acf_config",
    "write_aedt_hpc_artifacts",
]
