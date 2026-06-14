from __future__ import annotations

import pytest


def assert_public_si_overlay_material(config: dict, manifest: dict) -> None:
    """Assert public Si material data reaches Palace dielectric material blocks."""
    substrate_attrs = {
        attr
        for entry in manifest["entries"]
        if entry.get("role") == "dielectric_volume" and _is_si_substrate_entry(entry)
        for attr in entry.get("attributes", [])
    }

    assert substrate_attrs

    material_rows = [
        row
        for row in config["Domains"]["Materials"]
        if substrate_attrs.intersection(row["Attributes"])
    ]
    assert material_rows
    assert all(row["Permittivity"] == pytest.approx(11.45) for row in material_rows)


def _is_si_substrate_entry(entry: dict) -> bool:
    names = {entry.get("name", ""), *entry.get("physical_names", [])}
    normalized = {str(name).strip().lower() for name in names}
    return bool({"si", "silicon"} & normalized) or any("substrate" in name for name in normalized)
