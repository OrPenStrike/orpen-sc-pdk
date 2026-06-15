"""Public material records and solver-overlay export helpers."""

from __future__ import annotations

import copy
import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from orpen_sc_pdk.tech import (
    interface_preset_records,
    material_alias_records,
    material_properties,
)

_OVERLAY_SOURCE = "orpen-sc-pdk tech.material_properties"
_INTERFACE_TYPES = {"MA", "MS", "SA"}
_MATERIAL_KINDS = {
    "conductor",
    "superconductor",
    "mixed",
    "conductive",
    "dielectric",
    "vacuum",
}


def get_material_records() -> dict[str, dict[str, Any]]:
    """Return a copy of public PDK material records."""
    return copy.deepcopy(material_properties)


def get_material_alias_records() -> dict[str, str]:
    """Return public aliases for generated or external material names."""

    return dict(material_alias_records)


def validate_material_kind_records(
    records: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, str]:
    """Return normalized generic material kinds for public material records."""

    source_records = material_properties if records is None else records
    normalized: dict[str, str] = {}
    for name, record in source_records.items():
        material_name = _material_name(name)
        normalized[material_name] = _normalize_material_kind(material_name, record)
    return normalized


def validate_material_alias_records(
    records: Mapping[str, str] | None = None,
    *,
    material_records: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, str]:
    """Validate aliases from generated material names to public PDK names."""

    source_records = material_alias_records if records is None else records
    public_material_names = set(validate_material_kind_records(material_records))
    normalized: dict[str, str] = {}
    for alias, target in source_records.items():
        alias_name = _material_alias_name(alias)
        target_name = _material_alias_name(target)
        if target_name not in public_material_names:
            msg = (
                f"Unknown material alias target: alias {alias_name!r} targets "
                f"unknown public material "
                f"{target_name!r}."
            )
            raise ValueError(msg)
        normalized[alias_name] = target_name
    return normalized


def get_gsim_material_kind_map(
    records: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, str]:
    """Return ``material_kind_by_name`` input for gsim interface classification."""

    return dict(validate_material_kind_records(records))


def get_gsim_material_kind_alias_map(
    records: Mapping[str, str] | None = None,
    *,
    material_records: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, str]:
    """Return aliases accepted by gsim material-kind interface classification."""

    return dict(validate_material_alias_records(records, material_records=material_records))


def get_interface_preset_records() -> dict[str, dict[str, Any]]:
    """Return a copy of public dielectric-interface preset records."""
    return copy.deepcopy(interface_preset_records)


def validate_interface_preset_records(
    records: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Validate and normalize dielectric-interface preset records.

    The public PDK owns record names and process provenance. `gsim` remains the
    owner of Palace postprocessing, material resolution, and report parsing.
    """

    source_records = interface_preset_records if records is None else records
    normalized: dict[str, dict[str, Any]] = {}
    for name, record in source_records.items():
        normalized[str(name)] = _normalize_interface_preset_record(str(name), record)
    return normalized


def get_gsim_dielectric_interface_preset_kwargs(
    name: str,
    *,
    records: Mapping[str, Mapping[str, Any]] | None = None,
    role: str = "boundary_surface",
    entry_names: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Return kwargs accepted by the gsim dielectric-interface spec model."""

    presets = validate_interface_preset_records(records)
    if name not in presets:
        msg = f"Unknown interface preset {name!r}."
        raise KeyError(msg)

    preset = presets[name]
    kwargs: dict[str, Any] = {
        "interface_type": preset["interface_type"],
        "thickness": preset["thickness"],
        "loss_tangent": preset["loss_tangent"],
        "role": role,
        "entry_names": tuple(entry_names),
        "preset_name": name,
        "preset_source": preset["source"],
    }
    if "material_name" in preset:
        kwargs["material_name"] = preset["material_name"]
    else:
        kwargs["permittivity"] = preset["permittivity"]
    return kwargs


def get_gsim_material_overlay() -> dict[str, Any]:
    """Return public material records in the gsim material-overlay schema.

    The PDK remains the owner of material names and public process records.
    Solver-specific frequency evaluation remains in gsim. Infinite relative
    permittivity values mark conductor-like public records and are preserved as
    metadata instead of being exported as Palace permittivity values. Public
    generated-name aliases are exported as overlay metadata for gsim to expand
    during reusable material-overlay loading.
    """
    materials: dict[str, dict[str, Any]] = {}
    for name, record in get_material_records().items():
        materials[name] = _to_gsim_material_entry(record)
    return {"materials": materials, "material_aliases": get_material_alias_records()}


def write_gsim_material_overlay(path: str | Path) -> Path:
    """Write the public gsim material overlay as strict JSON."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(get_gsim_material_overlay(), indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    return output_path


def _to_gsim_material_entry(record: dict[str, Any]) -> dict[str, Any]:
    entry: dict[str, Any] = {}
    relative_permittivity = record.get("relative_permittivity")
    if _is_finite_number(relative_permittivity):
        permittivity = float(relative_permittivity)
        entry["relative_permittivity"] = permittivity
        entry["dispersion_models"] = [
            {
                "type": "constant",
                "permittivity": permittivity,
                "source": _OVERLAY_SOURCE,
            }
        ]
    elif relative_permittivity is not None:
        entry["material_role"] = "conductor"
        entry["relative_permittivity_note"] = str(relative_permittivity)

    for key in ("loss_tangent", "conductivity", "permeability", "material_axes"):
        value = record.get(key)
        if value is not None:
            entry[key] = value
    return entry


def _material_name(name: Any) -> str:
    if not isinstance(name, str) or not name:
        msg = "Material names must be non-empty strings."
        raise ValueError(msg)
    return name


def _material_alias_name(name: Any) -> str:
    if not isinstance(name, str) or not name:
        msg = "Material aliases must be non-empty strings."
        raise ValueError(msg)
    return name


def _interface_preset_source(value: Any, preset_name: str) -> str:
    if isinstance(value, bool) or not isinstance(value, str) or not value:
        msg = f"Interface preset {preset_name!r} must set a non-empty source string."
        raise ValueError(msg)
    return value


def _normalize_material_kind(material_name: str, record: Mapping[str, Any]) -> str:
    if not isinstance(record, Mapping):
        msg = f"Material record {material_name!r} must be a mapping."
        raise TypeError(msg)

    kind = record.get("material_kind")
    if isinstance(kind, bool) or not isinstance(kind, str) or not kind:
        msg = f"Material record {material_name!r} must set a non-empty material_kind string."
        raise ValueError(msg)

    normalized = kind.lower()
    if normalized not in _MATERIAL_KINDS:
        msg = (
            f"Material record {material_name!r} has unsupported material_kind "
            f"{kind!r}; expected one of {sorted(_MATERIAL_KINDS)}."
        )
        raise ValueError(msg)
    return normalized


def _normalize_interface_preset_record(
    name: str,
    record: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        msg = f"Interface preset {name!r} must be a mapping."
        raise TypeError(msg)

    interface_type = str(record.get("interface_type", "")).upper()
    if interface_type not in _INTERFACE_TYPES:
        msg = (
            f"Interface preset {name!r} must set interface_type to one of "
            f"{sorted(_INTERFACE_TYPES)}."
        )
        raise ValueError(msg)

    material_name = record.get("material_name")
    permittivity = record.get("permittivity")
    has_material_name = isinstance(material_name, str) and bool(material_name)
    has_permittivity = permittivity is not None
    if has_material_name == has_permittivity:
        msg = f"Interface preset {name!r} must set exactly one of material_name or permittivity."
        raise ValueError(msg)

    normalized: dict[str, Any] = {
        "interface_type": interface_type,
        "thickness": _positive_float(record.get("thickness"), name, "thickness"),
        "loss_tangent": _nonnegative_float(
            record.get("loss_tangent", 0.0),
            name,
            "loss_tangent",
        ),
        "source": _interface_preset_source(record.get("source"), name),
    }
    if has_material_name:
        normalized["material_name"] = str(material_name)
    else:
        normalized["permittivity"] = _positive_float(permittivity, name, "permittivity")

    description = record.get("description")
    if description is not None:
        normalized["description"] = str(description)
    return normalized


def _positive_float(value: Any, preset_name: str, field_name: str) -> float:
    if not _is_finite_number(value) or float(value) <= 0.0:
        msg = f"Interface preset {preset_name!r} field {field_name!r} must be > 0."
        raise ValueError(msg)
    return float(value)


def _nonnegative_float(value: Any, preset_name: str, field_name: str) -> float:
    if not _is_finite_number(value) or float(value) < 0.0:
        msg = f"Interface preset {preset_name!r} field {field_name!r} must be >= 0."
        raise ValueError(msg)
    return float(value)


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))
