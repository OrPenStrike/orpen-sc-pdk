"""Primitive AEDT package models for public handoff contracts.

This module owns the typed data model for host-side AEDT package generation:
recipe vocabulary, runtime policy, material context, case specs, package specs,
and package result records. It does not import the package writer or generated
runtime facade; implementation modules depend on these primitives, not the
other way around.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from orpen_sc_pdk.simulation.aedt.constants import (
    AEDT_MODELER_UNIT_ALIASES,
    AEDT_MODELER_UNIT_TO_UM,
)
from orpen_sc_pdk.simulation.aedt.hpc import AedtHpcProfileSpec, AedtHpcResourceSpec

AedtRecipeType = Literal[
    "hfss_driven_terminal",
    "hfss_eigenmode",
    "q3d_extraction",
    "q2d_extraction",
]
AedtPlatform = Literal["ubuntu", "windows"]
AedtSectionPlane = Literal["XY", "YZ", "ZX"]
AedtRotationAxis = Literal["X", "Y", "Z"]
AedtRuntimeVersionPolicy = Literal["auto", "require", "warn"]
AedtGrpcMode = Literal["insecure", "secure", "auto"]
AedtMatrixProblemType = Literal["C", "AC RL", "DC RL", "CG", "RL"]
AedtQ2dMatrixProblemType = Literal["CG", "RL"]
AedtQ3dMatrixProblemType = Literal["C", "AC RL", "DC RL"]
AedtMatrixType = Literal["Maxwell", "Couple", "Spice"]
AedtQ2dAssignmentSource = Literal["q2d_conductors", "object_patterns"]
AedtQ2dGeometryMode = Literal["hfss_section", "native_2d"]
AedtQ2dRegionMode = Literal["individual", "all", "transverse"]
AedtQ2dRegionPaddingType = Literal[
    "Absolute Offset",
    "Absolute Position",
    "Percentage Offset",
    "Transverse Percentage Offset",
]
AedtNativeRunMode = Literal["import", "solve"]
AedtParallelProgressMode = Literal["auto", "stream", "off"]
AedtResumePolicy = Literal["run_all", "skip_completed_retry_failed", "skip_completed_fail_failed"]

_MATERIAL_KINDS = {
    "conductor",
    "superconductor",
    "mixed",
    "conductive",
    "dielectric",
    "vacuum",
}


def safe_aedt_name(value: str) -> str:
    """Return a filesystem-safe AEDT token."""

    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("._")


def _normalize_material_kind(value: Any) -> str:
    text = str(value or "").strip().casefold()
    if text not in _MATERIAL_KINDS:
        raise ValueError(f"Unsupported AEDT material kind: {value!r}")
    return text


class AedtRotationSpec(BaseModel):
    """One rotation operation for AEDT geometry staging."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    axis: AedtRotationAxis
    angle_deg: float


class AedtQ2dConvergenceBlockSpec(BaseModel):
    """Q2D CG/RL convergence block settings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_pass: int = Field(default=99, ge=1)
    min_pass: int = Field(default=1, ge=1)
    min_converged_pass: int = Field(default=2, ge=1)
    percent_error: float = Field(default=0.01, gt=0)
    percent_refinement: float = Field(default=30, ge=0)
    use_loss_convergence: bool = False
    use_parameter_convergence: bool = False
    use_lossy_parameter_convergence: bool = False
    parameter_convergence_percent_error: float = Field(default=1, gt=0)


class AedtQ2dSetupSpec(BaseModel):
    """Q2D setup settings exposed from notebooks and package manifests."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    adaptive_frequency: str = "6GHz"
    enabled: bool = True
    save_fields: bool = True
    cg: AedtQ2dConvergenceBlockSpec = Field(default_factory=AedtQ2dConvergenceBlockSpec)
    rl: AedtQ2dConvergenceBlockSpec = Field(default_factory=AedtQ2dConvergenceBlockSpec)


class AedtQ2dRegionSpec(BaseModel):
    """Q2D Region settings written into each recipe manifest row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = True
    name: str = "Vacuum"
    material: str = "Vacuum"
    mode: AedtQ2dRegionMode = "individual"
    padding_type: AedtQ2dRegionPaddingType = "Absolute Offset"
    padding: dict[str, str] = Field(
        default_factory=lambda: {"+X": "0um", "-X": "0um", "+Y": "0um", "-Y": "0um"}
    )

    @field_validator("name", "material")
    @classmethod
    def _validate_text(cls, value: str) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("Q2D region text fields must not be empty")
        return text

    @field_validator("padding")
    @classmethod
    def _validate_padding(cls, value: dict[str, str]) -> dict[str, str]:
        allowed = {"+X", "-X", "+Y", "-Y"}
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ValueError(f"Q2D region padding has unsupported directions: {unknown}")
        return {
            direction: str(value.get(direction, "0um")) for direction in ("+X", "-X", "+Y", "-Y")
        }


class AedtMaterialPolicySpec(BaseModel):
    """AEDT material assignment policy for one recipe."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    conductor_material: str = "pec"
    material_condition: str = "cryogenic"

    @field_validator("conductor_material", "material_condition")
    @classmethod
    def _validate_text(cls, value: str) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("AEDT material policy fields must not be empty")
        return text


class AedtSupportedMaterialProperties(BaseModel):
    """AEDT-compatible scalar material properties compiled from public records."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    permittivity: float | None = None
    permeability: float | None = None
    dielectric_loss_tangent: float | None = None
    conductivity: float | None = None


class AedtUnsupportedMaterialProperties(BaseModel):
    """Material properties retained for audit because AEDT runner does not apply them."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fields: dict[str, Any] = Field(default_factory=dict)


class AedtLayerMaterialBinding(BaseModel):
    """LayerStack row bound to an AEDT object-name base and physical material."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    layer_name: str
    object_name_base: str
    aedt_layer_number: int | None = None
    aedt_datatype: int | None = None
    aedt_layer_tuple: str | None = None
    role: str
    physical_material_key: str
    aedt_material_name: str
    material_kind: str
    aedt_material_fallback_reason: str | None = None
    zmin_um: float | None = None
    thickness_um: float | None = None

    @field_validator("layer_name", "object_name_base", "role", "physical_material_key")
    @classmethod
    def _validate_nonempty(cls, value: str) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("AEDT material binding fields must not be empty")
        return text

    @field_validator("object_name_base")
    @classmethod
    def _validate_object_name_base(cls, value: str) -> str:
        safe = safe_aedt_name(value)
        if safe != value:
            raise ValueError(f"AEDT object_name_base must be a safe token: {value!r}")
        return value

    @field_validator("material_kind")
    @classmethod
    def _validate_material_kind(cls, value: str) -> str:
        return _normalize_material_kind(value)


class AedtCompiledMaterialSpec(BaseModel):
    """One project material that the generated PyAEDT runner can create/update."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    aedt_material_name: str
    source_physical_material_key: str
    material_kind: str
    supported_properties: AedtSupportedMaterialProperties = Field(
        default_factory=AedtSupportedMaterialProperties
    )
    unsupported_properties: AedtUnsupportedMaterialProperties = Field(
        default_factory=AedtUnsupportedMaterialProperties
    )
    source_layer_names: tuple[str, ...] = ()

    @field_validator("aedt_material_name", "source_physical_material_key")
    @classmethod
    def _validate_nonempty(cls, value: str) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("AEDT compiled material fields must not be empty")
        return text

    @field_validator("material_kind")
    @classmethod
    def _validate_material_kind(cls, value: str) -> str:
        return _normalize_material_kind(value)


class AedtMaterialContext(BaseModel):
    """Portable AEDT material/object assignment context for generated runners."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "aedt-material-context.v1"
    material_condition: str = "cryogenic"
    registry_hash: str | None = None
    layer_stack_hash: str | None = None
    bindings: tuple[AedtLayerMaterialBinding, ...] = ()
    compiled_materials: tuple[AedtCompiledMaterialSpec, ...] = ()


class AedtRuntimeSpec(BaseModel):
    """AEDT target-machine runtime policy for a portable package."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    aedt_version: str | None = None
    allowed_aedt_versions: tuple[str, ...] = ()
    version_policy: AedtRuntimeVersionPolicy = "auto"
    grpc_mode: AedtGrpcMode = "auto"
    grpc_local: bool | None = None

    @field_validator("aedt_version")
    @classmethod
    def _validate_optional_version(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            raise ValueError("aedt_version must not be empty")
        return text

    @field_validator("allowed_aedt_versions")
    @classmethod
    def _validate_allowed_versions(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        versions = tuple(str(item).strip() for item in value)
        if any(not item for item in versions):
            raise ValueError("allowed_aedt_versions must not contain empty entries")
        return versions


class AedtNativeRunProfileSpec(BaseModel):
    """Generated AEDT runner defaults for one execution mode."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: AedtNativeRunMode
    resume_policy: AedtResumePolicy = "run_all"
    skip_completed: bool = False
    continue_on_failure: bool = False
    parallel: bool = False
    max_workers: int | None = Field(default=None, ge=1)
    num_cores: int | None = Field(default=None, ge=1)
    memory_mb_total: int | None = Field(default=None, ge=1)
    memory_mb_per_worker: int | None = Field(default=None, ge=1)
    ram_percent: int | None = Field(default=None, ge=1, le=100)
    core_budget: int | None = Field(default=None, ge=1)
    progress: AedtParallelProgressMode = "auto"
    progress_interval_seconds: float = Field(default=5.0, gt=0)

    @model_validator(mode="after")
    def _validate_mode_contract(self) -> AedtNativeRunProfileSpec:
        if self.mode == "import" and (self.skip_completed or self.continue_on_failure):
            raise ValueError("import run profiles cannot skip or continue failed work")
        return self


class AedtRecipeSpec(BaseModel):
    """One AEDT solver recipe for a GDS/TECH case."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    type: AedtRecipeType
    setup_name: str = "Setup1"
    design_name: str | None = None
    setup_options: dict[str, Any] = Field(default_factory=dict)
    frequency_sweep: dict[str, Any] = Field(default_factory=dict)
    terminal_patterns: tuple[str, ...] = ()
    port_patterns: tuple[str, ...] = ()
    source_patterns: tuple[str, ...] = ()
    reference_patterns: tuple[str, ...] = ()
    net_patterns: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    signal_patterns: tuple[str, ...] = ()
    ground_patterns: tuple[str, ...] = ()
    assignment_source: AedtQ2dAssignmentSource | None = None
    q2d_geometry_mode: AedtQ2dGeometryMode = "hfss_section"
    mode_count: int | None = Field(default=None, ge=1)
    rotations: tuple[AedtRotationSpec, ...] = ()
    section_plane: AedtSectionPlane = "XY"
    matrix_problem_types: tuple[AedtMatrixProblemType, ...] = ("C", "AC RL")
    matrix_types: tuple[AedtMatrixType, ...] = ("Maxwell", "Couple")
    q2d_setup: AedtQ2dSetupSpec = Field(default_factory=AedtQ2dSetupSpec)
    q2d_region: AedtQ2dRegionSpec = Field(default_factory=AedtQ2dRegionSpec)
    material_policy: AedtMaterialPolicySpec = Field(default_factory=AedtMaterialPolicySpec)
    modeler_units: str = "um"

    @model_validator(mode="before")
    @classmethod
    def _apply_solver_matrix_defaults(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            return data
        payload = dict(data)
        if "matrix_problem_types" not in payload:
            if payload.get("type") == "q2d_extraction":
                payload["matrix_problem_types"] = ("CG", "RL")
            elif payload.get("type") == "q3d_extraction":
                payload["matrix_problem_types"] = ("C", "AC RL")
        return payload

    @field_validator("id", "setup_name", "design_name")
    @classmethod
    def _validate_safe_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        safe = safe_aedt_name(value)
        if safe != value:
            raise ValueError(f"AEDT names must be filesystem-safe tokens: {value!r}")
        return value

    @field_validator(
        "terminal_patterns",
        "port_patterns",
        "source_patterns",
        "reference_patterns",
        "signal_patterns",
        "ground_patterns",
        "matrix_problem_types",
        "matrix_types",
    )
    @classmethod
    def _validate_nonempty_tuple_entries(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not str(item).strip() for item in value):
            raise ValueError("tuple fields must not contain empty entries")
        return tuple(str(item) for item in value)

    @field_validator("net_patterns")
    @classmethod
    def _validate_net_patterns(
        cls,
        value: dict[str, tuple[str, ...]],
    ) -> dict[str, tuple[str, ...]]:
        normalized: dict[str, tuple[str, ...]] = {}
        for net_name, patterns in value.items():
            safe_net_name = safe_aedt_name(net_name)
            if safe_net_name != net_name:
                raise ValueError(f"net pattern keys must be safe AEDT names: {net_name!r}")
            if not patterns or any(not str(pattern).strip() for pattern in patterns):
                raise ValueError("net pattern values must contain non-empty patterns")
            normalized[net_name] = tuple(str(pattern) for pattern in patterns)
        return normalized

    @field_validator("modeler_units")
    @classmethod
    def _validate_modeler_units(cls, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("modeler_units must not be empty")
        normalized = AEDT_MODELER_UNIT_ALIASES.get(text.casefold(), text.casefold())
        if normalized not in AEDT_MODELER_UNIT_TO_UM:
            raise ValueError(
                f"modeler_units must be one of {sorted(AEDT_MODELER_UNIT_TO_UM)}; got {value!r}"
            )
        return normalized

    @model_validator(mode="after")
    def _validate_recipe_contract(self) -> AedtRecipeSpec:
        if self.type == "hfss_driven_terminal" and not (
            self.terminal_patterns or self.port_patterns
        ):
            raise ValueError(
                "hfss_driven_terminal recipes require terminal_patterns or port_patterns"
            )
        if self.type == "hfss_eigenmode" and self.mode_count is None:
            raise ValueError("hfss_eigenmode recipes require mode_count")
        if self.type == "q3d_extraction" and not (self.source_patterns or self.net_patterns):
            raise ValueError("q3d_extraction recipes require source_patterns or net_patterns")
        if self.type == "q3d_extraction":
            invalid = sorted(set(self.matrix_problem_types) - {"C", "AC RL", "DC RL"})
            if invalid:
                raise ValueError(f"q3d_extraction has invalid matrix problem types: {invalid}")
        if self.type == "q2d_extraction":
            invalid = sorted(set(self.matrix_problem_types) - {"CG", "RL"})
            if invalid:
                raise ValueError(f"q2d_extraction has invalid matrix problem types: {invalid}")
            if self.q2d_geometry_mode == "native_2d" and self.assignment_source != "q2d_conductors":
                raise ValueError(
                    "q2d_extraction native_2d geometry mode requires "
                    "assignment_source='q2d_conductors'"
                )
            if self.assignment_source == "q2d_conductors":
                return self
            if not self.signal_patterns:
                raise ValueError("q2d_extraction recipes require signal_patterns")
            if not self.ground_patterns:
                raise ValueError("q2d_extraction recipes require ground_patterns")
        return self

    def resolved_design_name(self, case_id: str) -> str:
        """Return the AEDT design name used for this recipe and case."""

        return self.design_name or safe_aedt_name(f"{case_id}_{self.id}")


class AedtNativeCaseSpec(BaseModel):
    """One GDS/TECH case included in an AEDT-native package."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    gds_path: Path
    tech_path: Path
    control_path: Path | None = None
    layer_mapping_csv_path: Path | None = None
    layer_mapping_json_path: Path | None = None
    aedt_material_context_path: Path | None = None
    source_metadata_path: Path | None = None
    q2d_conductors_csv_path: Path | None = None
    q2d_conductors_json_path: Path | None = None
    recipes: tuple[AedtRecipeSpec, ...]

    @field_validator("id")
    @classmethod
    def _validate_case_id(cls, value: str) -> str:
        safe = safe_aedt_name(value)
        if safe != value:
            raise ValueError(f"case id must be a safe AEDT token: {value!r}")
        return value

    @model_validator(mode="after")
    def _validate_case_contract(self) -> AedtNativeCaseSpec:
        if not self.recipes:
            raise ValueError("AEDT native cases require at least one recipe")
        recipe_ids = [recipe.id for recipe in self.recipes]
        if len(recipe_ids) != len(set(recipe_ids)):
            raise ValueError(f"case {self.id!r} has duplicate recipe ids")
        if any(
            recipe.type == "q2d_extraction"
            and recipe.assignment_source == "q2d_conductors"
            and self.q2d_conductors_json_path is None
            for recipe in self.recipes
        ):
            raise ValueError(
                f"case {self.id!r} uses q2d_conductors assignment but has no "
                "q2d_conductors_json_path"
            )
        if any(
            recipe.type == "q2d_extraction"
            and recipe.q2d_geometry_mode == "native_2d"
            and self.source_metadata_path is None
            for recipe in self.recipes
        ):
            raise ValueError(
                f"case {self.id!r} uses native_2d Q2D geometry but has no source_metadata_path"
            )
        return self


class AedtNativePackageSpec(BaseModel):
    """Validated AEDT-native package manifest source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    project_name: str
    project_path: Path | None = None
    platform: AedtPlatform = "ubuntu"
    runtime: AedtRuntimeSpec = Field(default_factory=AedtRuntimeSpec)
    hpc_profile: AedtHpcProfileSpec = Field(default_factory=AedtHpcProfileSpec)
    hpc_resource: AedtHpcResourceSpec | None = None
    import_run_profile: AedtNativeRunProfileSpec | None = None
    solve_run_profile: AedtNativeRunProfileSpec | None = None
    point_local_sweep: bool = False
    cases: tuple[AedtNativeCaseSpec, ...]

    @field_validator("project_name")
    @classmethod
    def _validate_project_name(cls, value: str) -> str:
        safe = safe_aedt_name(value)
        if safe != value:
            raise ValueError(f"project_name must be a safe AEDT token: {value!r}")
        return value

    @model_validator(mode="after")
    def _validate_package_contract(self) -> AedtNativePackageSpec:
        if not self.cases:
            raise ValueError("AEDT native packages require at least one case")
        case_ids = [case.id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("AEDT native package case ids must be unique")

        design_names: list[str] = []
        for case in self.cases:
            design_names.extend(recipe.resolved_design_name(case.id) for recipe in case.recipes)
        duplicates = sorted({name for name in design_names if design_names.count(name) > 1})
        if duplicates:
            raise ValueError(f"AEDT design names must be unique: {duplicates}")
        if self.import_run_profile is not None and self.import_run_profile.mode != "import":
            raise ValueError("import_run_profile must use mode='import'")
        if self.solve_run_profile is not None and self.solve_run_profile.mode != "solve":
            raise ValueError("solve_run_profile must use mode='solve'")
        return self

    def resolved_hpc_resource(self) -> AedtHpcResourceSpec:
        """Return the resource used to write ACF and run-config artifacts."""

        return self.hpc_resource or self.hpc_profile.resource()


class AedtNativePackageResult(BaseModel):
    """Paths written for one AEDT-native handoff package."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    package_dir: Path
    manifest_path: Path
    readme_path: Path
    requirements_path: Path
    gds_dir: Path
    tech_dir: Path
    layer_mapping_dir: Path
    metadata_dir: Path
    hpc_dir: Path
    run_configs_dir: Path
    acf_path: Path
    hpc_profile_path: Path
    import_run_config_path: Path
    solve_run_config_path: Path
    scripts_dir: Path
    python_script_path: Path
    q2d_script_path: Path
    bash_script_path: Path
    powershell_script_path: Path
    project_path: Path
    platform: AedtPlatform
    case_count: int
    recipe_count: int


class AedtNativeHandoffArchiveResult(BaseModel):
    """Archive produced for an AEDT-native handoff package."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    archive_path: Path
    included: tuple[str, ...]


__all__ = [
    "AedtCompiledMaterialSpec",
    "AedtGrpcMode",
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
    "safe_aedt_name",
]
