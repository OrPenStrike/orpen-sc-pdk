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
# # Public OrPen Xmon — Route B Eigenmode
# This direct public example lowers the layout-authored junction sheet at the
# finite-metal mid-height, verifies its two structured PEC-owner contacts, and
# prepares a manual LTlab Slurm handoff. It never submits or runs Palace.

# %% [markdown]
# ## Design And Geometry Controls

# %%
import json
from pathlib import Path

from orpen_sc_pdk.tech import OUTER_VACUUM_THICKNESS_UM

GEOMETRY_CONTROLS = {
    "route": "B",
    "component": "kosen2024_flip_chip_xmon_qubit",
    "port_name": "o_junction_lumped",
    "logical_metal": "D1_BOTTOM_M1",
    "inductance_h": 1e-12,
    "coupon_padding_um": 75.0,
    "auto_vacuum_padding_um": (0.0, 0.0, float(OUTER_VACUUM_THICKNESS_UM)),
}

INDIUM_GROUND_CONTROLS = {
    "fill": True,
    "fill_pitch_um": 80.0,
    "fill_clearance_um": 30.0,
}

# %% [markdown]
# ## Meshing Controls

# %%
MESH_CONTROLS = {"refined_mesh_size": 5.0, "max_mesh_size": 20.0}

# %% [markdown]
# ## Solver Controls

# %%
SOLVER_CONTROLS = {
    "num_modes": 2,
    "target": 5e9,
    "tolerance": 1e-6,
    "save": 0,
    "order": 1,
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
    / "kosen2024_flip_chip_xmon_route_b_eigenmode",
    "output_formats": ("gds", "xao", "msh2", "json", "sbatch", "tar.gz"),
}

# %% [markdown]
# ## Validation And Failure Controls

# %%
VALIDATION_CONTROLS = {
    "msh_version": "2.2",
    "lumped_port_count": 1,
    "no_solver_run": True,
}

# %% [markdown]
# ## Data Classification And Provenance

# %%
PROVENANCE = {
    "classification": "public",
    "orpen_sc_pdk_revision": "8be8fc48c26f6bed06298cab673d49b9a6afbe7f",
    "scgsim_revision": "9febe3f3b77528a17b3be45a4211a33fb47eec2a",
    "gsim_meshing_methodology": "8f5dc6c05255d003a9c6d8959537bcf8068379d3",
    "palace_runtime": "0.16.1",
    "palace_schema": "0.16.0",
    "route_b_port_contract": "exact overlap-bound terminal curves and finite PEC sidewalls",
}

# %%
import gdsfactory as gf
import orpen_sc_pdk
from orpen_sc_pdk import LAYER, LAYER_STACK, get_material_records

from scgsim.palace import EigenmodeSim
from scgsim.sgb import build_kosen2024_flip_chip_xmon_stack

EPR_SPECS = {
    kind: {"thickness": 0.003, "permittivity": 10.0, "loss_tangent": 0.0}
    for kind in ("MA", "MS", "SA")
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
sim = EigenmodeSim()
sim.set_geometry(component)
sim.set_stack(stack)
sim.set_output_dir(run_dir)
sim.set_vacuum_region(padding=GEOMETRY_CONTROLS["auto_vacuum_padding_um"])
sim.set_indium_ground_bumps(**INDIUM_GROUND_CONTROLS)
sim.set_surface_epr(representation=GEOMETRY_CONTROLS["route"], specs=EPR_SPECS)
sim.add_port(
    GEOMETRY_CONTROLS["port_name"],
    layer=GEOMETRY_CONTROLS["logical_metal"],
    layout_sheet=True,
    inductance=GEOMETRY_CONTROLS["inductance_h"],
)
sim.set_eigenmode(
    num_modes=SOLVER_CONTROLS["num_modes"],
    target=SOLVER_CONTROLS["target"],
    tolerance=SOLVER_CONTROLS["tolerance"],
    save=SOLVER_CONTROLS["save"],
)
sim.set_numerical(
    **MESH_CONTROLS,
    **{
        key: SOLVER_CONTROLS[key]
        for key in (
            "order",
            "tolerance",
            "max_iterations",
            "solver_type",
            "preconditioner",
            "device",
        )
    },
)

# %% [markdown]
# ## Build Mesh

# %%
mesh_path = sim.mesh()
assert f"$MeshFormat\n{VALIDATION_CONTROLS['msh_version']} 0 8" in mesh_path.read_text()
mesh_manifest = json.loads((run_dir / "metadata" / "mesh_manifest.json").read_text())
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
    for group in mesh_manifest["groups"]
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
    for group in mesh_manifest["groups"]
    if group["section"] == "volumes"
    and group.get("physical_attribute", {}).get("material_kinds") == ["conductor"]
]
gate = json.loads(
    (
        run_dir
        / "metadata"
        / "semantic_geometry"
        / "engine_gate_gmsh_brep_conformality.json"
    ).read_text()
)
port_records = [
    record
    for record in gate["records"]
    if record["source_record_kind"] == "route_b_lumped_port_mesh"
]
assert len(port_records) == 2
assert all(
    record["status"] == "pass"
    and record["shared_mesh_node_count"] > 0
    and record["expected_terminal_curve_ids"] == record["credited_terminal_curve_ids"]
    and all(record["per_terminal_curve_shared_node_counts"].values())
    for record in port_records
)
port_group = next(
    group for group in mesh_manifest["groups"] if group["section"] == "port_surfaces"
)
assert len(port_group["owner_semantic_ids"]) == 2
assert port_group["embedded_volume_id"] == "D0_TO_D1_GAP"
assert port_group["adjacent_solution_volume_ids"] == ["D0_TO_D1_GAP"]

# %% [markdown]
# ## Write And Validate Config

# %%
config_path = sim.write_config()
config = json.loads(config_path.read_text())
assert (
    len(config["Boundaries"]["LumpedPort"]) == VALIDATION_CONTROLS["lumped_port_count"]
)
port_config = config["Boundaries"]["LumpedPort"][0]
port_information = json.loads(
    (run_dir / "metadata" / "port_information.json").read_text()
)["ports"][0]
assert port_config["L"] == GEOMETRY_CONTROLS["inductance_h"]
assert port_config["Direction"] == port_information["direction"]

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
# No Palace process is run; no physics result is claimed.

# %%
assert VALIDATION_CONTROLS["no_solver_run"]

# %% [markdown]
# ## Simulation Performance / Benchmarks

# %%
print(
    {
        "mesh": str(mesh_path),
        "config": str(config_path),
        "handoff": str(handoff.archive_path),
        "inspection_run_dir": str(run_dir),
    }
)
