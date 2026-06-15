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
# # Public Eigenmode resonator workflow
#
# This notebook builds a publication-safe Eigenmode Palace fixture from a public
# OrPen resonator and reusable `gsim` APIs. It generates mesh/config/index
# artifacts, reloads material and interface provenance, displays synthetic
# public report tables, and leaves the real local Palace solve as an opt-in
# smoke step.

# %%
from __future__ import annotations

import tempfile
import warnings
from pathlib import Path

from gsim.palace import load_dielectric_interface_summary, load_eigenmode_report
from IPython.display import display

import orpen_sc_pdk
from orpen_sc_pdk.materials import get_gsim_material_overlay
from scripts.public_palace_smoke_evidence import (
    build_public_eigenmode_interface_postprocessing,
    build_public_eigenmode_postprocessing,
    build_public_eigenmode_resonator_sim,
    load_public_json,
    local_palace_run_settings,
    public_artifact_status,
    public_config_generation_summary,
    public_domain_material_table,
    public_index_map_lookup_table,
    public_solver_config_hints,
    run_public_eigenmode_local_smoke,
    select_public_report_table,
    write_public_eigenmode_report_fixture,
)

warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    message="Material model for evaluation at wavelength=.*has unspecified validity range.*",
    module="gsim.palace.materials",
)

orpen_sc_pdk.activate()

# %% [markdown]
# ## Mesh and Palace config
#
# The fixture uses a public resonator cell. `EigenmodeSim` owns the modal solve
# intent, while the postprocessing builder translates generated boundary roles
# into Palace `SurfaceFlux` entries and index-map rows.

# %%
with tempfile.TemporaryDirectory() as temp_dir:
    output_dir = Path(temp_dir) / "eigenmode-resonator"
    sim, mesh_result = build_public_eigenmode_resonator_sim(output_dir)
    config_hints = public_solver_config_hints()
    config_path = sim.write_config(
        postprocessing=build_public_eigenmode_postprocessing(mesh_result),
        validate_mesh=False,
        material_overlay=get_gsim_material_overlay(),
        hints=config_hints,
    )

    config = load_public_json(config_path)
    index_map = load_public_json(output_dir / "palace_index_map.json")
    domain_materials = public_domain_material_table(output_dir)
    index_lookup = public_index_map_lookup_table(output_dir)
    eigenmode_summary = {
        "problem_type": config["Problem"]["Type"],
        "profile_config_hints": config_hints,
        "config_generation": public_config_generation_summary(output_dir),
        "artifacts": public_artifact_status(output_dir),
        "energy_rows": len(config["Domains"]["Postprocessing"]["Energy"]),
        "surface_flux_names": sorted(
            {
                row["entry_name"]
                for row in index_map["entries"]
                if row["section"] == "Boundaries.Postprocessing.SurfaceFlux"
            }
        ),
        "index_lookup_rows": len(index_lookup),
    }

display(eigenmode_summary)
display(domain_materials)
display(index_lookup)

# %% [markdown]
# ## Caller-supplied interface classification
#
# The generated mesh manifest exposes material interfaces such as
# `air___silicon`. Public workflows keep MA/MS/SA preset values caller-supplied
# until source-backed default records are accepted into the public PDK contract.

# %%
with tempfile.TemporaryDirectory() as temp_dir:
    output_dir = Path(temp_dir) / "eigenmode-interface"
    sim, mesh_result = build_public_eigenmode_resonator_sim(output_dir)
    config_path = sim.write_config(
        postprocessing=build_public_eigenmode_interface_postprocessing(mesh_result),
        validate_mesh=False,
        material_overlay=get_gsim_material_overlay(),
        hints=public_solver_config_hints(),
    )

    config = load_public_json(config_path)
    domain_materials = public_domain_material_table(output_dir)
    interface_summary = load_dielectric_interface_summary(
        {
            "config.json": config_path,
            "palace_index_map.json": output_dir / "palace_index_map.json",
        }
    )
    interface_lookup = public_index_map_lookup_table(
        output_dir,
        sections=("Boundaries.Postprocessing.Dielectric",),
    )
    interface_preview = interface_summary.loc[
        :,
        [
            "surface_index",
            "source_name",
            "interface_type",
            "preset_name",
            "preset_source",
            "interface_material_name",
            "matched_material_name",
            "material_model_source",
            "permittivity",
            "loss_tangent",
        ],
    ]
    generated_interface_summary = {
        "problem_type": config["Problem"]["Type"],
        "config_generation": public_config_generation_summary(output_dir),
        "dielectric_interface_rows": len(config["Boundaries"]["Postprocessing"]["Dielectric"]),
        "index_lookup_rows": len(interface_lookup),
        "classified_interfaces": interface_preview.to_dict(orient="records"),
    }

display(generated_interface_summary)
display(domain_materials)
display(interface_lookup)

# %% [markdown]
# ## Report loading
#
# The docs build uses synthetic public Palace outputs so the same `gsim` loader
# contract can be exercised without a local solver or private run artifacts.

# %%
with tempfile.TemporaryDirectory() as temp_dir:
    source = write_public_eigenmode_report_fixture(Path(temp_dir) / "eigenmode-report")
    eigenmode_report = load_eigenmode_report(source)

    eigenmode_loss_budget = select_public_report_table(
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
    eigenmode_domain_loss = select_public_report_table(
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
    eigenmode_surface_loss = select_public_report_table(
        eigenmode_report.surface_loss,
        (
            "mode_index",
            "surface_index",
            "source_name",
            "interface_type",
            "preset_name",
            "preset_source",
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
        "eigenmode_loss_budget_rows": eigenmode_loss_budget["summary"]["rows"],
        "eigenmode_domain_loss_rows": eigenmode_domain_loss["summary"]["rows"],
        "eigenmode_surface_loss_rows": eigenmode_surface_loss["summary"]["rows"],
    }
)
display(eigenmode_loss_budget["summary"])
display(eigenmode_loss_budget["table"])
display(eigenmode_domain_loss["summary"])
display(eigenmode_domain_loss["table"])
display(eigenmode_surface_loss["summary"])
display(eigenmode_surface_loss["table"])

# %% [markdown]
# ## Optional local Palace smoke
#
# Normal docs builds report a skip reason. To run the coarse Eigenmode solve
# locally, set `ORPEN_RUN_LOCAL_PALACE_SMOKE=1` and configure either
# `PALACE_SIF` or `PALACE_EXECUTABLE`.

# %%
run_kwargs, skip_reason = local_palace_run_settings()
if skip_reason:
    local_smoke = {"status": "skipped", "reason": skip_reason}
else:
    with tempfile.TemporaryDirectory() as temp_dir:
        local_smoke = run_public_eigenmode_local_smoke(
            Path(temp_dir) / "eigenmode-local-smoke",
            run_kwargs,
        )

display(local_smoke)
