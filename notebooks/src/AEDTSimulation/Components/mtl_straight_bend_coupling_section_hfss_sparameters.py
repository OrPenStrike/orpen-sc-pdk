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
# # MTL straight-bend coupling-section HFSS S-parameters
#
# This is a single-point terminal-mode HFSS coupon for review. `lc` and `d`
# are geometry/model controls; the only solver sweep here is frequency. The
# superconducting metal is represented by zero-thickness PEC sheets. Only the
# silicon substrate and enclosing vacuum Region are 3D volumes.

# %% [markdown]
# ## Design And Geometry Controls

# %%
from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter

import gdsfactory as gf
import pandas as pd
import plotly.graph_objects as go
from ansys.aedt.core import Hfss
from IPython.display import display

import orpen_sc_pdk
from orpen_sc_pdk.simulation.aedt import aedt_material_name_from_physical_key
from orpen_sc_pdk.tech import OUTER_VACUUM_THICKNESS_UM

REPO_ROOT = Path(orpen_sc_pdk.__file__).resolve().parent.parent
if not (REPO_ROOT / "orpen_sc_pdk").is_dir():
    raise RuntimeError("The active orpen_sc_pdk package is not a source checkout.")
orpen_sc_pdk.activate()

LC_UM = 500.0
D_UM = 3.0
TERMINAL_OPEN_CLEARANCE_UM = None  # None uses the selected CPW cross-section gap.
SUBSTRATE_KEY = "Si"
REGION_PADDING_UM = OUTER_VACUUM_THICKNESS_UM

# %% [markdown]
# ## Sweep Parameter Controls
#
# `lc` and `d` select this one coupon geometry. They are intentionally not a
# geometry sweep in this candidate; inspect this single point before requesting
# a parameter-space run. `S` is the 3--8 GHz interpolating frequency sweep.

# %%
FREQUENCY_START_GHZ = 3.0
FREQUENCY_STOP_GHZ = 8.0
FREQUENCY_POINT_COUNT = 201
SWEEP_NAME = "S"
INTERPOLATION_TOLERANCE_PERCENT = 0.5
INTERPOLATION_MAX_SOLUTIONS = 250

# %% [markdown]
# ## Meshing Controls
#
# These are the default controls for future HFSS Setups and can be overridden
# in this notebook before preparing or solving the coupon.

# %%
MAX_ADAPTIVE_PASSES = 99
MINIMUM_CONVERGED_PASSES = 2
MAX_DELTA_S = 0.02

# %% [markdown]
# ## Solver Controls

# %%
HFSS_SETUP_NAME = "Setup1"
SOLUTION_TYPE = "Terminal"
PORT_IMPEDANCE_OHM = 50.0
NON_GRAPHICAL = True
CLOSE_DESKTOP = True

# %% [markdown]
# ## Execution Controls
#
# Both controls remain false in source so opening, static checking, or
# documentation builds cannot launch AEDT. `PREPARE_AEDT_SETUP` builds and
# saves the reviewable project without solving; `RUN_SOLVER` also analyzes it.

# %%
PREPARE_AEDT_SETUP = False
RUN_SOLVER = False
RUN_AEDT = PREPARE_AEDT_SETUP or RUN_SOLVER

# %% [markdown]
# ## Run And Sweep Identity Controls

# %% [markdown]
# ### Output / Run Identity

# %%
RUN_ID = "2026-08-12-mtl-straight-bend-coupling-section-hfss-closed-v1"
RUN_DIR = REPO_ROOT / "build" / "simulation" / "aedt" / "mtl_straight_bend_coupling" / RUN_ID
GDS_PATH = RUN_DIR / "mtl_straight_bend_coupling_section.gds"
PROJECT_PATH = RUN_DIR / "mtl_straight_bend_coupling_section.aedt"
TOUCHSTONE_PATH = RUN_DIR / "mtl_straight_bend_coupling_section.s4p"
S_PARAMETER_PLOT_PATH = RUN_DIR / "sparameters.html"
TIMING_PATH = RUN_DIR / "solve_timing.json"
ACF_PATH = REPO_ROOT / "notebooks" / "AEDTSimulation" / "HFSS_Local.acf"

# %% [markdown]
# ## Validation And Failure Controls
#
# The registered coupon owns the GDS layer and four-terminal metadata. Do not
# replace a missing factory with notebook-local geometry: that would make this
# run differ from the PDK component it is meant to review.

# %%
EXPECTED_COUPON_SCHEMA = "orpen-mtl-straight-bend-coupling-section-hfss-coupon.v1"
EXPECTED_PORT_COUNT = 4
EXPECTED_LAYER_NAMES = {"signal_p", "signal_r", "finite_ground", "substrate", "port_sheets"}

# %% [markdown]
# ## Data Classification And Provenance
#
# Inputs are public PDK geometry and local AEDT configuration. Any emitted GDS,
# AEDT project, Touchstone, plot, or timing is diagnostic, not promotable
# evidence, until a reviewed run receipt binds it to this source revision.

# %%
DATA_CLASSIFICATION = "public"
ALLOWED_CONSUMERS = "orpen_sc_pdk developers and reviewers"
EVIDENCE_STATUS = "diagnostic"

# %% [markdown]
# ## Review Coupon Before AEDT

# %%
coupon = gf.get_component(
    "mtl_straight_bend_coupling_section_hfss_coupon",
    coupled_length=LC_UM,
    inter_trace_ground_width=D_UM,
    terminal_open_clearance_um=TERMINAL_OPEN_CLEARANCE_UM,
)
coupon.plot()
display(
    pd.DataFrame(
        [
            {
                "port": port.name,
                "center_um": tuple(float(value) for value in port.center),
                "orientation_deg": port.orientation,
                "width_um": port.width,
            }
            for port in coupon.ports
        ]
    )
)
display(
    pd.DataFrame(
        [
            {
                "setup": HFSS_SETUP_NAME,
                "solution_type": SOLUTION_TYPE,
                "frequency_range_GHz": f"{FREQUENCY_START_GHZ}–{FREQUENCY_STOP_GHZ}",
                "output_points": FREQUENCY_POINT_COUNT,
                "max_adaptive_passes": MAX_ADAPTIVE_PASSES,
                "minimum_converged_passes": MINIMUM_CONVERGED_PASSES,
                "max_delta_S": MAX_DELTA_S,
                "terminal_open_clearance_um": coupon.info["hfss_coupon"][
                    "terminal_open_clearance_um"
                ],
                "sweep_type": "Interpolating",
            }
        ]
    )
)

# %% [markdown]
# ## Initialize HFSS App

# %%
if RUN_AEDT:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    project_exists = PROJECT_PATH.exists()
    hfss = Hfss(
        project=str(PROJECT_PATH),
        design="mtl_straight_bend_coupling_terminal",
        solution_type=SOLUTION_TYPE,
        non_graphical=NON_GRAPHICAL,
        new_desktop=True,
        close_on_exit=False,
    )
    hfss.modeler.model_units = "um"
    hfss.modeler.refresh_all_ids()
    build_model = not hfss.modeler.object_names
    print("Resuming existing project." if project_exists else "Created new project.")
else:
    hfss = None
    build_model = False
    print("AEDT is not started; enable PREPARE_AEDT_SETUP or RUN_SOLVER when ready.")

# %% [markdown]
# ## Import GDS, build vacuum, materials, boundaries, and four terminal ports
#
# The coupon already contains four rectangles on `D0_TOP_SIM_BOUNDARY`. Each
# rectangle fills one terminal ground-mask clearance, so HFSS only imports and
# assigns those sheets; it does not construct substitute port geometry.

# %%
if RUN_AEDT and build_model:
    metadata = coupon.info.get("hfss_coupon")
    if not isinstance(metadata, dict) or metadata.get("schema") != EXPECTED_COUPON_SCHEMA:
        raise RuntimeError(
            "The coupon must provide hfss_coupon metadata with the expected schema; "
            "update the shared coupon factory before running this notebook."
        )
    layer_specs = metadata.get("layers")
    port_specs = metadata.get("terminal_ports")
    if not isinstance(layer_specs, dict) or not isinstance(port_specs, dict):
        raise RuntimeError("hfss_coupon metadata must contain layers and terminal_ports mappings.")
    if set(layer_specs) != EXPECTED_LAYER_NAMES:
        raise RuntimeError(f"HFSS coupon layers must be {sorted(EXPECTED_LAYER_NAMES)!r}.")
    if len(port_specs) != EXPECTED_PORT_COUNT:
        raise RuntimeError(f"Expected {EXPECTED_PORT_COUNT} terminal ports, got {len(port_specs)}.")

    substrate_material = aedt_material_name_from_physical_key(SUBSTRATE_KEY)
    gds_layer_mapping = {
        int(spec["layer"][0]): (spec["zmin"], spec["thickness"]) for spec in layer_specs.values()
    }
    # PEC and port layers are 2D sheets; only the substrate has finite thickness.
    # AEDT 2024.2 HFSS exits while importing GDSFactory's metadata wrapper cell.
    # The run contract already comes from coupon.info, so the EM exchange file is plain GDS.
    coupon.write_gds(GDS_PATH, with_metadata=False)
    if not hfss.import_gds_3d(str(GDS_PATH), gds_layer_mapping, units="um", import_method=1):
        raise RuntimeError(f"Hfss.import_gds_3d failed for {GDS_PATH}")
    hfss.modeler.refresh_all_ids()

    imported_objects: dict[str, str | list[str]] = {}
    for object_name, spec in layer_specs.items():
        layer_number = int(spec["layer"][0])
        matches = [
            name for name in hfss.modeler.object_names if name.startswith(f"signal{layer_number}_")
        ]
        if object_name == "port_sheets":
            if not matches:
                raise RuntimeError("HFSS imported no GDS lumped-port sheets.")
            imported_objects[object_name] = matches
            continue
        if len(matches) != 1:
            raise RuntimeError(
                f"Expected one imported object for {object_name} on GDS layer {layer_number}, "
                f"got {matches!r}."
            )
        imported = hfss.modeler.get_object_from_name(matches[0])
        imported.name = object_name
        if object_name == "substrate":
            imported.material_name = substrate_material
        imported_objects[object_name] = object_name

    region = hfss.modeler.create_region(
        pad_value=[f"{REGION_PADDING_UM}um"] * 6,
        pad_type="Absolute Offset",
        name="Region",
    )
    region.material_name = "vacuum"
    # This coupon intentionally uses HFSS's default closed outer boundary.
    # No Radiation or PML boundary is assigned to the Vacuum Region.
    conductor_names = ["signal_p", "signal_r", "finite_ground"]
    hfss.assign_perfect_e(conductor_names, name="PerfectE")

    port_faces = []
    for sheet_name in imported_objects["port_sheets"]:
        port_faces.extend(
            (sheet_name, face) for face in hfss.modeler.get_object_from_name(sheet_name).faces
        )

    for port_name, spec in port_specs.items():
        if set(spec) != {
            "signal",
            "reference",
            "sheet",
            "sheet_center_um",
            "integration_line_um",
            "center_um",
            "orientation_deg",
        }:
            raise RuntimeError(f"Terminal port {port_name!r} has an invalid metadata contract.")
        if spec["signal"] not in {"signal_p", "signal_r"} or spec["reference"] != "finite_ground":
            raise RuntimeError(f"Terminal port {port_name!r} must bind a signal to finite_ground.")
        if port_name not in coupon.ports:
            raise RuntimeError(f"Coupon does not expose terminal port {port_name!r}.")
        coupon_port = coupon.ports[port_name]
        if tuple(float(value) for value in spec["center_um"]) != tuple(coupon_port.center):
            raise RuntimeError(
                f"Terminal port {port_name!r} center disagrees with coupon metadata."
            )
        if float(spec["orientation_deg"]) != float(coupon_port.orientation):
            raise RuntimeError(
                f"Terminal port {port_name!r} orientation disagrees with coupon metadata."
            )
        reference_name = imported_objects[spec["reference"]]
        expected_center = spec["sheet_center_um"]
        port_sheet_name, port_face = min(
            port_faces,
            key=lambda item: sum(
                (a - b) ** 2 for a, b in zip(item[1].center, expected_center, strict=True)
            ),
        )
        port_faces.remove((port_sheet_name, port_face))
        port_sheet = hfss.modeler.get_object_from_name(port_sheet_name)
        port_sheet.name = f"{port_name}_sheet"
        boundary = hfss.lumped_port(
            port_sheet.name,
            reference=reference_name,
            integration_line=[list(point) for point in spec["integration_line_um"]],
            impedance=PORT_IMPEDANCE_OHM,
            name=port_name,
        )
        if not boundary:
            raise RuntimeError(f"Failed to assign terminal port {port_name!r}.")
    hfss.save_project()

# %% [markdown]
# ## Geometry Validation

# %%
if RUN_AEDT:
    if build_model:
        expected_objects = set(layer_specs)
        if set(imported_objects) != expected_objects:
            raise RuntimeError("Imported-object assignment does not match coupon layer metadata.")
        # PyAEDT 1.3 exposes terminal names through excitation_names.
        if len(hfss.excitation_names) != EXPECTED_PORT_COUNT:
            raise RuntimeError(
                f"Expected {EXPECTED_PORT_COUNT} HFSS excitations, got {hfss.excitation_names!r}."
            )
    else:
        print("Existing project geometry retained; inspect it before solving a resumed project.")

# %% [markdown]
# ## Setup

# %%
if RUN_AEDT:
    setup = (
        hfss.get_setup(HFSS_SETUP_NAME)
        if HFSS_SETUP_NAME in hfss.setup_names
        else hfss.create_setup(HFSS_SETUP_NAME)
    )
    if not setup.enable_adaptive_setup_broadband(
        f"{FREQUENCY_START_GHZ}GHz",
        f"{FREQUENCY_STOP_GHZ}GHz",
        max_passes=MAX_ADAPTIVE_PASSES,
        max_delta_s=MAX_DELTA_S,
    ):
        raise RuntimeError("HFSS broadband adaptive setup configuration failed.")
    # PyAEDT's broadband helper has no minimum-converged-passes argument.
    setup.props["MinimumConvergedPasses"] = MINIMUM_CONVERGED_PASSES
    if not setup.update():
        raise RuntimeError("HFSS minimum-converged-passes update failed.")
    configured_sweeps = {
        sweep_name.rsplit(" : ", 1)[-1] for sweep_name in hfss.get_sweeps(HFSS_SETUP_NAME)
    }
    if SWEEP_NAME not in configured_sweeps:
        sweep = hfss.create_linear_count_sweep(
            HFSS_SETUP_NAME,
            "GHz",
            FREQUENCY_START_GHZ,
            FREQUENCY_STOP_GHZ,
            num_of_freq_points=FREQUENCY_POINT_COUNT,
            name=SWEEP_NAME,
            save_fields=False,
            sweep_type="Interpolating",
            interpolation_tol=INTERPOLATION_TOLERANCE_PERCENT,
            interpolation_max_solutions=INTERPOLATION_MAX_SOLUTIONS,
        )
        if not sweep:
            raise RuntimeError("HFSS interpolating S sweep configuration failed.")
    hfss.save_project()
    print(f"HFSS geometry and setup saved without requiring a solve: {PROJECT_PATH}")

# %% [markdown]
# ## Simulation

# %%
if RUN_SOLVER:
    started = perf_counter()
    solve_completed = hfss.analyze_setup(
        HFSS_SETUP_NAME,
        acf_file=str(ACF_PATH),
        revert_to_initial_mesh=False,
    )
    solve_seconds = perf_counter() - started
    if not solve_completed:
        raise RuntimeError(f"HFSS failed to complete setup {HFSS_SETUP_NAME!r}.")
    TIMING_PATH.write_text(
        json.dumps({"analyze_setup_seconds": solve_seconds}, indent=2) + "\n",
        encoding="utf-8",
    )
    hfss.save_project()

# %% [markdown]
# ## Physics Analysis Results

# %%
if RUN_SOLVER:
    touchstone = hfss.export_touchstone(
        setup=HFSS_SETUP_NAME,
        sweep=SWEEP_NAME,
        output_file=str(TOUCHSTONE_PATH),
    )
    if not touchstone:
        raise RuntimeError(f"HFSS Touchstone export failed for {TOUCHSTONE_PATH}.")
    s_parameter_traces = hfss.get_traces_for_plot(category="S")
    if not s_parameter_traces:
        raise RuntimeError("HFSS returned no terminal S-parameter traces.")
    solution_data = hfss.post.get_solution_data(
        expressions=s_parameter_traces,
        setup_sweep_name=f"{HFSS_SETUP_NAME} : {SWEEP_NAME}",
        primary_sweep_variable="Freq",
    )
    if not solution_data:
        raise RuntimeError("HFSS returned no S-parameter solution data.")
    figure = go.Figure()
    for expression in solution_data.expressions:
        frequencies, values = solution_data.get_expression_data(expression, formula="db20")
        figure.add_scatter(x=frequencies, y=values, mode="lines", name=expression)
    figure.update_layout(
        title="MTL straight-bend coupling section S-parameters",
        template="plotly_white",
        xaxis_title="Frequency (GHz)",
        yaxis_title="S-parameter (dB)",
    )
    figure.write_html(S_PARAMETER_PLOT_PATH, include_plotlyjs=True)
    figure.show()
    print(f"Touchstone: {touchstone}")
else:
    print("No HFSS results: set RUN_SOLVER = True in an authorized AEDT session.")

# %% [markdown]
# ## Simulation Performance / Benchmarks

# %%
if RUN_SOLVER:
    display(pd.DataFrame([json.loads(TIMING_PATH.read_text(encoding="utf-8"))]))

if RUN_AEDT:
    hfss.release_desktop(close_projects=True, close_desktop=CLOSE_DESKTOP)
