from __future__ import annotations

import json

import pytest

import orpen_sc_pdk
from orpen_sc_pdk import tech
from orpen_sc_pdk.materials import (
    get_gsim_material_overlay,
    get_material_records,
    write_gsim_material_overlay,
)


def test_material_records_are_public_copy() -> None:
    records = get_material_records()

    assert records["Si"]["relative_permittivity"] == pytest.approx(11.45)

    records["Si"]["relative_permittivity"] = 1.0
    assert tech.material_properties["Si"]["relative_permittivity"] == pytest.approx(11.45)


def test_public_import_surface_exposes_material_overlay_helpers() -> None:
    assert orpen_sc_pdk.get_material_records()["vacuum"]["relative_permittivity"] == 1.0
    assert "materials" in orpen_sc_pdk.get_gsim_material_overlay()


def test_gsim_material_overlay_maps_finite_dielectrics() -> None:
    overlay = get_gsim_material_overlay()
    materials = overlay["materials"]

    assert materials["vacuum"]["relative_permittivity"] == pytest.approx(1.0)
    assert materials["Si"]["relative_permittivity"] == pytest.approx(11.45)
    assert materials["Si"]["dispersion_models"] == [
        {
            "type": "constant",
            "permittivity": 11.45,
            "source": "orpen-sc-pdk tech.material_properties",
        }
    ]
    assert materials["AlOx_native_generic"]["relative_permittivity"] == pytest.approx(10.0)


def test_gsim_material_overlay_preserves_conductor_role_without_infinite_permittivity() -> None:
    materials = get_gsim_material_overlay()["materials"]

    assert materials["Al"]["material_role"] == "conductor"
    assert materials["Al"]["relative_permittivity_note"] == "inf"
    assert "relative_permittivity" not in materials["Al"]
    assert "permittivity" not in materials["Al"]
    assert "dispersion_models" not in materials["Al"]


def test_write_gsim_material_overlay_is_strict_json(tmp_path) -> None:
    overlay_path = write_gsim_material_overlay(tmp_path / "orpen-materials.json")

    data = json.loads(overlay_path.read_text())

    assert data["materials"]["Si"]["relative_permittivity"] == pytest.approx(11.45)
    assert "Infinity" not in overlay_path.read_text()


def test_written_gsim_material_overlay_loads_through_gsim(tmp_path) -> None:
    pytest.importorskip("gsim")
    from gsim.common.stack import load_overlay, load_overlay_data

    in_memory_overlay = load_overlay_data(get_gsim_material_overlay())
    overlay_path = write_gsim_material_overlay(tmp_path / "orpen-materials.json")
    file_overlay = load_overlay(overlay_path)

    assert in_memory_overlay["Si"].permittivity == pytest.approx(11.45)
    assert file_overlay["Si"].permittivity == pytest.approx(11.45)
    assert file_overlay["AlOx_native_generic"].permittivity == pytest.approx(10.0)


def test_gsim_palace_config_accepts_public_material_overlay(tmp_path) -> None:
    pytest.importorskip("gsim")
    from gsim.common.stack import LayerStack
    from gsim.palace.mesh.config_generator import generate_palace_config

    groups = {
        "volumes": {
            "silicon": {"phys_group": 1},
            "air": {"phys_group": 2},
        },
        "conductor_surfaces": {},
        "pec_surfaces": {},
        "port_surfaces": {},
        "boundary_surfaces": {},
    }

    config_path = generate_palace_config(
        groups=groups,
        ports=[],
        port_info=[],
        stack=LayerStack(
            materials={
                "silicon": {"permittivity": 11.9, "conductivity": 2.0},
                "air": {"permittivity": 1.0, "loss_tangent": 0.0},
            },
        ),
        output_path=tmp_path,
        model_name="palace",
        fmax=10e9,
        absorbing_boundary=False,
        material_overlay=get_gsim_material_overlay(),
    )

    materials = json.loads(config_path.read_text())["Domains"]["Materials"]
    by_attr = {tuple(row["Attributes"]): row for row in materials}

    assert by_attr[(1,)]["Permittivity"] == pytest.approx(11.45)
    assert by_attr[(1,)]["Conductivity"] == pytest.approx(2.0)
    assert by_attr[(2,)]["Permittivity"] == pytest.approx(1.0)
