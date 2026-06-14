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
# The cells stop at local mesh/config generation. A full Palace solve can be
# run from the generated `config.json` and `palace.msh` when a Palace binary is
# available.

# %%
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from gsim.palace import DrivenSim, EigenmodeSim, ElectrostaticSim
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


def _artifact_status(output_dir: Path) -> dict[str, bool]:
    return {
        name: (output_dir / name).exists()
        for name in ("palace.msh", "config.json", "mesh_manifest.json", "palace_index_map.json")
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
# ## Local solve boundary
#
# These examples prove public geometry, material/layer metadata, automatic
# Palace config generation, mesh physical-name manifests, and index-map
# artifacts. A full Palace solve is intentionally outside the default docs
# build; run it locally from the generated `palace.msh` and `config.json` when
# a Palace binary is available.
