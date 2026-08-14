# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.3
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Interdigital capacitor Q3D finger-length sweep
#
# Each point is an independent Q3D project and result. The listed lengths are
# editable run controls, not a qualification or optimization gate.

# %% [markdown]
# ## Setup and Imports

# %%
from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter, sleep

import gdsfactory as gf
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from ansys.aedt.core import Q3d
from IPython.display import HTML, clear_output, display

import orpen_sc_pdk
from orpen_sc_pdk.materials import get_material_records
from orpen_sc_pdk.simulation.aedt import (
    Axis,
    ParameterSpace,
    aedt_material_name_for_physical_material,
    aedt_material_name_from_physical_key,
    load_q3d_capacitance_result,
)
from orpen_sc_pdk.tech import METAL_THICKNESS_UM, OUTER_VACUUM_THICKNESS_UM, SUBSTRATE_THICKNESS_UM

REPO_ROOT = Path(orpen_sc_pdk.__file__).resolve().parent.parent
if not (REPO_ROOT / "orpen_sc_pdk").is_dir():
    raise RuntimeError("The active orpen_sc_pdk package is not a source checkout.")
orpen_sc_pdk.activate()

# %% [markdown]
# ## Setup and Run Controls

# %%

FINGERS = 20
FINGER_GAP_UM = 4.0
FINGER_WIDTH_UM = 3.3
TAPER_LENGTH_UM = 10.0
TERMINAL_EXTENSION_LENGTH_UM = 10.0
CAPACITOR_GROUND_GAP_UM = 16.0
TERMINAL_OPEN_CLEARANCE_UM = 6.0  # Match the selected CPW gap at each open cut plane.
COUPON_MARGIN_UM = 100.0
IDC_LAYOUT_CONTROLS = {
    "fingers": FINGERS,
    "finger_gap": FINGER_GAP_UM,
    "finger_width": FINGER_WIDTH_UM,
    "taper_length": TAPER_LENGTH_UM,
    "terminal_extension_length_um": TERMINAL_EXTENSION_LENGTH_UM,
    "capacitor_ground_gap": CAPACITOR_GROUND_GAP_UM,
}
IDC_COUPON_CONTROLS = {
    **IDC_LAYOUT_CONTROLS,
    "terminal_open_clearance_um": TERMINAL_OPEN_CLEARANCE_UM,
    "coupon_margin_um": COUPON_MARGIN_UM,
}
METAL_KEY = "Al"
SUBSTRATE_KEY = "Si"
SUPERCONDUCTING_METALS = True
REGION_PADDING_UM = OUTER_VACUUM_THICKNESS_UM

# %% [markdown]
# ## Sweep Parameter Controls

# %%
FINGER_LENGTHS_UM = (35.0, 50.0, 65.0, 80.0, 100.0)
PARAMETER_SPACE = ParameterSpace(
    Axis("finger_length_um", FINGER_LENGTHS_UM, default=FINGER_LENGTHS_UM[0])
)
SWEEP_POINTS = PARAMETER_SPACE.grid()

# %% [markdown]
# ### Q3D adaptive setup controls

# %%
Q3D_SETUP = {
    "name": "Setup1",
    "capacitance": {
        "MaxPass": 99,
        "MinPass": 1,
        "MinConvPass": 2,
        "PerError": 0.1,
        "PerRefine": 30,
        "AutoIncreaseSolutionOrder": True,
        "SolutionOrder": "High",
        "Solver Type": "Iterative",
    },
}

# %% [markdown]
# ### Solver controls

# %%
NON_GRAPHICAL = True
CLOSE_DESKTOP = True
SOLUTION_TYPE = "Q3D Extractor"

# %% [markdown]
# ### Execution controls

# %%
RUN_SOLVER = False
RESUME_EXISTING_PROJECTS = True

# %% [markdown]
# ### Run and artifact identity

# %%
SWEEP_RUN_ID = "2026-08-12-idc-q3d-compact-finger-length-v1"
RUN_ROOT = (
    REPO_ROOT / "build" / "simulation" / "aedt" / "interdigital_capacitor_q3d_length" / SWEEP_RUN_ID
)
SWEEP_TABLE_PATH = RUN_ROOT / "capacitance_length_sweep.csv"
SWEEP_PLOT_PATH = RUN_ROOT / "capacitance_length_sweep.html"
LENGTH_MODEL_PATH = RUN_ROOT / "capacitance_length_model.json"
ACF_PATH = REPO_ROOT / "notebooks" / "AEDTSimulation" / "Q3D_Local.acf"

# %% [markdown]
# A saved matrix is reused only with its deterministic point directory. A
# project without a matrix resumes its existing adaptive solution; an empty
# saved project is rebuilt from the same coupon GDS.

# %%

EXPECTED_NODE_LABELS = ("ground", "signal_1", "signal_2")

DATA_CLASSIFICATION = "public"
ALLOWED_CONSUMERS = "orpen_sc_pdk developers and reviewers"
EVIDENCE_STATUS = "diagnostic"

# %% [markdown]
# ## Create Simulation Component / Coupon

# %%
review_length_um = max(FINGER_LENGTHS_UM)
review_coupon = gf.get_component(
    "interdigital_capacitor_q3d_coupon",
    finger_length=review_length_um,
    **IDC_COUPON_CONTROLS,
)
review_coupon.plot()
footprint_rows = []
for point in SWEEP_POINTS:
    candidate = gf.get_component(
        "interdigital_capacitor",
        finger_length=point.coords["finger_length_um"],
        **IDC_LAYOUT_CONTROLS,
    )
    bbox = candidate.dbbox()
    footprint_rows.append(
        {
            "point_id": point.id,
            **point.coords,
            "layout_width_um": bbox.width(),
            "layout_height_um": bbox.height(),
        }
    )
footprint_table = pd.DataFrame(footprint_rows)
footprint_by_length = footprint_table.set_index("finger_length_um").to_dict("index")
display(footprint_table)

# %% [markdown]
# ## Initialize AEDT Project / App
#
# Each point opens one independent Q3D project inside the explicit sweep loop
# below. Completed Maxwell matrices are reused without opening AEDT.

# %% [markdown]
# ## Import GDS and Build the HFSS/Q3D/Q2D Model
#
# For an unsolved point, the loop exports its registered GDSFactory coupon,
# imports the four declared layers, and renames the resulting AEDT objects.

# %% [markdown]
# ## Geometry Verification
#
# The coupon plot and footprint table above are the pre-solve geometry review.
# AEDT object names are read back immediately after each GDS import.

# %% [markdown]
# ## Materials and Boundaries
#
# The loop assigns the selected metal model, silicon substrate, and a vacuum
# Region. Ground and both IDC conductors remain three separate Signal nets.

# %% [markdown]
# ## Ports / Nets / Excitations
#
# Q3D uses three Signal nets: `ground`, `signal_1`, and `signal_2`.

# %% [markdown]
# ## Simulation Setup
#
# `Q3D_SETUP` above is written directly to the capacitance-only setup.

# %% [markdown]
# ## Simulation Configuration
#
# The solve uses the common `Q3D_Local.acf` selected in the run controls.

# %% [markdown]
# ## Solve and Export

# %%
if RUN_SOLVER:
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    metal_condition = "cryogenic" if SUPERCONDUCTING_METALS else "room_temperature"
    metal_material = aedt_material_name_for_physical_material(
        METAL_KEY,
        material_kind=get_material_records()[METAL_KEY]["material_kind"],
        material_condition=metal_condition,
    )
    substrate_material = aedt_material_name_from_physical_key(SUBSTRATE_KEY)
    sweep_rows = []

    for point in SWEEP_POINTS:
        case_run_id = f"{SWEEP_RUN_ID}__{point.id}"
        case_dir = RUN_ROOT / point.id
        case_dir.mkdir(parents=True, exist_ok=True)
        project_path = case_dir / "interdigital_capacitor_q3d.aedt"
        gds_path = case_dir / "interdigital_capacitor_coupon.gds"
        matrix_path = case_dir / "c_maxwell_matrix.csv"
        timing_path = case_dir / "solve_timing.json"

        if RESUME_EXISTING_PROJECTS and matrix_path.exists():
            result = load_q3d_capacitance_result(
                matrix_path,
                node_labels=EXPECTED_NODE_LABELS,
                result_path=timing_path if timing_path.exists() else None,
            )
            status = "resumed_existing_result"
        else:
            coupon = gf.get_component(
                "interdigital_capacitor_q3d_coupon",
                finger_length=point.coords["finger_length_um"],
                **IDC_COUPON_CONTROLS,
            )
            coupon_layers = coupon.info["q3d_coupon"]["layers"]
            q3d_layers = {
                "signal_1": {
                    "layer": tuple(coupon_layers["signal_1"]),
                    "zmin": 0.0,
                    "thickness": METAL_THICKNESS_UM,
                    "material": metal_material,
                },
                "signal_2": {
                    "layer": tuple(coupon_layers["signal_2"]),
                    "zmin": 0.0,
                    "thickness": METAL_THICKNESS_UM,
                    "material": metal_material,
                },
                "ground": {
                    "layer": tuple(coupon_layers["finite_ground"]),
                    "zmin": 0.0,
                    "thickness": METAL_THICKNESS_UM,
                    "material": metal_material,
                },
                "substrate": {
                    "layer": tuple(coupon_layers["substrate_footprint"]),
                    "zmin": -SUBSTRATE_THICKNESS_UM,
                    "thickness": SUBSTRATE_THICKNESS_UM,
                    "material": substrate_material,
                },
            }
            q3d = Q3d(
                project=str(project_path),
                design="idc_q3d_length_sweep",
                solution_type=SOLUTION_TYPE,
                non_graphical=NON_GRAPHICAL,
                new_desktop=True,
                close_on_exit=False,
            )
            q3d.modeler.model_units = "um"
            q3d.modeler.refresh_all_ids()
            build_model = not q3d.modeler.object_names
            if build_model:
                coupon.write_gds(gds_path)
                gds_layer_mapping = {
                    spec["layer"][0]: (spec["zmin"], spec["thickness"])
                    for spec in q3d_layers.values()
                }
                if not q3d.import_gds_3d(
                    str(gds_path),
                    gds_layer_mapping,
                    units="um",
                    import_method=1,
                ):
                    raise RuntimeError(f"Q3d.import_gds_3d failed for {gds_path}")
                q3d.modeler.refresh_all_ids()
                for net_name, spec in q3d_layers.items():
                    layer_number = spec["layer"][0]
                    matches = [
                        name
                        for name in q3d.modeler.object_names
                        if name.startswith(f"signal{layer_number}_")
                    ]
                    if len(matches) != 1:
                        raise RuntimeError(
                            f"Expected one imported object for {net_name}, found {matches!r}"
                        )
                    imported = q3d.modeler.get_object_from_name(matches[0])
                    imported.name = net_name
                    imported.material_name = spec["material"]
                q3d.modeler.create_region(
                    pad_value=[f"{REGION_PADDING_UM}um"] * 6,
                    pad_type="Absolute Offset",
                    name="Region",
                ).material_name = "vacuum"
                for net_name in EXPECTED_NODE_LABELS:
                    q3d.assign_net(net_name, net_name=net_name, net_type="Signal")
                q3d.save_project()

            setup = (
                q3d.get_setup(Q3D_SETUP["name"])
                if Q3D_SETUP["name"] in q3d.setup_names
                else q3d.create_setup(Q3D_SETUP["name"])
            )
            # PyAEDT 1.3 omits disabled blocks when reopening a capacitance-only setup.
            setup.props.setdefault("AC", {})
            setup.props.setdefault("DC", {})
            setup.capacitance_enabled = True
            setup.ac_rl_enabled = False
            setup.dc_enabled = False
            setup.props["Cap"].update(Q3D_SETUP["capacitance"])
            setup.update()

            started = perf_counter()
            if not q3d.analyze_setup(
                setup.name,
                acf_file=str(ACF_PATH),
                revert_to_initial_mesh=False,
                blocking=False,
            ):
                raise RuntimeError(f"Q3D failed to start {case_run_id}.")
            sleep(1)
            completed_passes = 0
            while q3d.are_there_simulations_running:
                profiles = setup.get_profile()
                completed_passes = (
                    max(
                        (profile.num_adaptive_passes for profile in profiles.values()),
                        default=0,
                    )
                    if profiles
                    else completed_passes
                )
                clear_output(wait=True)
                display(
                    HTML(
                        f"<b>Q3D sweep is running</b> &middot; {point.id} &middot; "
                        f"{completed_passes} adaptive passes completed &middot; "
                        f"{perf_counter() - started:.1f} s elapsed"
                    )
                )
                sleep(5)
            elapsed_seconds = perf_counter() - started
            q3d.save_project()
            if not q3d.export_matrix_data(
                str(matrix_path),
                problem_type="C",
                matrix_type="Maxwell",
                setup=setup.name,
                c_unit="fF",
            ):
                raise RuntimeError(f"Q3D Maxwell export failed for {matrix_path}")
            result = load_q3d_capacitance_result(matrix_path, node_labels=EXPECTED_NODE_LABELS)
            timing_path.write_text(
                json.dumps({"analyze_setup_seconds": elapsed_seconds}, indent=2) + "\n",
                encoding="utf-8",
            )
            status = "solved" if build_model else "resumed_existing_project"
            q3d.release_desktop(close_projects=True, close_desktop=CLOSE_DESKTOP)

        if result.unit != "fF":
            raise RuntimeError(f"Expected Q3D capacitance in fF, got {result.unit!r}.")
        matrix = result.maxwell
        timings = (
            json.loads(timing_path.read_text(encoding="utf-8")) if timing_path.exists() else {}
        )
        elapsed_seconds = timings.get("analyze_setup_seconds", timings.get("analyze_setup"))
        sweep_rows.append(
            {
                "run_id": case_run_id,
                "finger_length_um": point.coords["finger_length_um"],
                "layout_width_um": footprint_by_length[point.coords["finger_length_um"]][
                    "layout_width_um"
                ],
                "layout_height_um": footprint_by_length[point.coords["finger_length_um"]][
                    "layout_height_um"
                ],
                "C1G_fF": -matrix.loc["signal_1", "ground"],
                "C2G_fF": -matrix.loc["signal_2", "ground"],
                "C12_fF": -matrix.loc["signal_1", "signal_2"],
                "solve_time_s": elapsed_seconds,
                "status": status,
                "project_path": str(project_path.relative_to(REPO_ROOT)),
                "result_path": str(matrix_path.relative_to(REPO_ROOT)),
            }
        )
else:
    sweep_rows = []
    print("RUN_SOLVER = False: AEDT is not started; no Q3D sweep results are created.")

# %% [markdown]
# ## Adaptive-Pass Convergence / Solver Diagnostics
#
# During a solve, the cell above shows the active point, completed adaptive
# passes, and elapsed time. Saved per-point timing receipts are summarized below.

# %% [markdown]
# ## Results: Plots and Readable Tables

# %% [markdown]
# ### Physics Analysis Results

# %%
if RUN_SOLVER:
    sweep_table = pd.DataFrame(sweep_rows).sort_values("finger_length_um")
    sweep_table.to_csv(SWEEP_TABLE_PATH, index=False)
elif SWEEP_TABLE_PATH.exists():
    sweep_table = pd.read_csv(SWEEP_TABLE_PATH).sort_values("finger_length_um")
else:
    sweep_table = None

if sweep_table is not None:
    sweep_table = sweep_table.drop(
        columns=["layout_width_um", "layout_height_um"], errors="ignore"
    ).merge(
        footprint_table[["finger_length_um", "layout_width_um", "layout_height_um"]],
        on="finger_length_um",
        how="left",
    )
    sweep_table.to_csv(SWEEP_TABLE_PATH, index=False)
    display(
        sweep_table[
            [
                "finger_length_um",
                "layout_width_um",
                "layout_height_um",
                "C1G_fF",
                "C2G_fF",
                "C12_fF",
                "status",
            ]
        ]
    )
    figure = go.Figure()
    for column, color in (("C1G_fF", "#2563eb"), ("C2G_fF", "#f59e0b"), ("C12_fF", "#7c3aed")):
        figure.add_scatter(
            x=sweep_table["finger_length_um"],
            y=sweep_table[column],
            mode="lines+markers",
            name=column.removesuffix("_fF"),
            line={"color": color},
        )
    figure.update_layout(
        title="IDC Q3D capacitance versus finger length",
        template="plotly_white",
        xaxis_title="Finger length (um)",
        yaxis_title="Capacitance (fF)",
    )
    figure.write_html(SWEEP_PLOT_PATH, include_plotlyjs=True)
    figure.show()
else:
    print("No saved Q3D sweep results are available.")

# %% [markdown]
# ### Finger-length mapping diagnostic
#
# These affine fits describe only the simulated 35–100 um interval and are not
# extrapolation or Design Target authority. The three branch capacitances retain
# the Q3D three-node reduction: C1G, C2G, and C12.

# %%
if sweep_table is not None:
    length = sweep_table["finger_length_um"].to_numpy(dtype=float)
    fit_rows = []
    length_model = {
        "status": "diagnostic_not_design_authority",
        "source_run_id": SWEEP_RUN_ID,
        "valid_finger_length_um": [float(length.min()), float(length.max())],
        "fixed_geometry_um": IDC_LAYOUT_CONTROLS,
        "affine_branch_models_fF": {},
    }
    for quantity in ("C1G_fF", "C2G_fF", "C12_fF"):
        measured = sweep_table[quantity].to_numpy(dtype=float)
        slope, intercept = np.polyfit(length, measured, 1)
        predicted = slope * length + intercept
        residual = measured - predicted
        r_squared = 1.0 - np.sum(residual**2) / np.sum((measured - measured.mean()) ** 2)
        record = {
            "slope_fF_per_um": float(slope),
            "intercept_fF": float(intercept),
            "r_squared": float(r_squared),
            "max_abs_residual_fF": float(np.max(np.abs(residual))),
        }
        length_model["affine_branch_models_fF"][quantity.removesuffix("_fF")] = record
        fit_rows.append({"quantity": quantity, **record})

    LENGTH_MODEL_PATH.write_text(
        json.dumps(length_model, indent=2) + "\n",
        encoding="utf-8",
    )
    display(pd.DataFrame(fit_rows))
    print(f"Diagnostic length model: {LENGTH_MODEL_PATH}")

# %% [markdown]
# ### Simulation Performance / Benchmarks

# %%
if sweep_table is not None:
    display(sweep_table[["finger_length_um", "solve_time_s", "status"]])

# %% [markdown]
# ## Save and Release AEDT
#
# Each point saves and releases its Q3D project inside the explicit sweep loop.
