"""Accepted target-specific material policy for new D3 Q2D extractions."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any

from orpen_sc_pdk.simulation.aedt.models import (
    AedtCompiledMaterialSpec,
    AedtMaterialContext,
    AedtMaterialPolicySpec,
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
        "allowed_consumers": ["orpen_candidate_validation"],
        "publication_state": "diagnostic",
        "promotion_eligible": False,
    }


def material_profile_hash() -> str:
    """Return the immutable requested-policy hash."""

    return sha256_json(d3_q2d_material_profile())


def d3_q2d_material_policy() -> AedtMaterialPolicySpec:
    """Return the recipe marker that makes resume checks require true readback."""

    return AedtMaterialPolicySpec(
        conductor_material=CONDUCTOR_AEDT_MATERIAL,
        material_condition="NOT_AVAILABLE",
        material_profile_id=MATERIAL_PROFILE_ID,
        readback_required=True,
    )


def _git_revision(*args: str) -> str:
    root = Path(__file__).resolve().parents[3]
    try:
        return subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"D3 Q2D packaging requires Git identity: {' '.join(args)}") from exc


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
    profile_hash = sha256_json(profile)
    return AedtMaterialContext(
        schema_version=MATERIAL_CONTEXT_SCHEMA,
        material_condition="NOT_AVAILABLE",
        material_profile=profile,
        material_profile_hash=profile_hash,
        registry_hash=sha256_json(
            {
                "schema_version": "d3-target-material-policy-registry.v1",
                "material_profile_hash": profile_hash,
            }
        ),
        readback_required=True,
        policy_source={
            "repository": "OrPen",
            "revision": _git_revision("rev-parse", "HEAD"),
            "integration_baseline_revision": _git_revision(
                "merge-base", "HEAD", "origin/develop"
            ),
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


def d3_q2d_policy_identity_from_context(context: dict[str, Any]) -> dict[str, Any]:
    """Return the case-neutral requested policy identity carried by cache keys."""

    return {
        "material_profile": context.get("material_profile"),
        "material_profile_hash": context.get("material_profile_hash"),
        "registry_hash": context.get("registry_hash"),
        "policy_source": context.get("policy_source"),
    }


@lru_cache(maxsize=1)
def d3_q2d_requested_policy_identity() -> dict[str, Any]:
    """Return the current source-bound identity for a new D3 request."""

    context = d3_q2d_material_context().model_dump(mode="json")
    return d3_q2d_policy_identity_from_context(context)


def validate_d3_q2d_material_receipt(
    *,
    material_context: dict[str, Any],
    write_attempt: dict[str, Any],
    receipt: dict[str, Any],
    expected_policy_identity: dict[str, Any],
    expected_case_id: str,
    expected_material_context_hash: str,
    expected_cross_section_hash: str,
    run_root: Path,
) -> dict[str, Any]:
    """Validate one complete requested/resolved/applied/readback receipt."""

    if material_context.get("schema_version") != MATERIAL_CONTEXT_SCHEMA:
        raise ValueError("D3 material context schema mismatch")
    if d3_q2d_policy_identity_from_context(material_context) != expected_policy_identity:
        raise ValueError("D3 material context does not match the request policy identity")
    profile = expected_policy_identity.get("material_profile")
    profile_hash = expected_policy_identity.get("material_profile_hash")
    if (
        profile != d3_q2d_material_profile()
        or profile_hash != sha256_json(profile)
        or expected_policy_identity.get("registry_hash")
        != sha256_json(
            {
                "schema_version": "d3-target-material-policy-registry.v1",
                "material_profile_hash": profile_hash,
            }
        )
        or not all(
            (expected_policy_identity.get("policy_source") or {}).get(field)
            for field in (
                "revision",
                "integration_baseline_revision",
                "path",
                "sha256",
                "runtime_bundle_sha256",
            )
        )
        or material_context.get("readback_required") is not True
        or material_context.get("material_condition") != "NOT_AVAILABLE"
    ):
        raise ValueError("D3 material request identity is incomplete")
    compiled = material_context.get("compiled_materials") or []
    if len(compiled) != 1:
        raise ValueError("D3 material context requires one custom project material")
    compiled_material = compiled[0]
    if (
        compiled_material.get("aedt_material_name") != SUBSTRATE_AEDT_MATERIAL
        or compiled_material.get("source_physical_material_key")
        != "d3-target-specific-silicon-er11p9"
        or compiled_material.get("supported_properties")
        != {
            "permittivity": SUBSTRATE_RELATIVE_PERMITTIVITY,
            "permeability": SUBSTRATE_RELATIVE_PERMEABILITY,
            "dielectric_loss_tangent": None,
            "conductivity": None,
        }
    ):
        raise ValueError("D3 compiled material does not match the accepted profile")

    if (
        write_attempt.get("status") != "write_attempt_accepted_by_api"
        or write_attempt.get("independent_readback") is not False
        or write_attempt.get("data_class") != profile.get("data_class")
        or write_attempt.get("allowed_consumers") != profile.get("allowed_consumers")
        or write_attempt.get("publication_state") != profile.get("publication_state")
        or write_attempt.get("promotion_eligible") is not False
    ):
        raise ValueError("D3 material write-attempt record is invalid")
    attempted_materials = write_attempt.get("materials") or []
    attempted = {
        item.get("aedt_material_name"): item.get("applied")
        for item in attempted_materials
    }
    if len(attempted_materials) != 1 or attempted != {
        SUBSTRATE_AEDT_MATERIAL: {
            "permittivity": SUBSTRATE_RELATIVE_PERMITTIVITY,
            "permeability": SUBSTRATE_RELATIVE_PERMEABILITY,
        }
    }:
        raise ValueError("D3 material write-attempt values mismatch")

    snapshot_hash = str(receipt.get("material_evidence_snapshot_hash") or "")
    receipt_payload = dict(receipt)
    receipt_payload.pop("material_evidence_snapshot_hash", None)
    if not snapshot_hash or snapshot_hash != sha256_json(receipt_payload):
        raise ValueError("D3 material evidence snapshot hash mismatch")
    authority = receipt.get("material_authority")
    if not isinstance(authority, dict) or receipt.get("material_authority_hash") != sha256_json(
        authority
    ):
        raise ValueError("D3 material authority hash mismatch")
    if (
        receipt.get("schema_version") != "aedt-material-readback.v1"
        or receipt.get("status") != "PASS"
        or receipt.get("data_class") != profile.get("data_class")
        or receipt.get("allowed_consumers") != profile.get("allowed_consumers")
        or receipt.get("publication_state") != profile.get("publication_state")
        or receipt.get("promotion_eligible") is not False
        or receipt.get("material_profile_id") != MATERIAL_PROFILE_ID
        or receipt.get("material_profile_hash") != profile_hash
        or receipt.get("stored_material_name") != authority.get("stored_material_name")
        or receipt.get("source_type") != authority.get("source_type")
        or receipt.get("method") != authority.get("readback_method")
        or authority.get("material_profile_hash") != profile_hash
        or authority.get("stored_material_name") != SUBSTRATE_AEDT_MATERIAL
        or authority.get("source_type") != "custom_project_material"
        or authority.get("policy_source") != expected_policy_identity.get("policy_source")
        or not authority.get("readback_method")
        or not all((authority.get("solver_identity") or {}).get(field) for field in (
            "aedt_version",
            "pyaedt_version",
        ))
    ):
        raise ValueError("D3 material authority does not match the request")
    properties = authority.get("properties") or {}
    for name, expected in (
        ("permittivity", SUBSTRATE_RELATIVE_PERMITTIVITY),
        ("permeability", SUBSTRATE_RELATIVE_PERMEABILITY),
    ):
        record = properties.get(name) or {}
        value = record.get("normalized_value")
        if (
            record.get("property_type") != "simple"
            or isinstance(value, bool)
            or not isinstance(value, (int, float))
            or value != expected
            or record.get("scientific_authority") is not True
        ):
            raise ValueError(f"D3 stored {name} mismatch")
    for name in ("dielectric_loss_tangent", "conductivity"):
        record = properties.get(name) or {}
        value = record.get("normalized_value")
        if (
            record.get("property_type") != "simple"
            or isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or record.get("scientific_authority") is not False
        ):
            raise ValueError(f"D3 solver-created {name} readback is invalid")

    expected_assignments = {
        ("q2d_die_D0", SUBSTRATE_AEDT_MATERIAL.casefold()),
        ("q2d_die_D1", SUBSTRATE_AEDT_MATERIAL.casefold()),
    }
    assignments = {
        (item.get("object_name"), str(item.get("stored_material_name") or "").casefold())
        for item in receipt.get("substrate_assignments") or []
    }
    if assignments != expected_assignments:
        raise ValueError("D3 substrate assignment readback mismatch")
    layers = receipt.get("provenance_layers") or {}
    readback_layer = layers.get("readback") or {}
    readback_properties = readback_layer.get("properties") or {}
    if (
        (layers.get("requested") or {}).get("material_context") != material_context
        or layers.get("resolved") != authority
        or layers.get("applied_write_attempt") != write_attempt
        or readback_layer.get("status") != "PASS"
        or readback_layer.get("stored_material_name") != authority.get("stored_material_name")
        or readback_layer.get("method") != authority.get("readback_method")
        or readback_layer.get("substrate_assignments")
        != receipt.get("substrate_assignments")
        or set(readback_properties) != set(properties)
        or any(
            "raw_value" not in readback_properties[name]
            or {
                field: readback_properties[name].get(field)
                for field in (
                    "property_type",
                    "normalized_value",
                    "scientific_authority",
                )
            }
            != properties[name]
            for name in properties
        )
    ):
        raise ValueError("D3 provenance layers are incomplete")
    identity = receipt.get("evidence_identity") or {}
    if (
        identity.get("case_id") != expected_case_id
        or identity.get("material_context_hash") != expected_material_context_hash
        or identity.get("cross_section_hash") != expected_cross_section_hash
        or not identity.get("layer_stack_hash")
        or not identity.get("geometry_settings_hash")
        or not identity.get("recipe_settings_hash")
    ):
        raise ValueError("D3 evidence identity does not match source artifacts")
    source_hashes = identity.get("source_hashes") or {}
    if source_hashes != {
        "aedt_material_context": expected_material_context_hash,
        "q2d_cross_section": expected_cross_section_hash,
    }:
        raise ValueError("D3 workflow source hashes do not match the receipt")

    saved_project = receipt.get("saved_project") or {}
    project_path = Path(str(saved_project.get("path") or ""))
    try:
        project_path.resolve().relative_to(run_root.resolve())
    except ValueError as exc:
        raise ValueError("D3 saved project is outside its run root") from exc
    if (
        not project_path.is_file()
        or project_path.stat().st_size != int(saved_project.get("size_bytes") or -1)
        or hashlib.sha256(project_path.read_bytes()).hexdigest() != saved_project.get("sha256")
    ):
        raise ValueError("D3 saved project record does not match the stored project")
    return {
        "material_profile_hash": str(profile_hash),
        "material_authority_hash": str(receipt["material_authority_hash"]),
        "material_evidence_snapshot_hash": snapshot_hash,
    }


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
    "d3_q2d_material_policy",
    "d3_q2d_material_profile",
    "d3_q2d_policy_identity_from_context",
    "d3_q2d_requested_policy_identity",
    "material_profile_hash",
    "sha256_json",
    "validate_d3_q2d_material_receipt",
    "write_d3_q2d_material_context",
]
