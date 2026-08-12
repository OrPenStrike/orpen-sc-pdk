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
# # CPW finite-ground HFSS convergence diagnostic

# %% [markdown]
# ## Setup and Imports

# %%
from __future__ import annotations

import json
from importlib.metadata import version as distribution_version
from pathlib import Path
from time import perf_counter, sleep

import gdsfactory as gf
import pandas as pd
import plotly.express as px
from ansys.aedt.core import Hfss
from IPython.display import HTML, clear_output, display
from skrf import Network
from skrf.io.touchstone import hfss_touchstone_2_gamma_z0

import orpen_sc_pdk
from orpen_sc_pdk.simulation.aedt import aedt_material_name_from_physical_key
from orpen_sc_pdk.tech import OUTER_VACUUM_THICKNESS_UM, SUBSTRATE_THICKNESS_UM

REPO_ROOT = Path(orpen_sc_pdk.__file__).resolve().parent.parent
if not (REPO_ROOT / "orpen_sc_pdk").is_dir():
    raise RuntimeError("Active orpen_sc_pdk checkout is invalid for notebook replay.")
orpen_sc_pdk.activate()

# %% [markdown]
# ## Setup and Run Controls

# %%
SIGNAL_WIDTH_UM = 10.0
GAP_UM = 6.0
TRACE_LENGTH_UM = 500.0
GROUND_WIDTH_OPTIONS = (10.0, 20.0, 40.0, 80.0, 160.0)
GROUND_WIDTH_UM = 10.0
if GROUND_WIDTH_UM not in GROUND_WIDTH_OPTIONS:
    raise ValueError(f"Unsupported ground width {GROUND_WIDTH_UM!r}")

FREQUENCY_START_GHZ = 3.0
FREQUENCY_STOP_GHZ = 8.0
FREQUENCY_POINT_COUNT = 20_000
SWEEP_TYPE = "Fast"
SWEEP_NAME = "S"

AEDT_VERSION = "2024.2"
PYAEDT_REQUIREMENT = "pyaedt[all]==1.3.0"
PYAEDT_VERSION = distribution_version("pyaedt")
PYAEDT_API_SOURCE = "https://github.com/ansys/pyaedt/tree/v1.3.0"

MAX_ADAPTIVE_PASSES = 99
MINIMUM_CONVERGED_PASSES = 2
MAX_DELTA_S = 0.02

SOLVER_SETUP_NAME = "Setup1"
SOLVER_SETUP_TYPE = "DrivenTerminal"
SOLUTION_TYPE = "Terminal"
NON_GRAPHICAL = True
CLOSE_DESKTOP = False

RUN_PREPARE = False
RUN_SOLVER = False
RUN_AEDT = RUN_PREPARE or RUN_SOLVER

RUN_ROOT = (
    REPO_ROOT / "build" / "simulation" / "aedt" / "cpw_finite_ground_hfss_convergence" / "w10_s6"
)
RUN_ROOT.mkdir(parents=True, exist_ok=True)

RUN_TAG = f"cpw_w10_s6_gw{GROUND_WIDTH_UM:g}um"
CASE_DIR = RUN_ROOT / RUN_TAG
CASE_DIR.mkdir(parents=True, exist_ok=True)
PROJECT_PATH = CASE_DIR / f"{RUN_TAG}.aedt"
DESIGN_NAME = RUN_TAG
GDS_PATH = CASE_DIR / f"{RUN_TAG}.gds"
METADATA_PATH = CASE_DIR / "diagnostic_metadata.json"
TIMING_PATH = CASE_DIR / "solve_timing.json"
RAW_TOUCHSTONE_PATH = CASE_DIR / "cpw_finite_ground.s2p"
DERIVED_CSV_PATH = CASE_DIR / "derived_diagnostics.csv"
COMBINED_CSV_PATH = RUN_ROOT / "combined_diagnostics.csv"

ACF_PATH = REPO_ROOT / "notebooks" / "AEDTSimulation" / "HFSS_Local.acf"

HFSS_SIGNAL_LAYER = (905, 0)
HFSS_GROUND_LAYER = (907, 0)
HFSS_SUBSTRATE_LAYER = (908, 0)
REGION_PAD = OUTER_VACUUM_THICKNESS_UM
SUBSTRATE_MATERIAL = "Si"
CANONICAL_PHYSICAL_PORTS = ("o1", "o2")

# %% [markdown]
# ## Create Simulation Component / Coupon


# %%
def _build_cpw_component(ground_width_um: float):
    component = gf.Component()

    signal = gf.components.rectangle(
        size=(TRACE_LENGTH_UM, SIGNAL_WIDTH_UM),
        centered=True,
        layer=HFSS_SIGNAL_LAYER,
    )
    top_ground = gf.components.rectangle(
        size=(TRACE_LENGTH_UM, ground_width_um),
        centered=True,
        layer=HFSS_GROUND_LAYER,
    )
    bottom_ground = gf.components.rectangle(
        size=(TRACE_LENGTH_UM, ground_width_um),
        centered=True,
        layer=HFSS_GROUND_LAYER,
    )
    # The substrate footprint follows the complete finite CPW cross-section:
    # ground - gap - signal - gap - ground.
    substrate = gf.components.rectangle(
        size=(TRACE_LENGTH_UM, SIGNAL_WIDTH_UM + 2 * (GAP_UM + ground_width_um)),
        centered=True,
        layer=HFSS_SUBSTRATE_LAYER,
    )

    signal_ref = component.add_ref(signal)
    top_ref = component.add_ref(top_ground)
    bottom_ref = component.add_ref(bottom_ground)
    sub_ref = component.add_ref(substrate)

    y_offset = SIGNAL_WIDTH_UM / 2 + GAP_UM + ground_width_um / 2
    top_ref.movey(+y_offset)
    bottom_ref.movey(-y_offset)

    return component, {
        "signal": signal_ref,
        "finite_ground_1": top_ref,
        "finite_ground_2": bottom_ref,
        "substrate": sub_ref,
    }


component, references = _build_cpw_component(GROUND_WIDTH_UM)

# Geometry proof and local interval checks.
probe_rows = []
for name, ref in references.items():
    box = ref.dbbox()
    probe_rows.append(
        {
            "name": name,
            "width_um": float(box.right - box.left),
            "height_um": float(box.top - box.bottom),
            "left_um": float(box.left),
            "right_um": float(box.right),
            "bottom_um": float(box.bottom),
            "top_um": float(box.top),
        }
    )
probe_df = pd.DataFrame(probe_rows)

expected_signal_w = probe_df.loc[probe_df.name == "signal", "width_um"].iloc[0]
expected_signal_h = probe_df.loc[probe_df.name == "signal", "height_um"].iloc[0]
expected_top = probe_df.loc[probe_df.name == "finite_ground_1", "height_um"].iloc[0]
expected_bottom = probe_df.loc[probe_df.name == "finite_ground_2", "height_um"].iloc[0]
expected_sub = probe_df.loc[probe_df.name == "substrate", "height_um"].iloc[0]
expected_sub_h = SIGNAL_WIDTH_UM + 2 * (GAP_UM + GROUND_WIDTH_UM)

if abs(expected_signal_w - TRACE_LENGTH_UM) > 1e-6:
    raise RuntimeError("Signal width mismatch")
if abs(expected_signal_h - SIGNAL_WIDTH_UM) > 1e-6:
    raise RuntimeError("Signal height mismatch")
if abs(expected_top - GROUND_WIDTH_UM) > 1e-6 or abs(expected_bottom - GROUND_WIDTH_UM) > 1e-6:
    raise RuntimeError("Ground widths mismatch")
if abs(expected_sub - expected_sub_h) > 1e-6:
    raise RuntimeError("Substrate height mismatch")
top_expected = expected_signal_h / 2 + GAP_UM
if abs(probe_df.loc[probe_df.name == "finite_ground_1", "bottom_um"].iloc[0] - top_expected) > 1e-6:
    raise RuntimeError("Top gap mismatch")
bottom_expected = -top_expected
if abs(probe_df.loc[probe_df.name == "finite_ground_2", "top_um"].iloc[0] - bottom_expected) > 1e-6:
    raise RuntimeError("Bottom gap mismatch")
if abs(probe_df.loc[probe_df.name == "signal", "left_um"].iloc[0] + TRACE_LENGTH_UM / 2) > 1e-6:
    raise RuntimeError("Signal left edge mismatch")
if abs(probe_df.loc[probe_df.name == "signal", "right_um"].iloc[0] - TRACE_LENGTH_UM / 2) > 1e-6:
    raise RuntimeError("Signal right edge mismatch")

CASE_DIR.mkdir(parents=True, exist_ok=True)
component.write_gds(GDS_PATH, with_metadata=False)

display(probe_df)
display(component.plot())

# %% [markdown]
# ## Initialize AEDT Project / App

# %%
if not RUN_AEDT:
    hfss = None
    print("AEDT is not started. Set RUN_PREPARE or RUN_SOLVER to initialize HFSS app.")
else:
    # Prepare builds geometry/materials/ports/setup from scratch. Solve-only
    # reuses that prepared model; the solve cell rebuilds its adaptive mesh.
    if RUN_SOLVER and not RUN_PREPARE and not PROJECT_PATH.exists():
        raise RuntimeError(
            f"RUN_SOLVER=True without RUN_PREPARE requires existing project {PROJECT_PATH!s}"
        )
    hfss = Hfss(
        project=str(PROJECT_PATH),
        design=DESIGN_NAME,
        solution_type=SOLUTION_TYPE,
        version=AEDT_VERSION,
        non_graphical=NON_GRAPHICAL,
        new_desktop=True,
        close_on_exit=False,
    )
    if hfss.desktop_class.aedt_version_id != AEDT_VERSION:
        raise RuntimeError(
            f"AEDT version mismatch: requested {AEDT_VERSION!r}, "
            f"connected {hfss.desktop_class.aedt_version_id!r}."
        )
    hfss.modeler.model_units = "um"

# %% [markdown]
# ## Import GDS and Build the HFSS/Q3D/Q2D Model

# %%
if RUN_PREPARE:
    if not hfss.import_gds_3d(
        str(GDS_PATH),
        {
            HFSS_SIGNAL_LAYER[0]: (0.0, 0.0),
            HFSS_GROUND_LAYER[0]: (0.0, 0.0),
            HFSS_SUBSTRATE_LAYER[0]: (-SUBSTRATE_THICKNESS_UM, SUBSTRATE_THICKNESS_UM),
        },
        units="um",
        import_method=1,
    ):
        raise RuntimeError("GDS import failed")

    hfss.modeler.refresh_all_ids()
    object_names = hfss.modeler.object_names

    signal_candidates = [n for n in object_names if n.startswith(f"signal{HFSS_SIGNAL_LAYER[0]}_")]
    ground_candidates = [n for n in object_names if n.startswith(f"signal{HFSS_GROUND_LAYER[0]}_")]
    substrate_candidates = [
        n for n in object_names if n.startswith(f"signal{HFSS_SUBSTRATE_LAYER[0]}_")
    ]

    if len(signal_candidates) != 1:
        raise RuntimeError(f"Expected one signal object, got {signal_candidates!r}")
    if len(ground_candidates) != 2:
        raise RuntimeError(f"Expected two ground objects, got {ground_candidates!r}")
    if len(substrate_candidates) != 1:
        raise RuntimeError(f"Expected one substrate object, got {substrate_candidates!r}")

    hfss.modeler.get_object_from_name(signal_candidates[0]).name = "signal"
    for order, old_name in enumerate(sorted(ground_candidates), start=1):
        hfss.modeler.get_object_from_name(old_name).name = f"finite_ground_{order}"
    hfss.modeler.get_object_from_name(substrate_candidates[0]).name = "substrate"

# %% [markdown]
# ## Geometry Verification

# %%
if RUN_AEDT:
    names = hfss.modeler.object_names
    if names.count("signal") != 1:
        raise RuntimeError(f"signal object count mismatch: {names}")
    if names.count("finite_ground_1") != 1 or names.count("finite_ground_2") != 1:
        raise RuntimeError(f"ground object count mismatch: {names}")
    if names.count("substrate") != 1:
        raise RuntimeError(f"substrate object count mismatch: {names}")

# %% [markdown]
# ## Materials and Boundaries

# %%
if RUN_PREPARE:
    hfss.modeler.create_region(
        pad_value=[0.0, 0.0, 0.0, 0.0, REGION_PAD, REGION_PAD],
        pad_type="Absolute Offset",
        name="Region",
    ).material_name = "vacuum"

    hfss.assign_perfect_e(
        ["signal", "finite_ground_1", "finite_ground_2"],
        name="PerfectE",
    )
    hfss.modeler.get_object_from_name(
        "substrate"
    ).material_name = aedt_material_name_from_physical_key(SUBSTRATE_MATERIAL)

# %% [markdown]
# ## Ports / Nets / Excitations

# %%
# Port face is the external Region face. Any XY padding changes the face aperture,
# so XY padding stays zero and both ports share the same cross-section as the coupon.
terminal_records = []
if RUN_PREPARE:
    region = hfss.modeler.get_object_from_name("Region")
    face_candidates = []
    for face in region.faces:
        c = face.center
        if abs(float(c[1])) > 1e-6:
            continue
        face_candidates.append((float(c[0]), float(c[2]), int(face.id)))

    if len(face_candidates) < 2:
        raise RuntimeError("Could not locate ±X faces on Region")

    xn_face = min((item for item in face_candidates if item[0] < 0), key=lambda item: item[0])
    xp_face = max((item for item in face_candidates if item[0] > 0), key=lambda item: item[0])

    setup_faces = {
        "o1": xn_face[2],
        "o2": xp_face[2],
    }

    for physical_port, face_id in setup_faces.items():
        before = set(hfss.oboundary.GetExcitationsOfType("Terminal"))
        boundary = hfss.wave_port(
            face_id,
            reference=["finite_ground_1", "finite_ground_2"],
            name=physical_port,
            modes=1,
            characteristic_impedance="Zpi",
            renormalize=False,
            deembed=0.0,
            terminals_rename=False,
        )
        if not boundary:
            raise RuntimeError(f"wave_port failed for {physical_port}")

        after = set(hfss.oboundary.GetExcitationsOfType("Terminal"))
        new_terms = sorted(after - before)
        if len(new_terms) != 1:
            raise RuntimeError(f"Expected one terminal for {physical_port}, got {new_terms!r}")

        terminal_records.append(
            {
                "physical_port": physical_port,
                "boundary_name": boundary.name,
                "terminal_name": new_terms[0],
                "face_id": face_id,
            }
        )

    if len(terminal_records) != len(CANONICAL_PHYSICAL_PORTS):
        raise RuntimeError("Terminal count mismatch")
elif RUN_SOLVER and not RUN_PREPARE:
    # Reuse existing terminals on prepared project; keep explicit fail-fast semantics.
    terminal_names = sorted(hfss.oboundary.GetExcitationsOfType("Terminal"))
    if len(terminal_names) != len(CANONICAL_PHYSICAL_PORTS):
        raise RuntimeError(
            f"Solve-only run expects {len(CANONICAL_PHYSICAL_PORTS)} existing terminals, "
            f"got {terminal_names!r}"
        )
    terminal_records = [
        {
            "physical_port": "o1",
            "boundary_name": "o1",
            "terminal_name": terminal_names[0],
            "face_id": None,
        },
        {
            "physical_port": "o2",
            "boundary_name": "o2",
            "terminal_name": terminal_names[1],
            "face_id": None,
        },
    ]

# %% [markdown]
# ## Simulation Setup

# %%
setup = None
if RUN_PREPARE:
    if SOLVER_SETUP_NAME in hfss.setup_names:
        setup = hfss.get_setup(SOLVER_SETUP_NAME)
    else:
        setup = hfss.create_setup(SOLVER_SETUP_NAME)

    if setup.props.get("SolveType") != SOLVER_SETUP_TYPE:
        setup.props["SolveType"] = SOLVER_SETUP_TYPE

    if not setup.enable_adaptive_setup_broadband(
        f"{FREQUENCY_START_GHZ}GHz",
        f"{FREQUENCY_STOP_GHZ}GHz",
        max_passes=MAX_ADAPTIVE_PASSES,
        max_delta_s=MAX_DELTA_S,
    ):
        raise RuntimeError("Adaptive setup failed")

    setup.props["MinimumConvergedPasses"] = MINIMUM_CONVERGED_PASSES
    if not setup.update():
        raise RuntimeError("Setup update failed")

elif RUN_SOLVER and not RUN_PREPARE:
    if SOLVER_SETUP_NAME not in hfss.setup_names:
        raise RuntimeError("Solve-only run expects existing setup; run with RUN_PREPARE=True first")
    setup = hfss.get_setup(SOLVER_SETUP_NAME)

if RUN_AEDT:
    sweep = setup.get_sweep(SWEEP_NAME)
    if sweep:
        sweep.props.update(
            {
                "RangeType": "LinearCount",
                "RangeStart": f"{FREQUENCY_START_GHZ}GHz",
                "RangeEnd": f"{FREQUENCY_STOP_GHZ}GHz",
                "RangeCount": FREQUENCY_POINT_COUNT,
                "Type": SWEEP_TYPE,
                "SaveFields": False,
                "SaveRadFields": False,
            }
        )
        sweep.update()
    else:
        sweep = hfss.create_linear_count_sweep(
            SOLVER_SETUP_NAME,
            "GHz",
            FREQUENCY_START_GHZ,
            FREQUENCY_STOP_GHZ,
            num_of_freq_points=FREQUENCY_POINT_COUNT,
            name=SWEEP_NAME,
            save_fields=False,
            sweep_type=SWEEP_TYPE,
        )
        if not sweep:
            raise RuntimeError("Could not create sweep")

    sweep_readback = {
        "type": str(sweep.props["Type"]),
        "start": str(sweep.props["RangeStart"]),
        "stop": str(sweep.props["RangeEnd"]),
        "point_count": int(sweep.props["RangeCount"]),
    }
    display(pd.DataFrame([sweep_readback]))
    if sweep_readback != {
        "type": SWEEP_TYPE,
        "start": f"{FREQUENCY_START_GHZ}GHz",
        "stop": f"{FREQUENCY_STOP_GHZ}GHz",
        "point_count": FREQUENCY_POINT_COUNT,
    }:
        raise RuntimeError(f"HFSS sweep readback mismatch: {sweep_readback}")

# %% [markdown]
# ## Simulation Configuration

# %%
if ACF_PATH.exists():
    print(f"ACF_PATH={ACF_PATH}")
    for line in ACF_PATH.read_text(encoding="utf-8").splitlines():
        if "NumCores" in line or "NumJobCores" in line:
            print(line)
            break
else:
    print("HFSS_Local.acf not found; check environment")

# %% [markdown]
# ## Solve and Export

# %%
if RUN_AEDT:
    hfss.save_project()

    if RUN_SOLVER:
        # Each width is a different geometry: discard the old adaptive mesh and
        # let HFSS refine a new mesh from its default initial mesh.
        hfss.oanalysis.RevertSetupToInitial(SOLVER_SETUP_NAME)
        start_time = perf_counter()
        solve_started = hfss.analyze_setup(
            name=None,
            acf_file=str(ACF_PATH),
            blocking=False,
        )
        if not solve_started:
            raise RuntimeError("HFSS analyze_setup failed")

        # AEDT 2024.2 can briefly report idle while handing the Fast sweep to a
        # background DSO worker. Require three consecutive idle polls only after
        # the solve has been observed running, while keeping progress visible.
        seen_running = False
        idle_polls = 0
        completed_passes = 0
        while not seen_running or idle_polls < 3:
            sleep(5)
            running = bool(hfss.desktop_class.are_there_simulations_running)
            seen_running = seen_running or running
            idle_polls = 0 if running else idle_polls + 1
            profile = hfss.get_setup(SOLVER_SETUP_NAME).get_profile()
            completed_passes = max(
                (entry.num_adaptive_passes for entry in profile.values()),
                default=completed_passes,
            )
            clear_output(wait=True)
            display(
                HTML(
                    f"HFSS {'running' if running else 'finishing'} {RUN_TAG} "
                    f"· adaptive passes: {completed_passes} "
                    f"· elapsed: {perf_counter() - start_time:.1f} s"
                )
            )
        elapsed = perf_counter() - start_time

        hfss.export_touchstone(
            setup=SOLVER_SETUP_NAME,
            sweep=SWEEP_NAME,
            output_file=str(RAW_TOUCHSTONE_PATH),
            renormalization=False,
            gamma_impedance_comments=True,
        )
        if not RAW_TOUCHSTONE_PATH.exists():
            raise RuntimeError("Touchstone export missing")

        TIMING_PATH.write_text(
            json.dumps(
                {
                    "run_tag": RUN_TAG,
                    "analyze_setup_seconds": elapsed,
                    "completed_adaptive_passes": completed_passes,
                    "ground_width_um": GROUND_WIDTH_UM,
                    "frequency_start_ghz": FREQUENCY_START_GHZ,
                    "frequency_stop_ghz": FREQUENCY_STOP_GHZ,
                    "frequency_point_count": FREQUENCY_POINT_COUNT,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        _, gamma, z0 = hfss_touchstone_2_gamma_z0(str(RAW_TOUCHSTONE_PATH))
        gamma = gamma.copy()
        z0 = z0.copy()

        network = Network(str(RAW_TOUCHSTONE_PATH))
        if not network.port_names:
            raise RuntimeError("Touchstone has no readable port names")

        desired_terminals = [
            entry["terminal_name"]
            for entry in sorted(terminal_records, key=lambda x: x["physical_port"])
        ]
        actual = list(network.port_names)
        if sorted(actual) != sorted(desired_terminals):
            raise RuntimeError(f"Port-name mismatch {actual!r} vs {desired_terminals!r}")

        permutation = [actual.index(name) for name in desired_terminals]
        if permutation != [0, 1]:
            network.s = network.s[:, permutation, :][:, :, permutation]
            network.z0 = network.z0[:, permutation]
            gamma = gamma[:, permutation]
            z0 = z0[:, permutation]
            network.port_names = desired_terminals
            terminal_order = "normalized"
        else:
            terminal_order = "original"

        df = pd.DataFrame(
            {
                "ground_width_um": [GROUND_WIDTH_UM] * len(network.f),
                "frequency_ghz": network.f / 1e9,
                "S11_abs": [abs(s) for s in network.s[:, 0, 0]],
                "S21_abs": [abs(s) for s in network.s[:, 1, 0]],
                "Re(Z0_o1)": [complex(v).real for v in z0[:, 0]],
                "Im(Z0_o1)": [complex(v).imag for v in z0[:, 0]],
                "Re(gamma_o1)": [complex(v).real for v in gamma[:, 0]],
                "Im(gamma_o1)": [complex(v).imag for v in gamma[:, 0]],
                "beta_o1": [complex(v).imag for v in gamma[:, 0]],
                "Re(Z0_o2)": [complex(v).real for v in z0[:, 1]],
                "Im(Z0_o2)": [complex(v).imag for v in z0[:, 1]],
                "Re(gamma_o2)": [complex(v).real for v in gamma[:, 1]],
                "Im(gamma_o2)": [complex(v).imag for v in gamma[:, 1]],
                "beta_o2": [complex(v).imag for v in gamma[:, 1]],
            }
        )
        DERIVED_CSV_PATH.write_text(df.to_csv(index=False), encoding="utf-8")

        metadata = {
            "kind": "cpw_finite_ground_hfss_convergence",
            "authority": "diagnostic_current_terminal_port_definition",
            "software": {
                "pyaedt_requirement": PYAEDT_REQUIREMENT,
                "pyaedt_version": PYAEDT_VERSION,
                "pyaedt_api_source": PYAEDT_API_SOURCE,
                "requested_aedt_version": AEDT_VERSION,
                "connected_aedt_version": hfss.desktop_class.aedt_version_id,
            },
            "run_tag": RUN_TAG,
            "ground_width_um": GROUND_WIDTH_UM,
            "trace_width_um": SIGNAL_WIDTH_UM,
            "gap_um": GAP_UM,
            "trace_length_um": TRACE_LENGTH_UM,
            "region_padding_um": [0.0, 0.0, 0.0, 0.0, REGION_PAD, REGION_PAD],
            "wave_ports": terminal_records,
            "terminal_order": terminal_order,
            "sweep": {
                "start_ghz": FREQUENCY_START_GHZ,
                "stop_ghz": FREQUENCY_STOP_GHZ,
                "point_count": FREQUENCY_POINT_COUNT,
                "sweep_type": SWEEP_TYPE,
            },
            "setup": {
                "type": SOLVER_SETUP_TYPE,
                "max_adaptive_passes": MAX_ADAPTIVE_PASSES,
                "min_converged_passes": MINIMUM_CONVERGED_PASSES,
                "max_delta_s": MAX_DELTA_S,
            },
        }
        METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        hfss.save_project()

# %% [markdown]
# ## Adaptive-Pass Convergence / Solver Diagnostics

# %%
if TIMING_PATH.exists():
    print(TIMING_PATH.read_text(encoding="utf-8"))
else:
    print("No timing data yet; run with RUN_SOLVER=True.")

# %% [markdown]
# ## Results: Plots and Readable Tables

# %% [markdown]
# ### Physics Analysis Results
#
# > **Diagnostic scope.** These traces use the current one-terminal Driven
# > Terminal port with both disconnected side grounds listed as references.
# > Until the CPW common-mode port definition is selected and rerun, use the
# > table below to diagnose port consistency; do not use it to select a ground
# > width.

# %%
result_frames = []
for width in GROUND_WIDTH_OPTIONS:
    run_tag = f"cpw_w10_s6_gw{width:g}um"
    csv_path = RUN_ROOT / run_tag / "derived_diagnostics.csv"
    if csv_path.exists():
        frame = pd.read_csv(csv_path)
        frame["ground_width_um"] = width
        result_frames.append(frame)

if result_frames:
    result_df = pd.concat(result_frames, ignore_index=True)
    result_df = result_df.sort_values(["ground_width_um", "frequency_ghz"]).reset_index(drop=True)
    result_df["S11_delta_from_prev_width"] = result_df.groupby("frequency_ghz")["S11_abs"].diff()
    result_df["S21_delta_from_prev_width"] = result_df.groupby("frequency_ghz")["S21_abs"].diff()
    result_df["Re(Z0)_mean"] = (result_df["Re(Z0_o1)"] + result_df["Re(Z0_o2)"]) / 2
    result_df["Re(Z0)_port_difference"] = (result_df["Re(Z0_o1)"] - result_df["Re(Z0_o2)"]).abs()
    result_df["Re(Z0)_delta_from_prev_width"] = result_df.groupby("frequency_ghz")[
        "Re(Z0)_mean"
    ].diff()

    s_parameters = result_df.melt(
        id_vars=["frequency_ghz", "ground_width_um"],
        value_vars=["S11_abs", "S21_abs"],
        var_name="metric",
        value_name="value",
    )
    display(
        px.line(
            s_parameters,
            x="frequency_ghz",
            y="value",
            color="ground_width_um",
            facet_row="metric",
            title="Finite-ground CPW W10/S6 scattering",
        ).update_layout(height=650)
    )

    port_impedance = result_df.melt(
        id_vars=["frequency_ghz", "ground_width_um"],
        value_vars=["Re(Z0_o1)", "Re(Z0_o2)"],
        var_name="port",
        value_name="impedance_ohm",
    )
    display(
        px.line(
            port_impedance,
            x="frequency_ghz",
            y="impedance_ohm",
            color="ground_width_um",
            line_dash="port",
            title="Finite-ground CPW W10/S6 port impedance",
        )
    )

    band_summary = result_df.groupby("ground_width_um", as_index=False).agg(
        S11_abs_max=("S11_abs", "max"),
        S21_abs_min=("S21_abs", "min"),
        Re_Z0_mean_ohm=("Re(Z0)_mean", "mean"),
        Re_Z0_port_difference_max_ohm=("Re(Z0)_port_difference", "max"),
        S11_change_from_previous_width_max=(
            "S11_delta_from_prev_width",
            lambda values: values.abs().max(),
        ),
        S21_change_from_previous_width_max=(
            "S21_delta_from_prev_width",
            lambda values: values.abs().max(),
        ),
        Re_Z0_change_from_previous_width_max_ohm=(
            "Re(Z0)_delta_from_prev_width",
            lambda values: values.abs().max(),
        ),
    )
    display(band_summary)

    COMBINED_CSV_PATH.write_text(result_df.to_csv(index=False), encoding="utf-8")
else:
    print("No solved cases found yet; run with RUN_SOLVER=True.")

# %% [markdown]
# ### Simulation Performance / Benchmarks

# %%
timing_frames = []
for width in GROUND_WIDTH_OPTIONS:
    run_tag = f"cpw_w10_s6_gw{width:g}um"
    timing_path = RUN_ROOT / run_tag / "solve_timing.json"
    if timing_path.exists():
        with timing_path.open(encoding="utf-8") as handle:
            timing_frames.append(json.loads(handle.read()))

if timing_frames:
    timing_df = pd.DataFrame(timing_frames)
    display(timing_df)
else:
    print("No timing data found yet; run with RUN_SOLVER=True.")

# %% [markdown]
# ## Save and Release AEDT

# %%
if RUN_AEDT:
    hfss.save_project()
    if CLOSE_DESKTOP:
        hfss.release_desktop(close_projects=True, close_desktop=True)
