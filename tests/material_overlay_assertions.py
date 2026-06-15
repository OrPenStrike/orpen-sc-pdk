from __future__ import annotations

from pathlib import Path

import pytest


def assert_public_si_overlay_material(config: dict, manifest: dict) -> None:
    """Assert public Si material data reaches Palace dielectric material blocks."""
    substrate_attrs = _public_si_substrate_attributes(manifest)

    assert substrate_attrs

    material_rows = [
        row
        for row in config["Domains"]["Materials"]
        if substrate_attrs.intersection(row["Attributes"])
    ]
    assert material_rows
    assert all(row["Permittivity"] == pytest.approx(11.45) for row in material_rows)


def assert_public_si_effective_material(
    config_path: str | Path,
    index_map_path: str | Path,
    manifest: dict,
) -> None:
    """Assert gsim can load effective public Si material rows from artifacts."""
    pytest.importorskip("gsim")
    import pandas as pd
    from gsim.palace import load_domain_material_summary

    substrate_attrs = _public_si_substrate_attributes(manifest)
    assert substrate_attrs

    summary = load_domain_material_summary(
        {
            "config.json": Path(config_path),
            "palace_index_map.json": Path(index_map_path),
        }
    )
    rows = [
        row for row in summary.to_dict("records") if row["material_attribute"] in substrate_attrs
    ]

    assert rows
    assert all(row["permittivity"] == pytest.approx(11.45) for row in rows)
    assert all(row["material_model_type"] == "constant" for row in rows)
    assert all(
        row["material_model_source"] == "orpen-sc-pdk tech.material_properties" for row in rows
    )
    assert all(pd.notna(row["domain_index"]) for row in rows)
    assert all(set(row["attributes"]).intersection(substrate_attrs) for row in rows)
    assert any(
        _is_si_substrate_entry(
            {
                "name": row.get("entry_name", ""),
                "physical_names": [
                    row.get("physical_name", ""),
                    row.get("source_name", ""),
                ],
            }
        )
        for row in rows
    )


def _public_si_substrate_attributes(manifest: dict) -> set[int]:
    return {
        attr
        for entry in manifest["entries"]
        if entry.get("role") == "dielectric_volume" and _is_si_substrate_entry(entry)
        for attr in entry.get("attributes", [])
    }


def _is_si_substrate_entry(entry: dict) -> bool:
    names = {entry.get("name", ""), *entry.get("physical_names", [])}
    normalized = {str(name).strip().lower() for name in names}
    return bool({"si", "silicon"} & normalized) or any("substrate" in name for name in normalized)
