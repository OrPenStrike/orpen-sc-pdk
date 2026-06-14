from __future__ import annotations

import json
from pathlib import Path

import pytest

import orpen_sc_pdk
from orpen_sc_pdk.cells import cpw_straight


def test_public_cpw_driven_gsim_port_postprocessing_artifacts(
    tmp_path: Path,
) -> None:
    """Public CPW driven fixture exercises gsim CPW port and index artifacts."""

    pytest.importorskip("gmsh")
    pytest.importorskip("gsim")

    from gsim.palace import DrivenSim
    from gsim.palace.mesh import (
        SurfaceFluxSpec,
        build_postprocessing_config_from_manifest,
    )

    orpen_sc_pdk.activate()
    component = cpw_straight(length=300, signal_width=10, gap=6, ground_width=40)

    output_dir = tmp_path / "palace-sim"
    sim = DrivenSim()
    sim.set_output_dir(output_dir)
    sim.set_geometry(component)
    sim.set_stack(
        include_substrate=True,
        substrate_thickness=20,
        add_oxide_dielectric=False,
        add_passivation_dielectric=False,
    )
    sim.set_airbox(margin_x=40, margin_y=40, z_above=50, z_below=10)
    sim.add_cpw_port("o1", layer="D0_TOP_M1", s_width=10, gap_width=6, length=10)
    sim.add_cpw_port(
        "o2",
        layer="D0_TOP_M1",
        s_width=10,
        gap_width=6,
        length=10,
        excited=False,
    )
    sim.set_driven(fmin=4e9, fmax=8e9, num_points=3, excitation_port="o1")

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

    postprocessing = build_postprocessing_config_from_manifest(
        mesh_result.manifest,
        surface_flux=(
            SurfaceFluxSpec(
                role="port_surface",
                flux_type="Power",
                two_sided=None,
            ),
        ),
    )
    config_path = sim.write_config(postprocessing=postprocessing)

    config = json.loads(Path(config_path).read_text())
    manifest = json.loads((output_dir / "mesh_manifest.json").read_text())
    index_map = json.loads((output_dir / "palace_index_map.json").read_text())

    assert (output_dir / "palace.msh").stat().st_size > 0
    assert config["Problem"]["Type"] == "Driven"

    lumped_ports = config["Boundaries"]["LumpedPort"]
    assert [port["Index"] for port in lumped_ports] == [1, 2]
    assert lumped_ports[0]["Excitation"] == 1
    assert lumped_ports[1]["Excitation"] is False
    assert all(len(port["Elements"]) == 2 for port in lumped_ports)

    surface_flux = config["Boundaries"]["Postprocessing"]["SurfaceFlux"]
    assert len(surface_flux) == 4
    assert all(row["Type"] == "Power" for row in surface_flux)

    manifest_port_entries = [
        entry for entry in manifest["entries"] if entry["role"] == "port_surface"
    ]
    assert {entry["name"] for entry in manifest_port_entries} == {
        "P1_E0",
        "P1_E1",
        "P2_E0",
        "P2_E1",
    }
    assert {entry["metadata"]["port"] for entry in manifest_port_entries} == {
        "P1",
        "P2",
    }
    assert all(entry["metadata"]["port_type"] == "cpw" for entry in manifest_port_entries)

    flux_by_index = {row["Index"]: row for row in surface_flux}
    flux_index_rows = [
        row
        for row in index_map["entries"]
        if row["section"] == "Boundaries.Postprocessing.SurfaceFlux"
    ]
    assert len(flux_index_rows) == 4
    for row in flux_index_rows:
        assert row["entry_name"] in {"P1_E0", "P1_E1", "P2_E0", "P2_E1"}
        assert row["metadata"]["port_type"] == "cpw"
        assert row["attributes"] == flux_by_index[row["index"]]["Attributes"]
