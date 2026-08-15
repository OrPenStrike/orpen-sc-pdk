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
import re
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
    profile = (material_context or {}).get("material_profile") or {}
    if profile:
        summary.update(
            {
                "data_class": profile.get("data_class"),
                "allowed_consumers": profile.get("allowed_consumers"),
                "publication_state": profile.get("publication_state"),
                "promotion_eligible": profile.get("promotion_eligible"),
            }
        )
    if result_dir is not None:
        write_json(result_dir / "aedt_material_context_applied.json", summary)
    return summary


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
    "register_aedt_materials",
]
