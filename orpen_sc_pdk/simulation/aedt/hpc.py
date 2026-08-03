"""Notebook-side AEDT HPC/ACF package helpers.

This module owns the small public model used to render ANSYS AEDT `.acf`
worker configuration files. It does not launch AEDT or decide solver geometry;
the native package writer copies these artifacts into a portable handoff.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_AEDT_Q2D_HPC_DESIGN_TYPE = "2D Extractor"
_AEDT_HPC_DEFAULT_ALLOWED_DISTRIBUTION_TYPES = (
    "Variations",
    "Frequencies",
    "Mesh Assembly",
    "Transient Excitations",
    "Domain Solver",
)


class AedtHpcResourceSpec(BaseModel):
    """Local AEDT worker resource policy used to render an ANSYS ACF file."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_name: str = "aedt-q2d-local"
    machine_name: str = "localhost"
    num_engines: int = Field(default=1, ge=1)
    num_cores: int = Field(default=4, ge=1)
    max_workers: int = Field(default=16, ge=1)
    core_budget: int | None = Field(default=64, ge=1)
    memory_mb_total: int | None = Field(default=240000, ge=1)
    memory_mb_per_worker: int | None = Field(default=None, ge=1)
    ram_percent: int | None = Field(default=None, ge=1, le=100)
    num_job_cores: int = Field(default=0, ge=0)
    num_gpus: int = Field(default=0, ge=0)
    use_auto_settings: bool = True
    num_variations_to_distribute: int = Field(default=1, ge=1)
    allowed_distribution_types: tuple[str, ...] = Field(
        default_factory=lambda: _AEDT_HPC_DEFAULT_ALLOWED_DISTRIBUTION_TYPES
    )

    @field_validator("profile_name", "machine_name")
    @classmethod
    def _validate_nonempty(cls, value: str) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("AEDT HPC resource text fields must not be empty")
        return text

    @field_validator("allowed_distribution_types")
    @classmethod
    def _validate_distribution_types(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(str(item).strip() for item in value)
        if not normalized or any(not item for item in normalized):
            raise ValueError("allowed_distribution_types must contain non-empty entries")
        return normalized

    @model_validator(mode="after")
    def _validate_resource_contract(self) -> AedtHpcResourceSpec:
        if self.core_budget is not None and self.num_cores * self.max_workers > self.core_budget:
            raise ValueError(
                "AEDT HPC worker core request exceeds core_budget: "
                f"num_cores={self.num_cores}, max_workers={self.max_workers}, "
                f"core_budget={self.core_budget}"
            )
        if self.memory_mb_per_worker is not None and self.memory_mb_total is not None:
            requested = self.memory_mb_per_worker * self.max_workers
            if requested > self.memory_mb_total:
                raise ValueError(
                    "AEDT HPC worker memory request exceeds memory_mb_total: "
                    f"{requested} MB requested for {self.max_workers} workers, "
                    f"memory_mb_total={self.memory_mb_total}"
                )
        return self

    def resolved_memory_mb_per_worker(self) -> int | None:
        """Return the per-worker memory budget in MB when it can be computed."""

        if self.memory_mb_per_worker is not None:
            return self.memory_mb_per_worker
        if self.memory_mb_total is None:
            return None
        return max(1, int(self.memory_mb_total // self.max_workers))

    def resolved_ram_percent(self) -> int:
        """Return the ACF `RAMPercent` value for one AEDT worker."""

        if self.ram_percent is not None:
            return self.ram_percent
        memory_mb_per_worker = self.resolved_memory_mb_per_worker()
        if self.memory_mb_total is None or memory_mb_per_worker is None:
            return 90
        return max(1, min(100, int(memory_mb_per_worker * 100 / self.memory_mb_total)))

    def resolved_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly resolved resource payload."""

        return {
            **self.model_dump(mode="json"),
            "memory_mb_per_worker_resolved": self.resolved_memory_mb_per_worker(),
            "ram_percent_resolved": self.resolved_ram_percent(),
            "worker_core_total": self.num_cores * self.max_workers,
        }


class AedtHpcValidationSpec(BaseModel):
    """Machine-level defaults that also bound generated AEDT worker resources."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    core_budget: int | None = Field(default=64, ge=1)
    memory_mb_total: int | None = Field(default=240000, ge=1)
    allowed_distribution_types: tuple[str, ...] = Field(
        default_factory=lambda: _AEDT_HPC_DEFAULT_ALLOWED_DISTRIBUTION_TYPES
    )

    @field_validator("allowed_distribution_types")
    @classmethod
    def _validate_distribution_types(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(str(item).strip() for item in value)
        if not normalized or any(not item for item in normalized):
            raise ValueError("allowed_distribution_types must contain non-empty entries")
        return normalized


class AedtHpcProfileSpec(BaseModel):
    """Named AEDT HPC profile with overridable resource defaults."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_name: str = "aedt-q2d-local"
    resource_defaults: dict[str, Any] = Field(default_factory=dict)
    validation: AedtHpcValidationSpec = Field(default_factory=AedtHpcValidationSpec)

    @field_validator("profile_name")
    @classmethod
    def _validate_profile_name(cls, value: str) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("AEDT HPC profile_name must not be empty")
        return text

    @model_validator(mode="after")
    def _validate_profile_defaults(self) -> AedtHpcProfileSpec:
        self.resource()
        return self

    def resource(self, **overrides: Any) -> AedtHpcResourceSpec:
        """Build a validated resource from profile defaults plus explicit overrides."""

        payload = {**self.resource_defaults, **overrides}
        payload["profile_name"] = payload.get("profile_name") or self.profile_name
        payload["core_budget"] = self.validation.core_budget
        payload["memory_mb_total"] = self.validation.memory_mb_total
        payload["allowed_distribution_types"] = self.validation.allowed_distribution_types
        return AedtHpcResourceSpec(**payload)


class AedtAcfConfigSpec(BaseModel):
    """ANSYS HPC configuration file content for AEDT point-local workers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    config_name: str = "OrPen_Q2D_Local"
    design_type: str = _AEDT_Q2D_HPC_DESIGN_TYPE
    resource: AedtHpcResourceSpec = Field(default_factory=AedtHpcResourceSpec)

    @field_validator("config_name", "design_type")
    @classmethod
    def _validate_nonempty(cls, value: str) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("ACF config fields must not be empty")
        return text

    def render(self) -> str:
        """Render an ANSYS `.acf` file."""

        return render_aedt_acf_config(self)


def render_aedt_acf_config(config: AedtAcfConfigSpec) -> str:
    """Render an ANSYS HPC configuration file from a validated spec."""

    resource = config.resource
    distribution_types = ", ".join(
        f"'{distribution_type}'" for distribution_type in resource.allowed_distribution_types
    )
    distribution_count = len(resource.allowed_distribution_types)
    return f"""$begin 'Configs'
\t$begin 'Configs'
\t\t$begin 'DSOConfig'
\t\t\tConfigName='{config.config_name}'
\t\t\tDesignType='{config.design_type}'
\t\t\t$begin 'DSOMachineList'
\t\t\t\t$begin 'DSOMachineInfo'
\t\t\t\t\tMachineName='{resource.machine_name}'
\t\t\t\t\tNumEngines={resource.num_engines}
\t\t\t\t\tNumCores={resource.num_cores}
\t\t\t\t\tIsEnabled=true
\t\t\t\t\tRAMPercent={resource.resolved_ram_percent()}
\t\t\t\t\tNumJobCores={resource.num_job_cores}
\t\t\t\t\tNumGPUs={resource.num_gpus}
\t\t\t\t$end 'DSOMachineInfo'
\t\t\t$end 'DSOMachineList'
\t\t\tUseAutoSettings={str(resource.use_auto_settings).lower()}
\t\t\tNumVariationsToDistribute={resource.num_variations_to_distribute}
\t\t\t$begin 'DSOJobDistributionInfo'
\t\t\t\tAllowedDistributionTypes[{distribution_count}: {distribution_types}]
\t\t\t\tEnable2LevelDistribution=false
\t\t\t\tNumL1Engines=0
\t\t\t\tUseDefaultsForDistributionTypes=false
\t\t\t\tContext()
\t\t\t$end 'DSOJobDistributionInfo'
\t\t\t$begin 'DSOMachineOptionsInfo'
\t\t\t\tMenuValues()
\t\t\t\tIntValues()
\t\t\t\tBoolValues()
\t\t\t\tDoubleValues()
\t\t\t$end 'DSOMachineOptionsInfo'
\t\t$end 'DSOConfig'
\t$end 'Configs'
$end 'Configs'
"""


def write_aedt_hpc_artifacts(
    package_dir: Path,
    hpc_dir: Path,
    resource: AedtHpcResourceSpec,
) -> tuple[dict[str, Any], Path, Path]:
    """Write AEDT HPC ACF/profile artifacts and return the manifest payload."""

    hpc_dir.mkdir(parents=True, exist_ok=True)
    acf_path = hpc_dir / "q2d_local.acf"
    profile_path = hpc_dir / "aedt_hpc_profile.json"
    acf_config = AedtAcfConfigSpec(resource=resource)
    acf_path.write_text(acf_config.render(), encoding="utf-8")
    payload = {
        "schema_version": "aedt-hpc-profile.v1",
        "profile": resource.profile_name,
        "acf_file": _relative_posix(package_dir, acf_path),
        "acf_config_name": acf_config.config_name,
        "acf_design_type": acf_config.design_type,
        "project_concurrency": "isolated_worker_projects",
        "resource": resource.resolved_payload(),
    }
    payload["profile_file"] = _relative_posix(package_dir, profile_path)
    profile_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload, acf_path, profile_path


def _relative_posix(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


__all__ = [
    "AedtAcfConfigSpec",
    "AedtHpcProfileSpec",
    "AedtHpcResourceSpec",
    "AedtHpcValidationSpec",
    "render_aedt_acf_config",
    "write_aedt_hpc_artifacts",
]
