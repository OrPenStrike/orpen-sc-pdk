"""Driven CPW integration checks for public OrPen-to-gsim Palace workflows."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from material_overlay_assertions import (
    assert_public_si_effective_material,
    assert_public_si_overlay_material,
)

from orpen_sc_pdk.cells import cpw_straight
from orpen_sc_pdk.materials import get_gsim_material_overlay
from orpen_sc_pdk.pdk import PDK


def _public_cpw_driven_sim(output_dir: Path):
    pytest.importorskip("gmsh")
    pytest.importorskip("gsim")

    from gsim.palace import DrivenSim

    PDK.activate()
    component = cpw_straight(length=300, signal_width=10, gap=6, ground_width=40)

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

    mesh_result = sim.mesh(
        preset="coarse",
        refined_mesh_size=20,
        max_mesh_size=200,
        margin_x=40,
        margin_y=40,
        planar_conductors=True,
        auto_size=False,
    )

    return sim, mesh_result


def test_public_cpw_driven_gsim_port_postprocessing_artifacts(
    tmp_path: Path,
) -> None:
    """Public CPW driven fixture exercises gsim CPW port and index artifacts."""

    output_dir = tmp_path / "palace-sim"
    sim, mesh_result = _public_cpw_driven_sim(output_dir)

    from gsim.palace.mesh import (
        SurfaceFluxSpec,
        build_postprocessing_config_from_manifest,
    )

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
    config_path = sim.write_config(
        postprocessing=postprocessing,
        material_overlay=get_gsim_material_overlay(),
    )

    config = json.loads(Path(config_path).read_text())
    manifest = json.loads((output_dir / "mesh_manifest.json").read_text())
    index_map = json.loads((output_dir / "palace_index_map.json").read_text())

    assert (output_dir / "palace.msh").stat().st_size > 0
    assert config["Problem"]["Type"] == "Driven"
    assert_public_si_overlay_material(config, manifest)
    assert_public_si_effective_material(
        config_path,
        output_dir / "palace_index_map.json",
        manifest,
    )

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


def test_public_cpw_driven_optional_local_palace_coarse_smoke(
    tmp_path: Path,
) -> None:
    """Optional local Palace smoke proves the public driven CPW fixture solves."""

    if os.environ.get("ORPEN_RUN_LOCAL_PALACE_SMOKE") != "1":
        pytest.skip("set ORPEN_RUN_LOCAL_PALACE_SMOKE=1 to run local Palace smoke")

    palace_sif = os.environ.get("PALACE_SIF")
    palace_executable = os.environ.get("PALACE_EXECUTABLE")
    if not palace_sif and not palace_executable:
        pytest.skip("set PALACE_SIF or PALACE_EXECUTABLE for local Palace smoke")

    executable_mode = os.environ.get("PALACE_EXECUTABLE_MODE", "wrapper")
    if executable_mode not in {"wrapper", "binary"}:
        msg = "PALACE_EXECUTABLE_MODE must be 'wrapper' or 'binary'"
        raise ValueError(msg)

    output_dir = tmp_path / "palace-smoke"
    sim, mesh_result = _public_cpw_driven_sim(output_dir)

    from gsim.palace import SParams, resolve_palace_result
    from gsim.palace.mesh import (
        SurfaceFluxSpec,
        build_postprocessing_config_from_manifest,
    )
    from gsim.palace.results import DrivenReport

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
    sim.write_config(
        postprocessing=postprocessing,
        validate_mesh=False,
        material_overlay=get_gsim_material_overlay(),
    )

    use_apptainer = palace_sif is not None
    run_kwargs = {
        "use_apptainer": use_apptainer,
        "num_processes": int(os.environ.get("PALACE_NP", "1")),
        "num_threads": int(os.environ.get("PALACE_NT", "1")),
        "verbose": False,
    }
    if use_apptainer:
        run_kwargs["palace_sif_path"] = palace_sif
    else:
        run_kwargs["palace_executable"] = palace_executable
        run_kwargs["executable_mode"] = executable_mode
        run_kwargs["serial"] = os.environ.get("PALACE_SERIAL") == "1"

    results = sim.run_local(**run_kwargs)
    report = (
        resolve_palace_result(output_dir, problem_type="Driven")
        .load_report(require_report=True)
        .require_report()
    )

    assert isinstance(results, SParams)
    assert isinstance(report, DrivenReport)
    assert results.port_names == ["o1", "o2"]
    assert report.sparams.port_names == ["o1", "o2"]
    assert len(results.freq) == 3
    assert len(report.sparams.freq) == 3
    assert ("o1", "o1") in results.keys()
    assert ("o2", "o1") in results.keys()
    assert "port-S.csv" in results.files
    assert results.files["port-S.csv"].stat().st_size > 0
    assert results.to_dataframe().notna().all().all()
    assert bool(report.sources.set_index("name").loc["port-S.csv", "loaded"])
    assert bool(report.sources.set_index("name").loc["palace_index_map.json", "loaded"])
    assert not report.index_map.empty
