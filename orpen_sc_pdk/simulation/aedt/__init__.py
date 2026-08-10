"""Notebook-side AEDT/PyAEDT handoff API for OrPen PDK workflows.

This package is the public Notebook-side facade used by private design repos to
turn GDS, TECH/XML, layer mapping, material sidecars, solver sidecars, and HPC
policy into a portable AEDT handoff package. It does not own private chip
geometry, notebook evidence, local AEDT licensing, or site machine policy. Once
the package is written, the target AEDT machine runs the copied
``runtime_bundle`` from inside the handoff package and does not import the
notebook repo or this checkout.

This ``__init__`` file owns the review map and public exports only. Runtime
behavior belongs to the files listed below.

Notebook-side pipeline:
1. The notebook creates an ``AedtNativePackageSpec`` from real artifacts.
2. ``materials.py`` compiles material policy into a portable material context.
3. ``hpc.py`` renders reviewed AEDT ACF/resource policy.
4. ``package.py`` writes ``manifest.yaml``, run configs, copied sources,
   launchers, README text, the copied ``runtime_bundle``, and optional archive.
5. Sweep runs remain one manifest case per point so point identity, sidecars,
   result folders, retry/skip policy, and worker project isolation are explicit.

Run-side pipeline inside the generated package:
1. ``scripts/run_aedt_native.py`` enters ``runtime_bundle/run_aedt_native.py``.
2. ``runtime_bundle/io.py`` loads the manifest, run config, paths, hashes, and
   audit files.
3. ``runtime_bundle/sweep.py`` either dispatches a serial run or starts isolated
   worker subprocesses for point-local parallel Q2D sweeps.
4. ``runtime_bundle/session.py`` owns AEDT version, gRPC/Desktop lifecycle,
   PyAEDT app registration, modeler units, save, close, and lifecycle audit.
5. ``runtime_bundle/materials.py`` creates AEDT project materials and binds
   imported objects to the compiled material context.
6. Solver logic imports/builds geometry, assigns boundaries, creates setup,
   solves with ACF/HPC policy, exports results, and writes completion evidence.

Current v1 boundary status:
- Notebook-side packaging, material context compilation, ACF rendering, run-side
  manifest I/O, material application, session lifecycle, and point-local sweep
  orchestration are implemented boundaries.
- ``runtime_bundle/run_aedt_native.py`` is the current run-side main entrypoint.
  It still hosts solver implementations and compatibility re-exports while the
  solver leaf modules remain reviewable fail-fast boundaries.
- ``runtime_bundle/solver/*`` names the target solver folder structure. Those
  modules should receive solver-specific code as it is moved out of the runner;
  until then, they must fail loudly instead of pretending to run.

File responsibility map:
- ``__init__.py``: public API exports plus this Notebook-side/Run-side review
  contract. It should not implement package writing or runtime behavior.
- ``constants.py``: small Notebook-side scalar constants shared by models and
  writers. Run-side scripts keep copied constants so handoff packages are
  self-contained.
- ``models.py``: Pydantic schemas for runtime policy, cases, recipes, materials,
  HPC settings, and package results. It should not copy files or import PyAEDT.
- ``materials.py``: Notebook-side compiler from repo material DB/layer mapping
  into the portable AEDT material context. It should not mutate AEDT projects.
- ``hpc.py``: Notebook-side HPC resource/profile validation and ACF rendering.
  It should not launch AEDT or choose solver geometry.
- ``geometry.py``: Notebook-side layout-copy preparation for AEDT/Q3D. It
  should not open AEDT or create chip-level ground/coupon geometry.
- ``package.py``: handoff directory writer, source copier, manifest/run-config
  writer, runtime bundle copier, launcher writer, and archive writer. It should
  not create PyAEDT sessions or solve recipes.
- ``templates.py``: text renderers for generated README, requirements, thin
  scripts, and shell launchers. It should not validate artifacts or write files.
- ``runtime_bundle/__init__.py``: Run-side package map and narrow imports for
  generated packages. It should not run the pipeline at import time.
- ``runtime_bundle/io.py``: manifest/run-config/path/hash/JSON/JSONL helpers and
  audit file conventions. It should not decide solver behavior.
- ``runtime_bundle/materials.py``: Run-side AEDT material creation and object
  material binding from the compiled context. It should not compile repo-side
  material policy.
- ``runtime_bundle/session.py``: AEDT session state, app construction,
  gRPC/Desktop settings, modeler units, save/release, messages, and lifecycle
  audit. It should not select manifest points or implement solver recipes.
- ``runtime_bundle/sweep.py``: parent orchestration for one-script parallel
  point-local runs, worker commands, progress, result/log routing, resume
  decisions, and current shared manifest selection helpers. It should not open
  AEDT Desktop or solve a recipe.
- ``runtime_bundle/run_aedt_native.py``: copied CLI entrypoint and transitional
  runtime dispatcher. It parses arguments, applies preflight/run configs,
  dispatches recipes, and currently holds solver code until that code moves into
  ``runtime_bundle/solver``.
- ``runtime_bundle/solver/__init__.py``: common fail-fast solver workflow
  contract and stage vocabulary.
- ``runtime_bundle/solver/hfss/__init__.py``: HFSS-family scaffold exports and
  boundary split between Driven Terminal and Eigenmode recipes.
- ``runtime_bundle/solver/hfss/driven_terminal.py``: target HFSS Driven
  Terminal boundary for GDS/AEDB import, setup/sweep, port resolution, solve,
  export, and save.
- ``runtime_bundle/solver/hfss/eigenmode.py``: target HFSS Eigenmode boundary
  for GDS/AEDB import, mode-count setup, solve, export, and save.
- ``runtime_bundle/solver/q3d.py``: target Q3D extraction boundary for layout
  handoff, Q3D design creation, source/reference or net assignment, matrix
  solve, export, and save.
- ``runtime_bundle/solver/q2d/``: target Q2D stage package for state, geometry,
  assignment, region, setup, solve, export, and audit.
- ``runtime_bundle/solver/q2d/__init__.py``: Q2D stage package exports and
  current fail-fast status.
- ``runtime_bundle/solver/q2d/workflow.py``: Q2D stage coordinator boundary.
- ``runtime_bundle/solver/q2d/state.py``: source hash, recipe hash, completion
  state, recovery, and stale-state rejection boundary.
- ``runtime_bundle/solver/q2d/geometry.py``: ``hfss_section`` and
  ``semantic_cross_section`` geometry construction boundary.
- ``runtime_bundle/solver/q2d/assignment.py``: signal/reference conductor
  assignment boundary from markers or explicit object patterns.
- ``runtime_bundle/solver/q2d/region.py``: Q2D Region creation/repair and
  padding/material audit boundary.
- ``runtime_bundle/solver/q2d/setup.py``: CG/RL setup block and convergence
  setting boundary.
- ``runtime_bundle/solver/q2d/solve.py``: ACF/HPC-controlled solve boundary.
- ``runtime_bundle/solver/q2d/export.py``: matrix, convergence, benchmark, and
  physical result export boundary.
- ``runtime_bundle/solver/q2d/audit.py``: stage decision, inventory, assignment,
  timing, AEDT message, and completion metadata boundary.
"""

from __future__ import annotations

from .geometry import prepare_interdigital_capacitor_q3d_geometry
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
    AedtQ3dRegionPaddingType,
    AedtQ3dRegionSpec,
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
from .parameter_space import Axis, ParameterSpace
from .q2d import (
    Air,
    Die,
    DieGap,
    FacePattern,
    Gap,
    Ground,
    Q2dDerivedSweepResult,
    Q2dFacetLineGrid,
    Q2dFormula,
    Q2dHeatMap,
    Q2dImpedanceFormula,
    Q2dLinePlot,
    Q2dMatrixElement,
    Q2dRawPoint,
    Q2dRawSweepResult,
    Q2dResultView,
    Q2dSemanticCrossSection,
    Stack,
    Trace,
    load_q2d_raw_sweep_result,
    validate_q2d_cross_section_payload,
    write_q2d_cross_section_payload,
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
    "AedtQ3dRegionPaddingType",
    "AedtQ3dRegionSpec",
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
    "Air",
    "Die",
    "DieGap",
    "FacePattern",
    "Gap",
    "Ground",
    "Q2dDerivedSweepResult",
    "Q2dFacetLineGrid",
    "Q2dFormula",
    "Q2dHeatMap",
    "Q2dImpedanceFormula",
    "Q2dLinePlot",
    "Q2dMatrixElement",
    "Q2dRawPoint",
    "Q2dRawSweepResult",
    "Q2dResultView",
    "load_q2d_raw_sweep_result",
    "Q2dSemanticCrossSection",
    "Stack",
    "Trace",
    "aedt_material_fallback_reason",
    "aedt_material_name_for_physical_material",
    "aedt_material_name_from_physical_key",
    "compile_aedt_material_context",
    "compile_aedt_material_context_from_mapping_path",
    "package_aedt_native_handoff",
    "prepare_aedt_native_handoff_package",
    "prepare_aedt_native_sweep_handoff_package",
    "prepare_interdigital_capacitor_q3d_geometry",
    "render_aedt_acf_config",
    "validate_q2d_cross_section_payload",
    "write_q2d_cross_section_payload",
    "Axis",
    "ParameterSpace",
    "write_aedt_hpc_artifacts",
]
