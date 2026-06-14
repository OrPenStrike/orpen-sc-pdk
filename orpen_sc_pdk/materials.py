"""Public material records and solver-overlay export helpers."""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any

from orpen_sc_pdk.tech import material_properties

_OVERLAY_SOURCE = "orpen-sc-pdk tech.material_properties"


def get_material_records() -> dict[str, dict[str, Any]]:
    """Return a copy of public PDK material records."""
    return copy.deepcopy(material_properties)


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


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))
