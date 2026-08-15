# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.5
# ---

# %% [markdown]
# # Public OrPen Xmon — Route A Electrostatic
# This manual-only example builds the public zero-argument PDK component. It
# prepares geometry, mesh, config, and an LTlab Slurm handoff; it never submits
# or runs Palace.

# %% [markdown]
# ## Design And Geometry Controls

# %%
from pathlib import Path

from orpen_sc_pdk.tech import OUTER_VACUUM_THICKNESS_UM

GEOMETRY_CONTROLS = {
    "route": "A",
    "component": "kosen2024_flip_chip_xmon_qubit",
    "coupon_padding_um": 75.0,
    "auto_vacuum_padding_um": (0.0, 0.0, float(OUTER_VACUUM_THICKNESS_UM)),
}

INDIUM_GROUND_CONTROLS = {
    "fill": True,
    "fill_pitch_um": 80.0,
    "fill_clearance_um": 30.0,
}
TERMINALS = {
    "xmon_pad": "xmon_pad",
    "coupler_1": "coupler_1",
    "coupler_2": "coupler_2",
    "coupler_3": "coupler_3",
    "coupler_4": "coupler_4",
}

# %% [markdown]
# ## Meshing Controls

# %%
MESH_CONTROLS = {"refined_mesh_size": 15.0, "max_mesh_size": 80.0}

# %% [markdown]
# ## Solver Controls

# %%
SOLVER_CONTROLS = {
    "order": 1,
    "tolerance": 1e-6,
    "max_iterations": 400,
    "solver_type": "Default",
    "preconditioner": "Default",
    "device": "CPU",
}

# %% [markdown]
# ## Execution Controls

# %%
EXECUTION_CONTROLS = {
    "machine_profiles": ("ltlab-local", "ltlab-slurm", "f1-slurm"),
    "selected_profile": "ltlab-slurm",
    "executable": "palace",
    "setup_commands": ("module load palace",),
    "resources": {
        "nodes": 1,
        "ntasks": 1,
        "cpus_per_task": 1,
        "command_style": "binary",
    },
}

# %% [markdown]
# ## Output And Run Identity Controls

# %%
try:
    NOTEBOOK_DIR = Path(__file__).resolve().parent
except NameError:
    NOTEBOOK_DIR = (
        Path.cwd() / "notebooks" if (Path.cwd() / "notebooks").is_dir() else Path.cwd()
    )

OUTPUT_CONTROLS = {
    "run_dir": NOTEBOOK_DIR
    / ".artifacts"
    / "kosen2024_flip_chip_xmon_route_a_electrostatic",
    "output_formats": ("gds", "xao", "msh2", "json", "sbatch", "tar.gz"),
}

# %% [markdown]
# ## Validation And Failure Controls

# %%
VALIDATION_CONTROLS = {"msh_version": "2.2", "terminal_count": 5, "no_solver_run": True}

# %% [markdown]
# ## Data Classification And Provenance
# All inputs are public.  The PDK is an optional reproducible example extra;
# no local path, private geometry, result, or receipt is stored in provenance.

# %%
PROVENANCE = {
    "classification": "public",
    "orpen_sc_pdk_revision": "8be8fc48c26f6bed06298cab673d49b9a6afbe7f",
    "scgsim_revision": "9febe3f3b77528a17b3be45a4211a33fb47eec2a",
    "gsim_meshing_methodology": "8f5dc6c05255d003a9c6d8959537bcf8068379d3",
    "palace_runtime": "0.16.1",
    "palace_schema": "0.16.0",
}

# %%
import json

import gdsfactory as gf
import orpen_sc_pdk
from orpen_sc_pdk import LAYER, LAYER_STACK, get_material_records

from scgsim.palace import ElectrostaticSim
from scgsim.sgb import build_kosen2024_flip_chip_xmon_stack

EPR_SPECS = {
    "MA": {"thickness": 0.003, "permittivity": 10.0, "loss_tangent": 0.0},
    "MS": {"thickness": 0.003, "permittivity": 10.0, "loss_tangent": 0.0},
    "SA": {"thickness": 0.003, "permittivity": 10.0, "loss_tangent": 0.0},
}

# %% [markdown]
# ## Build Component

# %%
orpen_sc_pdk.activate()
gf.clear_cache()
component = gf.get_component(GEOMETRY_CONTROLS["component"])
stack = build_kosen2024_flip_chip_xmon_stack(
    component=component,
    layer_stack=LAYER_STACK,
    material_records=get_material_records(),
    d0_top_ground_mask_layer=tuple(LAYER.D0_TOP_GROUND_MASK),
    indium_bump_layer=tuple(LAYER.D0_D1_INDIUM_BUMP),
    coupon_padding_um=GEOMETRY_CONTROLS["coupon_padding_um"],
    include_airbox=False,
)
solution_regions = stack["solution_regions"]
assert tuple(solution_regions) == (
    "D0_SUBSTRATE",
    "D0_TO_D1_GAP",
    "D1_SUBSTRATE",
)
assert (
    len(
        {
            json.dumps(region["geometry"]["domain_bounds_um"], sort_keys=True)
            for region in solution_regions.values()
        }
    )
    == 1
)
assert (
    solution_regions["D0_SUBSTRATE"]["geometry"]["z_max_um"]
    == solution_regions["D0_TO_D1_GAP"]["geometry"]["z_min_um"]
)
assert (
    solution_regions["D0_TO_D1_GAP"]["geometry"]["z_max_um"]
    == solution_regions["D1_SUBSTRATE"]["geometry"]["z_min_um"]
)
run_dir = OUTPUT_CONTROLS["run_dir"]
if run_dir.exists() and any(run_dir.iterdir()):
    raise FileExistsError(f"Preserving existing inspectable run folder: {run_dir}")

# %% [markdown]
# ## Configure Problem And EPR

# %%
sim = ElectrostaticSim()
sim.set_geometry(component)
sim.set_stack(stack)
sim.set_output_dir(run_dir)
sim.set_vacuum_region(padding=GEOMETRY_CONTROLS["auto_vacuum_padding_um"])
sim.set_indium_ground_bumps(**INDIUM_GROUND_CONTROLS)
sim.set_surface_epr(representation=GEOMETRY_CONTROLS["route"], specs=EPR_SPECS)
for terminal_name, net_id in TERMINALS.items():
    sim.add_terminal(terminal_name, net_id=net_id)
sim.set_electrostatic(
    unassigned_conductor_policy="ground", exterior_boundary_policy="none"
)
sim.set_numerical(**MESH_CONTROLS, **SOLVER_CONTROLS)

# %% [markdown]
# ## Build Mesh

# %%
mesh_path = sim.mesh()
assert f"$MeshFormat\n{VALIDATION_CONTROLS['msh_version']} 0 8" in mesh_path.read_text()
manifest = json.loads((run_dir / "metadata" / "mesh_manifest.json").read_text())
indium_receipt = json.loads(
    (run_dir / "metadata" / "indium_ground_bumps.json").read_text()
)
assert indium_receipt["controls"] == INDIUM_GROUND_CONTROLS
assert indium_receipt["counts"]["generated"] > 0
auto_stack = json.loads((run_dir / "geometry" / "design.stack.json").read_text())
auto_regions = auto_stack["solution_regions"]
assert tuple(auto_regions) == (
    "D0_SUBSTRATE",
    "D0_TO_D1_GAP",
    "D1_SUBSTRATE",
    "VACUUM_REGION",
)
auto_vacuum = auto_regions["VACUUM_REGION"]
assert auto_vacuum["material_id"] == "vacuum"
assert auto_vacuum["material_kind"] == "vacuum"
assert auto_vacuum["metadata"]["source"] == "set_vacuum_region"
assert (
    auto_vacuum["geometry"]["domain_bounds_um"]
    == auto_regions["D0_SUBSTRATE"]["geometry"]["domain_bounds_um"]
)
assert auto_regions["D0_TO_D1_GAP"]["material_id"] == "vacuum"
assert auto_stack["metadata"]["component_contract"] == (
    "kosen2024_flip_chip_xmon_qubit public zero-argument cell"
)
volume_groups = {
    group["name"]: group
    for group in manifest["groups"]
    if group["section"] == "volumes"
}
assert {"D0_SUBSTRATE", "D0_TO_D1_GAP", "D1_SUBSTRATE", "VACUUM_REGION"} <= set(
    volume_groups
)
assert set(volume_groups["D0_TO_D1_GAP"]["tags"]).isdisjoint(
    volume_groups["VACUUM_REGION"]["tags"]
)
assert not [
    group
    for group in manifest["groups"]
    if group["section"] == "volumes"
    and group.get("physical_attribute", {}).get("material_kinds") == ["conductor"]
]

# %% [markdown]
# ## Write And Validate Config

# %%
config_path = sim.write_config()
index_map = json.loads((run_dir / "metadata" / "palace_index_map.json").read_text())
terminal_entries = [
    entry for entry in index_map["entries"] if entry["section"] == "Boundaries.Terminal"
]
assert len(terminal_entries) == VALIDATION_CONTROLS["terminal_count"]
assert {entry["net_id"] for entry in terminal_entries} == set(TERMINALS.values())

# %% [markdown]
# ## Prepare And Inspect Handoff

# %%
handoff = sim.prepare_handoff(
    profile=EXECUTION_CONTROLS["selected_profile"],
    executable=EXECUTION_CONTROLS["executable"],
    resources=EXECUTION_CONTROLS["resources"],
    setup_commands=EXECUTION_CONTROLS["setup_commands"],
)
assert (
    handoff.script_path.name == "run_palace.sbatch" and handoff.archive_path.is_file()
)

# %% [markdown]
# ## Physics Analysis Results
# No Palace process is started by this notebook.  Physics results remain absent
# until the prepared manual handoff is submitted and resolved by its owner.

# %%
run_status = json.loads((run_dir / "metadata" / "palace_run_metadata.json").read_text())
assert run_status["status"] == "not_run"

# %% [markdown]
# ## Simulation Performance / Benchmarks

# %%
resource_record = json.loads(
    (run_dir / "metadata" / "palace_resource_record.json").read_text()
)
assert resource_record["status"] == "not_submitted"
print(
    {
        "mesh": str(mesh_path),
        "config": str(config_path),
        "handoff": str(handoff.archive_path),
    }
)
