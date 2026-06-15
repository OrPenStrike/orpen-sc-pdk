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
    from gsim.palace.results import load_domain_material_summary

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

    stack = LayerStack(
        materials={
            "silicon": {"permittivity": 11.9, "conductivity": 2.0},
            "air": {"permittivity": 1.0, "loss_tangent": 0.0},
        },
    )
    config_path = generate_palace_config(
        groups=groups,
        ports=[],
        port_info=[],
        stack=stack,
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
    assert stack.materials["silicon"]["permittivity"] == pytest.approx(11.9)
    material_resolution_path = tmp_path / "palace_material_resolution.json"
    assert material_resolution_path.exists()

    material_resolution = json.loads(material_resolution_path.read_text())
    si_resolution = next(
        row for row in material_resolution["materials"] if row["material_attribute"] == 1
    )
    assert si_resolution["stack_material_name"] == "silicon"
    assert si_resolution["matched_material_name"] == "silicon"
    assert si_resolution["model_type"] == "constant"
    assert si_resolution["model_source"] == "orpen-sc-pdk tech.material_properties"

    index_map_path = tmp_path / "palace_index_map.json"
    index_map_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "entries": [
                    {
                        "section": "Domains.Postprocessing.Energy",
                        "index": 1,
                        "entry_name": "silicon",
                        "role": "dielectric_volume",
                        "attributes": [1],
                        "physical_names": ["D1_SUBSTRATE"],
                        "dimension": 3,
                        "metadata": {"material": "Si"},
                    }
                ],
            }
        )
    )
    material_summary = load_domain_material_summary(
        {
            "config.json": config_path,
            "palace_index_map.json": index_map_path,
        }
    )
    si_row = material_summary.set_index("material_attribute").loc[1]
    assert si_row["source_name"] == "D1_SUBSTRATE"
    assert si_row["physical_name"] == "D1_SUBSTRATE"
    assert si_row["permittivity"] == pytest.approx(11.45)
    assert si_row["stack_material_name"] == "silicon"
    assert si_row["material_model_type"] == "constant"
    assert si_row["material_model_source"] == "orpen-sc-pdk tech.material_properties"


def test_gsim_dielectric_interface_summary_loads_public_interface_config(
    tmp_path,
) -> None:
    pytest.importorskip("gsim")
    from gsim.palace import load_dielectric_interface_summary

    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "Boundaries": {
                    "Postprocessing": {
                        "Dielectric": [
                            {
                                "Index": 7,
                                "Attributes": [70],
                                "Type": "SA",
                                "Thickness": 0.003,
                                "Permittivity": 4.0,
                                "LossTan": 0.0017,
                            }
                        ]
                    }
                }
            }
        )
    )
    index_map_path = tmp_path / "palace_index_map.json"
    index_map_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "entries": [
                    {
                        "section": "Boundaries.Postprocessing.Dielectric",
                        "index": 7,
                        "entry_name": "sa_interface",
                        "role": "boundary_surface",
                        "attributes": [70],
                        "physical_names": ["SA:D1_SUBSTRATE___OUTER_VACUUM"],
                        "dimension": 2,
                        "Type": "SA",
                    }
                ],
            }
        )
    )

    summary = load_dielectric_interface_summary(
        {"config.json": config_path, "palace_index_map.json": index_map_path}
    )

    row = summary.set_index("surface_index").loc[7]
    assert row["source_name"] == "SA:D1_SUBSTRATE___OUTER_VACUUM"
    assert row["interface_type"] == "SA"
    assert row["thickness"] == pytest.approx(0.003)
    assert row["permittivity"] == pytest.approx(4.0)
    assert row["loss_tangent"] == pytest.approx(0.0017)


def test_gsim_eigenmode_report_derives_public_loss_budget(tmp_path) -> None:
    pytest.importorskip("gsim")
    from gsim.palace import load_eigenmode_report

    eig_path = tmp_path / "eig.csv"
    eig_path.write_text(
        "m, Re{f} (GHz), Im{f} (GHz), Q, Error (Bkwd.), Error (Abs.)\n"
        "1, 5.0, 0.0, 2.0e6, 0.0, 0.0\n"
    )
    domain_e_path = tmp_path / "domain-E.csv"
    domain_e_path.write_text("m, E_elec[1] (J), p_elec[1]\n1, 1.0, 0.25\n")
    surface_q_path = tmp_path / "surface-Q.csv"
    surface_q_path.write_text("m, p_surf[2], Q_surf[2]\n1, 0.125, 1.0e6\n")
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "Domains": {
                    "Materials": [
                        {
                            "Attributes": [10],
                            "Name": "Si",
                            "Permittivity": 11.45,
                            "LossTan": 2.0e-6,
                        }
                    ]
                },
                "Boundaries": {
                    "Postprocessing": {
                        "Dielectric": [
                            {
                                "Index": 2,
                                "Attributes": [20],
                                "Type": "SA",
                                "Thickness": 0.003,
                                "Permittivity": 4.0,
                                "LossTan": 0.0017,
                            }
                        ]
                    }
                },
            }
        )
    )
    index_map_path = tmp_path / "palace_index_map.json"
    index_map_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "entries": [
                    {
                        "section": "Domains.Postprocessing.Energy",
                        "index": 1,
                        "entry_name": "substrate",
                        "role": "dielectric_volume",
                        "attributes": [10],
                        "physical_names": ["D1_SUBSTRATE"],
                        "dimension": 3,
                    },
                    {
                        "section": "Boundaries.Postprocessing.Dielectric",
                        "index": 2,
                        "entry_name": "sa_interface",
                        "role": "boundary_surface",
                        "attributes": [20],
                        "physical_names": ["SA:D1_SUBSTRATE___OUTER_VACUUM"],
                        "dimension": 2,
                        "Type": "SA",
                    },
                ],
            }
        )
    )

    report = load_eigenmode_report(
        {
            "eig.csv": eig_path,
            "domain-E.csv": domain_e_path,
            "surface-Q.csv": surface_q_path,
            "config.json": config_path,
            "palace_index_map.json": index_map_path,
        }
    )

    domain_row = report.domain_loss.set_index("domain_index").loc[1]
    assert domain_row["source_name"] == "D1_SUBSTRATE"
    assert domain_row["material_name"] == "Si"
    assert domain_row["p_elec"] == pytest.approx(0.25)
    assert domain_row["loss_tangent"] == pytest.approx(2.0e-6)
    assert domain_row["inverse_q"] == pytest.approx(5.0e-7)

    surface_row = report.surface_loss.set_index("surface_index").loc[2]
    assert surface_row["source_name"] == "SA:D1_SUBSTRATE___OUTER_VACUUM"
    assert surface_row["interface_type"] == "SA"
    assert surface_row["thickness"] == pytest.approx(0.003)
    assert surface_row["loss_tangent"] == pytest.approx(0.0017)
    assert surface_row["inverse_q"] == pytest.approx(1.0e-6)

    budget_row = report.loss_budget.set_index("mode_index").loc[1]
    assert budget_row["frequency_ghz"] == pytest.approx(5.0)
    assert budget_row["inverse_q_eig"] == pytest.approx(5.0e-7)
    assert budget_row["domain_inverse_q_sum"] == pytest.approx(5.0e-7)
    assert budget_row["surface_inverse_q_sum"] == pytest.approx(1.0e-6)
    assert budget_row["total_inverse_q_sum"] == pytest.approx(1.5e-6)
    assert budget_row["q_total"] == pytest.approx(1.0 / 1.5e-6)
    assert budget_row["domain_vs_eig_relative_error"] == pytest.approx(0.0)
