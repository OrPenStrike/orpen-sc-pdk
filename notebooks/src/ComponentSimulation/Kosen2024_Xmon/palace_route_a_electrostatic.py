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
# # Public OrPen Xmon — Route A Electrostatic
# This public workflow prepares a Palace manual handoff. It does not submit or run Palace.

# %%
from pathlib import Path

import gdsfactory as gf
from IPython.display import display
from scgsim.palace import ElectrostaticSim, resolve_palace_result
from scgsim.sgb import build_component_stack

import orpen_sc_pdk
from orpen_sc_pdk import LAYER_STACK, get_material_records
from orpen_sc_pdk.tech import OUTER_VACUUM_THICKNESS_UM

# Choose prepare_handoff to prepare a manual run or analyze_handoff to inspect returned results.
WORKFLOW_ACTION = "prepare_handoff"
# Use a unique ID for each new prepared run; SCGSim refuses non-empty output directories.
RUN_ID = "kosen2024_flip_chip_xmon_route_a_electrostatic"
RUN_ROOT = Path.cwd() / ".artifacts" / RUN_ID  # Root for this run's artifacts.
# Exact ID returned by Prepare Handoff; paste it here before analyzing a returned run.
EXPECTED_HANDOFF_ID = ""
if WORKFLOW_ACTION not in {"prepare_handoff", "analyze_handoff"}:
    raise ValueError("WORKFLOW_ACTION must be 'prepare_handoff' or 'analyze_handoff'.")

# %% [markdown]
# ## Build Component Coupon

# %%
if WORKFLOW_ACTION == "prepare_handoff":
    # PDK-registered layout cell whose geometry and semantic annotation are simulated.
    COMPONENT_NAME = "kosen2024_flip_chip_xmon_qubit"

    orpen_sc_pdk.activate()
    gf.clear_cache()
    component = gf.get_component(COMPONENT_NAME)
    display(component)

# %% [markdown]
# ## Configure EPR / Problem

# %%
if WORKFLOW_ACTION == "prepare_handoff":
    # Route A models zero-thickness PEC sheets; Route B models finite PEC exclusion shells.
    ROUTE = "A"
    # Expand every side of the component's XY bounds before constructing the coupon domains.
    COUPON_PADDING_UM = 75.0
    # Add symmetric X/Y/Z padding to the automatic vacuum envelope; only Z is expanded here.
    VACUUM_PADDING_UM = (0.0, 0.0, float(OUTER_VACUUM_THICKNESS_UM))
    INDIUM_GROUND_FILL = {
        # Add deterministic ground bumps after preserving all authored bump sites.
        "fill": True,
        # Center-to-center lattice spacing; a smaller pitch creates more mesh geometry.
        "fill_pitch_um": 80.0,
        # Minimum distance from semantic keepouts; a larger value rejects more sites.
        "fill_clearance_um": 30.0,
    }
    EPR_SPECS = {
        kind: {
            # Effective interface thickness used in Palace surface-energy postprocessing (um).
            "thickness": 0.003,
            # Relative permittivity used to convert interface fields into stored energy.
            "permittivity": 10.0,
            # Multiplies participation to estimate dielectric loss; zero disables that loss.
            "loss_tangent": 0.0,
        }
        for kind in ("MA", "MS", "SA")
    }
    # Palace applies unit voltage to each terminal in turn and returns the capacitance matrices.
    TERMINALS = {
        "xmon_pad": "xmon_pad",  # Report name -> exact structured conductor net.
        "coupler_1": "coupler_1",
        "coupler_2": "coupler_2",
        "coupler_3": "coupler_3",
        "coupler_4": "coupler_4",
        "ground": "Ground",
    }
    # Number of terminal field solutions saved for ParaView/GridFunction; 0 saves none.
    SAVE_FIELDS = 0
    # Unlisted structured conductors fail fast.
    UNASSIGNED_CONDUCTOR_POLICY = "error"
    # Leave exterior solution boundaries at Palace's natural zero-charge condition.
    EXTERIOR_BOUNDARY_POLICY = "none"

    stack = build_component_stack(
        component=component,
        layer_stack=LAYER_STACK,
        material_records=get_material_records(),
        coupon_padding_um=COUPON_PADDING_UM,
    )
    sim = ElectrostaticSim()
    sim.set_geometry(component)
    sim.set_stack(stack)
    sim.set_output_dir(RUN_ROOT)
    sim.set_vacuum_region(padding=VACUUM_PADDING_UM)
    sim.set_indium_ground_bumps(**INDIUM_GROUND_FILL)
    sim.set_surface_epr(representation=ROUTE, specs=EPR_SPECS)
    for terminal_name, net_id in TERMINALS.items():
        sim.add_terminal(terminal_name, net_id=net_id)
    sim.set_electrostatic(
        save_fields=SAVE_FIELDS,
        unassigned_conductor_policy=UNASSIGNED_CONDUCTOR_POLICY,
        exterior_boundary_policy=EXTERIOR_BOUNDARY_POLICY,
    )

# %% [markdown]
# ## Build Mesh

# %%
if WORKFLOW_ACTION == "prepare_handoff":
    # Target element size near SGB semantic refinement regions.
    # Smaller elements resolve interfaces more finely.
    REFINED_MESH_SIZE_UM = 15.0
    # Upper element size in bulk solution volumes; smaller increases the global tetrahedron count.
    MAX_MESH_SIZE_UM = 80.0

    sim.set_mesh(refined_mesh_size=REFINED_MESH_SIZE_UM, max_mesh_size=MAX_MESH_SIZE_UM)
    MESH_PATH = sim.mesh()

# %% [markdown]
# ## Generate Config

# %%
if WORKFLOW_ACTION == "prepare_handoff":
    # Polynomial degree of Palace's finite-element basis; higher order costs more memory and work.
    FEM_ORDER = 1
    # Relative residual tolerance for each terminal's linear solve.
    LINEAR_TOLERANCE = 1e-6
    # Maximum iterations allowed for each terminal's linear solve.
    MAX_ITERATIONS = 2000
    # Palace linear-solver selection; "Default" delegates the backend choice to Palace.
    SOLVER_TYPE = "Default"
    # Optional non-default preconditioner; "Default" keeps Palace's solver-dependent choice.
    PRECONDITIONER = "Default"
    # MFEM execution backend requested by Palace.
    DEVICE = "CPU"
    # Maximum adaptive-refinement iterations after the initial solve; 0 disables AMR.
    AMR_MAX_PASSES = 10
    # Palace Nonconformal AMR; SCGSim defaults false. Set True only to opt into NC AMR.
    AMR_NONCONFORMAL = False
    # Stop AMR when the estimated-error norm falls below this value.
    AMR_TOLERANCE = 2e-2
    # Dörfler error fraction marked per AMR pass; None keeps the Palace default.
    AMR_UPDATE_FRACTION = 0.3
    # Save each intermediate AMR solve under iterationX; None keeps the Palace default.
    SAVE_ADAPT_ITERATIONS = True
    # Use multigrid instead of Jacobi for the error-estimator solve; None keeps the default.
    ESTIMATOR_MG = False
    # Write field data in ParaView format; disabled here to reduce returned-run size.
    OUTPUT_PARAVIEW = False
    # Write MFEM grid-function files for GLVis; disabled here to reduce returned-run size.
    OUTPUT_GRID_FUNCTION = False

    sim.set_numerical(
        order=FEM_ORDER,
        tolerance=LINEAR_TOLERANCE,
        max_iterations=MAX_ITERATIONS,
        solver_type=SOLVER_TYPE,
        preconditioner=PRECONDITIONER,
        device=DEVICE,
        amr_max_passes=AMR_MAX_PASSES,
        amr_nonconformal=AMR_NONCONFORMAL,
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
if WORKFLOW_ACTION == "prepare_handoff":
    # Select the single-node Slurm handoff shape.
    MACHINE_PROFILE = "slurm-single-node"
    # Palace binary invoked by srun after the setup commands complete.
    PALACE_EXECUTABLE = "palace-x86_64.bin"
    # Commands executed inside the batch job before Palace starts.
    SETUP_COMMANDS = ("module load palace",)
    RESOURCES = {
        "nodes": 1,  # Allocate one Slurm node.
        "ntasks": 10,  # Launch ten MPI ranks for Palace.
        "cpus_per_task": 3,  # Give each MPI rank three CPU threads.
        "time": "00:30:00",  # Cancel the job if it exceeds thirty minutes.
        "mem": "256G",  # Reserve 256 GiB for the Slurm job.
        "launcher": ("srun", "--mpi=pmix"),  # Use Slurm's PMIx MPI launcher.
        "command_style": "binary",  # Invoke the binary directly; required for Slurm profiles.
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
# Returned handoff root whose receipt and handoff identity SCGSim must verify.
RETURNED_RUN_DIR = RUN_ROOT

if WORKFLOW_ACTION == "analyze_handoff":
    report = resolve_palace_result(
        RETURNED_RUN_DIR, expected_handoff_id=EXPECTED_HANDOFF_ID
    )
    display(report.show_all_results())
    display(report.show_simulation_benchmark())
