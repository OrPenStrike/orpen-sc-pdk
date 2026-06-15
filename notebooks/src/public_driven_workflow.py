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
# # Public Driven CPW workflow
#
# This notebook builds a publication-safe Driven Palace fixture from public
# OrPen cells and reusable `gsim` APIs. It generates mesh/config/index artifacts,
# reloads material and index provenance, displays synthetic public report
# tables, and leaves the real local Palace solve as an opt-in smoke step.

# %%
from __future__ import annotations

import tempfile
import warnings
from pathlib import Path

from gsim.palace import load_driven_report
from IPython.display import display

import orpen_sc_pdk
from orpen_sc_pdk.materials import get_gsim_material_overlay
from scripts.public_palace_smoke_evidence import (
    build_public_driven_cpw_sim,
    build_public_driven_postprocessing,
    load_public_json,
    local_palace_run_settings,
    public_artifact_status,
    public_config_generation_summary,
    public_domain_material_table,
    public_index_map_lookup_table,
    public_solver_config_hints,
    run_public_driven_local_smoke,
    select_public_report_table,
    write_public_driven_report_fixture,
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
# The fixture uses a public CPW straight with two CPW ports. `DrivenSim` owns the
# driven sweep intent, while the postprocessing builder translates generated
# port-surface roles into Palace `SurfaceFlux` entries and index-map rows.

# %%
with tempfile.TemporaryDirectory() as temp_dir:
    output_dir = Path(temp_dir) / "driven-cpw"
    sim, mesh_result = build_public_driven_cpw_sim(output_dir)
    config_hints = public_solver_config_hints()
    config_path = sim.write_config(
        postprocessing=build_public_driven_postprocessing(mesh_result),
        validate_mesh=False,
        material_overlay=get_gsim_material_overlay(),
        hints=config_hints,
    )

    config = load_public_json(config_path)
    index_map = load_public_json(output_dir / "palace_index_map.json")
    domain_materials = public_domain_material_table(output_dir)
    index_lookup = public_index_map_lookup_table(output_dir)
    driven_summary = {
        "problem_type": config["Problem"]["Type"],
        "profile_config_hints": config_hints,
        "config_generation": public_config_generation_summary(output_dir),
        "artifacts": public_artifact_status(output_dir),
        "lumped_port_count": len(config["Boundaries"]["LumpedPort"]),
        "surface_flux_rows": len(config["Boundaries"]["Postprocessing"]["SurfaceFlux"]),
        "index_lookup_rows": len(index_lookup),
        "indexed_ports": sorted(
            {
                row["metadata"]["port"]
                for row in index_map["entries"]
                if row["section"] == "Boundaries.Postprocessing.SurfaceFlux"
            }
        ),
    }

display(driven_summary)
display(domain_materials)
display(index_lookup)

# %% [markdown]
# ## Report loading
#
# The docs build uses synthetic public Palace outputs so the same `gsim` loader
# contract can be exercised without a local solver or private run artifacts.

# %%
with tempfile.TemporaryDirectory() as temp_dir:
    source = write_public_driven_report_fixture(Path(temp_dir) / "driven-report")
    driven_report = load_driven_report(source)

    driven_sparams = select_public_report_table(
        driven_report.sparams.to_dataframe(),
        (
            "freq_ghz",
            "S_o1_o1_db",
            "S_o2_o1_db",
            "S_o1_o1_deg",
            "S_o2_o1_deg",
        ),
    )
    driven_port_epr = select_public_report_table(
        driven_report.port_epr,
        (
            "mode_index",
            "port_index",
            "source_name",
            "entry_name",
            "postprocessing_type",
            "p_port",
            "abs_p_port_fraction",
        ),
    )

display(
    {
        "driven_frequency_rows": driven_sparams["summary"]["rows"],
        "driven_port_epr_rows": driven_port_epr["summary"]["rows"],
        "driven_missing_reports": list(driven_report.missing_reports),
    }
)
display(driven_sparams["summary"])
display(driven_sparams["table"])
display(driven_port_epr["summary"])
display(driven_port_epr["table"])

# %% [markdown]
# ## Optional local Palace smoke
#
# Normal docs builds report a skip reason. To run the coarse Driven solve
# locally, set `ORPEN_RUN_LOCAL_PALACE_SMOKE=1` and configure either
# `PALACE_SIF` or `PALACE_EXECUTABLE`.

# %%
run_kwargs, skip_reason = local_palace_run_settings()
if skip_reason:
    local_smoke = {"status": "skipped", "reason": skip_reason}
else:
    with tempfile.TemporaryDirectory() as temp_dir:
        local_smoke = run_public_driven_local_smoke(
            Path(temp_dir) / "driven-local-smoke",
            run_kwargs,
        )

display(local_smoke)
