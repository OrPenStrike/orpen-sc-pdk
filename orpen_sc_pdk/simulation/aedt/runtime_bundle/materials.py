"""Run-side AEDT material context helpers for handoff packages.

This module is copied with ``runtime_bundle`` into AEDT handoff packages and
executed on the target machine. It owns loading compiled material contexts,
binding imported objects back to layer-stack rows, creating AEDT project
materials, and writing material-application audit records. It does not compile
notebook-side material policy or decide solver boundary assignments.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from importlib import metadata
from pathlib import Path
from typing import Any

from .io import package_path, write_json


def load_aedt_material_context(case: dict[str, Any], package_root) -> dict[str, Any]:
    """Load the compiled material context referenced by a manifest case."""

    relative = case.get("aedt_material_context")
    if not relative:
        raise RuntimeError(f"case {case.get('id')!r} is missing aedt_material_context")
    path = package_path(package_root, relative)
    context = json.loads(path.read_text(encoding="utf-8"))
    if context.get("schema_version") not in {
        "aedt-material-context.v1",
        "aedt-material-context.v2",
    }:
        raise RuntimeError(
            f"Unsupported AEDT material context schema: {context.get('schema_version')!r}"
        )
    profile = context.get("material_profile")
    if profile is not None:
        encoded = json.dumps(
            profile,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        if hashlib.sha256(encoded).hexdigest() != context.get("material_profile_hash"):
            raise RuntimeError("AEDT material profile hash does not match its payload")
    return context


def material_context_bindings(material_context: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Return layer/object bindings from a compiled material context."""

    return list((material_context or {}).get("bindings") or [])


def material_context_compiled_materials(
    material_context: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Return AEDT material specs from a compiled material context."""

    return list((material_context or {}).get("compiled_materials") or [])


def material_context_binding_by_layer_number(
    material_context: dict[str, Any] | None,
) -> dict[int, dict[str, Any]]:
    """Index bindings by AEDT layer number for imported GDS object lookup."""

    bindings = {}
    for binding in material_context_bindings(material_context):
        layer = binding.get("aedt_layer_number")
        if layer is None:
            continue
        bindings[int(layer)] = binding
    return bindings


def material_context_binding_for_object_name(
    name: str,
    material_context: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Resolve an imported AEDT object name to its material-context binding."""

    text = str(name)
    layer = layer_number_from_object_name(text)
    if layer is not None:
        binding = material_context_binding_by_layer_number(material_context).get(layer)
        if binding is not None:
            return binding
    candidates = []
    for binding in material_context_bindings(material_context):
        base = str(binding.get("object_name_base") or "")
        if not base:
            continue
        if text == base or text.startswith(f"{base}_"):
            candidates.append(binding)
    if not candidates:
        return None
    candidates.sort(key=lambda item: len(str(item.get("object_name_base") or "")), reverse=True)
    return candidates[0]


def material_context_material_for_row(
    row: dict[str, Any],
    material_context: dict[str, Any] | None,
) -> Any:
    """Return the AEDT material name for a layer-mapping row, when bound."""

    layer = row.get("aedt_layer_number")
    if layer in (None, ""):
        return None
    binding = material_context_binding_by_layer_number(material_context).get(int(layer))
    if binding is None:
        return None
    return binding.get("aedt_material_name")


def ensure_aedt_project_materials(
    app: Any,
    material_context: dict[str, Any] | None,
    result_dir=None,
    *,
    allow_missing: bool = False,
) -> dict[str, Any]:
    """Create/update AEDT project materials declared by a material context.

    The target AEDT project owns the material objects. This function applies
    only properties supported by the compiled context and writes an audit
    summary when a result directory is supplied.
    """

    material_specs = material_context_compiled_materials(material_context)
    if not material_specs:
        return {"material_count": 0, "materials": []}
    materials_manager = getattr(app, "materials", None)
    if materials_manager is None:
        if allow_missing:
            summary = {
                "material_count": 0,
                "expected_material_count": len(material_specs),
                "materials": [],
                "skipped": True,
                "skip_reason": f"{type(app).__name__} has no materials manager",
            }
            if result_dir is not None:
                write_json(result_dir / "aedt_material_context_applied.json", summary)
            return summary
        raise RuntimeError(f"{type(app).__name__} does not expose a materials manager")

    records = []
    for spec in material_specs:
        name = str(spec.get("aedt_material_name") or "").strip()
        if not name:
            raise RuntimeError(f"Compiled AEDT material has no name: {spec}")
        material_obj = existing_or_new_aedt_material(materials_manager, name)
        supported = spec.get("supported_properties") or {}
        applied = apply_aedt_material_properties(material_obj, supported)
        records.append(
            {
                "aedt_material_name": name,
                "source_physical_material_key": spec.get("source_physical_material_key"),
                "material_kind": spec.get("material_kind"),
                "applied": applied,
                "unsupported_properties": spec.get("unsupported_properties") or {},
            }
        )
    summary = {
        "schema_version": "aedt-material-write-attempt.v1",
        "status": "write_attempt_accepted_by_api",
        "independent_readback": False,
        "material_count": len(records),
        "materials": records,
    }
    if result_dir is not None:
        write_json(result_dir / "aedt_material_context_applied.json", summary)
    return summary


def readback_aedt_project_materials(
    app: Any,
    material_context: dict[str, Any],
    expected_substrate_objects: list[str],
    result_dir,
    evidence_identity: dict[str, Any],
) -> dict[str, Any]:
    """Read stored project material values and object assignments after save."""

    if not material_context.get("readback_required"):
        raise RuntimeError("Promotion material readback requires readback_required=true")
    profile = material_context.get("material_profile")
    profile_hash = str(material_context.get("material_profile_hash") or "")
    if not isinstance(profile, dict) or not profile_hash:
        raise RuntimeError("Promotion material readback requires a hashed material profile")
    if profile.get("material_profile_id") != "d3-q2d-silicon-er11p9-scalar-v1":
        raise RuntimeError("Required material readback received an unsupported profile")
    expected_name = str(profile.get("solver_material_name") or "").strip()
    if not expected_name:
        raise RuntimeError("Material profile has no requested solver material name")

    manager = getattr(app, "materials", None)
    native_manager = getattr(manager, "_omaterial_manager", None)
    get_names = getattr(native_manager, "GetProjectMaterialNames", None)
    if manager is None or not callable(get_names):
        raise RuntimeError("AEDT project material-name readback is unavailable")
    raw_project_names = get_names()
    project_names = (
        [str(raw_project_names)]
        if isinstance(raw_project_names, str)
        else [str(value) for value in raw_project_names]
    )
    matching_names = [
        value for value in project_names if value.casefold() == expected_name.casefold()
    ]
    if len(matching_names) != 1:
        raise RuntimeError(
            f"Expected one custom project material {expected_name!r}, got {matching_names!r}"
        )
    stored_name = matching_names[0]
    fresh_reader = getattr(manager, "_aedmattolibrary", None)
    if not callable(fresh_reader):
        raise RuntimeError("AEDT GetData material reconstruction is unavailable")
    fresh = fresh_reader(stored_name)
    if fresh is None:
        raise RuntimeError(f"AEDT GetData returned no material for {stored_name!r}")

    properties = {
        name: _readback_scalar_property(getattr(fresh, name, None), name)
        for name in (
            "permittivity",
            "permeability",
            "dielectric_loss_tangent",
            "conductivity",
        )
    }
    expected = {"permittivity": 11.9, "permeability": 1.0}
    for property_name, expected_value in expected.items():
        record = properties[property_name]
        if record["property_type"] != "simple" or record["normalized_value"] != expected_value:
            raise RuntimeError(
                f"Stored AEDT {property_name} mismatch: {record!r}; expected {expected_value}"
            )

    if not expected_substrate_objects:
        raise RuntimeError("Material readback requires expected substrate objects")
    if set(expected_substrate_objects) != {"q2d_die_D0", "q2d_die_D1"}:
        raise RuntimeError(
            "D3 material readback requires exactly q2d_die_D0 and q2d_die_D1, got "
            f"{expected_substrate_objects!r}"
        )
    editor = getattr(getattr(app, "modeler", None), "oeditor", None)
    get_property = getattr(editor, "GetPropertyValue", None)
    if not callable(get_property):
        raise RuntimeError("AEDT object material readback is unavailable")
    assignments = []
    for object_name in expected_substrate_objects:
        assigned = str(
            get_property("Geometry3DAttributeTab", object_name, "Material") or ""
        ).strip().strip('"')
        if assigned.casefold() != stored_name.casefold():
            raise RuntimeError(
                f"AEDT object {object_name!r} material mismatch: {assigned!r} != {stored_name!r}"
            )
        assignments.append({"object_name": object_name, "stored_material_name": assigned})

    write_attempt_path = Path(result_dir) / "aedt_material_context_applied.json"
    if not write_attempt_path.is_file():
        raise RuntimeError("Material readback requires the separate write-attempt record")
    write_attempt = json.loads(write_attempt_path.read_text(encoding="utf-8"))
    if (
        write_attempt.get("status") != "write_attempt_accepted_by_api"
        or write_attempt.get("independent_readback") is not False
    ):
        raise RuntimeError("Material write-attempt record is invalid")

    project_file = Path(str(getattr(app, "project_file", None) or ""))
    if not project_file.is_file() or project_file.stat().st_size <= 0:
        raise RuntimeError(f"Saved AEDT project is unavailable for readback: {project_file}")
    project_record = {
        "path": str(project_file.resolve()),
        "size_bytes": project_file.stat().st_size,
        "sha256": hashlib.sha256(project_file.read_bytes()).hexdigest(),
    }

    try:
        pyaedt_version = metadata.version("ansys-aedt-core")
    except metadata.PackageNotFoundError as exc:
        raise RuntimeError("Installed PyAEDT distribution version is unavailable") from exc
    aedt_version = str(getattr(app, "aedt_version_id", None) or "").strip()
    if not aedt_version:
        raise RuntimeError("Running AEDT version is unavailable for material readback")
    method = "post-save-GetProjectMaterialNames-GetData-direct-object-property.v1"
    normalized_properties = {
        name: {
            "property_type": record["property_type"],
            "normalized_value": record["normalized_value"],
            "scientific_authority": record["scientific_authority"],
        }
        for name, record in properties.items()
    }
    authority = {
        "material_profile_hash": profile_hash,
        "stored_material_name": stored_name,
        "source_type": "custom_project_material",
        "properties": normalized_properties,
        "solver_identity": {
            "aedt_version": aedt_version,
            "pyaedt_version": pyaedt_version,
        },
        "policy_source": material_context.get("policy_source"),
        "readback_method": method,
    }
    authority_hash = hashlib.sha256(
        json.dumps(
            authority,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()
    receipt = {
        "schema_version": "aedt-material-readback.v1",
        "status": "PASS",
        "method": method,
        "material_profile_id": profile.get("material_profile_id"),
        "material_profile_hash": profile_hash,
        "stored_material_name": stored_name,
        "source_type": "custom_project_material",
        "material_authority": authority,
        "material_authority_hash": authority_hash,
        "substrate_assignments": assignments,
        "provenance_layers": {
            "requested": {
                "material_profile": profile,
                "material_profile_hash": profile_hash,
            },
            "resolved": authority,
            "applied_write_attempt": write_attempt,
            "readback": {
                "status": "PASS",
                "stored_material_name": stored_name,
                "properties": properties,
                "substrate_assignments": assignments,
                "method": method,
            },
        },
        "evidence_identity": evidence_identity,
        "saved_project": project_record,
    }
    evidence_hash = hashlib.sha256(
        json.dumps(
            receipt,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()
    record = {**receipt, "material_evidence_snapshot_hash": evidence_hash}
    write_json(result_dir / "aedt_material_readback.json", record)
    return record


def _readback_scalar_property(property_obj: Any, name: str) -> dict[str, Any]:
    if property_obj is None:
        raise RuntimeError(f"AEDT GetData material is missing property {name!r}")
    property_type = str(getattr(property_obj, "type", "") or "").strip().casefold()
    raw_value = getattr(property_obj, "value", None)
    try:
        normalized = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"AEDT stored material property {name!r} is not scalar: {raw_value!r}"
        ) from exc
    if not math.isfinite(normalized):
        raise RuntimeError(f"AEDT stored material property {name!r} is not finite")
    return {
        "property_type": property_type,
        "raw_value": raw_value if isinstance(raw_value, (str, int, float)) else str(raw_value),
        "normalized_value": normalized,
        "scientific_authority": name in {"permittivity", "permeability"},
    }


register_aedt_materials = ensure_aedt_project_materials


def existing_or_new_aedt_material(materials_manager: Any, name: str) -> Any:
    """Return an existing AEDT material object or create it through PyAEDT."""

    material_obj = None
    try:
        existing = materials_manager.exists_material(name)
        if existing is not None and existing is not False and hasattr(existing, "update"):
            material_obj = existing
    except Exception:
        material_obj = None
    if material_obj is None:
        try:
            material_obj = materials_manager.add_material(name)
        except Exception as exc:
            raise RuntimeError(f"Failed to create AEDT material {name!r}") from exc
    if material_obj is None:
        raise RuntimeError(f"PyAEDT did not return a material object for {name!r}")
    return material_obj


def apply_aedt_material_properties(material_obj: Any, supported: dict[str, Any]) -> dict[str, Any]:
    """Apply supported compiled properties to one AEDT material object."""

    property_names = (
        "permittivity",
        "permeability",
        "dielectric_loss_tangent",
        "conductivity",
    )
    applied = {}
    for property_name in property_names:
        value = supported.get(property_name)
        if value is None:
            continue
        try:
            setattr(material_obj, property_name, value)
            applied[property_name] = value
        except Exception as exc:
            raise RuntimeError(
                f"Failed to set AEDT material property {property_name!r} on "
                f"{getattr(material_obj, 'name', material_obj)!r}"
            ) from exc
    update = getattr(material_obj, "update", None)
    if callable(update):
        ok = update()
        if ok is False:
            material_name = getattr(material_obj, "name", material_obj)
            raise RuntimeError(f"AEDT material update returned False for {material_name!r}")
    return applied


def layer_number_from_object_name(name: str) -> int | None:
    """Parse the AEDT layer number from generated imported object names."""

    match = re.search(r"signal(\d+)", str(name), flags=re.IGNORECASE)
    return None if match is None else int(match.group(1))


__all__ = [
    "apply_aedt_material_properties",
    "ensure_aedt_project_materials",
    "existing_or_new_aedt_material",
    "layer_number_from_object_name",
    "load_aedt_material_context",
    "material_context_binding_by_layer_number",
    "material_context_binding_for_object_name",
    "material_context_bindings",
    "material_context_compiled_materials",
    "material_context_material_for_row",
    "readback_aedt_project_materials",
    "register_aedt_materials",
]
