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
from orpen_sc_pdk.cells import martinis2022_differential_ribbon_capacitor
from orpen_sc_pdk.materials import get_gsim_material_overlay


def _public_same_layer_capacitor_electrostatic_sim(output_dir: Path):
    pytest.importorskip("gmsh")
    pytest.importorskip("gsim")

    from gsim.palace import ElectrostaticSim

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

    return sim, mesh_result


def test_public_same_layer_capacitor_electrostatic_gsim_terminal_artifacts(
    tmp_path: Path,
) -> None:
    """Public same-layer capacitor fixture exercises terminal index artifacts."""

    output_dir = tmp_path / "palace-sim"
    sim, mesh_result = _public_same_layer_capacitor_electrostatic_sim(output_dir)

    from gsim.palace.mesh import build_postprocessing_config_from_manifest

    postprocessing = build_postprocessing_config_from_manifest(mesh_result.manifest)
    config_path = sim.write_config(
        postprocessing=postprocessing,
        material_overlay=get_gsim_material_overlay(),
    )

    config = json.loads(Path(config_path).read_text())
    manifest = json.loads((output_dir / "mesh_manifest.json").read_text())
    index_map = json.loads((output_dir / "palace_index_map.json").read_text())

    assert (output_dir / "palace.msh").stat().st_size > 0
    assert config["Problem"]["Type"] == "Electrostatic"
    assert "Electrostatic" in config["Solver"]
    assert_public_si_overlay_material(config, manifest)
    assert_public_si_effective_material(
        config_path,
        output_dir / "palace_index_map.json",
        manifest,
    )

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


def test_public_same_layer_capacitor_optional_local_palace_coarse_smoke(
    tmp_path: Path,
) -> None:
    """Optional local Palace smoke proves the public electrostatic fixture solves."""

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
    sim, mesh_result = _public_same_layer_capacitor_electrostatic_sim(output_dir)

    from gsim.palace import load_terminal_matrix
    from gsim.palace.mesh import build_postprocessing_config_from_manifest

    postprocessing = build_postprocessing_config_from_manifest(mesh_result.manifest)
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

    for filename in ("terminal-C.csv", "terminal-Cm.csv", "terminal-Cinv.csv"):
        path = results.get(filename)
        assert path is not None
        assert Path(path).stat().st_size > 0

    for matrix_kind in ("C", "Cm", "Cinv"):
        matrix = load_terminal_matrix(results, matrix_kind)
        assert matrix.terminal_names == ("positive", "negative")
        assert matrix.dataframe.shape == (2, 2)
        assert matrix.dataframe.notna().all().all()
        assert matrix.dataframe.abs().max().max() > 0

        long_frame = matrix.to_long_dataframe()
        assert len(long_frame) == 4
        assert set(long_frame["row_terminal"]) == {"positive", "negative"}
        assert set(long_frame["column_terminal"]) == {"positive", "negative"}
