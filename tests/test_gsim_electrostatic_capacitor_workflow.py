from __future__ import annotations

import json
from pathlib import Path

import pytest

import orpen_sc_pdk
from orpen_sc_pdk.cells import martinis2022_differential_ribbon_capacitor


def test_public_same_layer_capacitor_electrostatic_gsim_terminal_artifacts(
    tmp_path: Path,
) -> None:
    """Public same-layer capacitor fixture exercises terminal index artifacts."""

    pytest.importorskip("gmsh")
    pytest.importorskip("gsim")

    from gsim.palace import ElectrostaticSim
    from gsim.palace.mesh import build_postprocessing_config_from_manifest

    orpen_sc_pdk.activate()
    component = martinis2022_differential_ribbon_capacitor(
        a_um=20,
        b_um=35,
        ell_r_um=160,
    )
    positive_port = component.ports["o_mesh_positive_electrode"]
    negative_port = component.ports["o_mesh_negative_electrode"]
    positive_center = tuple(float(value) for value in positive_port.center)
    negative_center = tuple(float(value) for value in negative_port.center)

    assert positive_port.layer == negative_port.layer

    output_dir = tmp_path / "palace-sim"
    sim = ElectrostaticSim()
    sim.set_output_dir(output_dir)
    sim.set_geometry(component)
    sim.set_stack(
        include_substrate=True,
        substrate_thickness=20,
        add_oxide_dielectric=False,
        add_passivation_dielectric=False,
    )
    sim.set_airbox(margin_x=40, margin_y=40, z_above=50, z_below=10)
    sim.add_terminal("positive", layer="D0_TOP_M1", center=positive_center)
    sim.add_terminal("negative", layer="D0_TOP_M1", center=negative_center)
    sim.set_electrostatic(save_fields=0)

    sim.mesh(
        preset="coarse",
        refined_mesh_size=20,
        max_mesh_size=200,
        margin_x=40,
        margin_y=40,
        planar_conductors=True,
        auto_size=False,
    )
    mesh_result = sim._last_mesh_result

    postprocessing = build_postprocessing_config_from_manifest(mesh_result.manifest)
    config_path = sim.write_config(postprocessing=postprocessing)

    config = json.loads(Path(config_path).read_text())
    manifest = json.loads((output_dir / "mesh_manifest.json").read_text())
    index_map = json.loads((output_dir / "palace_index_map.json").read_text())

    assert (output_dir / "palace.msh").stat().st_size > 0
    assert config["Problem"]["Type"] == "Electrostatic"
    assert "Electrostatic" in config["Solver"]

    terminals = config["Boundaries"]["Terminal"]
    assert [terminal["Index"] for terminal in terminals] == [1, 2]
    assert all(terminal["Attributes"] for terminal in terminals)
    assert set(terminals[0]["Attributes"]).isdisjoint(terminals[1]["Attributes"])

    pec_entries = [entry for entry in manifest["entries"] if entry["role"] == "pec_surface"]
    assert len(pec_entries) == 2
    assert {entry["metadata"]["layer"] for entry in pec_entries} == {"D0_TOP_M1"}

    energy_rows = config["Domains"]["Postprocessing"]["Energy"]
    assert energy_rows

    terminal_rows = [row for row in index_map["entries"] if row["section"] == "Boundaries.Terminal"]
    assert {row["index"] for row in terminal_rows} == {1, 2}
    assert {row["terminal_name"] for row in terminal_rows} == {
        "positive",
        "negative",
    }
    assert {row["metadata"]["layer"] for row in terminal_rows} == {"D0_TOP_M1"}
