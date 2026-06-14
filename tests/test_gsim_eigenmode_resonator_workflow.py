from __future__ import annotations

import json
from pathlib import Path

import pytest

import orpen_sc_pdk
from orpen_sc_pdk.cells import resonator


def test_public_resonator_eigenmode_gsim_postprocessing_artifacts(
    tmp_path: Path,
) -> None:
    """Public resonator eigenmode fixture exercises the gsim Palace handoff."""

    pytest.importorskip("gmsh")
    pytest.importorskip("gsim")

    from gsim.palace import EigenmodeSim
    from gsim.palace.mesh import (
        SurfaceFluxSpec,
        build_postprocessing_config_from_manifest,
    )

    orpen_sc_pdk.activate()
    component = resonator(
        length=1200,
        meanders=2,
        coupling_length=120,
        hanger_straight_length=80,
        cpw_radius=30,
        bend_npoints=8,
    )

    output_dir = tmp_path / "palace-sim"
    sim = EigenmodeSim()
    sim.set_output_dir(output_dir)
    sim.set_geometry(component)
    sim.set_stack(
        include_substrate=True,
        substrate_thickness=20,
        add_oxide_dielectric=False,
        add_passivation_dielectric=False,
    )
    sim.set_airbox(margin_x=50, margin_y=50, z_above=50, z_below=10)
    sim.set_eigenmode(num_modes=2, target=6e9)

    sim.mesh(
        preset="coarse",
        refined_mesh_size=20,
        max_mesh_size=200,
        margin_x=50,
        margin_y=50,
        planar_conductors=True,
        auto_size=False,
    )
    mesh_result = sim._last_mesh_result

    postprocessing = build_postprocessing_config_from_manifest(
        mesh_result.manifest,
        surface_flux=(
            SurfaceFluxSpec(
                role="boundary_surface",
                entry_names=("absorbing",),
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
    assert config["Problem"]["Type"] == "Eigenmode"
    assert config["Domains"]["Postprocessing"]["Energy"]
    surface_flux = config["Boundaries"]["Postprocessing"]["SurfaceFlux"]
    assert len(surface_flux) == 1
    assert surface_flux[0]["Type"] == "Power"

    manifest_roles = {entry["role"] for entry in manifest["entries"]}
    assert {
        "dielectric_volume",
        "pec_surface",
        "boundary_surface",
        "refinement_line",
    } <= manifest_roles

    absorbing_rows = [
        row
        for row in index_map["entries"]
        if row["section"] == "Boundaries.Postprocessing.SurfaceFlux"
        and row["entry_name"] == "absorbing"
        and row["physical_names"] == ["absorbing"]
    ]
    assert len(absorbing_rows) == 1
    assert absorbing_rows[0]["index"] == surface_flux[0]["Index"]
    assert absorbing_rows[0]["attributes"] == surface_flux[0]["Attributes"]
