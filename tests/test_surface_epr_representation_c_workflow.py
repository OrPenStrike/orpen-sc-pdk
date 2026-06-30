"""Route C Surface EPR public workflow checks.

Responsibility:
Owns public PDK evidence that the Martinis ribbon Route C notebook can create a
real mesh/config using gsim-owned retained-volume Surface EPR interfaces.
Does not own Surface EPR geometry lowering, Palace result parsing, or public
interface preset definitions.
Source of Truth: docs/features/problem-type-notebook-suite.md and
notebooks/src/public_surface_epr_ribbon_capacitor_representation_c_workflow.py.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from orpen_sc_pdk.cells import martinis2022_differential_ribbon_capacitor
from orpen_sc_pdk.materials import (
    get_gsim_material_overlay,
    get_interface_preset_records,
    validate_interface_preset_records,
)
from orpen_sc_pdk.pdk import PDK


def _surface_epr_c_public_sim(output_dir: Path, *, max_its: int = 15):
    pytest.importorskip("gmsh")
    pytest.importorskip("gsim")

    from gsim.palace import ElectrostaticSim

    PDK.activate()
    component = martinis2022_differential_ribbon_capacitor(
        a_um=20,
        b_um=35,
        ell_r_um=160,
    ).copy()

    sim = ElectrostaticSim()
    sim.set_output_dir(output_dir)
    sim.set_geometry(component)
    sim.set_stack(PDK.get_layer_stack())
    sim.activate_substrate("D0_SUBSTRATE", die="D0", margin_x=40.0, margin_y=40.0)
    sim.activate_outer_vacuum(
        margin_x=0.0,
        margin_y=0.0,
        z_above=50.0,
        z_below=0.0,
    )
    public_presets = get_interface_preset_records()
    presets = validate_interface_preset_records(
        {
            "martinis2022_ms": {
                "interface_type": "MS",
                "thickness": 0.002,
                "permittivity": 9.8,
                "loss_tangent": 0.005,
                "source": "Martinis 2022 Table 2 ribbon example",
            },
            "Woods2019_Si_MA": public_presets["Woods2019_Si_MA"],
            "Woods2019_Si_SA": public_presets["Woods2019_Si_SA"],
        }
    )
    sim.set_surface_epr(
        representation="C",
        inset_margins_um=(0.0, 0.05, 0.1),
        interfaces={
            "MS": {
                "preset_name": "martinis2022_ms",
                "preset": presets["martinis2022_ms"],
                "face_kind": "bottom",
            },
            "MA": {
                "preset_name": "Woods2019_Si_MA",
                "preset": presets["Woods2019_Si_MA"],
                "face_kind": ("top", "sidewall"),
            },
            "SA": {
                "preset_name": "Woods2019_Si_SA",
                "preset": presets["Woods2019_Si_SA"],
                "face_kind": "top",
            },
        },
    )
    sim.add_terminal(
        "positive",
        layer="D0_TOP_M1",
        port_name="o_mesh_positive_electrode",
        physical_label="positive",
    )
    sim.add_terminal(
        "negative",
        layer="D0_TOP_M1",
        port_name="o_mesh_negative_electrode",
        physical_label="negative",
    )
    sim.set_electrostatic(save_fields=0)
    sim.set_palace_version("0.16.0")
    sim.set_refinement(max_its=max_its, tol=1e-3, update_fraction=0.3)
    sim.set_linear_solver(tol=1e-8, max_its=2000, estimator_mg=True)
    sim.set_output_formats(paraview=True, grid_function=False)

    mesh_result = sim.mesh(
        preset="coarse",
        refined_mesh_size=20,
        max_mesh_size=200,
        planar_conductors=False,
        auto_size=False,
    )
    return sim, mesh_result


def _surface_epr_entries(mesh_result) -> list:
    return [
        entry
        for entry in mesh_result.manifest.entries
        if entry.metadata.get("surface_epr") and entry.metadata.get("representation") == "C"
    ]


def test_public_surface_epr_c_terminal_labels_groups_and_config(tmp_path: Path) -> None:
    output_dir = tmp_path / "route-c"
    sim, mesh_result = _surface_epr_c_public_sim(output_dir)
    entries = _surface_epr_entries(mesh_result)

    assert [
        (terminal.name, terminal.layer, terminal.port_name, terminal.physical_label)
        for terminal in sim.terminals
    ] == [
        ("positive", "D0_TOP_M1", "o_mesh_positive_electrode", "positive"),
        ("negative", "D0_TOP_M1", "o_mesh_negative_electrode", "negative"),
    ]
    assert all(terminal.center is not None for terminal in sim.terminals)
    interface_types = {entry.metadata["interface_type"] for entry in entries}
    assert interface_types == {"MA", "MS", "SA"}
    expected_group_examples = {
        "MS__D0_TOP_M1@positive__D0_SUBSTRATE__BOTTOM__RING_0NM_50NM",
        "MS__D0_TOP_M1@negative__D0_SUBSTRATE__BOTTOM__RING_0NM_50NM",
        "MA__D0_TOP_M1@positive__AIR__TOP__RING_0NM_50NM",
        "MA__D0_TOP_M1@negative__AIR__TOP__RING_0NM_50NM",
        "MA__D0_TOP_M1@positive__AIR__SIDEWALL__RING_0NM_50NM",
        "MA__D0_TOP_M1@negative__AIR__SIDEWALL__RING_0NM_50NM",
        "SA__D0_SUBSTRATE__AIR__0000__RING_0NM_50NM",
    }
    assert expected_group_examples <= {entry.name for entry in entries}
    assert {entry.metadata.get("surface_epr_summary_kind") for entry in entries} == {
        "band",
        "core",
    }
    assert all(entry.attributes for entry in entries)

    config_path = sim.write_config(
        validate_mesh=False,
        material_overlay=get_gsim_material_overlay(),
        validate_schema=True,
    )
    config = json.loads(Path(config_path).read_text())
    terminals = config["Boundaries"]["Terminal"]
    assert {terminal["Index"] for terminal in terminals} == {1, 2}
    assert all(terminal["Attributes"] for terminal in terminals)

    child_attrs = {
        attr
        for entry in entries
        if entry.metadata.get("surface_epr_summary_kind") != "total"
        for attr in entry.attributes
    }
    dielectric_rows = config["Boundaries"]["Postprocessing"]["Dielectric"]
    assert {row["Type"] for row in dielectric_rows} == {"MA", "MS", "SA"}
    dielectric_attrs = {attr for row in dielectric_rows for attr in row.get("Attributes", ())}
    assert dielectric_attrs
    assert dielectric_attrs <= child_attrs


def test_public_surface_epr_c_optional_local_palace_smoke(tmp_path: Path) -> None:
    if os.environ.get("ORPEN_RUN_LOCAL_PALACE_SMOKE") != "1":
        pytest.skip("set ORPEN_RUN_LOCAL_PALACE_SMOKE=1 to run local Palace smoke")

    palace_sif = os.environ.get("PALACE_SIF")
    palace_executable = os.environ.get("PALACE_EXECUTABLE")
    setup_commands = tuple(
        command
        for command in os.environ.get(
            "PALACE_SETUP_COMMANDS",
            'eval "$(spack load --sh palace)"',
        ).splitlines()
        if command
    )
    if not palace_sif and not palace_executable and not setup_commands:
        pytest.skip(
            "set PALACE_SIF, PALACE_EXECUTABLE, or PALACE_SETUP_COMMANDS for local Palace smoke"
        )

    executable_mode = os.environ.get("PALACE_EXECUTABLE_MODE", "wrapper")
    if executable_mode not in {"wrapper", "binary"}:
        msg = "PALACE_EXECUTABLE_MODE must be 'wrapper' or 'binary'"
        raise ValueError(msg)

    output_dir = tmp_path / "route-c-palace"
    sim, _mesh_result = _surface_epr_c_public_sim(
        output_dir,
        max_its=int(os.environ.get("ORPEN_LOCAL_PALACE_SMOKE_MAX_ITS", "1")),
    )
    sim.write_config(
        validate_mesh=False,
        material_overlay=get_gsim_material_overlay(),
        validate_schema=True,
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
        if palace_executable:
            run_kwargs["palace_executable"] = palace_executable
        run_kwargs["executable_mode"] = executable_mode
        run_kwargs["serial"] = os.environ.get("PALACE_SERIAL") == "1"
        if setup_commands:
            run_kwargs["setup_commands"] = setup_commands

    results = sim.run_local(**run_kwargs)
    for filename in ("terminal-C.csv", "terminal-Cm.csv", "terminal-Cinv.csv"):
        path = results.get(filename)
        assert path is not None
        assert Path(path).stat().st_size > 0
