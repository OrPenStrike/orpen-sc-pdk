from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from material_overlay_assertions import (
    assert_public_si_effective_material,
    assert_public_si_overlay_material,
)

import orpen_sc_pdk
from orpen_sc_pdk.cells import resonator
from orpen_sc_pdk.materials import get_gsim_material_overlay


def _public_resonator_eigenmode_sim(output_dir: Path):
    pytest.importorskip("gmsh")
    pytest.importorskip("gsim")

    from gsim.palace import EigenmodeSim

    orpen_sc_pdk.activate()
    component = resonator(
        length=1200,
        meanders=2,
        coupling_length=120,
        hanger_straight_length=80,
        cpw_radius=30,
        bend_npoints=8,
    )

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

    return sim, mesh_result


def _eigenmode_postprocessing(mesh_result):
    from gsim.palace.mesh import (
        SurfaceFluxSpec,
        build_postprocessing_config_from_manifest,
    )

    return build_postprocessing_config_from_manifest(
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


def test_public_resonator_eigenmode_gsim_postprocessing_artifacts(
    tmp_path: Path,
) -> None:
    """Public resonator eigenmode fixture exercises the gsim Palace handoff."""

    output_dir = tmp_path / "palace-sim"
    sim, mesh_result = _public_resonator_eigenmode_sim(output_dir)

    postprocessing = _eigenmode_postprocessing(mesh_result)
    config_path = sim.write_config(
        postprocessing=postprocessing,
        material_overlay=get_gsim_material_overlay(),
    )

    config = json.loads(Path(config_path).read_text())
    manifest = json.loads((output_dir / "mesh_manifest.json").read_text())
    index_map = json.loads((output_dir / "palace_index_map.json").read_text())

    assert (output_dir / "palace.msh").stat().st_size > 0
    assert config["Problem"]["Type"] == "Eigenmode"
    assert_public_si_overlay_material(config, manifest)
    assert_public_si_effective_material(
        config_path,
        output_dir / "palace_index_map.json",
        manifest,
    )
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


def test_public_resonator_eigenmode_optional_local_palace_coarse_smoke(
    tmp_path: Path,
) -> None:
    """Optional local Palace smoke proves the public Eigenmode fixture solves."""

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
    sim, mesh_result = _public_resonator_eigenmode_sim(output_dir)
    sim.write_config(
        postprocessing=_eigenmode_postprocessing(mesh_result),
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

    from gsim.palace import load_eigenmode_report

    eig_path = results.get("eig.csv")
    assert eig_path is not None
    assert eig_path.stat().st_size > 0
    assert results["domain-E.csv"].stat().st_size > 0

    report = load_eigenmode_report(results)
    assert report.eigenmodes.n_modes == 2
    assert report.eigenmodes.freq_real_ghz.min() > 0
    assert report.eigenmodes.q.min() > 0
    assert {
        "frequency_ghz",
        "imaginary_frequency_ghz",
        "q_factor",
    } <= set(report.modes.columns)
    assert not report.domain_energy.empty
    assert bool(report.sources.set_index("name").loc["domain-E.csv", "loaded"])

    history = report.mode_history
    assert history["source_kind"].tolist() == ["final", "final"]
    assert history["mode_index"].tolist() == [1, 2]
    assert history["frequency_ghz"].min() > 0
