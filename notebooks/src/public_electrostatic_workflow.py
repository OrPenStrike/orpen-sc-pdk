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
# # Public Electrostatic capacitor workflow
#
# This notebook builds a publication-safe Electrostatic Palace fixture from a
# public OrPen capacitor and reusable `gsim` APIs. It generates
# mesh/config/index artifacts, reloads material and terminal provenance,
# displays synthetic public report tables, and leaves the real local Palace
# solve as an opt-in smoke step.

# %%
from __future__ import annotations

import tempfile
import warnings
from pathlib import Path

from gsim.palace import load_electrostatic_report
from IPython.display import display

import orpen_sc_pdk
from orpen_sc_pdk.materials import get_gsim_material_overlay
from scripts.public_palace_smoke_evidence import (
    build_public_electrostatic_capacitor_sim,
    build_public_electrostatic_postprocessing,
    load_public_json,
    local_palace_run_settings,
    public_artifact_status,
    public_config_generation_summary,
    public_domain_material_table,
    public_index_map_lookup_table,
    public_solver_config_hints,
    run_public_electrostatic_local_smoke,
    select_public_report_table,
    write_public_electrostatic_report_fixture,
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
# The fixture uses the public Martinis differential ribbon capacitor. Both
# electrodes live on the same metal layer, so `ElectrostaticSim` maps named
# terminals to separate center-selected PEC islands.

# %%
with tempfile.TemporaryDirectory() as temp_dir:
    output_dir = Path(temp_dir) / "electrostatic-capacitor"
    sim, mesh_result = build_public_electrostatic_capacitor_sim(output_dir)
    config_hints = public_solver_config_hints()
    config_path = sim.write_config(
        postprocessing=build_public_electrostatic_postprocessing(mesh_result),
        validate_mesh=False,
        material_overlay=get_gsim_material_overlay(),
        hints=config_hints,
    )

    config = load_public_json(config_path)
    index_map = load_public_json(output_dir / "palace_index_map.json")
    domain_materials = public_domain_material_table(output_dir)
    index_lookup = public_index_map_lookup_table(output_dir)
    electrostatic_summary = {
        "problem_type": config["Problem"]["Type"],
        "profile_config_hints": config_hints,
        "config_generation": public_config_generation_summary(output_dir),
        "artifacts": public_artifact_status(output_dir),
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
        "index_lookup_rows": len(index_lookup),
    }

display(electrostatic_summary)
display(domain_materials)
display(index_lookup)

# %% [markdown]
# ## Report loading
#
# The docs build uses synthetic public Palace outputs so the same `gsim` loader
# contract can be exercised without a local solver or private run artifacts.

# %%
with tempfile.TemporaryDirectory() as temp_dir:
    source = write_public_electrostatic_report_fixture(
        Path(temp_dir) / "electrostatic-report"
    )
    electrostatic_report = load_electrostatic_report(source, frequency_ghz=5.0)

    electrostatic_loss_budget = select_public_report_table(
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
    electrostatic_domain_loss = select_public_report_table(
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
    electrostatic_surface_loss = select_public_report_table(
        electrostatic_report.surface_loss,
        (
            "source_index",
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
            "t1_us",
        ),
    )

display(
    {
        "terminal_names": list(electrostatic_report.capacitance.terminal_names),
        "capacitance_shape": list(electrostatic_report.capacitance.dataframe.shape),
        "has_mutual_matrix": electrostatic_report.mutual_capacitance is not None,
        "has_inverse_matrix": electrostatic_report.inverse_capacitance is not None,
        "electrostatic_loss_budget_rows": electrostatic_loss_budget["summary"]["rows"],
        "electrostatic_domain_loss_rows": electrostatic_domain_loss["summary"]["rows"],
        "electrostatic_surface_loss_rows": electrostatic_surface_loss["summary"]["rows"],
    }
)
display(electrostatic_report.capacitance.dataframe)
display(electrostatic_loss_budget["summary"])
display(electrostatic_loss_budget["table"])
display(electrostatic_domain_loss["summary"])
display(electrostatic_domain_loss["table"])
display(electrostatic_surface_loss["summary"])
display(electrostatic_surface_loss["table"])

# %% [markdown]
# ## Optional local Palace smoke
#
# Normal docs builds report a skip reason. To run the coarse Electrostatic solve
# locally, set `ORPEN_RUN_LOCAL_PALACE_SMOKE=1` and configure either
# `PALACE_SIF` or `PALACE_EXECUTABLE`.

# %%
run_kwargs, skip_reason = local_palace_run_settings()
if skip_reason:
    local_smoke = {"status": "skipped", "reason": skip_reason}
else:
    with tempfile.TemporaryDirectory() as temp_dir:
        local_smoke = run_public_electrostatic_local_smoke(
            Path(temp_dir) / "electrostatic-local-smoke",
            run_kwargs,
        )

display(local_smoke)
