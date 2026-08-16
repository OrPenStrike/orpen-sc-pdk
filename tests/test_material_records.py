from __future__ import annotations

from importlib import import_module

import pytest

from orpen_sc_pdk.materials import (
    get_interface_preset_records,
    get_material_alias_records,
    get_material_records,
    validate_interface_preset_records,
    validate_material_alias_records,
    validate_material_kind_records,
)
from orpen_sc_pdk.tech import (
    interface_preset_records,
    material_alias_records,
    material_properties,
)


def test_public_material_records_are_copies() -> None:
    records = get_material_records()
    aliases = get_material_alias_records()

    assert records["Si"]["relative_permittivity"] == pytest.approx(11.45)
    assert records["Si"]["material_kind"] == "dielectric"
    assert aliases == {"air": "vacuum", "silicon": "Si"}

    records["Si"]["relative_permittivity"] = 1.0
    aliases["air"] = "Si"
    assert material_properties["Si"]["relative_permittivity"] == pytest.approx(11.45)
    assert material_alias_records["air"] == "vacuum"


def test_public_import_surface_exposes_only_solver_neutral_material_records() -> None:
    package = import_module("orpen_sc_pdk")

    assert package.get_material_records()["vacuum"]["relative_permittivity"] == 1.0
    assert package.get_material_alias_records()["air"] == "vacuum"
    assert "Woods2019_Si_SA" in package.get_interface_preset_records()
    assert not any(name.startswith("get_gsim_") for name in package.__all__)
    assert "write_gsim_material_overlay" not in package.__all__


@pytest.mark.parametrize(
    ("records", "match"),
    [
        ({"Si": {}}, "material_kind"),
        ({"Si": {"material_kind": "metal"}}, "unsupported"),
        ({"": {"material_kind": "dielectric"}}, "Material names"),
    ],
)
def test_material_kind_records_fail_closed(records, match) -> None:
    with pytest.raises(ValueError, match=match):
        validate_material_kind_records(records)


@pytest.mark.parametrize(
    ("records", "match"),
    [
        ({"air": "missing"}, "Unknown material alias target"),
        ({"": "Si"}, "Material aliases"),
        ({"air": ""}, "Material aliases"),
    ],
)
def test_material_alias_records_fail_closed(records, match) -> None:
    with pytest.raises(ValueError, match=match):
        validate_material_alias_records(records)


def test_interface_preset_records_are_public_copy() -> None:
    records = get_interface_preset_records()

    assert records["Woods2019_Si_SA"]["material_name"] == "Woods2019_Si_SA_effective"
    records["private_sa_example"] = {}
    assert interface_preset_records == {}


def test_interface_preset_records_validate_solver_neutral_schema() -> None:
    normalized = validate_interface_preset_records(
        {
            "public_sa_example": {
                "interface_type": "sa",
                "thickness": 0.003,
                "material_name": "AlOx_native_generic",
                "source": "public example only",
            }
        }
    )

    assert normalized["public_sa_example"] == {
        "interface_type": "SA",
        "thickness": 0.003,
        "loss_tangent": 0.0,
        "material_name": "AlOx_native_generic",
        "source": "public example only",
    }
