"""Public material records and solver-overlay export helpers."""

from __future__ import annotations

import copy
import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from orpen_sc_pdk.tech import interface_preset_records, material_properties

_OVERLAY_SOURCE = "orpen-sc-pdk tech.material_properties"
_INTERFACE_PRESET_SOURCE = "orpen-sc-pdk tech.interface_preset_records"
_INTERFACE_TYPES = {"MA", "MS", "SA"}


def get_material_records() -> dict[str, dict[str, Any]]:
    """Return a copy of public PDK material records."""
    return copy.deepcopy(material_properties)


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
    """Return kwargs accepted by `gsim.palace.mesh.DielectricInterfaceSpec`."""

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
    }
    if "material_name" in preset:
        kwargs["material_name"] = preset["material_name"]
    else:
        kwargs["permittivity"] = preset["permittivity"]
    return kwargs


def get_gsim_material_overlay() -> dict[str, dict[str, dict[str, Any]]]:
    """Return public material records in the gsim material-overlay schema.

    The PDK remains the owner of material names and public process records.
    Solver-specific frequency evaluation remains in gsim. Infinite relative
    permittivity values mark conductor-like public records and are preserved as
    metadata instead of being exported as Palace permittivity values.
    """
    materials: dict[str, dict[str, Any]] = {}
    for name, record in get_material_records().items():
        materials[name] = _to_gsim_material_entry(record)
    return {"materials": materials}


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
        "source": str(record.get("source", _INTERFACE_PRESET_SOURCE)),
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
