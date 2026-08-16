# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.3
# ---

# %% [markdown]
# # Public OrPen Xmon — Route B Eigenmode
# This public workflow prepares a Palace manual handoff. It does not submit or run Palace.

# %%
from pathlib import Path

import gdsfactory as gf
from IPython.display import display
from scgsim.palace import EigenmodeSim, resolve_palace_result
from scgsim.sgb import build_kosen2024_flip_chip_xmon_stack

import orpen_sc_pdk
from orpen_sc_pdk import LAYER, LAYER_STACK, get_material_records
from orpen_sc_pdk.tech import OUTER_VACUUM_THICKNESS_UM

WORKFLOW_ACTION = "prepare_handoff"
RUN_ID = "kosen2024_flip_chip_xmon_route_b_eigenmode"
RUN_ROOT = Path.cwd() / ".artifacts" / RUN_ID
if WORKFLOW_ACTION not in {"prepare_handoff", "analyze_handoff"}:
    raise ValueError("WORKFLOW_ACTION must be 'prepare_handoff' or 'analyze_handoff'.")

# %% [markdown]
# ## Build Component Coupon

# %%
COMPONENT_NAME = "kosen2024_flip_chip_xmon_qubit"

orpen_sc_pdk.activate()
gf.clear_cache()
component = gf.get_component(COMPONENT_NAME)
display(component)

# %% [markdown]
# ## Configure EPR / Problem

# %%
ROUTE = "B"
COUPON_PADDING_UM = 75.0
VACUUM_PADDING_UM = (0.0, 0.0, float(OUTER_VACUUM_THICKNESS_UM))
INDIUM_GROUND_FILL = {"fill": True, "fill_pitch_um": 80.0, "fill_clearance_um": 30.0}
EPR_SPECS = {
    kind: {"thickness": 0.003, "permittivity": 10.0, "loss_tangent": 0.0}
    for kind in ("MA", "MS", "SA")
}
PORT_NAME = "o_junction_lumped"
PORT_LAYER = "D1_BOTTOM_M1"
PORT_INDUCTANCE_H = 1e-12
NUM_MODES = 2
TARGET_HZ = 5e9
EIGENMODE_TOLERANCE = 1e-6
SAVE_FIELDS = 0

stack = build_kosen2024_flip_chip_xmon_stack(
    component=component,
    layer_stack=LAYER_STACK,
    material_records=get_material_records(),
    d0_top_ground_mask_layer=tuple(LAYER.D0_TOP_GROUND_MASK),
    indium_bump_layer=tuple(LAYER.D0_D1_INDIUM_BUMP),
    coupon_padding_um=COUPON_PADDING_UM,
    include_airbox=False,
)
sim = EigenmodeSim()
sim.set_geometry(component)
sim.set_stack(stack)
sim.set_output_dir(RUN_ROOT)
sim.set_vacuum_region(padding=VACUUM_PADDING_UM)
sim.set_indium_ground_bumps(**INDIUM_GROUND_FILL)
sim.set_surface_epr(representation=ROUTE, specs=EPR_SPECS)
sim.add_port(PORT_NAME, layer=PORT_LAYER, layout_sheet=True, inductance=PORT_INDUCTANCE_H)
sim.set_eigenmode(
    num_modes=NUM_MODES,
    target=TARGET_HZ,
    tolerance=EIGENMODE_TOLERANCE,
    save=SAVE_FIELDS,
)

# %% [markdown]
# ## Build Mesh

# %%
REFINED_MESH_SIZE_UM = 5.0
MAX_MESH_SIZE_UM = 20.0

sim.set_mesh(refined_mesh_size=REFINED_MESH_SIZE_UM, max_mesh_size=MAX_MESH_SIZE_UM)
MESH_PATH = sim.mesh()

# %% [markdown]
# ## Generate Config

# %%
FEM_ORDER = 1
LINEAR_TOLERANCE = 1e-6
MAX_ITERATIONS = 400
SOLVER_TYPE = "Default"
PRECONDITIONER = "Default"
DEVICE = "CPU"
AMR_MAX_PASSES = 0
AMR_TOLERANCE = 1e-2
AMR_UPDATE_FRACTION = None
SAVE_ADAPT_ITERATIONS = None
ESTIMATOR_MG = None
OUTPUT_PARAVIEW = False
OUTPUT_GRID_FUNCTION = False

sim.set_numerical(
    order=FEM_ORDER,
    tolerance=LINEAR_TOLERANCE,
    max_iterations=MAX_ITERATIONS,
    solver_type=SOLVER_TYPE,
    preconditioner=PRECONDITIONER,
    device=DEVICE,
    amr_max_passes=AMR_MAX_PASSES,
    amr_tolerance=AMR_TOLERANCE,
    amr_update_fraction=AMR_UPDATE_FRACTION,
    save_adapt_iterations=SAVE_ADAPT_ITERATIONS,
    estimator_mg=ESTIMATOR_MG,
    output_paraview=OUTPUT_PARAVIEW,
    output_grid_function=OUTPUT_GRID_FUNCTION,
)
CONFIG_PATH = sim.write_config()

# %% [markdown]
# ## Prepare Handoff

# %%
MACHINE_PROFILE = "ltlab-slurm"
PALACE_EXECUTABLE = "palace-x86_64.bin"
SETUP_COMMANDS = ("module load palace",)
RESOURCES = {
    "nodes": 1,
    "ntasks": 10,
    "cpus_per_task": 3,
    "time": "00:30:00",
    "mem": "256G",
    "launcher": ("srun", "--mpi=pmix"),
    "command_style": "binary",
}

HANDOFF = sim.prepare_handoff(
    profile=MACHINE_PROFILE,
    executable=PALACE_EXECUTABLE,
    resources=RESOURCES,
    setup_commands=SETUP_COMMANDS,
)

# %% [markdown]
# ## Analyze Returned Run

# %%
RETURNED_RUN_DIR = RUN_ROOT / "returned"

if WORKFLOW_ACTION == "analyze_handoff":
    report = resolve_palace_result(RETURNED_RUN_DIR, expected_handoff_id=HANDOFF.handoff_id)
    display(report.show_all_results())
    display(report.show_simulation_benchmark())
