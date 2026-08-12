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
# The all-conductor mesh sweep selected 80 um as the current W10/S6 working
# width: the mean modal Port Zo is nearly unchanged by the 160 um extension,
# while the smaller footprint is less likely to overlap nearby structures.
GROUND_WIDTH_UM = 80.0
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

CPW_CONDUCTOR_LENGTH_MESH_UM = SIGNAL_WIDTH_UM
CPW_CONDUCTOR_LENGTH_MESH_MAX_ADDITIONAL_ELEMENTS = 1_000_000
GROUND_SURFACE_MESH_LEVEL = 9  # Fine resolution / large mesh count.
MESH_PROFILE = "all-conductor-length-1m-ground-fine-zpi-zpv-v2"

SOLVER_SETUP_NAME = "Setup1"
SOLVER_SETUP_TYPE = "DrivenTerminal"
MODAL_SOLVER_SETUP_TYPE = "DrivenModal"
SOLUTION_TYPE = "Terminal"
MODAL_SOLUTION_TYPE = "Modal"
NON_GRAPHICAL = True
CLOSE_DESKTOP = False

RUN_PREPARE = False
RUN_SOLVER = False
RUN_AEDT = RUN_PREPARE or RUN_SOLVER

RUN_ROOT = (
    REPO_ROOT / "build" / "simulation" / "aedt" / "cpw_finite_ground_hfss_convergence" / "w10_s6"
)
RUN_ROOT.mkdir(parents=True, exist_ok=True)

RUN_TAG = f"cpw_w10_s6_gw{GROUND_WIDTH_UM:g}um_{MESH_PROFILE}"
CASE_DIR = RUN_ROOT / RUN_TAG
CASE_DIR.mkdir(parents=True, exist_ok=True)
PROJECT_PATH = CASE_DIR / f"{RUN_TAG}.aedt"
TERMINAL_DESIGN_NAME = f"{RUN_TAG}_HFSS_Terminal"
MODAL_DESIGN_NAME = f"{RUN_TAG}_HFSS_Modal_Zpv"
GDS_PATH = CASE_DIR / f"{RUN_TAG}.gds"
METADATA_PATH = CASE_DIR / "diagnostic_metadata.json"
TIMING_PATH = CASE_DIR / "solve_timing.json"
TERMINAL_TOUCHSTONE_PATH = CASE_DIR / "cpw_finite_ground_terminal.s2p"
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
        design=TERMINAL_DESIGN_NAME,
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
modal_port_records = []
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
    region_faces = sorted(
        (
            (float(face.center[0]), int(face.id))
            for face in hfss.modeler.get_object_from_name("Region").faces
            if abs(float(face.center[1])) <= 1e-6 and abs(float(face.center[0])) > 1e-6
        ),
        key=lambda item: item[0],
    )
    if len(region_faces) < 2:
        raise RuntimeError("Solve-only run could not locate the two Region port faces")
    terminal_records = [
        {
            "physical_port": "o1",
            "boundary_name": "o1",
            "terminal_name": terminal_names[0],
            "face_id": region_faces[0][1],
        },
        {
            "physical_port": "o2",
            "boundary_name": "o2",
            "terminal_name": terminal_names[1],
            "face_id": region_faces[-1][1],
        },
    ]
    modal_port_records = [
        {
            "physical_port": physical_port,
            "boundary_name": physical_port,
            "face_id": face_id,
            "integration_line_um": [
                [port_x, SIGNAL_WIDTH_UM / 2, 0.0],
                [port_x, SIGNAL_WIDTH_UM / 2 + GAP_UM, 0.0],
            ],
            "selected_characteristic_impedance": "Zpv",
        }
        for physical_port, port_x, face_id in (
            ("o1", -TRACE_LENGTH_UM / 2, region_faces[0][1]),
            ("o2", TRACE_LENGTH_UM / 2, region_faces[-1][1]),
        )
    ]

# %% [markdown]
# ## Simulation Setup

# %% [markdown]
# ### Mesh Operations
#
# The element ceiling applies to this one operation across the signal and both
# ground sheets. Reaching it stops this refinement; it does not cancel the HFSS
# solve. The separate ground surface approximation remains as an independent
# shape-approximation control.

# %%
cpw_conductor_length_mesh = None
ground_surface_mesh = None
if RUN_PREPARE:
    cpw_conductor_length_mesh = hfss.mesh.assign_length_mesh(
        assignment=["signal", "finite_ground_1", "finite_ground_2"],
        inside_selection=False,
        maximum_length=f"{CPW_CONDUCTOR_LENGTH_MESH_UM:g}um",
        maximum_elements=CPW_CONDUCTOR_LENGTH_MESH_MAX_ADDITIONAL_ELEMENTS,
        name="cpw_conductor_length_mesh",
    )
    ground_surface_mesh = hfss.mesh.assign_surface_mesh(
        assignment=["finite_ground_1", "finite_ground_2"],
        level=GROUND_SURFACE_MESH_LEVEL,
        name="ground_surface_fine_large",
    )
    if not cpw_conductor_length_mesh or not ground_surface_mesh:
        raise RuntimeError("HFSS mesh-operation assignment failed")

    display(
        pd.DataFrame(
            [
                {
                    "operation": cpw_conductor_length_mesh.name,
                    "assignment": "signal, finite_ground_1, finite_ground_2",
                    "setting": (
                        f"maximum length {CPW_CONDUCTOR_LENGTH_MESH_UM:g} um; "
                        f"up to {CPW_CONDUCTOR_LENGTH_MESH_MAX_ADDITIONAL_ELEMENTS:,} "
                        "additional elements"
                    ),
                },
                {
                    "operation": ground_surface_mesh.name,
                    "assignment": "finite_ground_1, finite_ground_2",
                    "setting": (
                        f"surface approximation level {GROUND_SURFACE_MESH_LEVEL} (Fine / Large)"
                    ),
                },
            ]
        )
    )

# %% [markdown]
# ### Adaptive Setup and Sweep

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

    if RUN_PREPARE:
        # Duplicate only after the Terminal design owns the complete geometry,
        # materials, boundaries, mesh, setup, and Fast sweep. The Modal design
        # therefore differs only in solution type and Wave Port definition.
        if MODAL_DESIGN_NAME in hfss.design_list:
            hfss.delete_design(MODAL_DESIGN_NAME, fallback_design=TERMINAL_DESIGN_NAME)
        hfss.set_active_design(TERMINAL_DESIGN_NAME)
        if not hfss.duplicate_design(MODAL_DESIGN_NAME):
            raise RuntimeError(f"Could not create {MODAL_DESIGN_NAME!r}")

        for boundary in list(hfss.boundaries):
            if boundary.type in {"Wave Port", "Terminal"}:
                boundary.delete()
        hfss.solution_type = MODAL_SOLUTION_TYPE

        region = hfss.modeler.get_object_from_name("Region")
        modal_faces = [
            (float(face.center[0]), int(face.id))
            for face in region.faces
            if abs(float(face.center[1])) <= 1e-6 and abs(float(face.center[0])) > 1e-6
        ]
        modal_setup_faces = {
            "o1": min(modal_faces, key=lambda item: item[0])[1],
            "o2": max(modal_faces, key=lambda item: item[0])[1],
        }
        port_x = {"o1": -TRACE_LENGTH_UM / 2, "o2": TRACE_LENGTH_UM / 2}
        for physical_port in CANONICAL_PHYSICAL_PORTS:
            integration_line = [
                [port_x[physical_port], SIGNAL_WIDTH_UM / 2, 0.0],
                [port_x[physical_port], SIGNAL_WIDTH_UM / 2 + GAP_UM, 0.0],
            ]
            boundary = hfss.wave_port(
                modal_setup_faces[physical_port],
                name=physical_port,
                integration_line=integration_line,
                modes=1,
                characteristic_impedance="Zpv",
                renormalize=False,
                deembed=0.0,
            )
            if not boundary:
                raise RuntimeError(f"Modal Zpv Wave Port failed for {physical_port}")
            modal_port_records.append(
                {
                    "physical_port": physical_port,
                    "boundary_name": boundary.name,
                    "face_id": modal_setup_faces[physical_port],
                    "integration_line_um": integration_line,
                    "selected_characteristic_impedance": "Zpv",
                }
            )

        modal_setup = hfss.get_setup(SOLVER_SETUP_NAME)
        modal_setup.props["SolveType"] = MODAL_SOLVER_SETUP_TYPE
        if not modal_setup.update():
            raise RuntimeError("Modal setup update failed")
        hfss.set_active_design(TERMINAL_DESIGN_NAME)

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
        design_timings = {}
        for design_name in (TERMINAL_DESIGN_NAME, MODAL_DESIGN_NAME):
            hfss.set_active_design(design_name)
            # Ground width changes the geometry, so each design starts from a
            # fresh adaptive mesh and lets HFSS refine it independently.
            hfss.oanalysis.RevertSetupToInitial(SOLVER_SETUP_NAME)
            start_time = perf_counter()
            if not hfss.analyze_setup(
                name=None,
                acf_file=str(ACF_PATH),
                blocking=False,
            ):
                raise RuntimeError(f"HFSS analyze_setup failed for {design_name}")

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
                        f"HFSS {'running' if running else 'finishing'} {design_name} "
                        f"· adaptive passes: {completed_passes} "
                        f"· elapsed: {perf_counter() - start_time:.1f} s"
                    )
                )
            design_timings[design_name] = {
                "analyze_setup_seconds": perf_counter() - start_time,
                "completed_adaptive_passes": completed_passes,
            }

        hfss.set_active_design(TERMINAL_DESIGN_NAME)
        hfss.export_touchstone(
            setup=SOLVER_SETUP_NAME,
            sweep=SWEEP_NAME,
            output_file=str(TERMINAL_TOUCHSTONE_PATH),
            renormalization=False,
            gamma_impedance_comments=True,
        )
        network = Network(str(TERMINAL_TOUCHSTONE_PATH))
        if not network.port_names:
            raise RuntimeError("Terminal Touchstone has no readable port names")

        # In the Terminal design no impedance line exists, so Modal Solution
        # Data Port Zo is the HFSS Zpi definition.
        zpi_data = hfss.post.get_solution_data(
            expressions=["Zo(o1)", "Zo(o2)", "Gamma(o1)", "Gamma(o2)"],
            setup_sweep_name=f"{SOLVER_SETUP_NAME} : {SWEEP_NAME}",
            report_category="Modal Solution Data",
        )
        if not zpi_data:
            raise RuntimeError("Terminal-design Modal Port Zo (Zpi) extraction failed")

        zpi_frequency_ghz, zpi_o1_real = zpi_data.get_expression_data("Zo(o1)", "real")
        _, zpi_o1_imag = zpi_data.get_expression_data("Zo(o1)", "imag")
        _, zpi_o2_real = zpi_data.get_expression_data("Zo(o2)", "real")
        _, zpi_o2_imag = zpi_data.get_expression_data("Zo(o2)", "imag")
        _, gamma_o1_real = zpi_data.get_expression_data("Gamma(o1)", "real")
        _, gamma_o1_imag = zpi_data.get_expression_data("Gamma(o1)", "imag")
        _, gamma_o2_real = zpi_data.get_expression_data("Gamma(o2)", "real")
        _, gamma_o2_imag = zpi_data.get_expression_data("Gamma(o2)", "imag")

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
            network.port_names = desired_terminals
            terminal_order = "normalized"
        else:
            terminal_order = "original"

        if max(abs(zpi_frequency_ghz - network.f / 1e9)) > 1e-9:
            raise RuntimeError("Terminal S and Terminal-design Zpi frequency grids differ")

        hfss.set_active_design(MODAL_DESIGN_NAME)
        port_zo_quantities = hfss.post.available_report_quantities(
            report_category="Modal Solution Data",
            solution=f"{SOLVER_SETUP_NAME} : {SWEEP_NAME}",
            quantities_category="Port Zo",
        )
        zpv_expressions = ["Zo(o1)", "Zo(o2)"]
        if not all(expression in port_zo_quantities for expression in zpv_expressions):
            raise RuntimeError(f"Unexpected Modal Zpv Port Zo quantities: {port_zo_quantities}")
        zpv_data = hfss.post.get_solution_data(
            expressions=zpv_expressions,
            setup_sweep_name=f"{SOLVER_SETUP_NAME} : {SWEEP_NAME}",
            report_category="Modal Solution Data",
        )
        if not zpv_data:
            raise RuntimeError("Modal-design Port Zo (Zpv) extraction failed")
        zpv_frequency_ghz, zpv_o1_real = zpv_data.get_expression_data("Zo(o1)", "real")
        _, zpv_o1_imag = zpv_data.get_expression_data("Zo(o1)", "imag")
        _, zpv_o2_real = zpv_data.get_expression_data("Zo(o2)", "real")
        _, zpv_o2_imag = zpv_data.get_expression_data("Zo(o2)", "imag")
        if max(abs(zpv_frequency_ghz - network.f / 1e9)) > 1e-9:
            raise RuntimeError("Terminal S and Modal-design Zpv frequency grids differ")

        df = pd.DataFrame(
            {
                "ground_width_um": [GROUND_WIDTH_UM] * len(network.f),
                "frequency_ghz": network.f / 1e9,
                "abs_St_o1_o1": [abs(s) for s in network.s[:, 0, 0]],
                "abs_St_o2_o2": [abs(s) for s in network.s[:, 1, 1]],
                "abs_St_o2_o1": [abs(s) for s in network.s[:, 1, 0]],
                "abs_St_o1_o2": [abs(s) for s in network.s[:, 0, 1]],
                "Re(Zpi_o1)": zpi_o1_real,
                "Im(Zpi_o1)": zpi_o1_imag,
                "Re(Zpi_o2)": zpi_o2_real,
                "Im(Zpi_o2)": zpi_o2_imag,
                "Re(Zpv_o1)": zpv_o1_real,
                "Im(Zpv_o1)": zpv_o1_imag,
                "Re(Zpv_o2)": zpv_o2_real,
                "Im(Zpv_o2)": zpv_o2_imag,
                "Re(Gamma_o1)": gamma_o1_real,
                "Im(Gamma_o1)": gamma_o1_imag,
                "beta_o1": gamma_o1_imag,
                "Re(Gamma_o2)": gamma_o2_real,
                "Im(Gamma_o2)": gamma_o2_imag,
                "beta_o2": gamma_o2_imag,
            }
        )
        DERIVED_CSV_PATH.write_text(df.to_csv(index=False), encoding="utf-8")

        metadata = {
            "kind": "cpw_finite_ground_hfss_convergence",
            "authority": "diagnostic_terminal_st_and_modal_zpi_zpv",
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
            "terminal_design": TERMINAL_DESIGN_NAME,
            "modal_zpv_design": MODAL_DESIGN_NAME,
            "terminal_wave_ports": terminal_records,
            "modal_zpv_wave_ports": modal_port_records,
            "terminal_order": terminal_order,
            "quantity_authority": {
                "terminal_scattering": (
                    "HFSS_Terminal / Terminal Solution Data / St(...) / Terminal Touchstone"
                ),
                "zpi": (
                    "HFSS_Terminal / Modal Solution Data / Port Zo / Zo(o1), Zo(o2); "
                    "no impedance line"
                ),
                "zpv": (
                    "HFSS_Modal_Zpv / Modal Solution Data / Port Zo / Zo(o1), Zo(o2); "
                    "selected Zpv with explicit signal-to-+Y-ground impedance line"
                ),
            },
            "sweep": {
                "start_ghz": FREQUENCY_START_GHZ,
                "stop_ghz": FREQUENCY_STOP_GHZ,
                "point_count": FREQUENCY_POINT_COUNT,
                "sweep_type": SWEEP_TYPE,
            },
            "setup": {
                "terminal_type": SOLVER_SETUP_TYPE,
                "modal_type": MODAL_SOLVER_SETUP_TYPE,
                "max_adaptive_passes": MAX_ADAPTIVE_PASSES,
                "min_converged_passes": MINIMUM_CONVERGED_PASSES,
                "max_delta_s": MAX_DELTA_S,
            },
            "mesh": {
                "profile": MESH_PROFILE,
                "cpw_conductor_length_mesh_um": CPW_CONDUCTOR_LENGTH_MESH_UM,
                "cpw_conductor_length_mesh_max_additional_elements": (
                    CPW_CONDUCTOR_LENGTH_MESH_MAX_ADDITIONAL_ELEMENTS
                ),
                "ground_surface_mesh_level": GROUND_SURFACE_MESH_LEVEL,
                "ground_surface_mesh_label": "Fine resolution / large mesh count",
            },
            "timing": design_timings,
        }
        METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        TIMING_PATH.write_text(json.dumps(design_timings, indent=2), encoding="utf-8")

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
# > **Quantity authority.** `|St|` comes from the HFSS Terminal design and
# > Terminal Solution Data. `Zpi` is the Terminal design's Modal Solution Data
# > `Port Zo` with no impedance line. `Zpv` is the Modal design's Modal Solution
# > Data `Port Zo`, selected with an explicit impedance line across the +Y CPW
# > slot. Touchstone impedance comments and Terminal `Zot(...)` are not used as
# > characteristic impedance.

# %%
result_frames = []
for width in GROUND_WIDTH_OPTIONS:
    run_tag = f"cpw_w10_s6_gw{width:g}um_{MESH_PROFILE}"
    csv_path = RUN_ROOT / run_tag / "derived_diagnostics.csv"
    if csv_path.exists():
        frame = pd.read_csv(csv_path)
        frame["ground_width_um"] = width
        result_frames.append(frame)

if result_frames:
    result_df = pd.concat(result_frames, ignore_index=True)
    result_df = result_df.sort_values(["ground_width_um", "frequency_ghz"]).reset_index(drop=True)
    result_df["Re(Zpi)_mean"] = (result_df["Re(Zpi_o1)"] + result_df["Re(Zpi_o2)"]) / 2
    result_df["Re(Zpv)_mean"] = (result_df["Re(Zpv_o1)"] + result_df["Re(Zpv_o2)"]) / 2
    result_df["Re(Zpi)_delta_from_prev_width"] = result_df.groupby("frequency_ghz")[
        "Re(Zpi)_mean"
    ].diff()
    result_df["Re(Zpv)_delta_from_prev_width"] = result_df.groupby("frequency_ghz")[
        "Re(Zpv)_mean"
    ].diff()

    s_parameters = result_df.melt(
        id_vars=["frequency_ghz", "ground_width_um"],
        value_vars=["abs_St_o1_o1", "abs_St_o2_o2", "abs_St_o2_o1", "abs_St_o1_o2"],
        var_name="Terminal Solution Data quantity",
        value_name="magnitude",
    )
    display(
        px.line(
            s_parameters,
            x="frequency_ghz",
            y="magnitude",
            color="ground_width_um",
            facet_row="Terminal Solution Data quantity",
            title="HFSS_Terminal · Terminal Solution Data · St",
        ).update_layout(height=650)
    )

    zpi_impedance = result_df.melt(
        id_vars=["frequency_ghz", "ground_width_um"],
        value_vars=["Re(Zpi_o1)", "Re(Zpi_o2)"],
        var_name="port",
        value_name="impedance_ohm",
    )
    display(
        px.line(
            zpi_impedance,
            x="frequency_ghz",
            y="impedance_ohm",
            color="ground_width_um",
            line_dash="port",
            title="HFSS_Terminal · Modal Solution Data · Port Zo = Zpi",
        )
    )

    zpv_impedance = result_df.melt(
        id_vars=["frequency_ghz", "ground_width_um"],
        value_vars=["Re(Zpv_o1)", "Re(Zpv_o2)"],
        var_name="port",
        value_name="impedance_ohm",
    )
    display(
        px.line(
            zpv_impedance,
            x="frequency_ghz",
            y="impedance_ohm",
            color="ground_width_um",
            line_dash="port",
            title="HFSS_Modal_Zpv · Modal Solution Data · Port Zo = Zpv",
        )
    )

    band_summary = result_df.groupby("ground_width_um", as_index=False).agg(
        abs_St_o1_o1_max=("abs_St_o1_o1", "max"),
        abs_St_o2_o1_min=("abs_St_o2_o1", "min"),
        Re_Zpi_mean_ohm=("Re(Zpi)_mean", "mean"),
        Re_Zpv_mean_ohm=("Re(Zpv)_mean", "mean"),
        Re_Zpi_change_from_previous_width_max_ohm=(
            "Re(Zpi)_delta_from_prev_width",
            lambda values: values.abs().max(),
        ),
        Re_Zpv_change_from_previous_width_max_ohm=(
            "Re(Zpv)_delta_from_prev_width",
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
    run_tag = f"cpw_w10_s6_gw{width:g}um_{MESH_PROFILE}"
    timing_path = RUN_ROOT / run_tag / "solve_timing.json"
    if timing_path.exists():
        with timing_path.open(encoding="utf-8") as handle:
            timing_frames.append((width, json.loads(handle.read())))

if timing_frames:
    timing_rows = []
    for width, timing in timing_frames:
        for design_name, values in timing.items():
            timing_rows.append(
                {
                    "ground_width_um": width,
                    "design": design_name,
                    **values,
                }
            )
    timing_df = pd.DataFrame(timing_rows)
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
