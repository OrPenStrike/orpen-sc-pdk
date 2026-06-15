# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.17.3
# ---

# %% [markdown]
# # Public simulation workflows
#
# This notebook demonstrates publication-safe Palace workflow fixtures for the
# public OrPen SC PDK. It exercises the reusable `gsim` mesh/config/artifact
# handoff for Driven, Eigenmode, and Electrostatic problem types without
# importing private layouts, private notebooks, saved private outputs, or
# private run folders.
#
# The geometry cells stop at local mesh/config generation. The report cells use
# synthetic public Palace artifacts to exercise reusable report loaders without
# requiring a local solver during the docs build. A full Palace solve can be run
# from the generated `config.json` and `palace.msh` when a Palace binary is
# available.

# %%
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd
from gsim.palace import (
    DrivenSim,
    EigenmodeSim,
    ElectrostaticSim,
    load_eigenmode_report,
    load_electrostatic_report,
)
from gsim.palace.mesh import (
    SurfaceFluxSpec,
    build_postprocessing_config_from_manifest,
)
from IPython.display import display

import orpen_sc_pdk
from orpen_sc_pdk.cells import (
    cpw_straight,
    martinis2022_differential_ribbon_capacitor,
    resonator,
)

orpen_sc_pdk.activate()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _write_json(path: Path, data: dict) -> Path:
    path.write_text(json.dumps(data, indent=2))
    return path


def _artifact_status(output_dir: Path) -> dict[str, bool]:
    return {
        name: (output_dir / name).exists()
        for name in ("palace.msh", "config.json", "mesh_manifest.json", "palace_index_map.json")
    }


def _display_report_table(
    title: str,
    frame: pd.DataFrame,
    columns: tuple[str, ...],
    max_rows: int = 8,
) -> pd.DataFrame:
    """Display a publication-safe subset of a reusable `gsim` report table."""

    selected_columns = [column for column in columns if column in frame.columns]
    preview = (
        frame.loc[:, selected_columns].head(max_rows).copy() if selected_columns else pd.DataFrame()
    )
    display(
        {
            "table": title,
            "rows": int(len(frame)),
            "shown_columns": selected_columns,
        }
    )
    display(preview)
    return preview


def _public_report_material_resolution() -> dict:
    return {
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
                "effective_material": {
                    "permittivity": 11.45,
                    "loss_tangent": 2.0e-6,
                },
                "palace_material": {
                    "Attributes": [10],
                    "Name": "Si",
                    "Permittivity": 11.45,
                    "LossTan": 2.0e-6,
                },
            }
        ],
        "interfaces": [
            {
                "interface_row_index": 1,
                "surface_index": 2,
                "surface_attributes": [20],
                "interface_type": "SA",
                "interface_material_name": "AlOx_native_generic",
                "matched_material_name": "AlOx_native_generic",
                "evaluation_frequency_hz": 5.0e9,
                "evaluation_frequency_ghz": 5.0,
                "model_type": "constant",
                "model_source": "orpen-sc-pdk tech.material_properties",
                "within_validity": True,
                "validity_note": None,
                "effective_material": {
                    "permittivity": 10.0,
                    "loss_tangent": 0.0017,
                },
                "palace_interface": {
                    "Index": 2,
                    "Attributes": [20],
                    "Type": "SA",
                    "Thickness": 0.003,
                    "Permittivity": 10.0,
                    "LossTan": 0.0017,
                },
            }
        ],
    }


def _write_public_eigenmode_report_fixture(output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    eig_path = output_dir / "eig.csv"
    eig_path.write_text(
        "m, Re{f} (GHz), Im{f} (GHz), Q, Error (Bkwd.), Error (Abs.)\n"
        "1, 5.0, 0.0, 2.0e6, 0.0, 0.0\n"
    )
    domain_e_path = output_dir / "domain-E.csv"
    domain_e_path.write_text("m, E_elec[1] (J), p_elec[1]\n1, 1.0, 0.25\n")
    surface_q_path = output_dir / "surface-Q.csv"
    surface_q_path.write_text("m, p_surf[2], Q_surf[2]\n1, 0.125, 1.0e6\n")
    config_path = _write_json(
        output_dir / "config.json",
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
                            "Permittivity": 10.0,
                            "LossTan": 0.0017,
                        }
                    ]
                }
            },
        },
    )
    index_map_path = _write_json(
        output_dir / "palace_index_map.json",
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
        },
    )
    material_resolution_path = _write_json(
        output_dir / "palace_material_resolution.json",
        _public_report_material_resolution(),
    )
    return {
        "eig.csv": eig_path,
        "domain-E.csv": domain_e_path,
        "surface-Q.csv": surface_q_path,
        "config.json": config_path,
        "palace_index_map.json": index_map_path,
        "palace_material_resolution.json": material_resolution_path,
    }


def _write_public_electrostatic_report_fixture(output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    terminal_c_path = output_dir / "terminal-C.csv"
    terminal_c_path.write_text(
        "i, C[i][1] (F), C[i][2] (F)\n1.00e+00, 1.0e-15, -2.0e-15\n2.00e+00, -2.0e-15, 4.0e-15\n"
    )
    domain_e_path = output_dir / "domain-E.csv"
    domain_e_path.write_text("i, E_elec[1] (J), p_elec[1]\n1, 1.0, 0.25\n2, 1.0, 0.125\n")
    surface_q_path = output_dir / "surface-Q.csv"
    surface_q_path.write_text("i, p_surf[2], Q_surf[2]\n1, 0.125, 1.0e6\n2, 0.25, 2.0e6\n")
    config_path = _write_json(
        output_dir / "config.json",
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
                            "Permittivity": 10.0,
                            "LossTan": 0.0017,
                        }
                    ]
                }
            },
        },
    )
    index_map_path = _write_json(
        output_dir / "palace_index_map.json",
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
        },
    )
    material_resolution_path = _write_json(
        output_dir / "palace_material_resolution.json",
        _public_report_material_resolution(),
    )
    return {
        "terminal-C.csv": terminal_c_path,
        "domain-E.csv": domain_e_path,
        "surface-Q.csv": surface_q_path,
        "config.json": config_path,
        "palace_index_map.json": index_map_path,
        "palace_material_resolution.json": material_resolution_path,
    }


# %% [markdown]
# ## Driven CPW workflow
#
# The driven fixture uses a public CPW straight with two CPW ports. The workflow
# writes a Driven `config.json`, mesh manifest, and Palace index map that links
# CPW port-surface `SurfaceFlux` indices back to generated port metadata.

# %%
with tempfile.TemporaryDirectory() as temp_dir:
    output_dir = Path(temp_dir) / "driven-cpw"
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
    sim.mesh(
        preset="coarse",
        refined_mesh_size=20,
        max_mesh_size=200,
        margin_x=40,
        margin_y=40,
        planar_conductors=True,
        auto_size=False,
    )

    postprocessing = build_postprocessing_config_from_manifest(
        sim._last_mesh_result.manifest,
        surface_flux=(
            SurfaceFluxSpec(
                role="port_surface",
                flux_type="Power",
                two_sided=None,
            ),
        ),
    )
    config_path = sim.write_config(postprocessing=postprocessing, validate_mesh=False)
    config = _load_json(config_path)
    index_map = _load_json(output_dir / "palace_index_map.json")
    driven_summary = {
        "problem_type": config["Problem"]["Type"],
        "artifacts": _artifact_status(output_dir),
        "lumped_port_count": len(config["Boundaries"]["LumpedPort"]),
        "surface_flux_rows": len(config["Boundaries"]["Postprocessing"]["SurfaceFlux"]),
        "indexed_ports": sorted(
            {
                row["metadata"]["port"]
                for row in index_map["entries"]
                if row["section"] == "Boundaries.Postprocessing.SurfaceFlux"
            }
        ),
    }

display(driven_summary)

# %% [markdown]
# ## Eigenmode resonator workflow
#
# The eigenmode fixture uses a public resonator cell. The workflow writes an
# Eigenmode `config.json`, mesh manifest, and Palace index map that links the
# absorbing boundary `SurfaceFlux` index back to the generated physical name.

# %%
with tempfile.TemporaryDirectory() as temp_dir:
    output_dir = Path(temp_dir) / "eigenmode-resonator"
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

    postprocessing = build_postprocessing_config_from_manifest(
        sim._last_mesh_result.manifest,
        surface_flux=(
            SurfaceFluxSpec(
                role="boundary_surface",
                entry_names=("absorbing",),
                flux_type="Power",
                two_sided=None,
            ),
        ),
    )
    config_path = sim.write_config(postprocessing=postprocessing, validate_mesh=False)
    config = _load_json(config_path)
    index_map = _load_json(output_dir / "palace_index_map.json")
    eigenmode_summary = {
        "problem_type": config["Problem"]["Type"],
        "artifacts": _artifact_status(output_dir),
        "energy_rows": len(config["Domains"]["Postprocessing"]["Energy"]),
        "surface_flux_names": sorted(
            {
                row["entry_name"]
                for row in index_map["entries"]
                if row["section"] == "Boundaries.Postprocessing.SurfaceFlux"
            }
        ),
    }

display(eigenmode_summary)

# %% [markdown]
# ## Electrostatic same-layer capacitor workflow
#
# The electrostatic fixture uses the public Martinis differential ribbon
# capacitor. Both electrodes live on the same metal layer, so the workflow uses
# `gsim` center-selected terminals to map positive and negative terminals to
# separate same-layer PEC islands.

# %%
with tempfile.TemporaryDirectory() as temp_dir:
    output_dir = Path(temp_dir) / "electrostatic-capacitor"
    component = martinis2022_differential_ribbon_capacitor(
        a_um=20,
        b_um=35,
        ell_r_um=160,
    )
    positive_port = component.ports["o_mesh_positive_electrode"]
    negative_port = component.ports["o_mesh_negative_electrode"]
    positive_center = tuple(float(value) for value in positive_port.center)
    negative_center = tuple(float(value) for value in negative_port.center)

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

    postprocessing = build_postprocessing_config_from_manifest(sim._last_mesh_result.manifest)
    config_path = sim.write_config(postprocessing=postprocessing, validate_mesh=False)
    config = _load_json(config_path)
    index_map = _load_json(output_dir / "palace_index_map.json")
    electrostatic_summary = {
        "problem_type": config["Problem"]["Type"],
        "artifacts": _artifact_status(output_dir),
        "terminal_count": len(config["Boundaries"]["Terminal"]),
        "terminal_names": sorted(
            {
                row["terminal_name"]
                for row in index_map["entries"]
                if row["section"] == "Boundaries.Terminal"
            }
        ),
        "terminal_layer_names": sorted(
            {
                row["metadata"]["layer"]
                for row in index_map["entries"]
                if row["section"] == "Boundaries.Terminal"
            }
        ),
    }

display(electrostatic_summary)

# %% [markdown]
# ## Reusable report table displays
#
# The report examples use synthetic public Palace artifacts so the docs build
# can exercise the same `gsim` report loaders without requiring a local Palace
# executable or publishing private solver output. The display helper keeps the
# notebook presentation layer separate from `gsim` report parsing.

# %%
with tempfile.TemporaryDirectory() as temp_dir:
    source = _write_public_eigenmode_report_fixture(Path(temp_dir) / "eigenmode-report")
    eigenmode_report = load_eigenmode_report(source)

    eigenmode_loss_budget = _display_report_table(
        "Eigenmode loss budget",
        eigenmode_report.loss_budget,
        (
            "mode_index",
            "frequency_ghz",
            "domain_inverse_q_sum",
            "surface_inverse_q_sum",
            "total_inverse_q_sum",
            "q_total",
            "t1_us",
        ),
    )
    eigenmode_domain_loss = _display_report_table(
        "Eigenmode domain loss",
        eigenmode_report.domain_loss,
        (
            "mode_index",
            "domain_index",
            "source_name",
            "material_name",
            "matched_material_name",
            "material_model_source",
            "p_elec",
            "loss_tangent",
            "inverse_q",
        ),
    )
    eigenmode_surface_loss = _display_report_table(
        "Eigenmode surface loss",
        eigenmode_report.surface_loss,
        (
            "mode_index",
            "surface_index",
            "source_name",
            "interface_type",
            "interface_material_name",
            "matched_material_name",
            "material_model_source",
            "p_surf",
            "loss_tangent",
            "inverse_q",
        ),
    )

display(
    {
        "eigenmode_loss_budget_rows": len(eigenmode_loss_budget),
        "eigenmode_domain_loss_rows": len(eigenmode_domain_loss),
        "eigenmode_surface_loss_rows": len(eigenmode_surface_loss),
    }
)

# %%
with tempfile.TemporaryDirectory() as temp_dir:
    source = _write_public_electrostatic_report_fixture(Path(temp_dir) / "electrostatic-report")
    electrostatic_report = load_electrostatic_report(source, frequency_ghz=5.0)

    electrostatic_loss_budget = _display_report_table(
        "Electrostatic loss budget",
        electrostatic_report.loss_budget,
        (
            "source_index",
            "domain_inverse_q_sum",
            "surface_inverse_q_sum",
            "total_inverse_q_sum",
            "q_total",
            "gamma_hz",
            "t1_us",
        ),
    )
    electrostatic_domain_loss = _display_report_table(
        "Electrostatic domain loss",
        electrostatic_report.domain_loss,
        (
            "source_index",
            "domain_index",
            "source_name",
            "material_name",
            "matched_material_name",
            "material_model_source",
            "p_elec",
            "loss_tangent",
            "inverse_q",
            "t1_us",
        ),
    )
    electrostatic_surface_loss = _display_report_table(
        "Electrostatic surface loss",
        electrostatic_report.surface_loss,
        (
            "source_index",
            "surface_index",
            "source_name",
            "interface_type",
            "interface_material_name",
            "matched_material_name",
            "material_model_source",
            "p_surf",
            "loss_tangent",
            "inverse_q",
            "t1_us",
        ),
    )

display(
    {
        "electrostatic_loss_budget_rows": len(electrostatic_loss_budget),
        "electrostatic_domain_loss_rows": len(electrostatic_domain_loss),
        "electrostatic_surface_loss_rows": len(electrostatic_surface_loss),
    }
)

# %% [markdown]
# ## Local solve boundary
#
# These examples prove public geometry, material/layer metadata, automatic
# Palace config generation, mesh physical-name manifests, index-map artifacts,
# and reusable report display tables. A full Palace solve is intentionally
# outside the default docs build; run it locally from the generated `palace.msh`
# and `config.json` when a Palace binary is available.
