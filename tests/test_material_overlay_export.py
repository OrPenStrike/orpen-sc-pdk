from __future__ import annotations

import json
import math

import pytest

import orpen_sc_pdk
from orpen_sc_pdk import tech
from orpen_sc_pdk.materials import (
    get_gsim_dielectric_interface_preset_kwargs,
    get_gsim_material_kind_alias_map,
    get_gsim_material_kind_map,
    get_gsim_material_overlay,
    get_interface_preset_records,
    get_material_alias_records,
    get_material_records,
    validate_interface_preset_records,
    validate_material_alias_records,
    validate_material_kind_records,
    write_gsim_material_overlay,
)


def test_material_records_are_public_copy() -> None:
    records = get_material_records()

    assert records["Si"]["relative_permittivity"] == pytest.approx(11.45)
    assert records["Si"]["permeability"] == pytest.approx(1.0)
    assert records["Si"]["material_kind"] == "dielectric"

    records["Si"]["relative_permittivity"] = 1.0
    records["Si"]["permeability"] = 2.0
    assert tech.material_properties["Si"]["relative_permittivity"] == pytest.approx(11.45)
    assert tech.material_properties["Si"]["permeability"] == pytest.approx(1.0)


def test_material_alias_records_are_public_copy() -> None:
    aliases = get_material_alias_records()

    assert aliases == {
        "air": "vacuum",
        "silicon": "Si",
    }

    aliases["air"] = "Si"
    assert tech.material_alias_records["air"] == "vacuum"


def test_public_import_surface_exposes_material_overlay_helpers() -> None:
    assert orpen_sc_pdk.get_material_records()["vacuum"]["relative_permittivity"] == 1.0
    assert orpen_sc_pdk.get_material_records()["vacuum"]["permeability"] == 1.0
    assert orpen_sc_pdk.get_gsim_material_kind_map()["vacuum"] == "vacuum"
    assert orpen_sc_pdk.get_material_alias_records()["air"] == "vacuum"
    assert orpen_sc_pdk.get_gsim_material_kind_alias_map()["silicon"] == "Si"
    assert "materials" in orpen_sc_pdk.get_gsim_material_overlay()
    assert orpen_sc_pdk.get_interface_preset_records() == {}


def test_gsim_material_kind_map_is_public_explicit_copy() -> None:
    kind_map = get_gsim_material_kind_map()

    assert kind_map == {
        "vacuum": "vacuum",
        "Si": "dielectric",
        "Al": "superconductor",
        "Nb": "superconductor",
        "TiN": "superconductor",
        "In": "superconductor",
        "AlOx_native_generic": "dielectric",
    }

    kind_map["Si"] = "vacuum"
    assert get_gsim_material_kind_map()["Si"] == "dielectric"


def test_gsim_material_kind_alias_map_targets_public_materials() -> None:
    alias_map = get_gsim_material_kind_alias_map()
    kind_map = get_gsim_material_kind_map()

    assert alias_map == {
        "air": "vacuum",
        "silicon": "Si",
    }
    assert all(target in kind_map for target in alias_map.values())
    assert set(alias_map).isdisjoint(tech.material_properties)

    alias_map["air"] = "Si"
    assert get_gsim_material_kind_alias_map()["air"] == "vacuum"


def test_gsim_material_kind_map_covers_public_layer_stack_materials() -> None:
    kind_map = get_gsim_material_kind_map()
    layer_stack_materials = {
        layer.material for layer in tech.LAYER_STACK.layers.values() if layer.material
    }

    assert layer_stack_materials <= set(kind_map)
    assert tech.interface_preset_records == {}


@pytest.mark.parametrize(
    ("records", "match"),
    [
        ({"Si": {}}, "material_kind"),
        ({"Si": {"material_kind": ""}}, "material_kind"),
        ({"Si": {"material_kind": None}}, "material_kind"),
        ({"Si": {"material_kind": True}}, "material_kind"),
        ({"Si": {"material_kind": "metal"}}, "unsupported"),
        ({"": {"material_kind": "dielectric"}}, "Material names"),
        ({None: {"material_kind": "dielectric"}}, "Material names"),
    ],
)
def test_gsim_material_kind_map_validates_records(records, match) -> None:
    with pytest.raises(ValueError, match=match):
        validate_material_kind_records(records)


@pytest.mark.parametrize(
    ("records", "match"),
    [
        ({"air": "missing"}, "Unknown material alias target"),
        ({"": "Si"}, "Material aliases"),
        ({None: "Si"}, "Material aliases"),
        ({"air": ""}, "Material aliases"),
        ({"air": None}, "Material aliases"),
    ],
)
def test_gsim_material_kind_alias_map_validates_records(records, match) -> None:
    with pytest.raises(ValueError, match=match):
        validate_material_alias_records(records)


def test_gsim_material_overlay_maps_finite_dielectrics() -> None:
    overlay = get_gsim_material_overlay()
    materials = overlay["materials"]

    assert materials["vacuum"]["relative_permittivity"] == pytest.approx(1.0)
    assert materials["vacuum"]["permeability"] == pytest.approx(1.0)
    assert "material_kind" not in materials["vacuum"]
    assert materials["Si"]["relative_permittivity"] == pytest.approx(11.45)
    assert materials["Si"]["permeability"] == pytest.approx(1.0)
    assert "material_kind" not in materials["Si"]
    assert materials["Si"]["dispersion_models"] == [
        {
            "type": "constant",
            "permittivity": 11.45,
            "source": "orpen-sc-pdk tech.material_properties",
        }
    ]
    assert materials["AlOx_native_generic"]["relative_permittivity"] == pytest.approx(10.0)
    assert materials["AlOx_native_generic"]["permeability"] == pytest.approx(1.0)


def test_gsim_material_overlay_preserves_conductor_role_without_infinite_permittivity() -> None:
    materials = get_gsim_material_overlay()["materials"]

    assert materials["Al"]["material_role"] == "conductor"
    assert materials["Al"]["relative_permittivity_note"] == "inf"
    assert "relative_permittivity" not in materials["Al"]
    assert "material_kind" not in materials["Al"]
    assert "permittivity" not in materials["Al"]
    assert "dispersion_models" not in materials["Al"]


def test_write_gsim_material_overlay_is_strict_json(tmp_path) -> None:
    overlay_path = write_gsim_material_overlay(tmp_path / "orpen-materials.json")

    data = json.loads(overlay_path.read_text())

    assert data["materials"]["Si"]["relative_permittivity"] == pytest.approx(11.45)
    assert data["materials"]["Si"]["permeability"] == pytest.approx(1.0)
    assert "Infinity" not in overlay_path.read_text()


def test_written_gsim_material_overlay_loads_through_gsim(tmp_path) -> None:
    pytest.importorskip("gsim")
    from gsim.common.stack import load_overlay, load_overlay_data

    in_memory_overlay = load_overlay_data(get_gsim_material_overlay())
    overlay_path = write_gsim_material_overlay(tmp_path / "orpen-materials.json")
    file_overlay = load_overlay(overlay_path)

    assert in_memory_overlay["Si"].permittivity == pytest.approx(11.45)
    assert in_memory_overlay["Si"].permeability == pytest.approx(1.0)
    assert file_overlay["Si"].permittivity == pytest.approx(11.45)
    assert file_overlay["Si"].permeability == pytest.approx(1.0)
    assert file_overlay["AlOx_native_generic"].permittivity == pytest.approx(10.0)
    assert file_overlay["AlOx_native_generic"].permeability == pytest.approx(1.0)


def test_interface_preset_records_are_public_copy_and_empty_by_default() -> None:
    records = get_interface_preset_records()

    assert records == {}

    records["private_sa_example"] = {
        "interface_type": "SA",
        "thickness": 0.003,
        "material_name": "AlOx_native_generic",
    }
    assert tech.interface_preset_records == {}


def test_interface_preset_schema_validates_caller_supplied_record() -> None:
    records = {
        "public_sa_example": {
            "interface_type": "sa",
            "thickness": 0.003,
            "material_name": "AlOx_native_generic",
            "source": "public example only",
            "description": "Example interface record without becoming a PDK default.",
        }
    }

    normalized = validate_interface_preset_records(records)
    record = normalized["public_sa_example"]

    assert record["interface_type"] == "SA"
    assert record["thickness"] == pytest.approx(0.003)
    assert record["loss_tangent"] == pytest.approx(0.0)
    assert record["material_name"] == "AlOx_native_generic"
    assert record["source"] == "public example only"

    kwargs = get_gsim_dielectric_interface_preset_kwargs(
        "public_sa_example",
        records=records,
        entry_names=("sa_interface",),
    )
    assert kwargs == {
        "interface_type": "SA",
        "thickness": 0.003,
        "loss_tangent": 0.0,
        "material_name": "AlOx_native_generic",
        "role": "boundary_surface",
        "entry_names": ("sa_interface",),
        "preset_name": "public_sa_example",
        "preset_source": "public example only",
    }


@pytest.mark.parametrize("source", ["", None, True])
def test_interface_preset_schema_requires_explicit_source(source) -> None:
    records = {
        "public_sa_example": {
            "interface_type": "SA",
            "thickness": 0.003,
            "material_name": "AlOx_native_generic",
            "source": source,
        }
    }

    with pytest.raises(ValueError, match="source"):
        validate_interface_preset_records(records)


def test_interface_preset_schema_rejects_missing_source() -> None:
    records = {
        "public_sa_example": {
            "interface_type": "SA",
            "thickness": 0.003,
            "material_name": "AlOx_native_generic",
        }
    }

    with pytest.raises(ValueError, match="source"):
        validate_interface_preset_records(records)


def test_interface_preset_schema_rejects_ambiguous_records() -> None:
    records = {
        "bad": {
            "interface_type": "SA",
            "thickness": 0.003,
            "material_name": "AlOx_native_generic",
            "permittivity": 10.0,
        }
    }

    with pytest.raises(ValueError, match="exactly one"):
        validate_interface_preset_records(records)


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
    assert by_attr[(1,)]["Permeability"] == pytest.approx(1.0)
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
    assert si_resolution["resolved_permeability"] == pytest.approx(1.0)

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
    assert si_row["permeability"] == pytest.approx(1.0)
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


def test_gsim_resolves_public_interface_material_overlay(tmp_path) -> None:
    pytest.importorskip("gsim")
    from gsim.common.stack import LayerStack
    from gsim.palace import load_dielectric_interface_summary
    from gsim.palace.mesh.config_generator import generate_palace_config

    groups = {
        "volumes": {"Si": {"phys_group": 1}},
        "conductor_surfaces": {},
        "pec_surfaces": {},
        "port_surfaces": {},
        "boundary_surfaces": {"sa_interface": {"phys_group": 70}},
    }
    stack = LayerStack(materials={"Si": {"permittivity": 11.45}})
    config_path = generate_palace_config(
        groups=groups,
        ports=[],
        port_info=[],
        stack=stack,
        output_path=tmp_path,
        model_name="palace",
        fmax=5e9,
        absorbing_boundary=False,
        boundary_postprocessing_config={
            "Dielectric": [
                {
                    "Index": 7,
                    "Attributes": [70],
                    "Type": "SA",
                    "Thickness": 0.003,
                    "_MaterialName": "AlOx_native_generic",
                }
            ]
        },
        material_overlay=get_gsim_material_overlay(),
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
                        "physical_names": ["SA:substrate___vacuum"],
                        "dimension": 2,
                        "Type": "SA",
                    }
                ],
            }
        )
    )

    interface = json.loads(config_path.read_text())["Boundaries"]["Postprocessing"]["Dielectric"][0]
    assert "_MaterialName" not in interface
    assert interface["Permittivity"] == pytest.approx(10.0)
    assert interface["LossTan"] == pytest.approx(0.0)

    summary = load_dielectric_interface_summary(
        {"config.json": config_path, "palace_index_map.json": index_map_path}
    )
    row = summary.set_index("surface_index").loc[7]
    assert row["source_name"] == "SA:substrate___vacuum"
    assert row["interface_material_name"] == "AlOx_native_generic"
    assert row["matched_material_name"] == "AlOx_native_generic"
    assert row["material_model_source"] == "orpen-sc-pdk tech.material_properties"
    assert row["permittivity"] == pytest.approx(10.0)
    assert row["loss_tangent"] == pytest.approx(0.0)


def test_gsim_accepts_public_interface_preset_kwargs(tmp_path) -> None:
    pytest.importorskip("gsim")
    from gsim.common.stack import LayerStack
    from gsim.palace import load_dielectric_interface_summary
    from gsim.palace.mesh import (
        DielectricInterfaceSpec,
        MeshManifest,
        MeshPhysicalGroup,
        build_postprocessing_config_from_manifest,
    )
    from gsim.palace.mesh.config_generator import generate_palace_config

    records = {
        "public_sa_example": {
            "interface_type": "SA",
            "thickness": 0.003,
            "material_name": "AlOx_native_generic",
            "source": "public example only",
        }
    }
    manifest = MeshManifest(
        entries=(
            MeshPhysicalGroup(
                name="sa_interface",
                role="boundary_surface",
                attributes=(70,),
                entity_tags=(70,),
                physical_names=("sa_interface",),
                dimension=2,
                metadata={},
            ),
        )
    )
    preset_kwargs = get_gsim_dielectric_interface_preset_kwargs(
        "public_sa_example",
        records=records,
        entry_names=("sa_interface",),
    )
    postprocessing = build_postprocessing_config_from_manifest(
        manifest,
        dielectric_interfaces=(DielectricInterfaceSpec(**preset_kwargs),),
    )

    config_path = generate_palace_config(
        groups={
            "volumes": {"Si": {"phys_group": 1}},
            "conductor_surfaces": {},
            "pec_surfaces": {},
            "port_surfaces": {},
            "boundary_surfaces": {"sa_interface": {"phys_group": 70}},
        },
        ports=[],
        port_info=[],
        stack=LayerStack(materials={"Si": {"permittivity": 11.45}}),
        output_path=tmp_path,
        model_name="palace",
        fmax=5e9,
        absorbing_boundary=False,
        boundary_postprocessing_config=postprocessing.boundaries,
        material_overlay=get_gsim_material_overlay(),
    )
    postprocessing.index_map.write_json(tmp_path / "palace_index_map.json")

    interface = json.loads(config_path.read_text())["Boundaries"]["Postprocessing"]["Dielectric"][0]
    assert "_MaterialName" not in interface
    assert interface["Type"] == "SA"
    assert interface["Permittivity"] == pytest.approx(10.0)
    assert interface["LossTan"] == pytest.approx(0.0)

    summary = load_dielectric_interface_summary(
        {
            "config.json": config_path,
            "palace_index_map.json": tmp_path / "palace_index_map.json",
        }
    )
    row = summary.set_index("surface_index").loc[1]
    assert row["source_name"] == "sa_interface"
    assert row["preset_name"] == "public_sa_example"
    assert row["preset_source"] == "public example only"
    assert row["interface_material_name"] == "AlOx_native_generic"
    assert row["material_model_source"] == "orpen-sc-pdk tech.material_properties"


def test_gsim_material_kind_classifier_accepts_public_interface_records(tmp_path) -> None:
    pytest.importorskip("gsim")
    from gsim.common.stack import LayerStack
    from gsim.palace import load_dielectric_interface_summary
    from gsim.palace.mesh import (
        build_dielectric_interface_specs_from_material_kinds,
        build_mesh_manifest,
        build_postprocessing_config_from_manifest,
    )
    from gsim.palace.mesh.config_generator import generate_palace_config

    records = {
        "public_ms_example": {
            "interface_type": "MS",
            "thickness": 0.002,
            "material_name": "AlOx_native_generic",
            "source": "public example only",
        }
    }
    groups = {
        "volumes": {"Si": {"phys_group": 1}},
        "conductor_surfaces": {},
        "pec_surfaces": {},
        "port_surfaces": {},
        "boundary_surfaces": {"Al___Si": {"phys_group": 70}},
    }
    manifest = build_mesh_manifest(groups)
    specs = build_dielectric_interface_specs_from_material_kinds(
        manifest,
        material_kind_by_name=get_gsim_material_kind_map(),
        presets=validate_interface_preset_records(records),
        preset_by_interface_type={"MS": "public_ms_example"},
    )
    postprocessing = build_postprocessing_config_from_manifest(
        manifest,
        dielectric_interfaces=specs,
    )

    assert postprocessing.boundaries["Dielectric"] == [
        {
            "Index": 1,
            "Attributes": [70],
            "Type": "MS",
            "Thickness": 0.002,
            "LossTan": 0.0,
            "_MaterialName": "AlOx_native_generic",
        }
    ]

    config_path = generate_palace_config(
        groups=groups,
        ports=[],
        port_info=[],
        stack=LayerStack(materials={"Si": {"permittivity": 11.45}}),
        output_path=tmp_path,
        model_name="palace",
        fmax=5e9,
        absorbing_boundary=False,
        boundary_postprocessing_config=postprocessing.boundaries,
        material_overlay=get_gsim_material_overlay(),
    )
    postprocessing.index_map.write_json(tmp_path / "palace_index_map.json")

    interface = json.loads(config_path.read_text())["Boundaries"]["Postprocessing"]["Dielectric"][0]
    assert "_MaterialName" not in interface
    assert interface["Type"] == "MS"
    assert interface["Permittivity"] == pytest.approx(10.0)
    assert interface["LossTan"] == pytest.approx(0.0)

    summary = load_dielectric_interface_summary(
        {
            "config.json": config_path,
            "palace_index_map.json": tmp_path / "palace_index_map.json",
        }
    )
    row = summary.set_index("surface_index").loc[1]
    assert row["source_name"] == "Al___Si"
    assert row["interface_type"] == "MS"
    assert row["preset_name"] == "public_ms_example"
    assert row["preset_source"] == "public example only"
    assert row["interface_material_name"] == "AlOx_native_generic"
    assert row["material_model_source"] == "orpen-sc-pdk tech.material_properties"


def test_gsim_material_kind_classifier_accepts_public_generated_aliases(tmp_path) -> None:
    pytest.importorskip("gsim")
    from gsim.common.stack import LayerStack
    from gsim.palace import load_dielectric_interface_summary
    from gsim.palace.mesh import (
        build_dielectric_interface_specs_from_material_kinds,
        build_mesh_manifest,
        build_postprocessing_config_from_manifest,
    )
    from gsim.palace.mesh.config_generator import generate_palace_config

    records = {
        "public_sa_example": {
            "interface_type": "SA",
            "thickness": 0.003,
            "material_name": "AlOx_native_generic",
            "source": "public example only",
        }
    }
    groups = {
        "volumes": {
            "silicon": {"phys_group": 1},
            "air": {"phys_group": 2},
        },
        "conductor_surfaces": {},
        "pec_surfaces": {},
        "port_surfaces": {},
        "boundary_surfaces": {"air___silicon": {"phys_group": 70}},
    }
    manifest = build_mesh_manifest(groups)
    specs = build_dielectric_interface_specs_from_material_kinds(
        manifest,
        material_kind_by_name=get_gsim_material_kind_map(),
        material_name_aliases=get_gsim_material_kind_alias_map(),
        presets=validate_interface_preset_records(records),
        preset_by_interface_type={"SA": "public_sa_example"},
    )
    postprocessing = build_postprocessing_config_from_manifest(
        manifest,
        dielectric_interfaces=specs,
    )

    assert postprocessing.boundaries["Dielectric"] == [
        {
            "Index": 1,
            "Attributes": [70],
            "Type": "SA",
            "Thickness": 0.003,
            "LossTan": 0.0,
            "_MaterialName": "AlOx_native_generic",
        }
    ]

    config_path = generate_palace_config(
        groups=groups,
        ports=[],
        port_info=[],
        stack=LayerStack(
            materials={
                "silicon": {"permittivity": 11.9},
                "air": {"permittivity": 1.0},
            }
        ),
        output_path=tmp_path,
        model_name="palace",
        fmax=5e9,
        absorbing_boundary=False,
        boundary_postprocessing_config=postprocessing.boundaries,
        material_overlay=get_gsim_material_overlay(),
    )
    postprocessing.index_map.write_json(tmp_path / "palace_index_map.json")

    interface = json.loads(config_path.read_text())["Boundaries"]["Postprocessing"]["Dielectric"][0]
    assert "_MaterialName" not in interface
    assert interface["Type"] == "SA"
    assert interface["Permittivity"] == pytest.approx(10.0)
    assert interface["LossTan"] == pytest.approx(0.0)

    summary = load_dielectric_interface_summary(
        {
            "config.json": config_path,
            "palace_index_map.json": tmp_path / "palace_index_map.json",
        }
    )
    row = summary.set_index("surface_index").loc[1]
    assert row["source_name"] == "air___silicon"
    assert row["interface_type"] == "SA"
    assert row["preset_name"] == "public_sa_example"
    assert row["preset_source"] == "public example only"
    assert row["interface_material_name"] == "AlOx_native_generic"
    assert row["material_model_source"] == "orpen-sc-pdk tech.material_properties"


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


def test_gsim_electrostatic_report_derives_public_loss_budget(tmp_path) -> None:
    pytest.importorskip("gsim")
    from gsim.palace import load_electrostatic_report

    terminal_c_path = tmp_path / "terminal-C.csv"
    terminal_c_path.write_text(
        "i, C[i][1] (F), C[i][2] (F)\n1.00e+00, 1.0e-15, -2.0e-15\n2.00e+00, -2.0e-15, 4.0e-15\n"
    )
    domain_e_path = tmp_path / "domain-E.csv"
    domain_e_path.write_text("i, E_elec[1] (J), p_elec[1]\n1, 1.0, 0.25\n2, 1.0, 0.125\n")
    surface_q_path = tmp_path / "surface-Q.csv"
    surface_q_path.write_text("i, p_surf[2], Q_surf[2]\n1, 0.125, 1.0e6\n2, 0.25, 2.0e6\n")
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
                        "section": "Boundaries.Terminal",
                        "index": 1,
                        "entry_name": "positive_electrode",
                        "role": "pec_surface",
                        "attributes": [11],
                        "physical_names": ["D0_TOP_M1@positive"],
                        "dimension": 2,
                        "terminal_name": "positive",
                    },
                    {
                        "section": "Boundaries.Terminal",
                        "index": 2,
                        "entry_name": "negative_electrode",
                        "role": "pec_surface",
                        "attributes": [12],
                        "physical_names": ["D0_TOP_M1@negative"],
                        "dimension": 2,
                        "terminal_name": "negative",
                    },
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
    material_resolution_path = tmp_path / "palace_material_resolution.json"
    material_resolution_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "materials": [
                    {
                        "material_row_index": 1,
                        "material_attribute": 10,
                        "material_attributes": [10],
                        "volume_name": "substrate",
                        "stack_material_name": "Si",
                        "matched_material_name": "Si",
                        "evaluation_frequency_hz": 5.0e9,
                        "evaluation_frequency_ghz": 5.0,
                        "model_type": "constant",
                        "model_source": "orpen-sc-pdk tech.material_properties",
                        "within_validity": True,
                        "validity_note": None,
                    }
                ],
            }
        )
    )

    source = {
        "terminal-C.csv": terminal_c_path,
        "domain-E.csv": domain_e_path,
        "surface-Q.csv": surface_q_path,
        "config.json": config_path,
        "palace_index_map.json": index_map_path,
        "palace_material_resolution.json": material_resolution_path,
    }
    report = load_electrostatic_report(source)

    assert report.capacitance.terminal_names == ("positive", "negative")
    assert report.mutual_capacitance is None
    assert report.inverse_capacitance is None
    material_row = report.domain_materials.set_index("material_attribute").loc[10]
    assert material_row["source_name"] == "D1_SUBSTRATE"
    assert material_row["material_model_source"] == "orpen-sc-pdk tech.material_properties"
    assert "t1_us" not in report.loss_budget.columns

    budget = report.loss_budget.set_index("source_index")
    assert budget.loc[1, "domain_inverse_q_sum"] == pytest.approx(5.0e-7)
    assert budget.loc[1, "surface_inverse_q_sum"] == pytest.approx(1.0e-6)
    assert budget.loc[1, "total_inverse_q_sum"] == pytest.approx(1.5e-6)
    assert budget.loc[2, "total_inverse_q_sum"] == pytest.approx(7.5e-7)

    report_with_t1 = load_electrostatic_report(source, frequency_ghz=5.0)
    budget_with_t1 = report_with_t1.loss_budget.set_index("source_index")
    assert budget_with_t1.loc[1, "gamma_hz"] == pytest.approx(5.0e9 * 1.5e-6)
    assert budget_with_t1.loc[1, "t1_us"] == pytest.approx(1.0e6 / (2.0 * math.pi * 5.0e9 * 1.5e-6))
