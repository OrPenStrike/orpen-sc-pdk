"""Accepted target-specific material policy for new D3 Q2D extractions."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from orpen_sc_pdk.simulation.aedt.models import (
    AedtCompiledMaterialSpec,
    AedtMaterialContext,
    AedtSupportedMaterialProperties,
)

MATERIAL_PROFILE_ID = "d3-q2d-silicon-er11p9-scalar-v1"
MATERIAL_PROFILE_SCHEMA = "d3-q2d-material-profile.v1"
MATERIAL_CONTEXT_SCHEMA = "aedt-material-context.v2"
SUBSTRATE_AEDT_MATERIAL = "D3Silicon_er11p9"
SUBSTRATE_RELATIVE_PERMITTIVITY = 11.9
SUBSTRATE_RELATIVE_PERMEABILITY = 1.0
CONDUCTOR_AEDT_MATERIAL = "pec"
REGION_AEDT_MATERIAL = "Vacuum"


def canonical_json(value: Any) -> str:
    """Return the canonical JSON representation used by D3 evidence hashes."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_json(value: Any) -> str:
    """Hash one canonical JSON value."""

    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def d3_q2d_material_profile() -> dict[str, Any]:
    """Return the accepted, case-neutral requested D3 material policy."""

    unavailable = {
        "status": "NOT_AVAILABLE",
        "reason": "not represented by the accepted scalar D3 Q2D target policy",
    }
    unconsumed = {
        "status": "NOT_AVAILABLE",
        "reason": "unconsumed by the lossless LC extraction; not assumed zero",
    }
    return {
        "schema_version": MATERIAL_PROFILE_SCHEMA,
        "material_profile_id": MATERIAL_PROFILE_ID,
        "material_profile_version": 1,
        "target_scope": "new_d3_q2d_single_and_coupled_pair",
        "physical_material_id": "d3-target-specific-silicon-er11p9",
        "physical_material_family": "silicon",
        "solver_material_id": SUBSTRATE_AEDT_MATERIAL,
        "solver_material_name": SUBSTRATE_AEDT_MATERIAL,
        "source_type": "custom_project_material",
        "default_vs_explicit_override": "explicit_custom_override",
        "electromagnetic_model": {
            "relative_permittivity": {
                "value": SUBSTRATE_RELATIVE_PERMITTIVITY,
                "unit": "1",
                "role": "scalar_isotropic_frequency_independent_target_policy",
            },
            "relative_permeability": {
                "value": SUBSTRATE_RELATIVE_PERMEABILITY,
                "unit": "1",
                "role": "explicit_nonmagnetic_modeling_assumption",
            },
            "temperature_K": unavailable,
            "empirical_condition": unavailable,
            "crystallographic_orientation": unavailable,
            "doping_resistivity": unavailable,
            "empirical_frequency_validity_range": unavailable,
            "dispersion": unavailable,
            "anisotropy": unavailable,
            "dielectric_loss_tangent": unconsumed,
            "conductivity": unconsumed,
        },
        "scientific_claims": {
            "measurement": False,
            "ansys_default": False,
            "cryogenic_material_claim": False,
        },
        "data_class": "project-internal",
        "allowed_consumers": [
            "orpen_candidate_validation",
            "reviewed_workbench_after_schema_handoff",
        ],
        "publication_state": "diagnostic_until_complete_true_readback",
    }


def material_profile_hash() -> str:
    """Return the immutable requested-policy hash."""

    return sha256_json(d3_q2d_material_profile())


def _repository_revision() -> str:
    root = Path(__file__).resolve().parents[3]
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("D3 Q2D packaging requires an exact OrPen Git revision") from exc


def _runtime_bundle_hash() -> str:
    root = Path(__file__).with_name("runtime_bundle")
    digest = hashlib.sha256()
    files = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    )
    if not files:
        raise RuntimeError(f"AEDT runtime bundle is empty: {root}")
    for path in files:
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def d3_q2d_material_context() -> AedtMaterialContext:
    """Compile the accepted profile into an explicit AEDT project material context."""

    profile = d3_q2d_material_profile()
    return AedtMaterialContext(
        schema_version=MATERIAL_CONTEXT_SCHEMA,
        material_condition="NOT_AVAILABLE",
        material_profile=profile,
        material_profile_hash=sha256_json(profile),
        readback_required=True,
        policy_source={
            "repository": "OrPen",
            "revision": _repository_revision(),
            "path": "orpen_sc_pdk/simulation/aedt/d3_q2d_material.py",
            "sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "runtime_bundle_sha256": _runtime_bundle_hash(),
        },
        compiled_materials=(
            AedtCompiledMaterialSpec(
                aedt_material_name=SUBSTRATE_AEDT_MATERIAL,
                source_physical_material_key="d3-target-specific-silicon-er11p9",
                material_kind="dielectric",
                supported_properties=AedtSupportedMaterialProperties(
                    permittivity=SUBSTRATE_RELATIVE_PERMITTIVITY,
                    permeability=SUBSTRATE_RELATIVE_PERMEABILITY,
                ),
            ),
        ),
    )


def write_d3_q2d_material_context(path: str | Path) -> Path:
    """Write the canonical context consumed by an AEDT handoff case."""

    output = Path(path)
    output.write_text(
        json.dumps(d3_q2d_material_context().model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    return output


__all__ = [
    "CONDUCTOR_AEDT_MATERIAL",
    "MATERIAL_CONTEXT_SCHEMA",
    "MATERIAL_PROFILE_ID",
    "REGION_AEDT_MATERIAL",
    "SUBSTRATE_AEDT_MATERIAL",
    "SUBSTRATE_RELATIVE_PERMEABILITY",
    "SUBSTRATE_RELATIVE_PERMITTIVITY",
    "canonical_json",
    "d3_q2d_material_context",
    "d3_q2d_material_profile",
    "material_profile_hash",
    "sha256_json",
    "write_d3_q2d_material_context",
]
