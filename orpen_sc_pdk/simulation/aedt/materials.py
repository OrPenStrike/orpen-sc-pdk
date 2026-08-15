"""Notebook-side AEDT material context compiler.

This module owns translation from public PDK layer/material sidecars into the
portable material context copied into AEDT handoff packages. It does not write
handoff package layouts or run PyAEDT.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from orpen_sc_pdk.materials import (
    get_material_alias_records,
    get_material_records,
    validate_aedt_material_records,
)
from orpen_sc_pdk.simulation.aedt.models import (
    AedtLayerMaterialBinding,
    AedtMaterialContext,
    _normalize_material_kind,
    safe_aedt_name,
)


def compile_aedt_material_context_from_mapping_path(
    path: str | Path,
    *,
    material_condition: str = "cryogenic",
) -> AedtMaterialContext:
    """Compile an AEDT material context from a layer-mapping JSON sidecar."""

    mapping_payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return compile_aedt_material_context(mapping_payload, material_condition=material_condition)


def compile_aedt_material_context(
    mapping_payload: Mapping[str, Any],
    *,
    material_condition: str = "cryogenic",
) -> AedtMaterialContext:
    """Compile public PDK layer/material bindings into a portable AEDT context."""

    records = get_material_records()
    validate_aedt_material_records(records)
    aliases = get_material_alias_records()
    rows = tuple(_aedt_material_mapping_rows(mapping_payload))
    bindings: list[AedtLayerMaterialBinding] = []

    for row in rows:
        layer_name = str(row.get("layer_name") or "").strip()
        if not layer_name:
            raise ValueError("AEDT layer mapping rows require layer_name")
        role = str(row.get("recommended_aedt_role") or "").strip() or "unknown"
        physical_material_key = str(row.get("material") or "").strip()
        if not physical_material_key:
            raise ValueError(f"AEDT layer {layer_name!r} has no material key")

        canonical_key, material = _resolve_material_record(physical_material_key, records, aliases)
        material_kind = _normalize_material_kind(material.get("material_kind"))
        _validate_aedt_role_material_kind(
            layer_name=layer_name,
            role=role,
            physical_material_key=canonical_key,
            material_kind=material_kind,
        )
        object_name_base = _aedt_object_name_base_from_row(row)
        aedt_material_name = _aedt_material_name_from_record(canonical_key, material)
        fallback_reason = aedt_material_fallback_reason(
            material_kind=material_kind,
            material_condition=material_condition,
        )
        binding = AedtLayerMaterialBinding(
            layer_name=layer_name,
            object_name_base=object_name_base,
            aedt_layer_number=_optional_int(row.get("aedt_layer_number")),
            aedt_datatype=_optional_int(row.get("aedt_datatype")),
            aedt_layer_tuple=_optional_text(row.get("aedt_layer_tuple")),
            role=role,
            physical_material_key=canonical_key,
            aedt_material_name=aedt_material_name,
            material_kind=material_kind,
            aedt_material_fallback_reason=fallback_reason,
            zmin_um=_optional_float(row.get("zmin_um")),
            thickness_um=_optional_float(row.get("thickness_um")),
        )
        bindings.append(binding)
    return AedtMaterialContext(
        material_condition=material_condition,
        registry_hash=_sha256_json({"materials": records, "material_aliases": aliases}),
        layer_stack_hash=_sha256_json(mapping_payload),
        bindings=tuple(sorted(bindings, key=lambda item: item.layer_name)),
        compiled_materials=(),
    )


def aedt_material_name_from_physical_key(physical_material_key: str) -> str:
    """Return the AEDT project material name for one physical material key."""

    canonical_key, material = _public_material_record(physical_material_key)
    return _aedt_material_name_from_record(canonical_key, material)


def aedt_material_name_for_physical_material(
    physical_material_key: str,
    *,
    material_kind: str,
    material_condition: str,
) -> str:
    """Return the AEDT assignment material for one physical material and condition."""

    canonical_key, material = _public_material_record(physical_material_key)
    canonical_kind = _normalize_material_kind(material.get("material_kind"))
    if _normalize_material_kind(material_kind) != canonical_kind:
        raise ValueError(
            f"AEDT material kind {material_kind!r} does not match public PDK material "
            f"{canonical_key!r} ({canonical_kind!r})."
        )
    return _aedt_material_name_from_record(canonical_key, material)


def aedt_material_fallback_reason(
    *,
    material_kind: str,
    material_condition: str,
) -> str | None:
    """Return why a physical material is represented by another AEDT material."""

    if material_kind == "superconductor":
        return (
            "superconducting public PDK materials are assigned as AEDT PEC; no numerical "
            "AEDT material is created"
        )
    return None


def _public_material_record(physical_material_key: str) -> tuple[str, Mapping[str, Any]]:
    records = get_material_records()
    validate_aedt_material_records(records)
    return _resolve_material_record(physical_material_key, records, get_material_alias_records())


def _aedt_material_name_from_record(
    physical_material_key: str,
    material: Mapping[str, Any],
) -> str:
    if material.get("is_superconducting"):
        return "pec"
    aedt_library_name = material.get("aedt_library_name")
    if not isinstance(aedt_library_name, str) or not aedt_library_name.strip():
        raise ValueError(
            f"Public PDK material {physical_material_key!r} has no explicit "
            "AEDT built-in library name."
        )
    return aedt_library_name


def _resolve_material_record(
    material_key: str,
    records: Mapping[str, Mapping[str, Any]],
    aliases: Mapping[str, str],
) -> tuple[str, Mapping[str, Any]]:
    text = str(material_key or "").strip()
    if not text:
        raise ValueError("Material key must not be empty")
    candidates = (text, aliases.get(text, ""))
    for candidate in candidates:
        if candidate and candidate in records:
            return candidate, records[candidate]
    raise KeyError(f"Unknown public PDK material key {material_key!r}")


def _aedt_material_mapping_rows(mapping_payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = mapping_payload.get("layers") or []
    if rows:
        return [row for row in rows if isinstance(row, Mapping)]
    import_rows = mapping_payload.get("gds_import_layers") or []
    region_rows = mapping_payload.get("region_layers") or []
    return [row for row in (*import_rows, *region_rows) if isinstance(row, Mapping)]


def _aedt_object_name_base_from_row(row: Mapping[str, Any]) -> str:
    role = str(row.get("recommended_aedt_role") or "").strip()
    import_policy = str(row.get("aedt_import_policy") or "").strip()
    if role == "vacuum_volume" or import_policy == "region":
        return "Vacuum"
    layer_name = str(row.get("layer_name") or "").strip()
    safe_layer_name = safe_aedt_name(layer_name)
    if safe_layer_name != layer_name:
        raise ValueError(
            f"AEDT object names must match safe LayerStack layer names; got {layer_name!r}"
        )
    return layer_name


def _validate_aedt_role_material_kind(
    *,
    layer_name: str,
    role: str,
    physical_material_key: str,
    material_kind: str,
) -> None:
    if role == "conductor" and material_kind not in {"conductor", "superconductor", "mixed"}:
        raise ValueError(
            f"AEDT conductor layer {layer_name!r} uses non-conductive material "
            f"{physical_material_key!r} ({material_kind})."
        )
    if role == "dielectric_volume" and material_kind not in {"dielectric", "mixed"}:
        raise ValueError(
            f"AEDT dielectric layer {layer_name!r} uses incompatible material "
            f"{physical_material_key!r} ({material_kind})."
        )
    if role == "vacuum_volume" and material_kind != "vacuum":
        raise ValueError(
            f"AEDT vacuum layer {layer_name!r} must use vacuum material, got "
            f"{physical_material_key!r} ({material_kind})."
        )


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _sha256_json(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


__all__ = [
    "aedt_material_fallback_reason",
    "aedt_material_name_for_physical_material",
    "aedt_material_name_from_physical_key",
    "compile_aedt_material_context",
    "compile_aedt_material_context_from_mapping_path",
]
